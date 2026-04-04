"""
Core registry operations on ``registry_agent/data/registry.md``.

This module has no web framework dependencies.  It is imported by both:

- ``registry_agent/server.py``  (FastAPI + MCP — network path)
- OpenCode skill              (``python registry_agent/core.py <cmd>`` — local path)
"""

import json
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

REGISTRY_FILE = Path(__file__).resolve().parent / "data" / "registry.md"

_FIELD_DISPLAY = {
    "url": "URL",
    "cli": "CLI",
    "mcp": "MCP",
    "handles": "Handles",
    "use_when": "Use when",
    "owner": "Owner",
    "tags": "Tags",
    "description": "Description",
}

_FIELD_ORDER = list(_FIELD_DISPLAY.keys())


# ---------------------------------------------------------------------------
# Parsing / writing
# ---------------------------------------------------------------------------


def _normalize_key(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_")


def _validate_service_entry(service: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cli = service.get("cli")
    if cli is not None:
        if not isinstance(cli, str) or not cli.startswith("/cli/"):
            errors.append("CLI must be a string starting with '/cli/'.")
    return errors


def parse_registry(path: Path = REGISTRY_FILE) -> list[dict[str, Any]]:
    """Parse *registry_agent/data/registry.md* into a list of service dicts."""
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    services: list[dict[str, Any]] = []

    for block in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue

        service_id = lines[0].strip()
        entry: dict[str, Any] = {"id": service_id}

        for line in lines[1:]:
            line = line.strip()
            if not line.startswith("- ") or ": " not in line:
                continue
            key, value = line[2:].split(": ", 1)
            key = _normalize_key(key)
            if key == "tags":
                entry[key] = [t.strip() for t in value.split(",")]
            else:
                entry[key] = value.strip()

        services.append(entry)

    return services


def _render_block(service: dict[str, Any]) -> str:
    lines = [f"## {service['id']}"]
    rendered_keys: set[str] = {"id"}

    for key in _FIELD_ORDER:
        if key not in service:
            continue
        rendered_keys.add(key)
        display = _FIELD_DISPLAY.get(key, key.replace("_", " ").title())
        value = service[key]
        if isinstance(value, list):
            value = ", ".join(value)
        lines.append(f"- {display}: {value}")

    for key, value in service.items():
        if key in rendered_keys:
            continue
        display = key.replace("_", " ").title()
        if isinstance(value, list):
            value = ", ".join(value)
        lines.append(f"- {display}: {value}")

    return "\n".join(lines)


def write_registry(services: list[dict[str, Any]], path: Path = REGISTRY_FILE) -> None:
    header = "# Service Registry\n\n"
    blocks = [_render_block(s) for s in services]
    path.write_text(header + "\n\n".join(blocks) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_list(path: Path = REGISTRY_FILE) -> dict[str, Any]:
    services = parse_registry(path)
    return {
        "services": [
            {
                "id": s["id"],
                "url": s.get("url", ""),
                "handles": s.get("handles", ""),
                "status": s.get("status", "live"),
            }
            for s in services
        ],
        "total": len(services),
    }


def cmd_get(service_id: str, path: Path = REGISTRY_FILE) -> dict[str, Any]:
    for s in parse_registry(path):
        if s["id"] == service_id:
            return {"service": s}
    return {
        "error": f"Service not found: {service_id}",
        "available": [s["id"] for s in parse_registry(path)],
    }


def _score_service(query: str, service: dict[str, Any]) -> float:
    """Score a service against a query using keyword overlap."""
    query_words = set(query.lower().split())
    score = 0.0
    handles = service.get("handles", "").lower()
    use_when = service.get("use_when", "").lower()
    tags = [t.lower() for t in service.get("tags", [])]
    for word in query_words:
        if word in handles:
            score += 2.0
        if word in use_when:
            score += 1.5
        if any(word in tag for tag in tags):
            score += 1.0
    return score


def cmd_resolve(
    query: str,
    path: Path = REGISTRY_FILE,
    *,
    limit: int = 5,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Return ranked service matches for the query.

    Uses lightweight keyword scoring so the response scales with registry size.
    Set ``include_raw=True`` to also return the full registry markdown (for
    callers that want to do their own LLM-powered reasoning).
    """
    services = parse_registry(path)
    scored = [(svc, _score_service(query, svc)) for svc in services]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    matches = [
        {
            **svc,
            "status": svc.get("status", "live"),
            "score": round(score, 2),
        }
        for svc, score in scored
        if score > 0
    ][:limit]

    result: dict[str, Any] = {
        "query": query,
        "matches": matches,
        "total_services": len(services),
        "returned": len(matches),
    }

    if include_raw:
        raw = path.read_text(encoding="utf-8") if path.exists() else ""
        result["registry_content"] = raw

    if not matches:
        result["instruction"] = (
            "No services matched your query. Consider broadening the search "
            "or use the 'list' command to see all available services."
        )

    return result


def cmd_register(service: dict[str, Any], path: Path = REGISTRY_FILE) -> dict[str, Any]:
    if "id" not in service:
        return {"error": "Service entry must include an 'id' field."}

    validation_errors = _validate_service_entry(service)
    if validation_errors:
        return {"error": "; ".join(validation_errors)}

    services = parse_registry(path)

    for i, existing in enumerate(services):
        if existing["id"] == service["id"]:
            # Preserve operational status unless the caller explicitly sets it
            if "status" not in service and "status" in existing:
                service = {**service, "status": existing["status"]}
            services[i] = service
            write_registry(services, path)
            return {"status": "updated", "service": service}

    services.append(service)
    write_registry(services, path)
    return {"status": "registered", "service": service}


def cmd_unregister(service_id: str, path: Path = REGISTRY_FILE) -> dict[str, Any]:
    services = parse_registry(path)
    filtered = [s for s in services if s["id"] != service_id]

    if len(filtered) == len(services):
        return {"error": f"Service not found: {service_id}"}

    write_registry(filtered, path)
    return {"status": "unregistered", "service_id": service_id}


VALID_STATUSES = {"live", "degraded", "maintenance"}


def cmd_setstatus(
    service_id: str, status: str, path: Path = REGISTRY_FILE
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        return {
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        }

    services = parse_registry(path)
    for svc in services:
        if svc["id"] == service_id:
            previous = svc.get("status", "live")
            svc["status"] = status
            write_registry(services, path)
            return {
                "status": "updated",
                "service_id": service_id,
                "previous": previous,
                "current": status,
            }

    return {
        "error": f"Service not found: {service_id}",
        "available": [s["id"] for s in services],
    }


# ---------------------------------------------------------------------------
# CLI entry point  —  python registry_agent/core.py <command> [args...]
# ---------------------------------------------------------------------------

USAGE = """\
Usage: python registry_agent/core.py <command> [args...]

Commands:
  list                          List all registered services
  get <service_id>              Get one service by ID
  resolve <query>               Semantic resolve — returns full registry for LLM
  register <json>               Register or update (pass service JSON object)
  unregister <service_id>       Remove a service by ID
  setstatus <service_id> <status>  Update service status (live|degraded|maintenance)
"""


def cli_main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return

    cmd = args[0]

    if cmd == "list":
        result = cmd_list()
    elif cmd == "get":
        if len(args) < 2:
            print("Error: service_id required", file=sys.stderr)
            sys.exit(1)
        result = cmd_get(args[1])
    elif cmd == "resolve":
        if len(args) < 2:
            print("Error: query required", file=sys.stderr)
            sys.exit(1)
        result = cmd_resolve(" ".join(args[1:]))
    elif cmd == "register":
        if len(args) < 2:
            print("Error: JSON service object required", file=sys.stderr)
            sys.exit(1)
        try:
            service = json.loads(" ".join(args[1:]))
        except json.JSONDecodeError as exc:
            print(f"Error: invalid JSON: {exc}", file=sys.stderr)
            sys.exit(1)
        result = cmd_register(service)
    elif cmd == "unregister":
        if len(args) < 2:
            print("Error: service_id required", file=sys.stderr)
            sys.exit(1)
        result = cmd_unregister(args[1])
    elif cmd == "setstatus":
        if len(args) < 3:
            print("Error: service_id and status required", file=sys.stderr)
            sys.exit(1)
        result = cmd_setstatus(args[1], args[2])
    else:
        print(f"Unknown command: {cmd}\n{USAGE}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    cli_main()
