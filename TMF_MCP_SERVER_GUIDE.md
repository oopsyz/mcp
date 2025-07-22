# TMF637 MCP Server Guide

This guide explains how to use the TMF637 MCP (Model Context Protocol) server, which allows AI assistants to interact with TMF637 Product Inventory API through the Model Context Protocol.

## Overview

The TMF637 MCP Server wraps the TMF637 mock server functionality and exposes it through a standardized MCP interface. This allows AI assistants to:

1. Query product inventory data
2. Create new products
3. Update existing products
4. Delete products
5. Access TMF API specifications

## Installation

### Prerequisites

- Python 3.8 or higher
- FastAPI
- Uvicorn
- PyYAML
- Pydantic

Install the required packages:

```bash
pip install fastapi uvicorn pydantic pyyaml
```

### Setup

1. Ensure you have the TMF637 OpenAPI specification YAML file in the `TMF637` directory
2. Run the MCP server:

```bash
python tmf637_mcp_server.py
```

By default, the server runs on `http://0.0.0.0:8000`.

## MCP Tools

The TMF637 MCP Server provides the following tools:

### get_available_specs

Returns a list of available TMF API specifications.

**Parameters**: None

**Example**:
```json
{
  "tool_calls": [
    {
      "name": "get_available_specs",
      "parameters": {}
    }
  ]
}
```

### get_product_inventory

Retrieves product inventory items with optional filtering.

**Parameters**:
- `spec_name` (string): Name of the TMF specification to use
- `filter_params` (object, optional): Key-value pairs for filtering products

**Example**:
```json
{
  "tool_calls": [
    {
      "name": "get_product_inventory",
      "parameters": {
        "spec_name": "TMF637-ProductInventory-v5.0.0.oas",
        "filter_params": {
          "status": "active"
        }
      }
    }
  ]
}
```

### get_product_by_id

Retrieves a specific product by ID.

**Parameters**:
- `spec_name` (string): Name of the TMF specification to use
- `product_id` (string): ID of the product to retrieve

**Example**:
```json
{
  "tool_calls": [
    {
      "name": "get_product_by_id",
      "parameters": {
        "spec_name": "TMF637-ProductInventory-v5.0.0.oas",
        "product_id": "product-1"
      }
    }
  ]
}
```

### create_product

Creates a new product in the inventory.

**Parameters**:
- `spec_name` (string): Name of the TMF specification to use
- `product_data` (object): Product data to create

**Example**:
```json
{
  "tool_calls": [
    {
      "name": "create_product",
      "parameters": {
        "spec_name": "TMF637-ProductInventory-v5.0.0.oas",
        "product_data": {
          "name": "5G Mobile Service",
          "description": "High-speed mobile service with unlimited data",
          "status": "active"
        }
      }
    }
  ]
}
```

### update_product

Updates an existing product.

**Parameters**:
- `spec_name` (string): Name of the TMF specification to use
- `product_id` (string): ID of the product to update
- `product_data` (object): Updated product data

**Example**:
```json
{
  "tool_calls": [
    {
      "name": "update_product",
      "parameters": {
        "spec_name": "TMF637-ProductInventory-v5.0.0.oas",
        "product_id": "product-1",
        "product_data": {
          "name": "5G Mobile Service Premium",
          "status": "active"
        }
      }
    }
  ]
}
```

### delete_product

Deletes a product from the inventory.

**Parameters**:
- `spec_name` (string): Name of the TMF specification to use
- `product_id` (string): ID of the product to delete

**Example**:
```json
{
  "tool_calls": [
    {
      "name": "delete_product",
      "parameters": {
        "spec_name": "TMF637-ProductInventory-v5.0.0.oas",
        "product_id": "product-1"
      }
    }
  ]
}
```

## Integrating with Kiro

To use this MCP server with Kiro, add the following configuration to your `.kiro/settings/mcp.json` file:

```json
{
  "mcpServers": {
    "tmf637": {
      "command": "python",
      "args": ["tmf637_mcp_server.py"],
      "env": {
        "PYTHONPATH": "."
      },
      "disabled": false,
      "autoApprove": ["get_available_specs", "get_product_inventory"]
    }
  }
}
```

## Response Format

All MCP responses follow this format:

```json
{
  "tool_responses": [
    {
      "name": "tool_name",
      "content": { /* response data */ },
      "status": "success"
    }
  ]
}
```

In case of an error:

```json
{
  "tool_responses": [
    {
      "name": "tool_name",
      "content": {},
      "status": "error",
      "error": "Error message"
    }
  ]
}
```

## Testing the MCP Server

You can test the MCP server using curl:

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "tool_calls": [
      {
        "name": "get_available_specs",
        "parameters": {}
      }
    ]
  }'
```

## Debug Endpoints

The TMF637 Mock Server includes several debug endpoints to help with troubleshooting and testing:

### View In-Memory Storage

```
GET http://localhost:8637/debug/storage
```

This endpoint shows all the data currently stored in the mock server's memory. Use this to see what products are available for testing.

### View Registered Routes

```
GET http://localhost:8637/debug/routes
```

This endpoint displays all the API routes that are registered in the server. It's useful for verifying that paths are correctly configured.

### Reset Storage to Initial State

```
POST http://localhost:8637/debug/reset
```

This endpoint resets the in-memory storage to its initial state with fresh sample data. Use this if your test data becomes corrupted or you want to start with a clean slate.

### Simulate Error Responses

```
GET http://localhost:8637/debug/error/{status_code}
```

This endpoint simulates specific HTTP error responses. Replace `{status_code}` with the HTTP status code you want to test (e.g., 400, 404, 500). This is useful for testing how your client handles different error scenarios.

## Extending the MCP Server

To add new tools to the MCP server:

1. Implement a new async function in `tmf637_mcp_server.py`
2. Add the function to the `tool_functions` dictionary
3. Restart the server

Example of adding a new tool:

```python
async def search_products(spec_name: str, query: str) -> Dict[str, Any]:
    """Search products by name or description"""
    # Implementation here
    return {"results": []}

# Add to tool_functions
tool_functions["search_products"] = search_products
```