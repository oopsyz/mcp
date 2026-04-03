"""
CLI Service Registry — HTTP network interface.

Core logic lives in ``registry_core.py``.  This module adds:
- FastAPI HTTP CLI API (``/cli/registry``)
- Health endpoint
- LLM-powered resolve via opencode serve (falls back to raw dump)
"""

import asyncio
import datetime
import json
import logging
import os
import re
from typing import Any

import requests

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from registry_core import (
    REGISTRY_FILE,
    VALID_STATUSES,
    cmd_get,
    cmd_list,
    cmd_register,
    cmd_resolve,
    cmd_setstatus,
    cmd_unregister,
    parse_registry,
    write_registry,
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("registry_server.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("registry")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 7700

CLI_NAMESPACE = "registry"
CLI_ROUTE = f"/cli/{CLI_NAMESPACE}"

OPENCODE_URL = os.environ.get("OPENCODE_URL", "http://127.0.0.1:4096")

RESOLVE_SYSTEM_PROMPT = """\
You are a service registry resolver. Match the user's natural language query \
to the most relevant registered service(s).

Return ONLY a valid JSON object — no markdown fences, no explanation, no other text:

{"matches":[{"id":"service-id","url":"http://...","cli":"/cli/...","mcp":"http://.../mcp","confidence":0.95,"reason":"one sentence: why this service matches the query","prerequisites":[{"id":"dep-service-id","note":"one sentence: what you need from this dependency and why"}]}]}

Rules:
- confidence: float 0.0–1.0
- Only include services with confidence > 0.5
- Order by confidence descending
- If nothing matches: {"matches":[]}
- prerequisites: derive from the service's "dependencies" field. For each dependency, write one sentence explaining what the caller needs from it. If dependencies is "none" or empty, use [].
- prerequisites notes must describe WHAT to get (e.g. "Requires a ProductOfferingRef"), not HOW to get it (no step-by-step sequences)
- ONLY output the JSON object, nothing else"""


def _now() -> str:
    return datetime.datetime.now().isoformat()


# ---------------------------------------------------------------------------
# opencode serve integration — LLM-powered resolve
# ---------------------------------------------------------------------------


def _extract_response_text(response_data: dict) -> str:
    """Extract text content from opencode message response."""
    parts = response_data.get("parts", [])
    texts = []
    for part in parts:
        if isinstance(part, dict):
            if "text" in part:
                texts.append(part["text"])
            elif "content" in part:
                texts.append(part["content"])
        elif isinstance(part, str):
            texts.append(part)
    if texts:
        return "\n".join(texts)
    if "text" in response_data:
        return response_data["text"]
    return ""


def _parse_json_from_text(text: str) -> dict | None:
    """Parse JSON from LLM text, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _resolve_via_opencode(
    query: str, services: list[dict], opencode_url: str = OPENCODE_URL
) -> dict | None:
    """Call opencode serve for LLM-powered semantic matching.

    Returns ``{"matches": [...]}`` on success, ``None`` on failure (caller
    should fall back to the raw-dump resolve).
    """
    try:
        # 1. Create session
        resp = requests.post(
            f"{opencode_url}/session",
            json={"title": "registry-resolve"},
            timeout=5,
        )
        if resp.status_code not in (200, 201):
            logger.warning("opencode session create failed: %d", resp.status_code)
            return None

        session_data = resp.json()
        session_id = session_data.get("id") or session_data.get("sessionID")
        if not session_id:
            logger.warning("opencode session missing id: %s", session_data)
            return None

        try:
            # 2. Send resolve message
            services_json = json.dumps(services, indent=2)
            message = f"Query: {query}\n\nRegistered services:\n{services_json}"

            resp = requests.post(
                f"{opencode_url}/session/{session_id}/message",
                json={
                    "system": RESOLVE_SYSTEM_PROMPT,
                    "tools": [],
                    "parts": [{"type": "text", "text": message}],
                },
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning("opencode message failed: %d", resp.status_code)
                return None

            # 3. Parse response
            text = _extract_response_text(resp.json())
            if not text:
                logger.warning("opencode returned empty response")
                return None

            parsed = _parse_json_from_text(text)
            if parsed and "matches" in parsed:
                return parsed

            logger.warning("opencode response not valid resolve JSON: %s", text[:200])
            return None
        finally:
            # 4. Clean up session
            try:
                requests.delete(f"{opencode_url}/session/{session_id}", timeout=5)
            except Exception:
                pass

    except requests.ConnectionError:
        logger.info("opencode not available at %s, using fallback", opencode_url)
        return None
    except Exception as exc:
        logger.warning("opencode resolve error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# CLI API — catalog + help metadata
# ---------------------------------------------------------------------------

COMMANDS: dict[str, dict[str, Any]] = {
    "list": {
        "summary": "List all registered services",
        "description": "Returns a brief listing of every service in the registry.",
        "arguments": [],
        "examples": [
            {
                "description": "List all services",
                "request": {"command": "list"},
            },
        ],
    },
    "get": {
        "summary": "Get a service by ID",
        "description": "Returns the full registry entry for one service.",
        "arguments": [
            {
                "name": "service_id",
                "type": "string",
                "required": True,
                "description": "Service identifier, e.g. 'tmf620/catalogmgt'",
            },
        ],
        "examples": [
            {
                "description": "Get TMF620 catalog service",
                "request": {
                    "command": "get",
                    "args": {"service_id": "tmf620/catalogmgt"},
                },
            },
        ],
    },
    "resolve": {
        "summary": "Semantic service resolution (LLM-powered with fallback)",
        "description": (
            "Semantic matching for a natural-language query. Tries LLM-powered "
            "matching via opencode serve first; falls back to lightweight keyword "
            "scoring if opencode is unavailable. Set include_raw=true to also get "
            "the full registry markdown."
        ),
        "arguments": [
            {
                "name": "query",
                "type": "string",
                "required": True,
                "description": (
                    "Natural-language description of what capability is needed, "
                    "e.g. 'I need to manage product orders'"
                ),
            },
            {
                "name": "limit",
                "type": "integer",
                "required": False,
                "default": 5,
                "description": "Maximum number of matches to return",
            },
            {
                "name": "include_raw",
                "type": "boolean",
                "required": False,
                "default": False,
                "description": (
                    "If true, also return the full registry_content for "
                    "LLM-powered reasoning"
                ),
            },
        ],
        "examples": [
            {
                "description": "Find a service for orders (LLM or keyword fallback)",
                "request": {
                    "command": "resolve",
                    "args": {"query": "I need to manage product orders"},
                },
            },
            {
                "description": "Find a service for catalog browsing",
                "request": {
                    "command": "resolve",
                    "args": {"query": "browse product catalogs and specifications"},
                },
            },
            {
                "description": "Get top match with full registry for fallback reasoning",
                "request": {
                    "command": "resolve",
                    "args": {"query": "manage orders", "limit": 1, "include_raw": True},
                },
            },
        ],
    },
    "register": {
        "summary": "Register or update a service",
        "description": (
            "Add a new service to the registry, or update an existing one. "
            "Pass the service entry as a JSON body."
        ),
        "arguments": [
            {
                "name": "body",
                "type": "object",
                "required": True,
                "description": (
                    "Service object with id, url, cli, mcp, handles, "
                    "use_when, owner, tags"
                ),
            },
        ],
        "examples": [
            {
                "description": "Register a new order service",
                "request": {
                    "command": "register",
                    "args": {
                        "body": {
                            "id": "tmf622/ordermgt",
                            "url": "http://localhost:7702",
                            "cli": "/cli/tmf622/ordermgt",
                            "mcp": "http://localhost:7702/mcp",
                            "handles": "product orders, order lifecycle",
                            "use_when": "agent needs to place, track, or cancel orders",
                            "owner": "order-team",
                            "tags": ["order", "fulfillment", "tmf622"],
                        }
                    },
                },
            },
        ],
    },
    "unregister": {
        "summary": "Remove a service from the registry",
        "description": "Remove a service by ID. It will no longer appear in lookups.",
        "arguments": [
            {
                "name": "service_id",
                "type": "string",
                "required": True,
                "description": "Service identifier to remove",
            },
        ],
        "examples": [
            {
                "description": "Remove a service",
                "request": {
                    "command": "unregister",
                    "args": {"service_id": "tmf622/ordermgt"},
                },
            },
        ],
    },
    "setstatus": {
        "summary": "Update the status of a registered service",
        "description": (
            f"Set the operational status of a service. "
            f"Valid values: {', '.join(sorted(VALID_STATUSES))}. "
            "Status is surfaced in list and resolve responses. "
            "Callers (agents, monitors, or operators) can use this to signal "
            "that a service is degraded or under maintenance."
        ),
        "arguments": [
            {
                "name": "service_id",
                "type": "string",
                "required": True,
                "description": "Service identifier to update",
            },
            {
                "name": "status",
                "type": "string",
                "required": True,
                "description": "New status: live | degraded | maintenance",
            },
        ],
        "examples": [
            {
                "description": "Mark a service as degraded",
                "request": {
                    "command": "setstatus",
                    "args": {"service_id": "tmf622/ordermgt", "status": "degraded"},
                },
            },
            {
                "description": "Return a service to live",
                "request": {
                    "command": "setstatus",
                    "args": {"service_id": "tmf622/ordermgt", "status": "live"},
                },
            },
        ],
    },
}


def get_catalog_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "service": "registry",
        "namespace": CLI_NAMESPACE,
        "canonical_endpoint": CLI_ROUTE,
        "how_to_invoke": {
            "endpoint": f"POST {CLI_ROUTE}",
            "shape": {"command": "<command>", "args": {}, "stream": False},
        },
        "how_to_get_help": {
            "all_commands": (
                f'GET {CLI_ROUTE} or POST {CLI_ROUTE} {{"command":"help"}}'
            ),
            "one_command": (
                f'POST {CLI_ROUTE} {{"command":"help","args":{{"command":"<cmd>"}}}}'
            ),
        },
        "commands": [
            {"name": name, "kind": "command", "summary": spec["summary"]}
            for name, spec in COMMANDS.items()
        ],
        "total": len(COMMANDS),
    }


def get_command_help_payload(command: str) -> dict[str, Any] | None:
    spec = COMMANDS.get(command)
    if spec is None:
        return None
    return {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "command": command,
        "summary": spec["summary"],
        "description": spec["description"],
        "arguments": spec["arguments"],
        "examples": spec["examples"],
    }


# ---------------------------------------------------------------------------
# JSON error helper
# ---------------------------------------------------------------------------


def _json_error(
    status_code: int,
    code: str,
    message: str,
    *,
    next_actions: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if next_actions:
        error["next_actions"] = next_actions
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "interface": "cli",
            "version": "1.0",
            "error": error,
        },
    )


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


def _init_registry():
    if not REGISTRY_FILE.exists():
        logger.info("Creating empty registry at %s", REGISTRY_FILE)
        write_registry([])

    count = len(parse_registry())
    logger.info("Registry loaded: %d service(s) from %s", count, REGISTRY_FILE)


_init_registry()

app = FastAPI(
    title="CLI Service Registry",
    description="Agent-facing service registry with semantic discovery",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Health -----------------------------------------------------------------


@app.get("/health", include_in_schema=False)
async def health_check():
    services = parse_registry()
    return {
        "status": "healthy",
        "registry_file": str(REGISTRY_FILE),
        "services_count": len(services),
        "timestamp": _now(),
    }


# -- CLI API ----------------------------------------------------------------


@app.get(CLI_ROUTE, include_in_schema=False)
@app.get("/cli", include_in_schema=False)
async def cli_catalog():
    return get_catalog_payload()


@app.post(CLI_ROUTE, include_in_schema=False)
@app.post("/cli", include_in_schema=False)
async def cli_dispatch(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return _json_error(400, "invalid_json", "Request body must be valid JSON.")

    if not isinstance(payload, dict):
        return _json_error(
            400, "invalid_request", "Request body must be a JSON object."
        )

    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        return _json_error(
            400, "invalid_command", "Command must be a non-empty string."
        )

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return _json_error(400, "invalid_arguments", "args must be a JSON object.")

    cmd = command.strip()

    # -- help ---------------------------------------------------------------
    if cmd == "help":
        target = args.get("command")
        if target is None:
            return get_catalog_payload()
        hp = get_command_help_payload(target.strip() if isinstance(target, str) else "")
        if hp is None:
            return _json_error(
                404,
                "help_target_not_found",
                f"Unknown command: {target}",
                next_actions=[{"type": "help", "request": {"command": "help"}}],
            )
        return hp

    # -- dispatch -----------------------------------------------------------
    result: dict[str, Any] | None = None

    if cmd == "list":
        result = await asyncio.to_thread(cmd_list)

    elif cmd == "get":
        service_id = args.get("service_id")
        if not service_id:
            return _json_error(
                400, "missing_required_argument", "service_id is required"
            )
        result = await asyncio.to_thread(cmd_get, service_id)

    elif cmd == "resolve":
        query = args.get("query")
        if not query:
            return _json_error(400, "missing_required_argument", "query is required")

        limit = args.get("limit", 5)
        include_raw = args.get("include_raw", False)

        # Try LLM-powered resolve via opencode serve
        services = await asyncio.to_thread(parse_registry)
        smart = await asyncio.to_thread(_resolve_via_opencode, query, services)

        if smart is not None:
            # LLM succeeded (or returned empty, which is still success)
            matches = smart["matches"][:limit]
            result = {
                "query": query,
                "matches": matches,
                "resolved_by": "opencode",
            }
            # If LLM found nothing, add guidance
            if not matches:
                result["note"] = (
                    "No matches found. Use 'list' to see all services, "
                    "or try a different query."
                )
        else:
            # Fallback: opencode unavailable, use keyword scoring.
            # prerequisites is not present — dependency notes require LLM reasoning.
            result = await asyncio.to_thread(
                cmd_resolve, query, limit=limit, include_raw=include_raw
            )
            result["resolved_by"] = "fallback"

    elif cmd == "register":
        body = args.get("body")
        if not isinstance(body, dict):
            return _json_error(
                400,
                "missing_required_argument",
                "body (service object) is required",
            )
        result = await asyncio.to_thread(cmd_register, body)

    elif cmd == "unregister":
        service_id = args.get("service_id")
        if not service_id:
            return _json_error(
                400, "missing_required_argument", "service_id is required"
            )
        result = await asyncio.to_thread(cmd_unregister, service_id)

    elif cmd == "setstatus":
        service_id = args.get("service_id")
        status = args.get("status")
        if not service_id:
            return _json_error(
                400, "missing_required_argument", "service_id is required"
            )
        if not status:
            return _json_error(
                400, "missing_required_argument", "status is required"
            )
        result = await asyncio.to_thread(cmd_setstatus, service_id, status)

    else:
        return _json_error(
            404,
            "command_not_found",
            f"Unknown command: {cmd}",
            next_actions=[{"type": "help", "request": {"command": "help"}}],
        )

    return {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "command": cmd,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    import uvicorn

    host = DEFAULT_HOST
    port = DEFAULT_PORT

    print(f"Starting CLI Service Registry on http://{host}:{port}")
    print(f"Registry file: {REGISTRY_FILE}")
    print(f"Health check:  http://{host}:{port}/health")
    print(f"HTTP CLI API:  http://{host}:{port}{CLI_ROUTE}")
    print(f"opencode URL:  {OPENCODE_URL} (for LLM-powered resolve)")

    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
