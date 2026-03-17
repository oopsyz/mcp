# TMF620 Quick Start

## Prerequisites

Install `uv` or ensure Python 3.10+ is available:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv
```

`uv` will create a local `.venv/` automatically when you run `uv sync`.

## Start The Mock API

```bash
uv sync
uv run tmf620-mock-server
```

The default TMF620 API base URL is `http://localhost:8801/tmf-api/productCatalogManagement/v4`.

## Use The CLI

The CLI talks directly to the configured TMF620 API URL. With the default `config.json`, that means it talks directly to the mock server running on port `8801`.

```bash
# Check API health
uv run tmf620 health

# Discover command surface as JSON
uv run tmf620 discover

# List catalogs
uv run tmf620 catalog list

# Get one catalog
uv run tmf620 catalog get cat-001

# List offerings for a catalog
uv run tmf620 offering list --catalog-id cat-001

# Create an offering
uv run tmf620 offering create --name "Premium Ethernet" --description "Managed enterprise access" --catalog-id cat-001
```

## Start The MCP Server

If you need MCP-native agent integration, run the server separately:

```bash
uv run tmf620-mcp-server
```

The MCP server will be available at `http://localhost:7701`, with health at `http://localhost:7701/health`.

This is a separate adapter. The CLI does not go through the MCP server.

## Configuration

Both the CLI and MCP server read `config.json` by default:

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

You can override the config path with `TMF620_CONFIG_PATH` or `tmf620 --config path/to/config.json ...`.

## Notes

- The CLI talks directly to the TMF620 API.
- The CLI supports both `--help` and `tmf620 discover` for agent discovery.
- The MCP server is now a thin adapter over the same shared client logic.
- The MCP adapter in this repo exposes 9 tools.
- If the API is not running at the configured URL, both the CLI and MCP server will fail.
