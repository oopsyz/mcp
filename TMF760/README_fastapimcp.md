# Ultra-Simplified TMF760 MCP HTTP Server

This is an ultra-simplified implementation of the TMF760 MCP HTTP Server using the `FastApiMCP` class from the `fastapi-mcp` library.

## Features

- **Automatic MCP Tool Generation**: Automatically exposes FastAPI endpoints as MCP tools
- **RESTful API**: Provides a clean RESTful API for direct HTTP access
- **MCP Protocol Support**: Implements the MCP protocol for AI agent integration
- **Minimal Code**: Significantly less code than manual MCP implementation
- **Type Safety**: Uses FastAPI's type annotations and validation

## How It Works

This implementation:

1. Defines standard FastAPI endpoints with proper type annotations
2. Uses `FastApiMCP` to automatically expose these endpoints as MCP tools
3. Prefixes all tool names with "tmf760_" for consistency

## Installation

```bash
pip install -r mcp_requirements_simplified.txt
```

## Running the Server

```bash
python run_mcp_server_fastapimcp.py
```

Or with custom settings:

```bash
python run_mcp_server_fastapimcp.py --host 0.0.0.0 --port 8761 --tmf760-url http://localhost:8760
```

## Available Endpoints

### REST API Endpoints

- `GET /api/health` - Check API health
- `GET /api/check-configurations` - List check configurations
- `POST /api/check-configurations` - Create check configuration
- `GET /api/check-configurations/{id}` - Get check configuration
- `GET /api/query-configurations` - List query configurations
- `POST /api/query-configurations` - Create query configuration
- `GET /api/query-configurations/{id}` - Get query configuration
- `POST /api/hub` - Create event subscription
- `DELETE /api/hub/{id}` - Delete event subscription

### MCP Tools (automatically generated)

- `tmf760_health_check` - Check API health
- `tmf760_list_check_configurations` - List check configurations
- `tmf760_create_check_configuration` - Create check configuration
- `tmf760_get_check_configuration` - Get check configuration
- `tmf760_list_query_configurations` - List query configurations
- `tmf760_create_query_configuration` - Create query configuration
- `tmf760_get_query_configuration` - Get query configuration
- `tmf760_create_hub` - Create event subscription
- `tmf760_delete_hub` - Delete event subscription

## MCP Client Configuration

Add the following to your MCP client configuration (e.g., `.kiro/settings/mcp.json`):

```json
{
  "mcpServers": {
    "tmf760-product-configuration": {
      "command": "python",
      "args": ["TMF760/tmf760_mcp_http_server_fastapimcp.py"],
      "env": {
        "TMF760_BASE_URL": "http://localhost:8760"
      },
      "disabled": false,
      "autoApprove": [
        "tmf760_health_check",
        "tmf760_list_check_configurations",
        "tmf760_list_query_configurations"
      ]
    }
  }
}
```

## Advantages Over Previous Implementations

1. **Less Code**: Significantly less code than manual MCP implementation
2. **Automatic Schema Generation**: Schemas are generated from FastAPI type annotations
3. **Dual Access**: Both REST API and MCP tools from the same endpoints
4. **Better Documentation**: FastAPI generates comprehensive API documentation
5. **Type Safety**: Full type checking and validation