#!/bin/bash
set -e

cleanup() {
  if [ -n "${MOCK_PID:-}" ] && kill -0 "$MOCK_PID" 2>/dev/null; then
    kill "$MOCK_PID" 2>/dev/null || true
    wait "$MOCK_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

echo "Starting TMF620 Mock API Server..."
uv run tmf620-mock-server &
MOCK_PID=$!

# Wait for mock server to be somewhat ready
sleep 2

echo "Starting TMF620 MCP Server..."
# Run MCP server in foreground
uv run tmf620-mcp-server
