#!/usr/bin/env python3
"""
Run script for the TMF637 Product Inventory API MCP Server
"""

import argparse
import os
import sys

def main():
    """Parse arguments and start the MCP server"""
    parser = argparse.ArgumentParser(description="Start the TMF637 Product Inventory API MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8638, help="Port to bind the server to")
    parser.add_argument("--tmf637-url", default="http://localhost:8637", help="URL of the TMF637 API server")
    
    args = parser.parse_args()
    
    # Set environment variables for the server
    os.environ["HOST"] = args.host
    os.environ["PORT"] = str(args.port)
    os.environ["TMF637_API_URL"] = args.tmf637_url
    
    # Import and run the server
    try:
        from tmf637_mcp_server import app
        import uvicorn
        
        print(f"Starting TMF637 Product Inventory API MCP Server...")
        print(f"Server: http://{args.host}:{args.port}")
        print(f"TMF637 API: {args.tmf637_url}")
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