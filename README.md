# TMF620 CLI + MCP Server

TMF620 Product Catalog Management with three layers:

- a mock TMF620 API
- a shared Python client
- two adapters over that client: CLI and MCP

This keeps the operational logic in one place while supporting both shell-first workflows and MCP-native AI agents.

Request paths:

- CLI -> `tmf620_core.py` -> TMF620 API
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
- catalog, offering, and specification operations

### 3. CLI Adapter

File: `tmf620_cli.py`

- direct shell interface for humans, scripts, CI, and CLI-native agents
- exposed as the `tmf620` console script
- talks directly to the configured TMF620 API URL

### 4. MCP Adapter

File: `tmf620_mcp_server.py`

- FastAPI + `fastapi-mcp`
- exposes the same operations as MCP tools for MCP-capable agents
- delegates into `tmf620_core.py`

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
http://localhost:8801/tmf-api/productCatalogManagement/v4
```

### Use the CLI

```bash
uv run tmf620 health
uv run tmf620 discover
uv run tmf620 catalog list
uv run tmf620 catalog get cat-001
uv run tmf620 offering list --catalog-id cat-001
uv run tmf620 specification list
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

`config.json` is used by both the CLI and MCP server:

```json
{
  "mcp_server": {
    "host": "localhost",
    "port": 7701,
    "name": "TMF620 Product Catalog API"
  },
  "tmf620_api": {
    "url": "http://localhost:8801/tmf-api/productCatalogManagement/v4"
  }
}
```

You can also override the config path with `TMF620_CONFIG_PATH`.

## CLI Commands

```bash
# Health and config
uv run tmf620 health
uv run tmf620 config
uv run tmf620 discover

# Catalogs
uv run tmf620 catalog list
uv run tmf620 catalog get cat-001

# Product offerings
uv run tmf620 offering list --catalog-id cat-001
uv run tmf620 offering get po-001
uv run tmf620 offering create --name "Premium Ethernet" --description "Managed enterprise access" --catalog-id cat-001

# Product specifications
uv run tmf620 specification list
uv run tmf620 specification get ps-001
uv run tmf620 specification create --name "Broadband Gold" --description "Gold tier broadband spec" --version 2.0
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

The CLI is not routed through the MCP server. By default it talks directly to the mock API because `config.json` points `tmf620_api.url` at `http://localhost:8801/tmf-api/productCatalogManagement/v4`.

## Agent Discovery

For machine-readable CLI discovery, use:

```bash
uv run tmf620 discover
```

This returns the full command tree, arguments, and examples as JSON so an LLM or agent runtime does not need to scrape `--help` output.

## Python Helper Usage

```python
from tmf620_client import get_catalogs, get_product_offerings

catalogs = get_catalogs()
offerings = get_product_offerings("cat-001")
```

## Testing

```bash
# Mock API
curl http://localhost:8801/tmf-api/productCatalogManagement/v4/catalog

# CLI
uv run tmf620 health
uv run tmf620 catalog list

# MCP server
curl http://localhost:7701/health
```

## Packaging

Console scripts exposed by `pyproject.toml`:

- `tmf620-mock-server`
- `tmf620-mcp-server`
- `tmf620`
