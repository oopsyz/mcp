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

Manages and queries the CLI service registry stored in `registry.md`.

All operations run through `registry_core.py` in the project root. Use
`uv run python registry_core.py <command> [args...]` to invoke.

## Commands

### List all services

```bash
uv run python registry_core.py list
```

Returns JSON with all services (id, url, handles).

### Get one service by ID

```bash
uv run python registry_core.py get <service_id>
```

Example:

```bash
uv run python registry_core.py get tmf620/catalogmgt
```

### Resolve — semantic service discovery

```bash
uv run python registry_core.py resolve <natural language query>
```

Returns the full registry content plus structured service data so you can
reason over the `handles` and `use_when` fields to pick the best match.

Example:

```bash
uv run python registry_core.py resolve I need to manage product orders
```

After resolving, explore the matched service's command catalog:

```bash
curl -s <URL><CLI>
```

Then invoke commands on it:

```bash
curl -s -X POST <URL><CLI> \
  -H "Content-Type: application/json" \
  -d '{"command":"<cmd>","args":{...}}'
```

### Register a new service

```bash
uv run python registry_core.py register '<json>'
```

Example:

```bash
uv run python registry_core.py register '{"id":"tmf622/ordermgt","url":"http://localhost:7702","cli":"/cli/tmf622/ordermgt","mcp":"http://localhost:7702/mcp","handles":"product orders, order lifecycle","use_when":"agent needs to place, track, or cancel orders","owner":"order-team","tags":["order","fulfillment","tmf622"]}'
```

### Unregister a service

```bash
uv run python registry_core.py unregister <service_id>
```

## Chaining: Resolve then Invoke

The typical workflow for a user request like "show me the active catalogs":

1. Resolve: `uv run python registry_core.py resolve product catalogs`
2. Read the result, pick the best service (match on `handles` / `use_when`)
3. Explore: `curl -s <url><cli>`
4. Invoke: `curl -s -X POST <url><cli> -H "Content-Type: application/json" -d '{"command":"catalog list","args":{"lifecycle_status":"Active"}}'`

## Guidelines

- Always run resolve or list first before making assumptions about available services
- Match user intent against `handles` and `use_when` fields
- When multiple services match, present options and let the user choose
- For write operations (register, unregister), confirm with the user first
- After resolving a service, explore its CLI API to find the right command
