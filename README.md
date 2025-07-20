# TMF620 MCP Server

(The last version was a quick prototype. Here's a cleaner implementation)

A modern TMF620 Product Catalog Management system with MCP (Model Context Protocol) support for AI agents, built with Python and `uv` for fast, reliable dependency management.

## 🚀 Features

- **TMF620 Compliant**: Full implementation of TM Forum TMF620 Product Catalog Management API
- **MCP Integration**: Native Model Context Protocol support for AI agents
- **Modern Python**: Built with `uv` for fast dependency resolution and packaging
- **Production Ready**: Docker support, proper configuration management, and deployment tools
- **Developer Friendly**: Hot reload, comprehensive docs, and easy testing

## 🏗️ Architecture

The system consists of two main components:

### 1. **Mock TMF620 API** (`mock_tmf620_api_fastapi.py`)
- FastAPI-based TMF620 compliant API server
- Sample catalog data (catalogs, product offerings, specifications)
- Built-in Swagger documentation and MCP integration
- Configurable features (CORS, docs, MCP)

### 2. **MCP Server** (`tmf620_mcp_server.py`)
- MCP protocol server for AI agent integration
- Connects to TMF620 API (mock or real)
- Provides structured tools for catalog management
- Health monitoring and error handling

## 🔄 Data Flow

```
AI Agent → MCP Server → TMF620 API → Catalog Data
    ↑         ↓           ↓
   Tools   HTTP Calls   JSON Response
```

## ⚡ Quick Start

### Prerequisites

Install `uv` for fast dependency management:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

### Option 1: Using uv (Recommended)

```bash
# Install dependencies
uv sync

# Start both services (two terminals)
uv run tmf620-mock-server    # Terminal 1
uv run tmf620-mcp-server     # Terminal 2
```

### Option 2: Background Processes

```bash
# Windows
start uv run tmf620-mock-server
start uv run tmf620-mcp-server

# Linux/Mac
uv run tmf620-mock-server &
uv run tmf620-mcp-server &
```

### Option 3: Traditional Python

```bash
# Install dependencies
pip install -r requirements.txt

# Start services manually
python mock_tmf620_api_fastapi.py  # Terminal 1
python tmf620_mcp_server.py        # Terminal 2
```

## 🔧 Configuration

The system uses JSON configuration files:

### `config.json` - MCP Server & API Connection
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

### `mock_server_config.json` - Mock Server Settings
```json
{
  "server": {
    "host": "localhost",
    "port": 8801,
    "protocol": "http"
  },
  "features": {
    "enable_cors": true,
    "enable_docs": true,
    "enable_mcp": true
  }
}
```

## 🌐 Available Services

### Mock TMF620 API (Port 8801)

- **API Endpoints**: Full TMF620-compliant catalog management
- **Swagger UI**: http://localhost:8801/docs
- **ReDoc**: http://localhost:8801/redoc
- **MCP Interface**: http://localhost:8801/mcp

### MCP Server (Port 7701)

- **MCP Tools**: Tools for AI agents to interact with the catalog
- **Health Check**: Monitor server and API connection health
- **Error Handling**: Comprehensive error handling and logging

## 🤖 Using with Claude Desktop

Add the following to your Claude Desktop configuration:

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

Or using traditional Python:

```json
{
  "mcpServers": {
    "tmf620-mcp": {
      "command": "python",
      "args": ["tmf620_mcp_server.py"],
      "cwd": "/path/to/tmf620-mcp-server"
    }
  }
}
```

## Available MCP Tools

The MCP server provides these tools for AI agents:

### Catalog Management
- `list_catalogs`: List all product catalogs
- `get_catalog`: Get a specific catalog by ID

### Product Offering Management
- `list_product_offerings`: List product offerings (optionally filtered by catalog)
- `get_product_offering`: Get a specific product offering by ID
- `create_product_offering`: Create a new product offering

### Product Specification Management
- `list_product_specifications`: List all product specifications
- `get_product_specification`: Get a specific product specification by ID
- `create_product_specification`: Create a new product specification

### System Tools
- `health`: Check server and API connection health

## Example Usage

### Using the Python Client

```python
from tmf620_client import get_catalogs, get_product_offerings

# Get all catalogs
catalogs = get_catalogs()
for catalog in catalogs:
    print(f"Catalog: {catalog['name']}")

# Get offerings for a specific catalog
offerings = get_product_offerings("cat-001")
for offering in offerings:
    print(f"Offering: {offering['name']}")
```

### Using MCP Tools with AI Agents

Once you have the MCP server configured with your AI agent, you can ask natural language questions and the AI will automatically use the appropriate tools:

```
"Show me all the product catalogs"
→ AI calls tmf620.list_catalogs

"Get details for catalog cat-001"  
→ AI calls tmf620.get_catalog with catalog_id=cat-001

"What product offerings are in the electronics catalog?"
→ AI calls tmf620.list_product_offerings with catalog_id

"Create a new premium service offering in catalog cat-001"
→ AI calls tmf620.create_product_offering with appropriate parameters

"Is the TMF620 system healthy?"
→ AI calls tmf620.health
```

**Note**: The AI automatically selects and calls the right tools based on your requests. No special commands needed - just ask naturally! See the "Using with Claude Desktop" section above for MCP server setup instructions.

## 🧪 Testing

### Test the Mock API

```bash
# Test with client script
uv run tmf620_client.py

# Or use curl with correct port
curl http://localhost:8801/tmf-api/productCatalogManagement/v4/catalog
```

### Test the MCP Server

```bash
# Check health (note: correct port 7701)
curl http://localhost:7701/health
```

## 🚀 Deployment

### Package for Distribution

```bash
# Build wheel package
uv build

# Install from wheel
uv pip install dist/tmf620_mcp_server-1.0.0-py3-none-any.whl
```

### Production Deployment

```bash
# Create production environment
uv venv production
source production/bin/activate  # Linux/Mac
# or production\Scripts\activate  # Windows

# Install production dependencies
uv sync --frozen

# Run with production server
uv run uvicorn mock_tmf620_api_fastapi:app --host 0.0.0.0 --port 8801
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install uv
RUN uv sync --frozen
EXPOSE 8801 7701
CMD ["sh", "-c", "uv run tmf620-mock-server & uv run tmf620-mcp-server & wait"]
```

## 🛠️ Development

### Install Development Dependencies

```bash
uv sync --group dev
```

### Code Quality

```bash
# Format code
uv run black .

# Lint code
uv run ruff check .
```

### Adding New Endpoints

1. **Add to Mock API**: Add new FastAPI routes in `mock_tmf620_api_fastapi.py`
2. **Add to MCP Server**: Add corresponding tools in `tmf620_mcp_server.py`
3. **Update Configuration**: Add endpoint definitions in `config.json`

### Debugging

- Check logs from both servers
- Use the health check endpoint: `curl http://localhost:7701/health`
- Test API endpoints directly: `curl http://localhost:8801/tmf-api/productCatalogManagement/v4/catalog`

## 🏆 Architecture Benefits

1. **Modern Tooling**: Uses `uv` for fast, reliable dependency management
2. **Separation of Concerns**: Mock API and MCP server are cleanly separated
3. **Configuration Management**: JSON-based configuration for easy environment management
4. **Production Ready**: Docker support, proper packaging, and deployment tools
5. **Developer Experience**: Hot reload, comprehensive docs, and easy testing
6. **AI Integration**: Native MCP support for seamless AI agent interaction

## 📄 License

This project is licensed under the MIT License. 