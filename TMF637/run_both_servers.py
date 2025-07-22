#!/usr/bin/env python3
"""
Run script for both TMF637 Product Inventory API Mock Server and MCP Server
"""

import argparse
import os
import sys
import subprocess
import time
import signal
import atexit

# Global variables to store process handles
mock_server_process = None
mcp_server_process = None

def cleanup():
    """Clean up function to terminate processes on exit"""
    if mock_server_process:
        print("Terminating Mock Server...")
        mock_server_process.terminate()
        mock_server_process.wait()
    
    if mcp_server_process:
        print("Terminating MCP Server...")
        mcp_server_process.terminate()
        mcp_server_process.wait()

def signal_handler(sig, frame):
    """Signal handler for graceful shutdown"""
    print("Received shutdown signal. Cleaning up...")
    cleanup()
    sys.exit(0)

def main():
    """Parse arguments and start both servers"""
    parser = argparse.ArgumentParser(description="Start both TMF637 Product Inventory API Mock Server and MCP Server")
    parser.add_argument("--mock-host", default="0.0.0.0", help="Host to bind the mock server to")
    parser.add_argument("--mock-port", type=int, default=8637, help="Port to bind the mock server to")
    parser.add_argument("--mcp-host", default="0.0.0.0", help="Host to bind the MCP server to")
    parser.add_argument("--mcp-port", type=int, default=8638, help="Port to bind the MCP server to")
    parser.add_argument("--delay", type=float, default=0, help="Simulated network delay for mock server in seconds")
    parser.add_argument("--spec", default="TMF637-ProductInventory-v5.0.0.oas.yaml", 
                        help="Path to the OpenAPI specification YAML file")
    
    args = parser.parse_args()
    
    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the mock server
    global mock_server_process
    mock_server_cmd = [
        sys.executable,
        "tmf637_mock_server.py",
        "--spec", args.spec,
        "--host", args.mock_host,
        "--port", str(args.mock_port),
        "--delay", str(args.delay)
    ]
    
    print(f"Starting TMF637 Product Inventory API Mock Server...")
    print(f"Command: {' '.join(mock_server_cmd)}")
    mock_server_process = subprocess.Popen(mock_server_cmd, cwd="TMF637")
    
    # Wait a bit for the mock server to start
    time.sleep(2)
    
    # Start the MCP server
    global mcp_server_process
    mcp_server_cmd = [
        sys.executable,
        "tmf637_mcp_server.py"
    ]
    
    # Set environment variables for the MCP server
    env = os.environ.copy()
    env["HOST"] = args.mcp_host
    env["PORT"] = str(args.mcp_port)
    env["TMF637_API_URL"] = f"http://{args.mock_host}:{args.mock_port}"
    
    print(f"Starting TMF637 Product Inventory API MCP Server...")
    print(f"Command: {' '.join(mcp_server_cmd)}")
    print(f"TMF637 API URL: {env['TMF637_API_URL']}")
    mcp_server_process = subprocess.Popen(mcp_server_cmd, env=env, cwd="TMF637")
    
    print("\nBoth servers are running:")
    print(f"Mock Server: http://{args.mock_host}:{args.mock_port}")
    print(f"MCP Server: http://{args.mcp_host}:{args.mcp_port}")
    print(f"MCP Endpoint: http://{args.mcp_host}:{args.mcp_port}/mcp")
    print("\nPress Ctrl+C to stop both servers.")
    
    # Wait for both processes to complete (which should be never unless interrupted)
    try:
        mock_server_process.wait()
        mcp_server_process.wait()
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Shutting down...")
        cleanup()

if __name__ == "__main__":
    main()