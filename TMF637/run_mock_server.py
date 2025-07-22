#!/usr/bin/env python3
"""
Run script for the TMF637 Product Inventory API Mock Server
"""

import argparse
import os
import sys

def main():
    """Parse arguments and start the mock server"""
    parser = argparse.ArgumentParser(description="Start the TMF637 Product Inventory API Mock Server")
    parser.add_argument("--spec", default="TMF637-ProductInventory-v5.0.0.oas.yaml", 
                        help="Path to the OpenAPI specification YAML file")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8637, help="Port to bind the server to")
    parser.add_argument("--delay", type=float, default=0, help="Simulated network delay in seconds")
    parser.add_argument("--debug", action="store_true", help="Print debug information")
    
    args = parser.parse_args()
    
    # Import and run the server
    try:
        from tmf637_mock_server import main as mock_server_main
        
        # Run the mock server with the provided arguments
        sys_args = [
            sys.argv[0],
            "--spec", os.path.basename(args.spec),
            "--host", args.host,
            "--port", str(args.port),
            "--delay", str(args.delay),
            "--log-level", "DEBUG" if args.debug else "INFO"
        ]
        
        if args.debug:
            print("Starting server with arguments:", sys_args)
            print("Access debug routes at:")
            print(f"  http://{args.host}:{args.port}/debug/routes")
            print(f"  http://{args.host}:{args.port}/debug/storage")
        
        sys.argv = sys_args
        mock_server_main()
    except ImportError as e:
        print(f"Error: {e}")
        print("Make sure you have installed the required dependencies:")
        print("pip install fastapi uvicorn pyyaml")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()