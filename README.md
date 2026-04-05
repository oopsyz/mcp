# TMF620 CLI vs MCP

This repo exposes the TMF620 command layer through two interfaces:

- a compact HTTP CLI API for progressive discovery
- an MCP server used here as a reference surface for benchmarking and testing

Documentation index: [docs/README.md](docs/README.md)

Repository layout:

- `tmf620/` - TMF620 mock API, shared client, commands, server, and benchmark
- `tests/` - pytest-discoverable wrappers plus standalone conformance, API, and edge-case scripts
- `docs/` - long-form protocol docs and guides
- `benchmarks/` - benchmark scripts and baseline data
- `scripts/` - repo entrypoint scripts
- `specs/` - source OpenAPI and protocol specs
- `tmf620/config/` - TMF620 runtime configuration files
- `DOMAIN.md` / `AGENTS.md` - repo-level contracts and agent instructions
- `tmf620/config/config.json` - canonical runtime data and configuration

The TMF620 sample implementation is kept in a service-local folder so it can be deployed independently of other systems.

The CLI API is the cheaper discovery path for agents that only need one command branch at a time. The MCP server is retained here as a comparison point for discovery payloads, tool-list size, and latency measurements.

The practical reasons to keep both are:

- compact discovery: agents can start with `GET /cli/tmf620/catalogmgt` instead of ingesting the full MCP tool list up front
- progressive help: agents can expand one command branch at a time with `help`
- stronger MCP contracts: MCP tools now expose explicit schemas instead of a generic `args` object
- simpler automation: `curl` works well for both humans and agents, especially when the command surface is already structured
- one shared command layer: the same command definitions back the HTTP CLI API, the MCP reference surface, and the benchmark

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

Use the TMF620 compose file for the mock API + MCP server.

```bash
docker compose -f docker-compose.yml up --build
```

TMF620 stack exposes:

- mock API at `http://localhost:8801/tmf-api/productCatalogManagement/v5`
- MCP transport at `http://localhost:7701/mcp`
- HTTP CLI API at `http://localhost:7701/cli/tmf620/catalogmgt`

The containers use environment overrides rather than rewriting config files. Set them in the matching compose file, or use a `.env` file with Docker Compose:

- `TMF620_API_URL`

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

### Use the HTTP CLI API

```bash
curl http://localhost:7701/cli/tmf620/catalogmgt
curl "http://localhost:7701/cli/tmf620/catalogmgt?verbose=true"
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"offering patch"}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"lifecycle_status":"Active","limit":5}}'
```

### Start the MCP server

```bash
uv run tmf620-mcp-server
```

Default MCP server URL:

```text
http://localhost:7701
```

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

## HTTP CLI Commands

```bash
# Discovery
curl http://localhost:7701/cli/tmf620/catalogmgt
curl "http://localhost:7701/cli/tmf620/catalogmgt?verbose=true"
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"offering"}}'

# Read/list commands
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"limit":5}}'
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"lifecycle_status":"Active","limit":5}}'

# Create/patch commands use JSON bodies because TMF620 resource payloads are wide
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog create","args":{"body":{"name":"Business Catalog","lifecycleStatus":"Active"}}}'
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

## Testing

```bash
# Mock API
curl http://localhost:8801/tmf-api/productCatalogManagement/v5/productCatalog

# HTTP CLI API
curl http://localhost:7701/cli/tmf620/catalogmgt
curl -X POST http://localhost:7701/cli/tmf620/catalogmgt -H "Content-Type: application/json" -d '{"command":"catalog list","args":{}}'

# MCP server
curl http://localhost:7701/health

# Pytest suite
pytest tests
```

## Token Benchmark

Use the built-in benchmark to measure the live MCP tool payload alongside the compact HTTP CLI discovery flow:

```bash
uv run tmf620-benchmark token
uv run tmf620-benchmark token --output json
```

## Latency Benchmark

Use the latency benchmark when you want request-to-answer timing, not just invoke-only timing:

```bash
uv run tmf620-benchmark latency 30 --warmup 1
```

## Packaging

Console scripts exposed by `pyproject.toml`:

- `tmf620-mock-server`
- `tmf620-mcp-server`
- `tmf620-benchmark`
