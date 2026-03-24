# Agent Guidance

## Preferred Interface

For TMF620 command discovery and invocation, use the bash tool with `curl` against the HTTP CLI API.

- Discovery: `GET http://localhost:7701/api/cli`
- Per-command help: `POST http://localhost:7701/api/cli` with `{"command":"help","args":{"command":"<command path>"}}`
- Invoke: `POST http://localhost:7701/api/cli` with `{"command":"<command path>","args":{...}}`
- Stream: add `"stream": true` to the same POST body

Preferred shell pattern:

- `curl -s http://localhost:7701/api/cli`
- `curl -s -X POST http://localhost:7701/api/cli -H "Content-Type: application/json" -d '{"command":"help","args":{"command":"catalog list"}}'`
- `curl -s -X POST http://localhost:7701/api/cli -H "Content-Type: application/json" -d '{"command":"catalog list","args":{"limit":1}}'`

## Source of Truth

The shared command layer lives in `tmf620_commands.py`.

- `tmf620_mcp_server.py` exposes the HTTP CLI API and MCP server

When changing command names, arguments, discovery output, or invocation behavior, update `tmf620_commands.py` first.

## Local URLs

- Mock TMF620 API: `http://localhost:8801/tmf-api/productCatalogManagement/v5`
- MCP server and HTTP CLI API: `http://localhost:7701`
- HTTP CLI API endpoint: `http://localhost:7701/api/cli`

## Validation Order

When validating command behavior, prefer this order:

1. `GET /api/cli`
2. `POST /api/cli` with `help`
3. `POST /api/cli` invoke
