
#!/usr/bin/env python3
"""
Run both the TMF629 mock and MCP servers.
"""
import subprocess
import time

if __name__ == "__main__":
    # Start the mock server
    mock_server = subprocess.Popen(["python", "tmf629_mock_server.py"])
    print("Started mock server.")

    # Wait a moment for the mock server to start
    time.sleep(2)

    # Start the MCP server
    mcp_server = subprocess.Popen(["python", "run_mcp_server.py"])
    print("Started MCP server.")

    try:
        # Wait for the processes to complete
        mock_server.wait()
        mcp_server.wait()
    except KeyboardInterrupt:
        print("Shutting down servers...")
        mock_server.terminate()
        mcp_server.terminate()
