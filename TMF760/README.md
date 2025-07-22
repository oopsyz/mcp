# TMF760 Product Configuration API Server

This is a server stub implementation of the TMF760 Product Configuration API based on the OpenAPI specification.

## Features

- **CheckProductConfiguration** endpoints for validating product configurations
- **QueryProductConfiguration** endpoints for querying product configurations  
- **Event subscription** (hub) management
- **Notification listeners** for various events
- In-memory storage for demonstration purposes
- Auto-generated OpenAPI documentation

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

### Option 1: Using the run script
```bash
python run_server.py
```

### Option 2: Direct uvicorn command
```bash
uvicorn tmf760_server:app --host 0.0.0.0 --port 8760 --reload
```

The server will start on `http://localhost:8760`

## API Documentation

Once the server is running, you can access:

- **Interactive API Documentation (Swagger UI)**: http://localhost:8760/docs
- **Alternative API Documentation (ReDoc)**: http://localhost:8760/redoc  
- **OpenAPI JSON Specification**: http://localhost:8760/openapi.json

## API Endpoints

### CheckProductConfiguration
- `GET /checkProductConfiguration` - List configurations
- `POST /checkProductConfiguration` - Create new configuration
- `GET /checkProductConfiguration/{id}` - Get configuration by ID

### QueryProductConfiguration  
- `GET /queryProductConfiguration` - List configurations
- `POST /queryProductConfiguration` - Create new configuration
- `GET /queryProductConfiguration/{id}` - Get configuration by ID

### Event Subscription
- `POST /hub` - Create event subscription
- `DELETE /hub/{id}` - Remove event subscription

### Notification Listeners
- Various POST endpoints under `/listener/` for different event types

### Health Check
- `GET /health` - Server health status

## Example Usage

### Create a CheckProductConfiguration
```bash
curl -X POST "http://localhost:8760/checkProductConfiguration" \
  -H "Content-Type: application/json" \
  -d '{
    "instantSync": true,
    "provideAlternatives": false
  }'
```

### List CheckProductConfigurations
```bash
curl "http://localhost:8760/checkProductConfiguration"
```

### Create Event Subscription
```bash
curl -X POST "http://localhost:8760/hub" \
  -H "Content-Type: application/json" \
  -d '{
    "callback": "http://your-callback-url.com/notifications"
  }'
```

## Implementation Notes

This is a **stub implementation** for development and testing purposes:

- Uses in-memory storage (data is lost when server restarts)
- Simplified data models compared to the full TMF760 specification
- Basic validation and error handling
- Event notifications are accepted but not actually sent

For production use, you would need to:

- Implement persistent storage (database)
- Add comprehensive data models matching the full TMF760 spec
- Implement actual business logic for product configuration
- Add authentication and authorization
- Implement real event notification delivery
- Add comprehensive error handling and validation
- Add logging and monitoring

## MCP Server

This package includes both stdio-based and HTTP-based MCP (Model Context Protocol) servers that expose the TMF760 API as tools for use in MCP-compatible applications.

### MCP Server Setup

1. Install MCP dependencies:
```bash
pip install -r mcp_requirements.txt
```

2. Start the TMF760 API server:
```bash
python run_server.py
```

### Option 1: Stdio MCP Server (for MCP clients like Kiro)

3. The stdio MCP server is launched automatically by MCP clients:
```bash
python tmf760_mcp_server.py
```

### Option 2: HTTP MCP Server (for remote access)

3. Start the HTTP MCP server:
```bash
python run_mcp_server.py
```

Or with custom settings:
```bash
python run_mcp_server.py --host 0.0.0.0 --port 8761 --tmf760-url http://localhost:8760
```

The HTTP MCP server will be available at `http://localhost:8761` with these endpoints:
- `GET /` - Server information
- `GET /tools` - List available TMF760 tools  
- `POST /execute` - Execute TMF760 tools
- `GET/POST /mcp` - MCP Protocol endpoint (for MCP clients)
- `GET /.well-known/mcp` - MCP discovery endpoint
- `GET /health` - Health check
- `GET /examples` - Example requests
- `GET /docs` - API documentation (Swagger UI)

### Option 3: OAuth-compatible MCP Server (for MCP clients)

3. Start the OAuth-compatible MCP server:
```bash
python run_mcp_oauth_server.py
```

Or with custom settings:
```bash
python run_mcp_oauth_server.py --host 0.0.0.0 --port 8761 --tmf760-url http://localhost:8760
```

The OAuth-compatible MCP server includes all standard endpoints plus OAuth discovery endpoints:
- `GET /.well-known/oauth-protected-resource/mcp` - MCP OAuth resource metadata
- `GET /.well-known/oauth-protected-resource` - OAuth resource metadata
- `GET /.well-known/oauth-authorization-server/mcp` - MCP OAuth server metadata
- `GET /.well-known/oauth-authorization-server` - OAuth server metadata
- `POST /register` - Client registration endpoint

### MCP Configuration

Add the following to your MCP client configuration (e.g., `.kiro/settings/mcp.json`):

```json
{
  "mcpServers": {
    "tmf760-product-configuration": {
      "command": "python",
      "args": ["tmf760_mcp_server.py"],
      "cwd": "/path/to/TMF760",
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

### Available MCP Tools

- `tmf760_health_check` - Check API server health
- `tmf760_list_check_configurations` - List CheckProductConfiguration objects
- `tmf760_create_check_configuration` - Create new CheckProductConfiguration
- `tmf760_get_check_configuration` - Get CheckProductConfiguration by ID
- `tmf760_list_query_configurations` - List QueryProductConfiguration objects
- `tmf760_create_query_configuration` - Create new QueryProductConfiguration
- `tmf760_get_query_configuration` - Get QueryProductConfiguration by ID
- `tmf760_create_hub` - Create event subscription hub
- `tmf760_delete_hub` - Delete event subscription hub

### Testing MCP Servers

**Test stdio MCP server:**
```bash
python test_mcp_server.py
```

**Test HTTP MCP server:**
```bash
python test_http_mcp.py
```

### Using the HTTP MCP Server

You can call tools directly via HTTP:

```bash
# List available tools
curl http://localhost:8761/tools

# Execute a tool
curl -X POST http://localhost:8761/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "tmf760_health_check",
    "arguments": {}
  }'

# Create a check configuration
curl -X POST http://localhost:8761/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "tmf760_create_check_configuration",
    "arguments": {
      "configuration": {
        "instantSync": true,
        "provideAlternatives": false
      }
    }
  }'
```

### Using the HTTP MCP Server from Python

#### Option 1: Using the `/execute` endpoint

```python
import httpx

async def call_tmf760_tool(tool_name, arguments):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8761/execute",
            json={
                "tool": tool_name,
                "arguments": arguments
            }
        )
        result = response.json()
        if result["success"]:
            return result["data"]
        else:
            raise Exception(f"Tool execution failed: {result.get('error')}")

# Example usage
async def main():
    # Check health
    health = await call_tmf760_tool("tmf760_health_check", {})
    print(f"Health: {health}")
    
    # Create configuration
    config = await call_tmf760_tool(
        "tmf760_create_check_configuration", 
        {
            "configuration": {
                "instantSync": True,
                "provideAlternatives": False
            }
        }
    )
    print(f"Created configuration: {config}")
```

#### Option 2: Using the MCP Protocol endpoint

```python
import httpx
import json

async def call_mcp_tool(tool_name, arguments):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8761/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "callTool",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
        )
        result = response.json()
        if "error" in result:
            raise Exception(f"Tool execution failed: {result['error']['message']}")
        
        # Parse the text content
        content = result["result"]["content"][0]["text"]
        return json.loads(content)

# Example usage with MCP client
from mcp.client.http import http_client

async def use_mcp_client():
    async with http_client("http://localhost:8761") as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {tools}")
        
        # Call a tool
        result = await client.call_tool(
            "tmf760_health_check", 
            {}
        )
        print(f"Health check result: {result}")
```

## TMF760 Specification

This implementation is based on the TMF760 Product Configuration Management API v5.0.0 specification from TM Forum.

The Product Configuration API drives the configuration of new product offerings and modification of existing products for various user engagement channels, using product catalog data, policy data, and existing product inventory data.