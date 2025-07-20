# TMF620 MCP Server - Quick Start

## Prerequisites

Install `uv` (recommended) or ensure Python 3.8+ is available:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv
```

**Note**: `uv` will automatically create a `.venv/` directory in your project folder to isolate dependencies.

## Start MCP Server Only

### Option 1: Console Script (Recommended)

```bash
# Install dependencies and start MCP server
uv sync && uv run tmf620-mcp-server
```

### Option 2: Direct File Execution

```bash
uv run python tmf620_mcp_server.py
```

### Option 3: Traditional Python

```bash
pip install -r requirements.txt
python tmf620_mcp_server.py
```

## Verify MCP Server is Running

The MCP server will be available at: **http://localhost:7701**

```bash
# Test connection
curl http://localhost:7701/health
```

## Configuration

The MCP server reads from `config.json`:

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

## Important Notes

⚠️ **The MCP server expects a TMF620 API to be running at the configured URL**

- Default: `http://localhost:8801/tmf-api/productCatalogManagement/v4`
- If you need the mock API too, start it separately: `uv run tmf620-mock-server`
- Update `config.json` to point to your actual TMF620 API endpoint

## Available MCP Tools

Once running, the MCP server exposes these tools:

- `list_catalogs` - List all product catalogs
- `get_catalog` - Get specific catalog by ID
- `list_product_offerings` - List product offerings
- `get_product_offering` - Get specific product offering
- `list_product_specifications` - List product specifications
- `get_product_specification` - Get specific product specification
- `create_product_offering` - Create new product offering
- `create_product_specification` - Create new product specification
- `health` - Check server health

## Troubleshooting

**Connection refused?**
- Check if port 7701 is available
- Verify config.json has correct settings

**API connection errors?**
- Ensure TMF620 API is running at configured URL
- Check `tmf620_api.url` in config.json

**Need the mock API too?**
- Start both: `uv run tmf620-mock-server` + `uv run tmf620-mcp-server` (two terminals)
- Or see `README.md` for complete setup