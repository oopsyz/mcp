# CLI-Style HTTP API Core Specification

Status: Draft v1

This document defines a minimal wire contract for CLI-style HTTP APIs intended for LLM agents.

The goal is simple: an agent should be able to discover a service, inspect one command at a time, and invoke commands through one endpoint without learning route-specific behavior.

Implementation guidance and examples live in `CLI_API_PATTERN.md`.

Companion specifications:

- `SPEC_OPENAPI_MAPPING.md` - optional guidance for generating a CLI service from OpenAPI
- `SPEC_FEDERATION_EXTENSION.md` - optional guidance for multi-service discovery and federation

---

## 1. Design Goals

This specification is intentionally narrow.

It standardizes:

- a single HTTP endpoint for discovery and invocation
- a uniform JSON request shape
- a reserved `help` command
- compact discovery and per-command help
- standard non-streaming responses
- standard error codes
- optional NDJSON streaming

It does not standardize:

- authentication or authorization
- backend implementation details
- command naming conventions beyond reserved names
- risk derivation policy
- OpenAPI generation rules
- async job handling

---

## 2. Core Principles

**P1 - Single endpoint.**
All agent-facing discovery and invocation happen through one endpoint.

**P2 - Progressive disclosure.**
Agents should be able to see a compact command catalog first, then fetch detailed help only for the command they want to run.

**P3 - Help is part of the protocol.**
`help` is a reserved command. Agents must not need out-of-band documentation to inspect commands.

**P4 - Invocation is uniform.**
Agents send the same JSON envelope for every command.

**P5 - Errors must guide recovery.**
Error responses must be machine-readable and should make the next step obvious.

**P6 - Streaming is optional.**
Streaming is useful for list-like outputs, but must remain opt-in and predictable.

---

## 3. Endpoint Contract

The canonical CLI endpoint defined by this specification is `/cli`.
Deployments MAY place additional infrastructure prefixes in front of it, but `/cli` is the agent-facing protocol root.

### 3.1 Discovery

```text
GET /cli
```

Returns the root command catalog.

### 3.2 Dispatch

```text
POST /cli
Content-Type: application/json
```

Accepts:

- `help`
- domain commands

---

## 4. Request Shape

All command requests use this JSON envelope:

```json
{
  "command": "<command_name>",
  "args": {},
  "stream": false
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `command` | string | MUST | Command to run. |
| `args` | object | SHOULD | Named arguments for the command. Omit or send `{}` when unused. |
| `stream` | boolean | MAY | If `true`, the response is NDJSON. Default is `false`. |

Rules:

- `command` MUST be a non-empty string.
- `args`, when present, MUST be a JSON object.
- `stream`, when present, MUST be a boolean.

### 4.1 Help Request

`help` is invoked using the same request envelope:

```json
{
  "command": "help",
  "args": {
    "command": "<command_name>"
  }
}
```

Rules:

- Omitting `args.command` means "return the root catalog."
- Setting `args.command` means "return detailed help for that command."
- Unknown help targets MUST return `help_target_not_found`.

This spec uses `args.command` instead of a separate node identifier on purpose. The wire contract should stay simple unless a service has a proven need for a richer discovery graph.

---

## 5. Response Envelope

All non-streaming JSON responses MUST include:

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0"
}
```

`status` MUST be one of:

- `ok`
- `error`

---

## 6. Discovery Model

This spec standardizes command-path discovery, not a full node tree.

Services MAY organize commands hierarchically using command paths such as:

- `catalog list`
- `catalog get`
- `offering create`

The wire contract treats each full command path as the command identity.

### 6.1 Root Catalog Response

`GET /cli` and `POST /cli {"command":"help"}` MUST return the root catalog:

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "service": "<service_name>",
  "commands": [
    {
      "name": "catalog",
      "kind": "group",
      "summary": "Browse catalog commands."
    },
    {
      "name": "health",
      "kind": "command",
      "summary": "Check service health."
    }
  ],
  "total": 2
}
```

Rules:

- `commands` MUST be compact.
- Each entry MUST include `name`, `kind`, and `summary`.
- `kind` MUST be `command` or `group`.
- `total` MUST equal the number of returned entries.
- Root discovery MUST NOT inline full argument schemas for every command.

For `kind: "group"` entries, `name` is a discovery label, not an invokable command by itself unless the service explicitly documents it as one.

### 6.2 Group Help Response

If a service uses grouped command paths, `help` for a group SHOULD return its child entries:

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "command": "catalog",
  "kind": "group",
  "summary": "Browse catalog commands.",
  "subcommands": [
    {
      "name": "list",
      "kind": "command",
      "summary": "List catalogs."
    },
    {
      "name": "get",
      "kind": "command",
      "summary": "Get one catalog by ID."
    }
  ]
}
```

Rules:

- Group help MUST remain compact.
- Group help MUST NOT expand full parameter schemas for every child command.

### 6.3 Command Help Response

Detailed help for a leaf command MUST return enough information for an agent to invoke it correctly:

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "command": "catalog list",
  "summary": "List catalogs.",
  "description": "Return catalogs from the backing service.",
  "risk": {
    "level": "read",
    "reversible": true,
    "idempotent": true,
    "confirmation_required": false
  },
  "arguments": [
    {
      "name": "limit",
      "required": false,
      "type": "integer",
      "default": null,
      "description": "Maximum number of records to return."
    }
  ],
  "examples": [
    {
      "description": "List the first 5 catalogs",
      "request": {
        "command": "catalog list",
        "args": {
          "limit": 5
        }
      }
    }
  ]
}
```

Rules:

- `command` MUST be the full invokable command string.
- `arguments` MUST describe the accepted `args` keys for that command.
- Each argument entry MUST include:
  - `name`
  - `required`
  - `default`
- `type`, `description`, `enum`, `example`, and `warning` are RECOMMENDED when useful.
- `risk`, when present, MUST be an object with the following fields:
  - `level` (REQUIRED) — MUST be one of `read`, `write`, `destructive`, or `simulate`.
    - `read` — no side effects.
    - `write` — creates or modifies state.
    - `destructive` — removes or irreversibly changes state.
    - `simulate` — dry-run; no persistent side effects.
  - `reversible` (RECOMMENDED) — boolean indicating whether the effect can be undone.
  - `idempotent` (RECOMMENDED) — boolean indicating whether repeated calls produce the same result.
  - `confirmation_required` (RECOMMENDED) — boolean hint that an agent should seek user confirmation before invoking.
  - Omitting `risk` means the service does not declare it; agents SHOULD NOT assume safety from absence.
  - Companion specs (e.g. `SPEC_OPENAPI_MAPPING.md`) MAY define derivation rules for populating `risk` from source metadata.

This spec does not require one exact schema vocabulary beyond those common fields. The objective is agent usability, not schema maximalism.

---

## 7. Invocation Response

Successful non-streaming invocation responses MUST use this shape:

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "command": "<command_name>",
  "result": {}
}
```

Rules:

- `result` MUST contain the command-specific output.
- Implementations MAY include additional top-level metadata such as `resources` when useful.

---

## 8. Error Response

Error responses MUST use this shape:

```json
{
  "status": "error",
  "interface": "cli",
  "version": "1.0",
  "error": {
    "code": "<machine_readable_code>",
    "message": "<human_readable_message>"
  }
}
```

The following error codes are required:

| Code | When to use |
|---|---|
| `command_not_found` | The requested command is not registered as an invokable command. |
| `help_target_not_found` | `help` referenced an unknown command or group. |
| `missing_required_argument` | A required argument was omitted. |
| `invalid_argument` | One argument failed validation. |
| `invalid_arguments` | `args` is not an object, or multiple argument validation errors occurred. |
| `invalid_request` | The JSON body is structurally valid but the top-level shape is wrong. |
| `invalid_command` | `command` is missing or is not a non-empty string. |
| `invalid_json` | The request body is not valid JSON. |
| `tool_invocation_failed` | The command ran but the underlying tool failed unexpectedly. |
| `stream_failed` | A streaming response failed after the stream started. |

Rules:

- `code` MUST be snake_case.
- `message` MUST be human-readable.
- Implementations MAY add `retryable`, `suggestions`, or `next_actions`.

---

## 9. Streaming Protocol

Streaming is optional. When used, it MUST be explicitly requested with:

```json
{
  "command": "<command_name>",
  "args": {},
  "stream": true
}
```

The response MUST use:

```text
Content-Type: application/x-ndjson
```

Each chunk is one JSON object followed by `\n`.

### 9.1 Chunk Types

**Started**

```json
{"type":"started","command":"<command_name>","interface":"cli","version":"1.0"}
```

**Item**

```json
{"type":"item","data":{}}
```

**Done**

```json
{"type":"done","command":"<command_name>","total":0}
```

**Result**

```json
{"type":"result","command":"<command_name>","data":{}}
```

**Error**

```json
{"type":"error","error":{"code":"<code>","message":"<message>"}}
```

### 9.2 Streaming Rules

- The first chunk MUST be `started`.
- For commands that naturally return a collection, implementations SHOULD emit zero or more `item` chunks followed by one `done` chunk.
- For commands that return a single result object, implementations SHOULD emit one `result` chunk and terminate the stream.
- If an error occurs after the stream has started, implementations MUST emit an `error` chunk and terminate the stream.

This spec intentionally does not require every command to support streaming, and it does not require one exact mapping from backend payload shape to chunk shape. It only standardizes the stream envelope.

---

## 10. Reserved Command Names

The following names are reserved and MUST NOT be used for domain commands:

- `help`

Future versions may reserve additional names, but this version keeps the reserved surface minimal.

---

## 11. Conformance

A conformant implementation MUST:

1. Expose `GET /cli` and return a root catalog.
2. Accept `POST /cli` with the request envelope defined in this document.
3. Support `help` as a reserved command.
4. Return root discovery for `POST /cli {"command":"help"}`.
5. Return command or group help for `POST /cli {"command":"help","args":{"command":"..."}}`.
6. Return `help_target_not_found` for unknown help targets.
7. Return `command_not_found` for unknown invokable commands.
8. Include `interface: "cli"` and `version: "1.0"` in every non-streaming JSON response.
9. Use the standard error response shape.
10. If streaming is supported, emit NDJSON beginning with `started`.

A conformant implementation SHOULD:

- keep root discovery compact
- provide concrete examples in command help
- include argument defaults when known
- use standard error codes consistently
- support streaming for list-like commands
- include `risk` metadata in command help responses
