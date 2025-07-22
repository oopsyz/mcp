# TMF637 Product Inventory API MCP Server

This project implements an MCP (Model Context Protocol) server for the TMF637 Product Inventory API, allowing AI agents to interact with product inventory data through structured tools.

## Features

- **TMF637 API Client**: Client for interacting with TMF637 Product Inventory API
- **Mock TMF637 API Server**: Mock implementation of the TMF637 API based on the OpenAPI specification
- **MCP Server**: Exposes TMF637 API operations as MCP tools for AI agents
- **Configurable**: Easily configurable through environment variables or command-line arguments

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the Servers

### Option 1: Run both servers together (recommended)

```bash
python run_both_servers.py
```

This will start both the mock server and the MCP server with default settings.

### Option 2: Run servers separately

Start the mock server:

```bash
python run_mock_server.py
```

Start the MCP server:

```bash
python run_mcp_server.py
```

### Configuration Options

#### Mock Server

```bash
python run_mock_server.py --spec TMF637-ProductInventory-v5.0.0.oas.yaml --host 0.0.0.0 --port 8637 --delay 0
```

- `--spec`: Path to the OpenAPI specification YAML file
- `--host`: Host to bind the server to
- `--port`: Port to bind the server to
- `--delay`: Simulated network delay in seconds

#### MCP Server

```bash
python run_mcp_server.py --host 0.0.0.0 --port 8638 --tmf637-url http://localhost:8637
```

- `--host`: Host to bind the server to
- `--port`: Port to bind the server to
- `--tmf637-url`: URL of the TMF637 API server

## Available MCP Tools

The MCP server exposes the following tools:

- `tmf637_list_products`: List all products
- `tmf637_create_product`: Create a new product
- `tmf637_get_product`: Get a product by ID
- `tmf637_update_product`: Update a product
- `tmf637_patch_product`: Partially update a product
- `tmf637_delete_product`: Delete a product
- `tmf637_create_hub`: Create an event subscription hub
- `tmf637_delete_hub`: Delete an event subscription hub
- `tmf637_health_check`: Check the health status of the TMF637 API server

## MCP Client Configuration

Add the following to your MCP client configuration (e.g., `.kiro/settings/mcp.json`):

```json
{
  "mcpServers": {
    "tmf637-product-inventory": {
      "command": "python",
      "args": ["TMF637/tmf637_mcp_server.py"],
      "env": {
        "TMF637_API_URL": "http://localhost:8637"
      },
      "disabled": false,
      "autoApprove": [
        "tmf637_health_check",
        "tmf637_list_products"
      ]
    }
  }
}
```

## Example Usage

Once the servers are running, AI agents can use the MCP tools like this:

```
"List all products in the inventory"
→ AI calls tmf637_list_products

"Get details for product XYZ"
→ AI calls tmf637_get_product with id=XYZ

"Create a new product"
→ AI calls tmf637_create_product with appropriate parameters
```

## API Documentation

- **Mock Server Documentation**: http://localhost:8637/docs
- **MCP Server Documentation**: http://localhost:8638/docs