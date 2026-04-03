# CLAUDE

Role: da
Bootstrap: Read `AGENTS.md` first.
Instruction: Then read `DOMAIN.md` (mandatory entrypoint for this level).
Guardrail: `AGENTS.md` and `DOMAIN.md` remain the canonical contract files. Keep mutable operational detail in linked canonical artifacts, not in `CLAUDE.md`.

## Claude Guidance

## Preferred Interface

For TMF620 command discovery and invocation, use the bash tool with `curl` against the HTTP CLI API. This is the preferred interface for Claude agents.

- Discovery: `GET http://localhost:7701/cli/tmf620/catalogmgt`
- Per-command help: `POST http://localhost:7701/cli/tmf620/catalogmgt` with `{"command":"help","args":{"command":"<command path>"}}`
- Invoke: `POST http://localhost:7701/cli/tmf620/catalogmgt` with `{"command":"<command path>","args":{...}}`
- Stream: add `"stream": true` to the same POST body

Preferred shell pattern:

- `curl -s http://localhost:7701/cli/tmf620/catalogmgt`
- `curl -s -X POST http://localhost:7701/cli/tmf620/catalogmgt -H "Content-Type: application/json" -d '{"command":"help","args":{"command":"catalog list"}}'`
- `curl -s -X POST http://localhost:7701/cli/tmf620/catalogmgt -H "Content-Type: application/json" -d '{"command":"catalog list","args":{"limit":1}}'`

## Source of Truth

The shared command layer lives in `tmf620_commands.py`.

- `tmf620_mcp_server.py` exposes the HTTP CLI API and MCP server

When changing command names, arguments, discovery output, or invocation behavior, update `tmf620_commands.py` first.

## Local URLs

- Mock TMF620 API: `http://localhost:8801/tmf-api/productCatalogManagement/v5`
- MCP server and HTTP CLI API: `http://localhost:7701`
- HTTP CLI API endpoint: `http://localhost:7701/cli/tmf620/catalogmgt`

## Validation Order

When validating command behavior, prefer this order:

1. `GET /cli/tmf620/catalogmgt`
2. `POST /cli/tmf620/catalogmgt` with `help`
3. `POST /cli/tmf620/catalogmgt` invoke


