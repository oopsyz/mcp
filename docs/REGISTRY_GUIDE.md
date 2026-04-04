# CLI Service Registry

An agent-facing service registry that stores service metadata in a plain Markdown file and exposes it over the same CLI-style HTTP API contract used by every other service in this project.

The registry does not do semantic matching itself. It returns the full registry content so the calling agent (Qwen, Claude, GPT, or any local model) can reason over natural-language descriptions and pick the right service. The intelligence is in the caller, not the registry.

---

## Why a Markdown File

The registry data lives in `registry_agent/data/registry.md`. Each H2 block is one service entry.

- Human-readable and editable with any text editor
- Git-trackable with meaningful diffs
- No database, no schema migrations, no infrastructure
- Optimized for agent comprehension: the `Handles` and `Use when` fields are written in natural language so an LLM can match on intent, not keywords

The file is the single source of truth. The server reads it on every request and writes back to it on register/unregister. Changes made by hand or by the API are equivalent.

---

## Architecture

The registry has a shared core (`registry_agent/core.py`) with two access paths:

```text
registry_agent/data/registry.md
    ├── OpenCode skill/agent  ← local, no server needed
    ├── OpenCode sidecar (port 4096) ← semantic matching runtime
    └── HTTP server (port 7700)  ← network access, LLM-powered resolve
                    ↓
              opencode serve (port 4096)  ← for semantic matching
```

### Path 1: OpenCode Skill (Local)

Runs `registry_agent/core.py` directly — no server dependency. Use in `opencode serve`.

```sh
# List services
uv run python registry_agent/core.py list

# Get one service
uv run python registry_agent/core.py get tmf620/catalogmgt

# Semantic resolve (returns raw dump for agent to reason over)
uv run python registry_agent/core.py resolve I need to manage product orders

# Register
uv run python registry_agent/core.py register '{"id":"...","url":"...","handles":"..."}'

# Unregister
uv run python registry_agent/core.py unregister tmf622/ordermgt
```

### Path 2: HTTP Server (Network, LLM-Powered)

Start the registry server on port 7700:

```sh
uv run registry-server
```

The server exposes the HTTP CLI API:

```bash
# List services (fast, no LLM)
curl -s -X POST http://localhost:7700/cli/registry \
  -H "Content-Type: application/json" \
  -d '{"command":"list"}'

# Get one (fast, no LLM)
curl -s -X POST http://localhost:7700/cli/registry \
  -H "Content-Type: application/json" \
  -d '{"command":"get","args":{"service_id":"tmf620/catalogmgt"}}'

# Resolve (LLM-powered via opencode serve)
curl -s -X POST http://localhost:7700/cli/registry \
  -H "Content-Type: application/json" \
  -d '{"command":"resolve","args":{"query":"I need to manage product orders"}}'
```

**For LLM-powered resolve to work:**

- `docker-compose.registry.yml` starts an `opencode` sidecar on port 4096
- set `OPENCODE_URL` only if you want to target an external opencode instance
- If opencode is unavailable, resolve falls back to returning the raw dump

---

## Registry Entry Format

Each service in `registry_agent/data/registry.md` follows this structure:

```markdown
## <service-id>
- URL: <base url>
- CLI: <cli endpoint path>
- MCP: <mcp endpoint url>
- Handles: <what this service does, natural language>
- Use when: <when an agent should pick this service>
- Dependencies: <comma-separated full service IDs (e.g. tmf620/catalogmgt), or "none">
- Owner: <team or person>
- Tags: <comma-separated tags>
```

Example:

```markdown
## tmf622/ordermgt
- URL: http://localhost:7702
- CLI: /cli/tmf622/ordermgt
- MCP: http://localhost:7702/mcp
- Handles: product orders, order items, order lifecycle, cancellations, returns
- Use when: agent needs to place, track, modify, or cancel a product order
- Dependencies: tmf620/catalogmgt, tmf632/partymgt
- Owner: order-team
- Tags: order, fulfillment, tmf622
```

The `Handles` and `Use when` fields are the most important — write them in the language a client agent would think in, not in API jargon.

The `Dependencies` field encodes the inter-service knowledge that only the registry has. When the resolver sees `Dependencies: tmf620/catalogmgt, tmf632/partymgt`, it tells the calling agent: *"You will need a ProductOfferingRef from tmf620 and a PartyRef from tmf632 before you can use this service."* The agent does not need to know this upfront — the resolver provides it as part of the resolve response.

---

## Commands

All commands follow the standard CLI API contract.

### Discovery

```bash
curl -s http://localhost:7700/cli/registry
```

### list

List all registered services with brief summaries.

```bash
curl -s -X POST http://localhost:7700/cli/registry \
  -H "Content-Type: application/json" \
  -d '{"command":"list"}'
```

### get

Get full details of one service by ID.

```bash
curl -s -X POST http://localhost:7700/cli/registry \
  -H "Content-Type: application/json" \
  -d '{"command":"get","args":{"service_id":"tmf620/catalogmgt"}}'
```

### resolve

**LLM-powered semantic service resolution.** The client describes what it needs in natural language. The registry server calls opencode serve to match the query semantically and returns ranked matches with confidence scores.

```bash
curl -s -X POST http://localhost:7700/cli/registry \
  -H "Content-Type: application/json" \
  -d '{"command":"resolve","args":{"query":"I need to manage product orders"}}'
```

**Success response** (OpenCode available, matches found):

```json
{
  "status": "ok",
  "command": "resolve",
  "result": {
    "query": "I want to purchase a 5G data plan",
    "matches": [
      {
        "id": "tmf622/ordermgt",
        "url": "http://localhost:7702",
        "cli": "/cli/tmf622/ordermgt",
        "mcp": "http://localhost:7702/mcp",
        "confidence": 0.95,
        "reason": "Primary tool for creating product orders.",
        "prerequisites": [
          { "id": "tmf620/catalogmgt", "note": "Requires a ProductOfferingRef — query tmf620/catalogmgt to find available 5G plans." },
          { "id": "tmf632/partymgt", "note": "Requires a RelatedPartyRef — query tmf632/partymgt to get the customer party ID." }
        ]
      },
      {
        "id": "tmf620/catalogmgt",
        "url": "http://localhost:7701",
        "cli": "/cli/tmf620/catalogmgt",
        "mcp": "http://localhost:7701/mcp",
        "confidence": 0.78,
        "reason": "Use to find available 5G offerings and their IDs before placing an order.",
        "prerequisites": []
      }
    ],
    "resolved_by": "opencode"
  }
}
```

**No matches response** (OpenCode found nothing, stays light):

```json
{
  "status": "ok",
  "command": "resolve",
  "result": {
    "query": "something very weird",
    "matches": [],
    "note": "No matches found. Use 'list' to see all services, or try a different query.",
    "resolved_by": "opencode"
  }
}
```

Note: The `note` field provides guidance when no matches are found. The response is kept **light and efficient**—never includes the full registry when using the LLM path, even if `include_raw=true`.

**Fallback response** (OpenCode unavailable):

The fallback is a degraded, temporary mode — keyword scoring only, no LLM reasoning. Check `resolved_by` before relying on `prerequisites`:

```json
{
  "status": "ok",
  "command": "resolve",
  "result": {
    "query": "I need to manage product orders",
    "matches": [
      {
        "id": "tmf622/ordermgt",
        "url": "http://localhost:7702",
        "cli": "/cli/tmf622/ordermgt",
        "handles": "product orders, order lifecycle",
        "use_when": "agent needs to place, track, or cancel orders",
        "owner": "order-team",
        "tags": ["order", "fulfillment", "tmf622"],
        "score": 4.5
      }
    ],
    "total_services": 5,
    "returned": 1,
    "resolved_by": "fallback"
  }
}
```

**Shape contract gated on `resolved_by`:**

| Field | `resolved_by: opencode` | `resolved_by: fallback` |
| --- | --- | --- |
| `matches[].confidence` | float 0–1 | absent (`score` instead) |
| `matches[].reason` | present | absent |
| `matches[].prerequisites` | populated by LLM | **absent** |
| `total_services` / `returned` | absent | present |

`prerequisites` is only present on `resolved_by: opencode` responses. It is not synthesized in the fallback — dependency notes require LLM reasoning. Clients must guard on `resolved_by` before accessing it.

**With full registry** (fallback + `include_raw=true`):

If you want the full registry markdown for the calling agent to reason over, pass `include_raw=true` — but this only works with the fallback (keyword scoring), not the LLM path:

```json
{
  "status": "ok",
  "command": "resolve",
  "result": {
    "query": "manage orders",
    "matches": [ /* keyword-scored matches */ ],
    "total_services": 5,
    "returned": 1,
    "registry_content": "# Service Registry\n\n## tmf620/catalogmgt\n...",
    "instruction": "You are a service registry resolver...",
    "resolved_by": "fallback"
  }
}
```

Note: `include_raw` is ignored when opencode serve is available. The LLM path always returns **compact matches only** to minimize token usage in the calling agent.

**Architecture:**

1. Registry server receives the query
2. It calls opencode serve (`POST /session/:id/message`) with a system prompt: "return ONLY a JSON object with matches"
3. Registry parses the LLM response and extracts the matches
4. Returns structured matches to the client

**Graceful degradation:** If OpenCode is unreachable, the registry falls back to Option A behavior (returns raw dump). This ensures resolve always returns *something* useful.

### register

Add a new service or update an existing one. The service entry is written to `registry_agent/data/registry.md`.

```bash
curl -s -X POST http://localhost:7700/cli/registry \
  -H "Content-Type: application/json" \
  -d '{
    "command": "register",
    "args": {
      "body": {
        "id": "tmf622/ordermgt",
        "url": "http://localhost:7702",
        "cli": "/cli/tmf622/ordermgt",
        "mcp": "http://localhost:7702/mcp",
        "handles": "product orders, order items, order lifecycle, cancellations, returns",
        "use_when": "agent needs to place, track, modify, or cancel orders",
        "owner": "order-team",
        "tags": ["order", "fulfillment", "tmf622"]
      }
    }
  }'
```

If a service with the same ID already exists, it is replaced.

### unregister

Remove a service by ID.

```bash
curl -s -X POST http://localhost:7700/cli/registry \
  -H "Content-Type: application/json" \
  -d '{"command":"unregister","args":{"service_id":"tmf622/ordermgt"}}'
```

---

---

## Configuration

### Environment Variables

- `OPENCODE_URL` — URL to opencode serve for LLM-powered resolve
  - Default: `http://127.0.0.1:4096`
  - In compose: `http://opencode:4096`
  - Example: `OPENCODE_URL=http://opencode.internal:4096 uv run registry-server`

### Startup Behavior

When `registry-server` starts, it logs:
- Registry file location
- Health check endpoint
- HTTP CLI API endpoint
- opencode URL (for LLM-powered resolve)

If OpenCode is unreachable at startup, the registry still starts — resolve will just use the fallback (raw dump).

---

## OpenCode Chat Agent

The registry also ships as an OpenCode agent at `.opencode/agents/agent/service-registry.md`. This is the **human chat interface** — it runs inside `opencode serve` and reads `registry_agent/data/registry.md` directly, with no dependency on the registry server.

### What it does

The agent has access to `bash`, `read`, `write`, `grep`, `glob`, and `webfetch`. In a single conversation it can:

1. **Read `registry_agent/data/registry.md`** to find services matching the user's intent
2. **Explore a service** by curling its CLI API for the command catalog
3. **Invoke commands** on the discovered service
4. **Chain operations** across multiple services in one turn

### Example conversation

```text
User: "I need to work with product catalogs"

Agent: reads registry_agent/data/registry.md, finds tmf620/catalogmgt
       → "Found the catalog service at localhost:7701. It handles
          product catalogs, specifications, offerings, and pricing."

User: "What commands does it have?"

Agent: curl -s http://localhost:7701/cli/tmf620/catalogmgt
       → shows command catalog (catalog, offering, specification, etc.)

User: "List the first 3 offerings"

Agent: curl -s -X POST http://localhost:7701/cli/tmf620/catalogmgt \
         -H "Content-Type: application/json" \
         -d '{"command":"offering list","args":{"limit":3}}'
       → shows the offerings
```

### When to use which interface

| Path          | Interface            | Use when |
|---------------|----------------------|----------|
| Human in chat | OpenCode agent/skill | Conversational discovery, ad-hoc queries, chaining |
| CI/CD, scripts | Registry server HTTP | Automation, health checks, bulk operations, self-registration |

Both read and write the same `registry_agent/data/registry.md` file.

---

## Agent Interaction Flow

```text
Agent                          Registry                     Target Service
  |                               |                               |
  |  resolve("manage orders")     |                               |
  |------------------------------>|                               |
  |  full registry + instruction  |                               |
  |<------------------------------|                               |
  |                               |                               |
  |  (LLM picks tmf622/ordermgt)  |                               |
  |                               |                               |
  |  GET /cli/tmf622/ordermgt     |                               |
  |---------------------------------------------->                |
  |  command catalog              |                               |
  |<----------------------------------------------|               |
  |                               |                               |
  |  POST /cli/tmf622/ordermgt    |                               |
  |  {"command":"order list"}     |                               |
  |---------------------------------------------->                |
  |  order results                |                               |
  |<----------------------------------------------|               |
```

The registry is a one-hop lookup. After resolution, the agent talks directly to the target service.

---

## Self-Registration

Services can register themselves on startup by calling the `register` command or `registry_register` MCP tool. A typical pattern:

1. Service starts and binds to its port
2. Service calls `POST /cli/registry {"command":"register","args":{"body":{...}}}`
3. Registry appends the entry to `registry_agent/data/registry.md`
4. Other agents can now discover this service via `resolve`

For environments where services cannot self-register, add entries to `registry_agent/data/registry.md` by hand or through CI/CD.

---

## Local URLs

| Service | URL |
|---------|-----|
| Registry server | `http://localhost:7700` |
| Registry CLI API | `http://localhost:7700/cli/registry` |
| Registry MCP | `http://localhost:7700/mcp` |
| Registry health | `http://localhost:7700/health` |

---

## Files

| File | Role |
|------|------|
| `registry_agent/data/registry.md` | Service data — the single source of truth |
| `registry_agent/server.py` | FastAPI + MCP server (machine-to-machine) |
| `.opencode/agents/agent/service-registry.md` | OpenCode chat agent (human interface) |
| `opencode.json` | OpenCode MCP client configuration |
