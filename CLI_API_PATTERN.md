# Building a CLI-Style HTTP API for LLM Agents

## Why This Pattern

Large MCP tool lists do not scale well for agent use. As the number of tools grows, many runtimes keep resending the full tool surface, which turns discovery into repeated context cost.

A CLI-style HTTP API shifts that cost. The agent starts with a compact catalog, asks for help on one command at a time, and only pays for the part of the surface it actually uses.

Practical benefits:

- Compact discovery with `GET /api/cli`
- Progressive help with `POST /api/cli {"command":"help",...}`
- Lower token cost than exposing every operation as a separate tool
- Simple automation with `curl`
- One shared command layer for HTTP, MCP, tests, and benchmarks

This pattern is especially useful when a service has dozens of operations or more.

---

## What This Pattern Is

A CLI-style HTTP API is a single-endpoint interface for discovery and invocation:

```text
POST /api/cli
{ "command": "<name>", "args": { ... }, "stream": false }
```

One endpoint. One request envelope. Built-in help.

The agent workflow is:

1. `GET /api/cli`
2. `POST /api/cli {"command":"help","args":{"command":"..."}}`
3. `POST /api/cli {"command":"...","args":{...}}`

---

## Core Principles

### 1. Single endpoint

All discovery and invocation happen through one URL.

### 2. Progressive disclosure

The catalog stays compact. Full detail is fetched only for one command at a time.

- `GET /api/cli` -> compact catalog
- `POST {"command":"help","args":{"command":"<name>"}}` -> detailed help
- `POST {"command":"<name>","args":{...}}` -> invoke

### 3. Help is part of the protocol

`help` is a reserved command. Agents should not need out-of-band docs.

### 4. Schema is curated

You control the help payload. Add examples, enums, ranges, warnings, and domain hints where useful.

### 5. Registry scope is explicit

Decide intentionally which commands belong in the agent-facing registry. Starting with read-oriented commands is often the safest default, but the wire contract should not force one policy for every service.

### 6. Streaming is opt-in

Streaming should only happen when the caller sets `"stream": true`.

---

## Building It

### Step 1 - Write tools as async functions

```python
async def list_items(context, category: str = "all", limit: int = 20) -> dict:
    """
    List items in the catalogue.

    :param category: Filter by category.
    :param limit: Maximum number of items to return.
    """
    rows = await db.fetch("SELECT * FROM items WHERE category = $1 LIMIT $2", category, limit)
    return {
        "items": [dict(r) for r in rows],
        "total": len(rows),
        "dataset": "catalogue",
    }
```

Conventions:

- The first parameter is `context`
- Tools usually return a dict
- List-like commands should preferably return `{"items": [...], ...}` so streaming stays natural

### Step 2 - Define registries

```python
def _all_tool_names() -> list[str]:
    return [
        "list_items",
        "get_item",
        "search_items",
        "health",
        "create_item",
        "delete_item",
    ]


def _all_tool_registry() -> dict[str, object]:
    return {name: globals()[name] for name in _all_tool_names()}


def _cli_command_names() -> list[str]:
    return [
        "list_items",
        "get_item",
        "search_items",
        "health",
    ]


def _cli_command_registry() -> dict[str, object]:
    registry = _all_tool_registry()
    return {name: registry[name] for name in _cli_command_names() if name in registry}
```

The split is intentional. Internal and agent-facing registries do not have to be the same.

### Step 3 - Build schema helpers

```python
import inspect


def _annotation_name(annotation) -> str | None:
    if annotation is inspect.Signature.empty:
        return None
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)


def _describe_tool(tool_name: str, tool) -> dict:
    sig = inspect.signature(tool)
    arguments = []
    for param in sig.parameters.values():
        if param.name == "context":
            continue
        arguments.append(
            {
                "name": param.name,
                "required": param.default is inspect.Parameter.empty,
                "default": None if param.default is inspect.Parameter.empty else param.default,
                "type": _annotation_name(param.annotation),
            }
        )
    return {
        "command": tool_name,
        "summary": (inspect.getdoc(tool) or "").splitlines()[0] if inspect.getdoc(tool) else "",
        "description": inspect.getdoc(tool) or "",
        "arguments": arguments,
    }


def _usage_example(tool_name: str, arguments: list[dict]) -> dict:
    args = {}
    for arg in arguments:
        if arg["required"]:
            args[arg["name"]] = f"<{arg['name']}>"
        elif arg["default"] is not None:
            args[arg["name"]] = arg["default"]
    return {"command": tool_name, "args": args}
```

### Step 4 - Enrich with domain knowledge

```python
_PARAMETER_ENRICHMENTS = {
    "list_items": {
        "category": {
            "enum": ["all", "electronics", "clothing", "food"],
            "description": "Filter by product category.",
        },
        "limit": {
            "range": [1, 100],
            "description": "Number of items to return. Max 100.",
        },
    }
}


def _describe_command(tool_name: str, tool) -> dict:
    details = _describe_tool(tool_name, tool)
    enrichments = _PARAMETER_ENRICHMENTS.get(tool_name, {})
    for arg in details["arguments"]:
        arg.update(enrichments.get(arg["name"], {}))
    details["examples"] = [
        {
            "description": f"Invoke {tool_name}",
            "request": _usage_example(tool_name, details["arguments"]),
        }
    ]
    return details
```

Useful fields include:

- `enum`
- `range`
- `description`
- `example`
- `warning`

### Step 5 - Build discovery and help payloads

```python
def _catalog_payload() -> dict:
    registry = _cli_command_registry()
    commands = []
    for name in sorted(registry):
        commands.append(
            {
                "name": name,
                "kind": "command",
                "summary": (inspect.getdoc(registry[name]) or "").splitlines()[0],
            }
        )
    return {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "service": "my-service",
        "how_to_invoke": {
            "endpoint": "POST /api/cli",
            "shape": {"command": "<command_name>", "args": {}, "stream": False},
        },
        "how_to_get_help": {
            "all_commands": "GET /api/cli or POST /api/cli {\"command\": \"help\"}",
            "one_command": "POST /api/cli {\"command\": \"help\", \"args\": {\"command\": \"<name>\"}}",
        },
        "commands": commands,
        "total": len(commands),
    }


def _command_help_payload(command_name: str) -> dict | None:
    registry = _cli_command_registry()
    tool = registry.get(command_name)
    if tool is None:
        return None
    return {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "command": command_name,
        **_describe_command(command_name, tool),
    }
```

Keep the default catalog compact. If you want a richer debugging view, expose that separately or behind an explicit switch.

### Step 6 - Add streaming

```python
import json


async def _stream_cli_response(command: str, args: dict):
    yield json.dumps(
        {"type": "started", "command": command, "interface": "cli", "version": "1.0"}
    ) + "\n"

    try:
        tool_response = await _invoke_tool(command, args)
        body = json.loads(tool_response.body)

        if tool_response.status_code != 200:
            yield json.dumps({"type": "error", "error": body.get("error", {})}) + "\n"
            return

        result = body.get("result", {})
        items = result.get("items") if isinstance(result, dict) else None

        if isinstance(items, list):
            for item in items:
                yield json.dumps({"type": "item", "data": item}) + "\n"
            meta = {k: v for k, v in result.items() if k != "items"}
            yield json.dumps(
                {"type": "done", "command": command, "total": len(items), **meta}
            ) + "\n"
            return

        yield json.dumps({"type": "result", "command": command, "data": result}) + "\n"
    except Exception as exc:
        yield json.dumps(
            {"type": "error", "error": {"code": "stream_failed", "message": str(exc)}}
        ) + "\n"
```

### Step 7 - Add the route handler

```python
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {
            "status": "error",
            "interface": "cli",
            "version": "1.0",
            "error": {"code": code, "message": message},
        },
        status_code=status_code,
    )


@app.custom_route("/api/cli", methods=["GET"])
async def cli_catalog(request: Request):
    return JSONResponse(_catalog_payload())


@app.custom_route("/api/cli", methods=["POST"])
async def cli_dispatch(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return _error(400, "invalid_json", "Request body must be valid JSON.")

    if not isinstance(payload, dict):
        return _error(400, "invalid_request", "Request body must be a JSON object.")

    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        return _error(400, "invalid_command", "'command' must be a non-empty string.")

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return _error(400, "invalid_arguments", "'args' must be a JSON object.")

    stream = payload.get("stream", False)
    if not isinstance(stream, bool):
        return _error(400, "invalid_request", "'stream' must be a boolean.")

    normalized = command.strip()

    if normalized == "help":
        target = args.get("command")
        if target is None:
            return JSONResponse(_catalog_payload())
        if not isinstance(target, str) or not target.strip():
            return _error(400, "invalid_arguments", "'args.command' must be a non-empty string.")
        result = _command_help_payload(target.strip())
        if result is None:
            return _error(404, "help_target_not_found", f"Unknown help target: {target}")
        return JSONResponse(result)

    if normalized not in _cli_command_registry():
        return _error(404, "command_not_found", f"Unknown command: {normalized}")

    if stream:
        return StreamingResponse(
            _stream_cli_response(normalized, args),
            media_type="application/x-ndjson",
        )

    tool_response = await _invoke_tool(normalized, args)
    if tool_response.status_code != 200:
        return tool_response

    body = json.loads(tool_response.body)
    return JSONResponse(
        {
            "status": "ok",
            "interface": "cli",
            "version": "1.0",
            "command": normalized,
            "result": body["result"],
        }
    )
```

---

## What the Agent Sees

### Level 1 - Catalog

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "commands": [
    {"name": "get_item", "kind": "command", "summary": "Retrieve a single item by ID."},
    {"name": "list_items", "kind": "command", "summary": "List items in the catalogue."},
    {"name": "search_items", "kind": "command", "summary": "Semantic search over the item catalogue."}
  ],
  "total": 3
}
```

### Level 2 - Command help

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "command": "list_items",
  "summary": "List items in the catalogue.",
  "arguments": [
    {"name": "category", "required": false, "default": "all", "enum": ["all", "electronics"]},
    {"name": "limit", "required": false, "default": 20, "range": [1, 100]}
  ],
  "examples": [
    {
      "description": "Invoke list_items",
      "request": {"command": "list_items", "args": {"category": "all", "limit": 20}}
    }
  ]
}
```

### Level 3 - Invocation

```json
POST /api/cli
{"command":"list_items","args":{"category":"electronics","limit":5},"stream":true}
```

```ndjson
{"type":"started","command":"list_items","interface":"cli","version":"1.0"}
{"type":"item","data":{"id":1,"name":"Laptop"}}
{"type":"item","data":{"id":2,"name":"Phone"}}
{"type":"done","command":"list_items","total":2,"dataset":"catalogue"}
```

---

## Interaction Flow

### Basic

```text
1. GET  /api/cli                                        -> discover commands
2. POST {"command":"help","args":{"command":"..."}}     -> inspect one command
3. POST {"command":"...","args":{...}}                  -> invoke
```

### With semantic narrowing

At larger tool counts, add a `semantic_find` command so the agent can narrow before opening help for a specific command.

---

## Checklist

### Registry

- [ ] Separate internal and CLI-facing registries if needed
- [ ] Decide explicitly which write or destructive commands belong in the CLI registry
- [ ] Prefer `{"items": [...], ...}` for list-like commands

### Discovery

- [ ] `GET /api/cli` returns a compact catalog
- [ ] `POST {"command":"help"}` returns the same catalog
- [ ] `POST {"command":"help","args":{"command":"<name>"}}` returns detailed help
- [ ] Unknown help targets return `help_target_not_found`
- [ ] Unknown commands return `command_not_found`

### Error handling

- [ ] Invalid JSON -> `invalid_json`
- [ ] Non-object body -> `invalid_request`
- [ ] Missing or empty command -> `invalid_command`
- [ ] Non-object args -> `invalid_arguments`
- [ ] Tool failure -> `tool_invocation_failed`

### Streaming

- [ ] Streaming is only enabled by `"stream": true`
- [ ] First chunk is `started`
- [ ] Item collections emit `item` then `done`
- [ ] Single-result commands emit `result`
- [ ] Stream-time failures emit `error`

---

## Client Integrations

### Bash / curl

```bash
curl -s http://myserver:9000/api/cli | jq .
```

```bash
curl -s -X POST http://myserver:9000/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"list_items"}}' | jq .
```

```bash
curl -s -X POST http://myserver:9000/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"list_items","args":{"category":"electronics","limit":5}}' | jq .
```

```bash
curl -s --no-buffer -X POST http://myserver:9000/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"list_items","args":{"limit":100},"stream":true}'
```

### MCP

For MCP clients, expose one `cli` tool that proxies to the same command registry. That keeps `tools/list` small while preserving the same discover -> help -> invoke workflow.

```python
@app.tool()
async def cli(context, command: str, args: dict = {}, stream: bool = False) -> dict:
    normalized = command.strip() if isinstance(command, str) else ""

    if normalized == "help":
        target = args.get("command")
        if target:
            result = _command_help_payload(target.strip())
            if result is None:
                return {
                    "status": "error",
                    "interface": "cli",
                    "version": "1.0",
                    "error": {
                        "code": "help_target_not_found",
                        "message": f"Unknown help target: {target}",
                    },
                }
            return result
        return _catalog_payload()

    registry = _cli_command_registry()
    if normalized not in registry:
        return {
            "status": "error",
            "interface": "cli",
            "version": "1.0",
            "error": {"code": "command_not_found", "message": f"Unknown command: {normalized}"},
        }

    result = await registry[normalized](context, **args)
    return {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "command": normalized,
        "result": result,
    }
```

---

## Things to Consider

**Security**

- Add authentication before exposing `/api/cli` remotely
- Enforce authorization by command group or capability
- Add rate limits
- Add audit logging
- Validate all arguments before dispatch

**Read vs write**

Start with read-oriented commands if you want the safest rollout, then add write commands intentionally where the agent use case justifies them.

**Schema drift**

If parameter enrichments are maintained separately from function signatures, keep them in sync.

**Context handling**

If tools use an MCP `context`, remember HTTP callers may not have one.

**Versioning**

Include a `version` field in non-streaming responses so agents can detect contract changes.
