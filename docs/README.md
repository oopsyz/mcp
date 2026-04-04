# Documentation Index

This directory holds the longer-form docs so the repository root stays focused on
runtime entrypoints, canonical data, and repo-level contracts.

## Core Protocol Docs

- [SPEC.md](./SPEC.md)
- [CLI_API_PATTERN.md](./CLI_API_PATTERN.md)
- [SPEC_OPENAPI_MAPPING.md](./SPEC_OPENAPI_MAPPING.md)
- [SPEC_FEDERATION_EXTENSION.md](./SPEC_FEDERATION_EXTENSION.md)

## Guides

- [QUICKSTART.md](./QUICKSTART.md)
- [REGISTRY_GUIDE.md](./REGISTRY_GUIDE.md)
- [SPEC.zh-CN.md](./SPEC.zh-CN.md)

## Top-Level Files

- [README.md](../README.md) - repo overview and setup
- [DOMAIN.md](../DOMAIN.md) - domain entrypoint and contract
- [AGENTS.md](../AGENTS.md) - repo-specific agent instructions
- [pyproject.toml](../pyproject.toml) - project configuration and console scripts
- [opencode.json](../opencode.json) - OpenCode MCP client config

## Runtime Packages

- [tmf620/](../tmf620/) - TMF620 mock API, shared client, command layer, server, and benchmark
- [registry_agent/](../registry_agent/) - agent-facing registry core and HTTP CLI server

## Notes

- `SPEC.md` remains the normative CLI API spec.
- The registry is an agent-facing service that resolves intent to service IDs.
- MCP in this repo is used as a reference surface for benchmarking and testing.
