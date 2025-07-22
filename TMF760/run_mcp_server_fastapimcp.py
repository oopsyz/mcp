#!/usr/bin/env python3
"""
Run script for the ultra-simplified TMF760 MCP HTTP Server using FastApiMCP
"""

import argparse
import os
import sys

def main():
    """Parse arguments and start the MCP server"""
    parser = argparse.ArgumentParser(description="Start the TMF760 MCP HTTP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8761, help="Port to bind the server to")
    parser.add_argument("--tmf760-url", default="http://localhost:8760", help="URL of the TMF760 API server")
    
    args = parser.parse_args()
    
    # Set environment variables for the server
    os.environ["MCP_HOST"] = args.host
    os.environ["MCP_PORT"] = str(args.port)
    os.environ["TMF760_BASE_URL"] = args.tmf760_url
    
    # Import and run the server
    try:
        from tmf760_mcp_http_server_fastapimcp import app
        import uvicorn
        
        print(f"Starting TMF760 MCP HTTP Server (FastApiMCP)...")
        print(f"Server: http://{args.host}:{args.port}")
        print(f"TMF760 API: {args.tmf760_url}")
        print(f"Documentation: http://{args.host}:{args.port}/docs")
        print(f"MCP Endpoint: http://{args.host}:{args.port}/mcp")
        print(f"API Endpoints: http://{args.host}:{args.port}/api")
        
        uvicorn.run(app, host=args.host, port=args.port)
    except ImportError as e:
        print(f"Error: {e}")
        print("Make sure you have installed the required dependencies:")
        print("pip install fastapi uvicorn httpx fastapi-mcp")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()