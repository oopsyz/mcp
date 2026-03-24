#!/bin/bash
set -e

echo "Starting TMF620 Mock API Server..."
uv run tmf620-mock-server &
MOCK_PID=$!

# Wait for mock server to be somewhat ready
sleep 2

echo "Starting TMF620 MCP Server..."
# Run MCP server in foreground
uv run tmf620-mcp-server

# If MCP server exits, kill the mock server
kill $MOCK_PID
