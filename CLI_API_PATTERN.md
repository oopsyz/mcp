# Building a CLI-Style HTTP API for LLM Agents

## What This Pattern Is

A CLI-style HTTP API is a single-endpoint HTTP interface designed for LLM agents to discover and invoke server-side tools interactively — the same way a human uses a command-line tool with `--help`.

```
POST /api/cli
{ "command": "<name>", "args": { ... }, "stream": false }
```

One endpoint. All tools. Discovery built in. No URL construction, no per-tool routes.

Example: in the TMF620 repo, the MCP adapter exposes `38` generated command tools plus `2` compatibility tools. The measured wrapped MCP tool payload is `3,735` tokens, while compact `GET /api/cli` is `189` tokens, compact group help is `105` tokens, and compact catalog + group help + leaf help is `512` tokens. That gap is why the rest of this pattern prefers compact progressive discovery for larger surfaces.

This pattern is well-suited for services with many tools because the LLM pays context cost proportional to what it actually uses — not the full tool surface upfront.

---

## Core Principles

**1. Single endpoint, command dispatch**
All tools are reachable through one URL. The LLM constructs `{"command": "...", "args": {...}}` — no URL templating, no per-tool routes to remember.

**2. Progressive disclosure**

- `GET /api/cli` → names + one-line summaries only (compact)
- `POST {"command": "help", "args": {"command": "<name>"}}` → full schema for one tool
- `POST {"command": "...", "args": {...}}` → invoke

The LLM fetches detail on demand, not all at once.

Compact-by-default catalogs are preferable for large services. If you want a richer top-level catalog for debugging or manual inspection, expose it behind an explicit switch such as `GET /api/cli?verbose=true` instead of making every caller pay that cost by default. The same principle applies to branch help: group nodes can stay compact, while leaf-command help expands to the full argument schema.

If you want to validate the tradeoff in a real implementation, build a small benchmark that tokenizes the compact catalog, compact group help, leaf help, and the wrapped MCP tool payload. That makes the savings visible instead of theoretical.

**3. Help is a first-class command**
`help` is a reserved command name. The LLM can always ask what's available and how to use it — no out-of-band documentation needed.

**4. Schema is yours to control**
Unlike MCP JSON Schema (derived from type annotations), the CLI schema is a dict you build. You can add enums, valid ranges, domain hints, warnings, and examples that JSON Schema can't express.

**5. Read vs destructive separation**
Decide explicitly which tools belong in the CLI registry. Destructive or privileged tools should require deliberate exposure — not be included by default.

**6. Streaming is opt-in**
`"stream": true` switches the response to NDJSON chunked transfer. Non-streaming callers are unaffected.

---

## Building It: Step by Step

### Step 1 — Write your tools as async functions

```python
async def list_items(context, category: str = "all", limit: int = 20) -> dict:
    """
    List items in the catalogue.

    :param category: Filter by category (default: all).
    :param limit: Maximum number of items to return (default: 20).
    """
    rows = await db.fetch("SELECT * FROM items WHERE category = $1 LIMIT $2", category, limit)
    return {
        "items": [dict(r) for r in rows],
        "total": len(rows),
        "dataset": "catalogue",
    }
```

Key conventions:

- First parameter is `context` (MCP lifecycle, can be `None` for HTTP callers — don't rely on it)
- Return a dict with an `items` list, or adapt a richer internal response shape so the CLI layer can still stream from an item list naturally
- Docstring first line becomes the catalog summary; full docstring goes in per-command help

### Step 2 — Define two registries

```python
# All tools registered internally (full surface)
def _all_tool_names() -> list[str]:
    return [
        "list_items",
        "get_item",
        "search_items",
        "health",
        "create_item",   # kept here but NOT in CLI registry
        "delete_item",   # kept here but NOT in CLI registry
    ]

def _all_tool_registry() -> dict[str, object]:
    return {name: globals()[name] for name in _all_tool_names()}


# CLI-exposed subset (read-only, safe for agents)
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

The split is intentional — the full registry may include mutation or admin tools. The CLI registry is the safe, agent-facing subset.

### Step 3 — Build the schema helpers

```python
import inspect

def _annotation_name(annotation) -> str | None:
    if annotation is inspect.Signature.empty:
        return None
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)


def _describe_tool(tool_name: str, tool) -> dict:
    """Full schema for per-command help."""
    sig = inspect.signature(tool)
    parameters = []
    for param in sig.parameters.values():
        if param.name == "context":
            continue
        parameters.append({
            "name": param.name,
            "required": param.default is inspect.Parameter.empty,
            "default": None if param.default is inspect.Parameter.empty else param.default,
            "annotation": _annotation_name(param.annotation),
        })
    return {
        "name": tool_name,
        "summary": inspect.getdoc(tool) or "",
        "parameters": parameters,
    }


def _describe_tool_summary(tool_name: str, tool) -> dict:
    """One-liner for the catalog."""
    doc = inspect.getdoc(tool) or ""
    return {
        "name": tool_name,
        "summary": doc.splitlines()[0] if doc else "",
    }


def _usage_example(tool_name: str, parameters: list[dict]) -> dict:
    args = {}
    for p in parameters:
        if p["required"]:
            args[p["name"]] = f"<{p['name']}>"
        elif p["default"] is not None:
            args[p["name"]] = p["default"]
    return {"command": tool_name, "args": args}
```

### Step 4 — Enrich schemas with domain knowledge

The base `_describe_tool` derives everything from type annotations. Enrich it for parameters where valid values are finite or constrained:

```python
# Extend _describe_tool output for specific commands
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
    },
    "search_items": {
        "sort": {
            "enum": ["relevance", "price_asc", "price_desc", "newest"],
        },
    },
}

def _describe_command(tool_name: str, tool) -> dict:
    details = _describe_tool(tool_name, tool)
    enrichments = _PARAMETER_ENRICHMENTS.get(tool_name, {})
    for param in details["parameters"]:
        extra = enrichments.get(param["name"], {})
        param.update(extra)
    details["usage"] = _usage_example(tool_name, details["parameters"])
    details["streaming"] = {
        "supported": True,
        "enable": "Add \"stream\": true alongside \"command\" and \"args\".",
    }
    return details
```

Enrichments to consider per parameter:

- `enum` — finite set of valid values
- `range` — `[min, max]` for numeric parameters
- `description` — domain-specific explanation beyond what the docstring says
- `example` — a concrete value the LLM can copy
- `warning` — side effects or gotchas ("this query can be slow on large datasets")

### Step 5 — Build the catalog and help payloads

```python
def _catalog_payload() -> dict:
    registry = _cli_command_registry()
    commands = [
        _describe_tool_summary(name, registry[name])
        for name in sorted(registry)
    ]
    return {
        "status": "ok",
        "service": "my-service",
        "interface": "cli",
        "how_to_invoke": {
            "endpoint": "POST /api/cli",
            "shape": {"command": "<command_name>", "args": {}, "stream": False},
        },
        "how_to_get_help": {
            "all_commands": "GET /api/cli  or  POST /api/cli {\"command\": \"help\"}",
            "one_command": "POST /api/cli {\"command\": \"help\", \"args\": {\"command\": \"<name>\"}}",
        },
        "streaming": {
            "supported": True,
            "enable": "Add \"stream\": true to any command request.",
            "content_type": "application/x-ndjson",
            "chunk_types": {
                "started": "Emitted immediately when the request is accepted.",
                "item": "One chunk per result item (tools that return an items array).",
                "done": "Final chunk with total item count and result metadata.",
                "result": "Single-chunk response for tools that do not return an items array.",
                "error": "Emitted on tool error or unexpected exception.",
            },
        },
        "commands": commands,
        "total": len(commands),
    }

For larger command sets, keep this catalog payload compact by default. If you also want a richer catalog, expose it through an explicit `verbose=true` switch or a separate helper rather than expanding the default discovery response.

def _command_help_payload(command_name: str) -> dict | None:
    registry = _cli_command_registry()
    tool = registry.get(command_name)
    if tool is None:
        return None
    params = _describe_tool(command_name, tool)["parameters"]
    return {
        "status": "ok",
        "service": "my-service",
        "interface": "cli",
        "how_to_invoke": {
            "endpoint": "POST /api/cli",
            "shape": _usage_example(command_name, params),
        },
        "how_to_stream": {
            "example": {**_usage_example(command_name, params), "stream": True},
        },
        "command": _describe_command(command_name, tool),
    }
```

### Step 6 — The streaming generator

```python
from starlette.responses import StreamingResponse
import json

async def _stream_cli_response(command: str, args: dict):
    yield json.dumps({"type": "started", "command": command}) + "\n"
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
            yield json.dumps({"type": "done", "command": command, "total": len(items), **meta}) + "\n"
        else:
            yield json.dumps({"type": "result", "command": command, "data": result}) + "\n"
    except Exception as exc:
        yield json.dumps({"type": "error", "error": {"code": "stream_failed", "message": str(exc)}}) + "\n"
```

### Step 7 — The route handler

```python
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

@app.custom_route("/api/cli", methods=["GET"])
async def cli_help(request: Request):
    return JSONResponse(_catalog_payload())


@app.custom_route("/api/cli", methods=["POST"])
async def cli_invoke(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "error": {"code": "invalid_json", "message": "Request body must be valid JSON."}}, status_code=400)

    if not isinstance(payload, dict):
        return JSONResponse({"status": "error", "error": {"code": "invalid_request", "message": "Request body must be a JSON object."}}, status_code=400)

    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        return JSONResponse({"status": "error", "error": {"code": "invalid_command", "message": "'command' must be a non-empty string."}}, status_code=400)

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return JSONResponse({"status": "error", "error": {"code": "invalid_arguments", "message": "'args' must be a JSON object."}}, status_code=400)

    stream = payload.get("stream", False)
    if not isinstance(stream, bool):
        return JSONResponse({"status": "error", "error": {"code": "invalid_request", "message": "'stream' must be a boolean."}}, status_code=400)

    normalized = command.strip()

    # help command
    if normalized == "help":
        target = args.get("command")
        if target:
            result = _command_help_payload(target.strip())
            if result is None:
                return JSONResponse({"status": "error", "error": {"code": "command_not_found", "message": f"Unknown command: {target}"}}, status_code=404)
            return JSONResponse(result)
        return JSONResponse(_catalog_payload())

    if normalized not in _cli_command_registry():
        return JSONResponse({"status": "error", "error": {"code": "command_not_found", "message": f"Unknown command: {normalized}"}}, status_code=404)

    if stream:
        return StreamingResponse(_stream_cli_response(normalized, args), media_type="application/x-ndjson")

    tool_response = await _invoke_tool(normalized, args)
    if tool_response.status_code != 200:
        return tool_response

    body = json.loads(tool_response.body)
    return JSONResponse({"status": "ok", "interface": "cli", "command": body["tool"], "args": body["arguments"], "result": body["result"]})
```

---

## What the LLM Sees at Each Level

### Level 1 — Catalog (`GET /api/cli`)

```json
{
  "status": "ok",
  "how_to_invoke": { "endpoint": "POST /api/cli", "shape": {...} },
  "how_to_get_help": { "one_command": "POST /api/cli {\"command\": \"help\", ...}" },
  "streaming": { "supported": true, ... },
  "commands": [
    {"name": "get_item", "summary": "Retrieve a single item by ID."},
    {"name": "list_items", "summary": "List items in the catalogue."},
    {"name": "search_items", "summary": "Semantic search over the item catalogue."}
  ],
  "total": 3
}
```

~100 bytes per command. Scales to 100 tools without bloating context.

### Level 2 — Command detail (`POST {"command": "help", "args": {"command": "list_items"}}`)

```json
{
  "how_to_invoke": { "shape": {"command": "list_items", "args": {"limit": 20}} },
  "how_to_stream": { "example": {"command": "list_items", "args": {"limit": 20}, "stream": true} },
  "command": {
    "name": "list_items",
    "summary": "List items in the catalogue.\n\n:param category: ...",
    "parameters": [
      {"name": "category", "required": false, "default": "all", "enum": ["all", "electronics", ...]},
      {"name": "limit", "required": false, "default": 20, "range": [1, 100]}
    ],
    "usage": {"command": "list_items", "args": {"limit": 20}},
    "streaming": {"supported": true, "enable": "Add \"stream\": true ..."}
  }
}
```

### Level 3 — Invocation

```json
POST /api/cli
{"command": "list_items", "args": {"category": "electronics", "limit": 5}, "stream": true}
```

```
{"type": "started", "command": "list_items"}
{"type": "item", "data": {"id": 1, "name": "Laptop", ...}}
{"type": "item", "data": {"id": 2, "name": "Phone", ...}}
{"type": "done", "total": 2, "dataset": "catalogue"}
```

---

## LLM Interaction Flow

### Basic flow

```
1. GET  /api/cli                                          → discover what exists
2. POST {"command": "help", "args": {"command": "..."}}   → inspect one tool
3. POST {"command": "...", "args": {...}}                  → invoke
4. POST {"command": "...", "args": {...}}                  → refine or chain
```

### With semantic discovery (recommended at 50+ tools)

Add a `semantic_find` command backed by a vector search over tool names and descriptions. The LLM narrows by intent before browsing:

```
1. POST {"command": "semantic_find", "args": {"query": "find products by price range"}}
   → returns 3-5 relevant command summaries
2. POST {"command": "help", "args": {"command": "search_items"}}
   → full schema
3. POST {"command": "search_items", "args": {...}, "stream": true}
   → streamed results
```

### System prompt for the LLM

Keep it minimal — the interface is self-describing:

```
You have access to a CLI API at POST /api/cli.
Start with GET /api/cli to discover available commands.
Use {"command": "help", "args": {"command": "<name>"}} to get full parameter details before invoking.
Use "stream": true for commands that return large result sets.
```

---

## Checklist

### Registry

- [ ] Separate full internal registry from CLI-exposed subset
- [ ] Exclude destructive, privileged, or mutation tools from CLI registry
- [ ] All CLI tools return `{"items": [...], ...}` for streaming to work naturally
- [ ] Tools that don't return items (health checks, single-record lookups) return a flat dict

### Schema

- [ ] First line of every docstring is a clear one-liner (used as catalog summary)
- [ ] All parameters have type annotations
- [ ] Enums added for parameters with finite valid values
- [ ] Ranges added for numeric parameters with bounds
- [ ] At least one usage example per command

### Discovery

- [ ] `GET /api/cli` returns catalog with summaries only (not full schemas)
- [ ] `POST {"command": "help"}` returns same catalog
- [ ] `POST {"command": "help", "args": {"command": "<name>"}}` returns full detail
- [ ] Catalog includes `how_to_invoke` and `how_to_get_help` instructions
- [ ] Unknown command returns `command_not_found` error with 404

### Streaming

- [ ] `"stream": true` switches to `StreamingResponse` with `application/x-ndjson`
- [ ] Generator emits `started` immediately
- [ ] Generator emits one `item` chunk per element in `items`
- [ ] Generator emits `done` with total and metadata
- [ ] Generator emits `error` chunk on exception (does not raise)
- [ ] Non-streaming path unchanged for clients that don't set `"stream": true`

### Error handling

- [ ] Invalid JSON → 400 `invalid_json`
- [ ] Non-object body → 400 `invalid_request`
- [ ] Missing or empty command → 400 `invalid_command`
- [ ] Non-object args → 400 `invalid_arguments`
- [ ] Unknown command → 404 `command_not_found`
- [ ] Tool invocation error → 500 `tool_invocation_failed` with message

---

## Client Integrations

### Bash / curl — LLMs with bash tool and shell scripts

No client library needed. Any environment with `curl` can use the service.

**Discover:**

```bash
curl -s http://myserver:9000/api/cli | jq .
```

**Inspect a command:**

```bash
curl -s -X POST http://myserver:9000/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command": "help", "args": {"command": "list_items"}}' | jq .
```

**Invoke:**

```bash
curl -s -X POST http://myserver:9000/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command": "list_items", "args": {"category": "electronics", "limit": 5}}' | jq .
```

**Stream (NDJSON):**

```bash
curl -s --no-buffer -X POST http://myserver:9000/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command": "list_items", "args": {"limit": 100}, "stream": true}'
```

**Reusable shell helper:**

```bash
#!/bin/bash
MCP_URL="${MY_SERVICE_URL:-http://localhost:9000}"

cli() {
  local command=$1
  local args=${2:-'{}'}
  curl -s -X POST "$MCP_URL/api/cli" \
    -H "Content-Type: application/json" \
    -d "{\"command\": \"$command\", \"args\": $args}" | jq .
}

cli list_items '{"category": "electronics"}'
cli help '{"command": "search_items"}'
```

**An LLM with a bash tool** follows the same discover → inspect → invoke pattern a human would. No MCP, no SDK — just `curl`. The system prompt can be as simple as:

```text
You have bash access. The service is at http://myserver:9000.
Run: curl -s http://myserver:9000/api/cli | jq .
to discover available commands, then invoke them as needed.
```

---

### MCP — Claude Desktop and MCP-aware frameworks

TMF620 is a concrete example of why this matters: the wrapped MCP tool payload is `3,735` tokens for `40` visible tools in the adapter, while the compact HTTP CLI path is `189` tokens for the initial catalog and `512` tokens through one leaf command. The exact numbers vary by schema size, but the shape of the tradeoff is stable: MCP discovery grows with the tool surface, while compact CLI discovery grows with only the branch the agent actually inspects.

For MCP clients, expose a single `cli` tool that proxies to the same underlying command registry. The MCP client sees **one tool** instead of the full surface — the LLM drives discovery through `help` exactly as it would over HTTP.

**Why one tool, not many:**

- MCP `tools/list` sends full JSON Schema for every registered tool upfront
- At 20 tools: ~14KB in context before the LLM does anything; at 100 tools: ~70KB
- A single `cli` tool keeps `tools/list` tiny; the LLM pays context cost only for commands it actually uses

**Implementation — direct function calls (no HTTP round-trip):**

```python
from mcp.server.fastmcp import Context

@app.tool()
async def cli(
    context: Context,
    command: str,
    args: dict = {},
    stream: bool = False,
) -> dict:
    """
    Invoke a service command interactively.

    Start with command='help' to discover available commands.
    Use command='help', args={'command': '<name>'} for full parameter details.
    Supports all commands from GET /api/cli.

    :param command: Command name to invoke, or 'help' for discovery.
    :param args: Command arguments as a key-value dict.
    :param stream: Not applicable via MCP — use HTTP /api/cli for streaming.
    """
    normalized = command.strip() if isinstance(command, str) else ""

    if normalized == "help":
        target = args.get("command")
        if target:
            result = _command_help_payload(target.strip())
            if result is None:
                return {"status": "error", "error": {"code": "command_not_found", "message": f"Unknown command: {target}"}}
            return result
        return _catalog_payload()

    registry = _cli_command_registry()
    if normalized not in registry:
        return {"status": "error", "error": {"code": "command_not_found", "message": f"Unknown command: {normalized}"}}

    tool_fn = registry[normalized]
    try:
        result = await tool_fn(context, **args)
    except TypeError as exc:
        return {"status": "error", "error": {"code": "invalid_arguments", "message": str(exc)}}

    return {"status": "ok", "interface": "mcp-cli", "command": normalized, "args": args, "result": result}
```

**Key points:**

- Calls `_cli_command_registry()` and the tool functions directly — no HTTP round-trip, no running server required
- Passes the real `Context` object through — tools get progress notifications if they use it
- `stream: bool` parameter is declared for schema completeness but streaming is not applicable via MCP (MCP tool results are single responses); direct clients should use `POST /api/cli` with `"stream": true` for NDJSON streaming
- `help` and discovery work identically to the HTTP interface — same `_catalog_payload()` and `_command_help_payload()` functions

**Claude Desktop config:**

```json
{
  "mcpServers": {
    "my-service": {
      "url": "http://localhost:9000/mcp"
    }
  }
}
```

**What Claude Desktop sees in `tools/list`:**

```json
[
  {
    "name": "cli",
    "description": "Invoke a service command interactively.\n\nStart with command='help' to discover...",
    "inputSchema": {
      "type": "object",
      "properties": {
        "command": {"type": "string"},
        "args": {"type": "object"},
        "stream": {"type": "boolean"}
      },
      "required": ["command"]
    }
  }
]
```

One tool. Minimal context cost. Full surface accessible through `help`.

---

### Summary: All three clients, one implementation

```text
Claude Desktop / MCP frameworks   →  MCP tool "cli"  ↘
HTTP agents / LLM with HTTP tool  →  POST /api/cli   →  shared registry + tool functions
LLM with bash / shell scripts     →  curl            ↗
```

The tool functions, registry, schema helpers, and catalog/help payloads are written once. All three client paths share them — no logic is duplicated.

---

## Things to Consider

**Auth** — the `/api/cli` endpoint has no authentication by default. Sit behind a reverse proxy that handles API keys or JWT before exposing remotely.

**Read vs write** — be deliberate about what goes in the CLI registry. A good default: if a tool modifies state, it does not belong in the CLI registry unless there is an explicit reason.

**Streaming defaults** — streaming is opt-in. For tools that routinely return hundreds of items, consider documenting expected sizes in the command summary so the LLM knows to request streaming.

**Schema drift** — parameter enrichments (`_PARAMETER_ENRICHMENTS`) are maintained separately from the function signatures. When you rename a parameter or add a new one, update the enrichments too.

**`context` parameter** — tools that declare `context: Context` will receive `None` when called through the HTTP path. Do not rely on `context` inside tools that are also exposed via `/api/cli`. Use logging instead of `context.info()`.

**Semantic discovery** — at 20-30 tools the catalog is manageable. At 50+ tools, add a `semantic_find` command backed by vector search over tool metadata. Without it, the LLM must scan all summaries linearly.

**Versioning** — if the tool surface changes significantly, consider a `version` field in the catalog payload. Agents that cache the catalog can detect when it is stale.
