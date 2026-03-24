# TMF620 CLI + MCP Server

We added the `TMF620` CLI to better support AI agents, especially in shell-first workflows where direct command execution is simpler than MCP integration alone.

TMF620 Product Catalog Management with three layers:

- a mock TMF620 API
- a shared Python client
- two adapters over that client: HTTP CLI API and MCP

This keeps the operational logic in one place while supporting HTTP and MCP adapters over the same TMF620 command set.

Request paths:

- HTTP CLI API -> `tmf620_mcp_server.py` -> `tmf620_commands.py` -> `tmf620_core.py` -> TMF620 API
- MCP client -> `tmf620_mcp_server.py` -> `tmf620_core.py` -> TMF620 API

## Components

### 1. Mock TMF620 API

File: `mock_tmf620_api_fastapi.py`

- FastAPI-based TMF620 mock server
- sample catalogs, offerings, and specifications
- Swagger docs and optional MCP exposure

### 2. Shared TMF620 Client

File: `tmf620_core.py`

- config loading
- HTTP request handling
- health checks
- generic CRUD helpers for TMF620 resources
- catalog, category, offering, price, specification, import/export job, and hub operations

### 3. Shared Command Layer

File: `tmf620_commands.py`

- canonical TMF620 command registry
- machine-readable discover/help payloads
- structured command invocation shared by shell and HTTP adapters

### 4. MCP + HTTP CLI Adapter

File: `tmf620_mcp_server.py`

- FastAPI + `fastapi-mcp`
- exposes `/api/cli` for the HTTP CLI API pattern
- exposes the same operations as MCP tools for MCP-capable agents
- delegates HTTP CLI requests into `tmf620_commands.py`
- delegates MCP tools into `tmf620_core.py`

## Quick Start

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
curl http://localhost:7701/api/cli
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"catalog list"}}'
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"lifecycle_status":"Active","limit":5}}'
curl -X POST http://localhost:7701/api/cli \
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
GET  http://localhost:7701/api/cli
POST http://localhost:7701/api/cli
```

## Configuration

`config.json` is used by both the HTTP CLI API and MCP server:

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

You can also override the config path with `TMF620_CONFIG_PATH`.

## HTTP CLI Commands

```bash
# Discovery
curl http://localhost:7701/api/cli
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"offering patch"}}'

# Read/list commands
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"category list","args":{"limit":5}}'
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"lifecycle_status":"Active","limit":5}}'
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"offering list","args":{"catalog_id":"cat-001","limit":10,"offset":5}}'
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"price get","args":{"price_id":"pop-001"}}'

# Create/patch commands use JSON bodies because TMF620 resource payloads are wide
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog create","args":{"body":{"name":"Business Catalog","lifecycleStatus":"Active"}}}'
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"offering patch","args":{"offering_id":"po-001","body":{"description":"Updated description"}}}'
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"hub create","args":{"body":{"callback":"https://example.com/hooks/tmf620","query":"eventType=ProductOfferingCreateEvent"}}}'

# Delete commands
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"category delete","args":{"category_id":"category-001"}}'
curl -X POST http://localhost:7701/api/cli \
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

- `list_catalogs`
- `get_catalog`
- `list_product_offerings`
- `get_product_offering`
- `create_product_offering`
- `list_product_specifications`
- `get_product_specification`
- `create_product_specification`
- `health`

Tool count in this repo's MCP adapter: `9`

The HTTP CLI API is routed through the MCP server. It uses the same `config.json` and shared command layer as the rest of the repo.

## Agent Discovery

For machine-readable discovery, use:

```bash
curl http://localhost:7701/api/cli
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"offering patch"}}'
```

This returns the command catalog, or one command's detailed schema, as JSON so an LLM or agent runtime does not need to scrape human help output.

## HTTP CLI API

The repo also exposes the CLI-style HTTP API pattern described in `CLI_API_PATTERN.md`.

For agents, this is the canonical machine-facing command surface.

Discovery:

```bash
curl http://localhost:7701/api/cli
```

Per-command help:

```bash
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"catalog list"}}'
```

Invoke:

```bash
curl -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"limit":1}}'
```

Stream:

```bash
curl -N -X POST http://localhost:7701/api/cli \
  -H "Content-Type: application/json" \
  -d '{"command":"catalog list","args":{"limit":1},"stream":true}'
```

## Python Usage

```python
from tmf620_core import TMF620Client

client = TMF620Client()
catalogs = client.list_catalogs(limit=5)
offerings = client.list_product_offerings(catalog_id="cat-001", limit=10)
```

Import `TMF620Client` from `tmf620_core.py` directly for Python usage.

## Testing

```bash
# Mock API
curl http://localhost:8801/tmf-api/productCatalogManagement/v5/productCatalog

# HTTP CLI API
curl http://localhost:7701/api/cli
curl -X POST http://localhost:7701/api/cli -H "Content-Type: application/json" -d '{"command":"catalog list","args":{}}'

# MCP server
curl http://localhost:7701/health
```

## Packaging

Console scripts exposed by `pyproject.toml`:

- `tmf620-mock-server`
- `tmf620-mcp-server`
- `tmf620`
