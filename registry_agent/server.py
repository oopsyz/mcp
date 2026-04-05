"""
CLI Service Registry - HTTP network interface.

Core logic lives in ``registry_agent/core.py``. This module adds:
- FastAPI HTTP CLI API (``/cli/registry``)
- Health endpoint
- OpenCode-backed resolve that reuses the registry chat agent
"""

import asyncio
import datetime
import json
import logging
import os
import re
import time
from functools import lru_cache
from typing import Any

from contextlib import asynccontextmanager
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from .core import (
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

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7700

CLI_NAMESPACE = "registry"
CLI_ROUTE = f"/cli/{CLI_NAMESPACE}"

OPENCODE_URL = os.environ.get("OPENCODE_URL", "http://127.0.0.1:4096")
OPENCODE_AGENT = os.environ.get("OPENCODE_AGENT", "service-registry")
OPENCODE_TIMEOUT_SECONDS = float(os.environ.get("OPENCODE_TIMEOUT_SECONDS", "30"))
OPENCODE_REQUEST_TIMEOUT_SECONDS = float(
    os.environ.get("OPENCODE_REQUEST_TIMEOUT_SECONDS", str(OPENCODE_TIMEOUT_SECONDS))
)
TMF_CATALOG_JSON = os.environ.get(
    "TMF_CATALOG_JSON",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "tmf_api_catalog.json")),
)

PROGRAMMATIC_RESOLVE_PROMPT = """\
PROGRAMMATIC RESOLVE REQUEST

Query: {query}

Use the live registry.md in this project as the source of truth for callable
services across the whole registry.

Use {tmf_catalog_json} only as a reference-only validation corpus for TMF API
IDs and names. It is not a service registry. Do not use it for general service
discovery.

When a registry response mentions a TMF API, validate that the TMF ID and name
are real and correctly paired against the TMF catalog JSON before returning the
answer.

You may inspect local files and use shell tools such as rg, cat, or jq if that
helps you verify an answer. Do not guess when the local files can confirm it.

When the query implies TMF API selection or validation:
- verify the candidate TMF API IDs and names against the TMF catalog JSON
- prefer the registry entry over model memory for service selection
- if a service match depends on a specific TMF API, mention that in the
  rationale/evidence fields inside the JSON

Return only the JSON object required by the programmatic resolve contract.
Be helpful even when there is no match: include interpreted_intent, summary,
and related_services in the JSON response."""


def _now() -> str:
    return datetime.datetime.now().isoformat()


# ---------------------------------------------------------------------------
# opencode serve integration - registry-agent-backed resolve
# ---------------------------------------------------------------------------


def _extract_response_text(response_data: dict) -> str:
    """Extract text content from opencode message response."""
    parts = response_data.get("parts", [])
    texts = []
    for part in parts:
        if isinstance(part, dict):
            part_type = str(part.get("type", "")).strip().lower()
            if part_type == "text" and "text" in part:
                texts.append(part["text"])
            elif part_type == "content" and "content" in part:
                texts.append(part["content"])
        elif isinstance(part, str):
            texts.append(part)
    if texts:
        return "\n".join(texts)
    if "text" in response_data:
        return response_data["text"]
    return ""


def _message_role(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    role = str(message.get("role", "")).strip().lower()
    if role:
        return role
    info = message.get("info")
    if isinstance(info, dict):
        return str(info.get("role", "")).strip().lower()
    return ""


def _assistant_message_completed(message: Any) -> bool:
    if not isinstance(message, dict):
        return False
    info = message.get("info")
    if not isinstance(info, dict):
        return False
    time_info = info.get("time")
    if isinstance(time_info, dict) and time_info.get("completed") is not None:
        return True
    finish = str(info.get("finish", "")).strip().lower()
    return bool(finish)


def _assistant_message_error(message: Any) -> str | None:
    if not isinstance(message, dict):
        return None
    info = message.get("info")
    if not isinstance(info, dict):
        return None
    error = info.get("error")
    if not isinstance(error, dict):
        return None
    name = str(error.get("name") or "").strip()
    message_text = str(error.get("message") or "").strip()
    return ": ".join(part for part in (name, message_text) if part) or "unknown error"


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


@lru_cache(maxsize=1)
def _load_tmf_catalog() -> dict[str, dict[str, Any]]:
    try:
        with open(TMF_CATALOG_JSON, encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:
        logger.warning("failed to load TMF catalog %s: %s", TMF_CATALOG_JSON, exc)
        return {}

    apis = payload.get("apis", [])
    result: dict[str, dict[str, Any]] = {}
    if isinstance(apis, list):
        for item in apis:
            if not isinstance(item, dict):
                continue
            api_id = str(item.get("id", "")).strip().upper()
            if api_id:
                result[api_id] = item
    return result


def _extract_tmf_api_ids(*texts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in re.findall(r"\bTMF\d{3,4}\b", str(text), flags=re.IGNORECASE):
            api_id = match.upper()
            if api_id not in seen:
                seen.add(api_id)
                found.append(api_id)
    return found


def _match_service_tmf_api(service: dict[str, Any]) -> str | None:
    candidates = _extract_tmf_api_ids(
        str(service.get("id", "")),
        str(service.get("handles", "")),
        str(service.get("use_when", "")),
        " ".join(str(tag) for tag in service.get("tags", []) if isinstance(tag, str)),
    )
    if candidates:
        return candidates[0]
    service_id = str(service.get("id", ""))
    match = re.match(r"^(tmf\d{3,4})/", service_id, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def _build_tmf_validation(api_id: str | None) -> dict[str, Any] | None:
    if not api_id:
        return None
    catalog = _load_tmf_catalog()
    entry = catalog.get(api_id.upper())
    if not entry:
        return {
            "validated": False,
            "tmf_api_id": api_id.upper(),
            "tmf_api_name": None,
        }
    return {
        "validated": True,
        "tmf_api_id": api_id.upper(),
        "tmf_api_name": entry.get("name"),
    }


def _build_reference_suggestions(result: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = _load_tmf_catalog()
    texts: list[str] = [str(result.get("summary", ""))]
    for key in ("related_services",):
        values = result.get(key, [])
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict):
                    texts.append(str(item.get("reason", "")))
                    texts.append(str(item.get("id", "")))

    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for api_id in _extract_tmf_api_ids(*texts):
        entry = catalog.get(api_id)
        if not entry or api_id in seen:
            continue
        seen.add(api_id)
        suggestions.append(
            {
                "tmf_api_id": api_id,
                "tmf_api_name": entry.get("name"),
                "validated": True,
            }
        )
    return suggestions


def _normalize_resolve_result(result: dict[str, Any], limit: int) -> dict[str, Any]:
    matches = result.get("matches", [])
    if isinstance(matches, list):
        normalized_matches: list[dict[str, Any]] = []
        for match in matches[:limit]:
            if not isinstance(match, dict):
                continue
            enriched = dict(match)
            tmf_validation = _build_tmf_validation(_match_service_tmf_api(enriched))
            if tmf_validation is not None:
                enriched["tmf_validation"] = tmf_validation
            normalized_matches.append(enriched)
        result["matches"] = normalized_matches
        if normalized_matches and "resolved_by" in result:
            result.pop("resolved_by", None)

    if "closest_related_services" in result and "related_services" not in result:
        result["related_services"] = result.pop("closest_related_services")
    else:
        result.pop("closest_related_services", None)

    result.pop("suggestions", None)
    result.setdefault("reference_suggestions", _build_reference_suggestions(result))
    result.setdefault("related_services", [])
    return result


def _resolve_via_opencode(query: str, opencode_url: str = OPENCODE_URL) -> dict | None:
    """Call the OpenCode registry agent for semantic matching.

    Returns ``{"matches": [...]}`` on success, ``None`` on failure so the
    caller can fall back to deterministic keyword scoring.
    """
    try:
        resp = requests.post(
            f"{opencode_url}/session",
            json={"title": "registry-resolve"},
            timeout=OPENCODE_REQUEST_TIMEOUT_SECONDS,
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
            prompt = PROGRAMMATIC_RESOLVE_PROMPT.format(
                query=query,
                tmf_catalog_json=TMF_CATALOG_JSON,
            )
            resp = requests.post(
                f"{opencode_url}/session/{session_id}/message",
                json={
                    "agent": OPENCODE_AGENT,
                    "parts": [{"type": "text", "text": prompt}],
                },
                timeout=OPENCODE_REQUEST_TIMEOUT_SECONDS,
            )
            if resp.status_code != 200:
                logger.warning("opencode message failed: %d", resp.status_code)
                return None

            response_data = resp.json()
            if isinstance(response_data, dict):
                parsed = _parse_json_from_text(_extract_response_text(response_data))
                if parsed and "matches" in parsed:
                    return parsed

            deadline = datetime.datetime.now() + datetime.timedelta(
                seconds=OPENCODE_TIMEOUT_SECONDS
            )
            latest_text = ""

            while datetime.datetime.now() < deadline:
                resp = requests.get(
                    f"{opencode_url}/session/{session_id}/message",
                    timeout=OPENCODE_REQUEST_TIMEOUT_SECONDS,
                )
                if resp.status_code != 200:
                    logger.warning("opencode messages poll failed: %d", resp.status_code)
                    return None

                messages = resp.json()
                if not isinstance(messages, list):
                    logger.warning("opencode messages payload was not a list")
                    return None

                for message in messages:
                    if _message_role(message) != "assistant":
                        continue
                    text = _extract_response_text(message)
                    if text:
                        latest_text = text
                    error_text = _assistant_message_error(message)
                    if error_text:
                        logger.warning("opencode assistant error: %s", error_text)
                        return None
                    if _assistant_message_completed(message):
                        parsed = _parse_json_from_text(text or latest_text)
                        if parsed and "matches" in parsed:
                            return parsed
                        if text or latest_text:
                            logger.warning(
                                "opencode completed assistant response not valid resolve JSON: %s",
                                (text or latest_text)[:200],
                            )

                time_left = (deadline - datetime.datetime.now()).total_seconds()
                if time_left <= 0:
                    break
                time.sleep(min(1.0, time_left))

            logger.warning("opencode resolve timed out after %.1f seconds", OPENCODE_TIMEOUT_SECONDS)
            return None
        finally:
            try:
                requests.delete(
                    f"{opencode_url}/session/{session_id}",
                    timeout=OPENCODE_REQUEST_TIMEOUT_SECONDS,
                )
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
            "Semantic matching for a natural-language query. Delegates to the "
            "OpenCode registry agent first and falls back to lightweight keyword "
            "scoring if OpenCode is unavailable. Set include_raw=true to also get "
            "the full registry markdown on fallback."
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
                "description": "Find a service for orders (OpenCode agent or keyword fallback)",
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_registry()
    yield

app = FastAPI(
    title="CLI Service Registry",
    description="Agent-facing service registry with semantic discovery",
    version="1.0.0",
    lifespan=lifespan,
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

        # Try semantic resolve via the OpenCode registry agent
        smart = await asyncio.to_thread(_resolve_via_opencode, query)

        if smart is not None:
            # Preserve the agent's richer response shape instead of collapsing
            # it to matches-only. This keeps semantic intent, rationale, and
            # related services available to callers.
            result = {"query": query, **smart, "resolved_by": "opencode-agent"}
            matches = result.get("matches", [])
            if isinstance(matches, list):
                result["matches"] = matches[:limit]
        else:
            # Fallback: OpenCode unavailable, use keyword scoring.
            # prerequisites is not present because dependency notes require
            # semantic reasoning from the registry agent.
            result = await asyncio.to_thread(
                cmd_resolve, query, limit=limit, include_raw=include_raw
            )
            result["resolved_by"] = "fallback"

        result = _normalize_resolve_result(result, limit)

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
    print(f"opencode URL:  {OPENCODE_URL} (for registry-agent resolve)")
    print(f"opencode agent: {OPENCODE_AGENT}")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
