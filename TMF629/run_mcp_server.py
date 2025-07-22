
#!/usr/bin/env python3
"""
Run the TMF629 MCP server.
"""
import os
import uvicorn
from tmf629_mcp_server import app, tmf_client

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))
    tmf_api_url = os.getenv("TMF_API_URL", "http://localhost:8080")

    # Set the TMF API URL for the client
    tmf_client.base_url = tmf_api_url
    
    print(f"Starting TMF629 MCP Server...")
    print(f"Server: http://{host}:{port}")
    print(f"TMF API: {tmf_client.base_url}")
    print(f"Documentation: http://{host}:{port}/docs")
    print(f"MCP Endpoint: http://{host}:{port}/mcp")
    
    uvicorn.run(app, host=host, port=port)
