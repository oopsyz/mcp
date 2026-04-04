# TMF620 CLI vs MCP

This repo exposes the TMF620 command layer through two interfaces:

- a compact HTTP CLI API for progressive discovery
- an MCP server used here as a reference surface for benchmarking and testing

It also includes an agent-facing service registry for federated discovery across
multiple CLI services in the same style. This is not a conventional backend
registry with a database or matching engine; it is designed to resolve natural-
language requests when the client does not know the exact service name.

Documentation index: [docs/README.md](docs/README.md)

Repository layout:

- `tmf620/` - TMF620 mock API, shared client, commands, server, and benchmark
- `registry_agent/` - agent-facing registry core and HTTP CLI server
- `tests/` - pytest-discoverable wrappers plus standalone conformance, API, registry, and edge-case scripts
- `docs/` - long-form protocol docs and guides
- `benchmarks/` - benchmark scripts and baseline data
- `scripts/` - repo entrypoint scripts
- `specs/` - source OpenAPI and protocol specs
- `tmf620/config/` - TMF620 runtime configuration files
- `registry_agent/data/` - canonical registry data
- `DOMAIN.md` / `AGENTS.md` - repo-level contracts and agent instructions
- `registry_agent/data/registry.md` / `tmf620/config/config.json` - canonical runtime data and configuration

The TMF620 sample implementation and the registry service are kept in separate
service-local folders so they can be deployed to different servers without
sharing runtime assets.

The CLI API is the cheaper discovery path for agents that only need one command branch at a time. The MCP server is retained here as a comparison point for discovery payloads, tool-list size, and latency measurements.

The practical reasons to keep both are:

- compact discovery: agents can start with `GET /cli/tmf620/catalogmgt` instead of ingesting the full MCP tool list up front
- progressive help: agents can expand one command branch at a time with `help`
- stronger MCP contracts: MCP tools now expose explicit schemas instead of a generic `args` object
- simpler automation: `curl` works well for both humans and agents, especially when the command surface is already structured
- one shared command layer: the same command definitions back the HTTP CLI API, the MCP reference surface, and the benchmark

The current token benchmark numbers are:

- MCP tool surface: `38` tools
- raw MCP discovery payload: `7,143` tokens
- OpenAI-wrapped MCP tool payload: `6,535` tokens

Shared CLI discovery numbers:

- compact `GET /cli/tmf620/catalogmgt`: `254` tokens
- compact group help: `125` tokens
- leaf help: `245` tokens
- compact catalog + group help: `379` tokens
- compact catalog + group help + leaf help: `624` tokens

That matters because many agent runtimes resend the tool list on each model call or session turn. In that common pattern, a large MCP tool surface becomes repeated context cost. Compact CLI discovery avoids paying for every tool up front and instead expands only the branch the agent needs.

This repo is not claiming a universal MCP tool-count limit. The point is more pragmatic: once you have a few dozen tools, full-tool discovery becomes expensive enough that progressive CLI discovery is easier to justify and easier to benchmark.

TMF620 Product Catalog Management with three layers:

- a mock TMF620 API
- a shared Python client
- two adapters over that client: HTTP CLI API and MCP

This keeps the operational logic in one place while supporting HTTP and MCP adapters over the same TMF620 command set.

Request paths:

- HTTP CLI API -> `tmf620/server.py` -> `tmf620/commands.py` -> `tmf620/core.py` -> TMF620 API
- MCP client -> `tmf620/server.py` -> `tmf620/core.py` -> TMF620 API

## Components

### 1. Mock TMF620 API

File: `tmf620/mock_api.py`

- FastAPI-based TMF620 mock server
- sample catalogs, offerings, and specifications
- Swagger docs

### 2. Shared TMF620 Client

File: `tmf620/core.py`

- config loading
- HTTP request handling
- health checks
- generic CRUD helpers for TMF620 resources
- catalog, category, offering, price, specification, import/export job, and hub operations

### 3. Shared Command Layer

File: `tmf620/commands.py`

- canonical TMF620 command registry
- machine-readable discover/help payloads
- structured command invocation shared by shell and HTTP adapters

### 4. MCP + HTTP CLI Adapter

File: `tmf620/server.py`

- FastAPI + the official MCP SDK (`FastMCP`)
- exposes `/cli/tmf620/catalogmgt` as the primary HTTP CLI endpoint
- keeps `/cli` and `/api/cli` as compatibility aliases
- exposes explicit MCP tools for benchmarking and test coverage
- delegates HTTP CLI requests into `tmf620/commands.py`
- delegates MCP tools into the shared command layer

### 5. Registry Agent

Files: `registry_agent/core.py`, `registry_agent/server.py`, `registry_agent/data/registry.md`

- Markdown-backed, agent-facing registry for service discovery
- exposes `/cli/registry` for list, get, resolve, register, unregister, and setstatus
- uses `registry_agent/data/registry.md` as the single source of truth
- `resolve` is LLM-powered via opencode serve (falls back to keyword scoring if unavailable); set `OPENCODE_URL` to point at your opencode instance (default `http://127.0.0.1:4096`)
- resolve response includes `prerequisites` — inter-service dependencies derived from the `Dependencies` field in `registry_agent/data/registry.md` — so agents know what other services to query before calling the matched service
- `setstatus` lets any caller (agent, monitor, operator) mark a service as `live`, `degraded`, or `maintenance`; status is surfaced in both `list` and `resolve`
- pairs with `.opencode/agents/agent/service-registry.md` for natural-language lookup and routing when the target service is not known in advance
- implements the registry pattern described in `docs/SPEC_FEDERATION_EXTENSION.md` section 8.14

Use the registry agent when you need to turn a natural-language intent into the
right service first, then jump to that service's own CLI discovery surface.

## Docker

Use Docker if you want the TMF620 stack and registry service together in one containerized runtime.

```bash
docker compose up --build
```

The container exposes:

- mock API at `http://localhost:8801/tmf-api/productCatalogManagement/v5`
- MCP transport at `http://localhost:7701/mcp`
- HTTP CLI API at `http://localhost:7701/cli/tmf620/catalogmgt`
- registry server at `http://localhost:7700`

The container uses environment overrides rather than rewriting config files. Set them in `docker-compose.yml`, or use a `.env` file with Docker Compose:

- `TMF620_API_URL`

![Quick start](docs/assets/quick_start.png)

## Without Docker

Use this path for local development with `uv`.

### Install dependencies

```bash
uv sync
```

### Start the mock API

```bash
uv run tmf620-mock-server
```

Default API base URL:

```text
http://localhost:8801/tmf-api/productCatalogManagement/v5
```

### Use the HTTP CLI API

```bash
curl http://localhost:7701/cli/tmf620/catalogmgt
curl "http://localhost:7701/cli/tmf620/catalogmgt?verbose=true"
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"catalog list"}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"lifecycle_status":"Active","limit":5}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog get","args":{"catalog_id":"cat-001"}}'
```

### Start the MCP server

```bash
uv run tmf620-mcp-server
```

Default MCP server URL:

```text
http://localhost:7701
```

HTTP CLI API endpoints:

```text
GET  http://localhost:7701/cli/tmf620/catalogmgt
POST http://localhost:7701/cli/tmf620/catalogmgt
```

### Start the registry server

```bash
uv run registry-server
```

Or use the convenience script:

```bash
bash scripts/start-registry.sh
```

To enable LLM-powered resolve, point the registry at a running opencode instance:

```bash
OPENCODE_URL=http://127.0.0.1:4096 uv run registry-server
```

Default registry URLs:

```text
http://localhost:7700
http://localhost:7700/cli/registry
```

Registry data lives in `registry_agent/data/registry.md`. The registry agent is useful when a client
only has a description like "manage product orders" and needs the correct service
before calling that service's own CLI API. If opencode is not running, resolve
falls back to keyword scoring automatically.

## Configuration

`tmf620/config/config.json` is used by both the HTTP CLI API and MCP server:

```json
{
  "mcp_server": {
    "host": "localhost",
    "port": 7701,
    "name": "TMF620 Product Catalog API"
  },
  "tmf620_api": {
    "url": "http://localhost:8801/tmf-api/productCatalogManagement/v5"
  }
}
```

Environment variables override file values at runtime:

- `TMF620_API_URL`

You can also override the config path with `TMF620_CONFIG_PATH`.

The registry agent uses `registry_agent/data/registry.md` directly as its runtime source of truth,
so updates from `register`, `unregister`, `setstatus`, or manual edits are all
reflected immediately on the next request.

## HTTP CLI Commands

```bash
# Discovery
curl http://localhost:7701/cli/tmf620/catalogmgt
curl "http://localhost:7701/cli/tmf620/catalogmgt?verbose=true"
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"offering patch"}}'

# Read/list commands
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"category list","args":{"limit":5}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"lifecycle_status":"Active","limit":5}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"offering list","args":{"catalog_id":"cat-001","limit":10,"offset":5}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"price get","args":{"price_id":"pop-001"}}'

# Create/patch commands use JSON bodies because TMF620 resource payloads are wide
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog create","args":{"body":{"name":"Business Catalog","lifecycleStatus":"Active"}}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"offering patch","args":{"offering_id":"po-001","body":{"description":"Updated description"}}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"hub create","args":{"body":{"callback":"https://example.com/hooks/tmf620","query":"eventType=ProductOfferingCreateEvent"}}}'

# Delete commands
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"category delete","args":{"category_id":"category-001"}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"hub delete","args":{"hub_id":"hub-001"}}'
```

## MCP Usage

Example Claude Desktop config:

```json
{
  "mcpServers": {
    "tmf620-mcp": {
      "command": "uv",
      "args": ["run", "tmf620-mcp-server"],
      "cwd": "/path/to/tmf620-mcp-server"
    }
  }
}
```

Available MCP tools:

- `tmf620_health`
- `tmf620_config`
- `tmf620_discover`
- one explicit tool per leaf command in `tmf620/commands.py`

Tool count in this repo's MCP server: `38` total tools.

The HTTP CLI API and MCP server share the same `tmf620/config/config.json` and command layer, but the MCP server is mainly used here to benchmark discovery size, validate tool schemas, and compare latency against the CLI path.

The registry server uses the same CLI-style discovery flow:

- `list`
- `get`
- `resolve`
- `register`
- `unregister`
- `setstatus`

## Agent Discovery

For machine-readable discovery, use:

```bash
curl http://localhost:7701/cli/tmf620/catalogmgt
curl "http://localhost:7701/cli/tmf620/catalogmgt?verbose=true"
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"offering patch"}}'
```

`GET /cli/tmf620/catalogmgt` now returns the compact catalog by default. Use `verbose=true` only when you actually need the richer top-level payload. Per-command help remains the preferred way to expand one branch at a time.
Group-level help is also compact by default. Leaf-command help returns the detailed argument schema.

## HTTP CLI API

The repo also exposes the CLI-style HTTP API pattern described in `docs/CLI_API_PATTERN.md`.

For agents, this is the canonical machine-facing command surface.

Discovery:

```bash
curl http://localhost:7701/cli/tmf620/catalogmgt
```

Verbose discovery:

```bash
curl "http://localhost:7701/cli/tmf620/catalogmgt?verbose=true"
```

Per-command help:

```bash
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"offering"}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"catalog list"}}'
```

Verbose catalog via `help`:

```bash
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"verbose":true}}'
```

Verbose group help:

```bash
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"offering","verbose":true}}'
```

Invoke:

```bash
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"limit":1}}'
```

Stream:

```bash
curl -N -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"limit":1},"stream":true}'
```

## Python Usage

```python
from tmf620.core import TMF620Client

client = TMF620Client()
catalogs = client.list_catalogs(limit=5)
offerings = client.list_product_offerings(catalog_id="cat-001", limit=10)
```

Import `TMF620Client` from `tmf620.core` directly for Python usage.

## Testing

```bash
# Mock API
curl http://localhost:8801/tmf-api/productCatalogManagement/v5/productCatalog

# HTTP CLI API
curl http://localhost:7701/cli/tmf620/catalogmgt
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt -H "Content-Type: application/json" -d '{"command":"catalog list","args":{}}'

# MCP server
curl http://localhost:7701/health

# Registry server
curl http://localhost:7700/health
curl -X POST http://localhost:7700/cli/registry -H "Content-Type: application/json" -d '{"command":"list"}'

# Standalone scripts
python tests/conformance_test.py
python tests/test_cli_api.py
python tests/test_registry.py
python tests/edge_test.py
pytest tests/test_suite.py
```

## Token Benchmark

Use the built-in benchmark to measure the live MCP tool payload alongside the compact HTTP CLI discovery flow:

```bash
uv run tmf620-benchmark token
uv run tmf620-benchmark token --output json
```

The token benchmark fetches the MCP tool list from the running server, so the stack must be up before you run it:

Start the stack first:

- `docker compose up --build`
- or `uv run tmf620-mcp-server`

It measures:

- compact `GET /cli/tmf620/catalogmgt` catalog
- compact group help and leaf help from `tmf620/commands.py`
- raw MCP tool objects from the live MCP server
- OpenAI-style wrapped MCP tool payloads of the form `{"type":"function","function":{...}}`

This makes it easy to reproduce the context-size comparison locally after future changes.

## Latency Benchmark

Use the latency benchmark when you want request-to-answer timing, not just invoke-only timing:

```bash
uv run tmf620-benchmark latency 30 --warmup 1
```

This benchmark measures the end-user path:

- CLI: `GET /cli/tmf620/catalogmgt`, `help`, then command invoke
- MCP: `list_tools`, then `tools/call`

Use `--cold-start` when you want a fresh MCP connection per iteration:

```bash
uv run tmf620-benchmark latency 30 --warmup 1 --cold-start
```

That mode includes MCP `initialize`, `list_tools`, and `tools/call` in the timed span.

Latest 30-iteration run:

| Mode | CLI | MCP |
| --- | ---: | ---: |
| Invoke-only | about `45ms` to `49ms` | about `53ms` to `56ms` |
| End-to-end | about `105ms` to `162ms` | about `107ms` to `117ms` |
| Cold-start | about `100ms` to `168ms` | about `453ms` to `483ms` |

Takeaways:

- invoke-only timing is the raw command execution path
- end-to-end timing includes CLI discovery and MCP tool lookup
- cold-start timing includes MCP `initialize`, `list_tools`, and `tools/call`

## Packaging

Console scripts exposed by `pyproject.toml`:

- `tmf620-mock-server`
- `tmf620-mcp-server`
- `tmf620-benchmark`
- `registry-server`
- `registry-cli`
