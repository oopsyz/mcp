---
name: registry
description: >
  Use this skill when the user wants to discover, list, register, or resolve
  CLI services from the service registry. Triggers include: finding a service
  by intent, listing available services, registering a new service, removing
  a service, or exploring what a service can do. Keywords: registry, service,
  discover, resolve, find service, list services, register, unregister.
version: "1.0.0"
---

# Service Registry Skill

Manages and queries the CLI service registry stored in `registry_agent/data/registry.md`.

Use `registry_agent/data/registry.md` as the source of truth for service discovery. Read the registry directly and reason over `handles`, `use_when`, `tags`, `dependencies`, and `status`.

When a response mentions a TMF API, validate the TMF ID and name against
`.opencode/skills/registry/references/tmf-api-reference-catalog.md`. Treat that
TMF catalog as reference-only, not as a service registry.

Use `registry_agent/core.py` only for deterministic maintenance operations:

```bash
python3 registry_agent/core.py list
python3 registry_agent/core.py get <service_id>
python3 registry_agent/core.py register '<json>'
python3 registry_agent/core.py unregister <service_id>
python3 registry_agent/core.py setstatus <service_id> <status>
```

Do not use `python3 registry_agent/core.py resolve ...` as the primary reasoning path. That command is only a deterministic fallback when OpenCode-backed semantic resolve is unavailable.

## Resolve Workflow

For vague user intent, read `registry_agent/data/registry.md` directly:

1. infer the likely capability from the user's language
2. match against `handles`, `use_when`, `tags`, and dependency context
3. rank the best service candidates
4. if the user is asking for an action, then explore and invoke the matched service CLI

## CLI API Contract

Every registered service follows the same HTTP CLI API pattern. Use `bash` with `curl` to interact:

### Discover commands

```bash
curl -s <URL><CLI>
```

### Get help for a command

```bash
curl -s -X POST <URL><CLI> \
  -H "Content-Type: application/json" \
  -d '{"command":"help","args":{"command":"<command path>"}}'
```

### Invoke a command

```bash
curl -s -X POST <URL><CLI> \
  -H "Content-Type: application/json" \
  -d '{"command":"<command path>","args":{...}}'
```

## Chaining: Resolve then Invoke

The typical workflow for a user request like "show me the active catalogs":

1. Read `registry_agent/data/registry.md`
2. Pick the best matching service for product catalogs
3. Explore: `curl -s <url><cli>`
4. Invoke: `curl -s -X POST <url><cli> -H "Content-Type: application/json" -d '{"command":"catalog list","args":{"lifecycle_status":"Active"}}'`

## Guidelines

- Always resolve or list first before making assumptions about available services
- Match user intent against `handles`, `use_when`, `tags`, and dependency context
- When multiple services match, present options and let the user choose
- For write operations (register, unregister), confirm with the user first
- After resolving a service, explore its CLI API to find the right command
