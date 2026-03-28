# CLI-Style HTTP API Specification for LLM Agents

Status: Draft v1 (language-agnostic)

This document is the normative wire contract for CLI-style HTTP APIs designed for LLM agent consumption. It defines what conformant implementations MUST produce and MUST accept. Implementation guidance and code examples live in `CLI_API_PATTERN.md`.

---

## 1. Problem Statement

LLM agents calling HTTP APIs face a fixed cost: the agent must load the full tool surface into context before it can act. As service APIs grow, this cost becomes prohibitive. The CLI-style HTTP API pattern solves this by making the API surface itself progressive — the agent pays context cost proportional to what it actually uses.

A conformant implementation exposes a single endpoint. The agent discovers commands on demand, fetches help for only the commands it needs, and invokes them with a uniform request shape. No URL construction, no per-tool routes, no upfront schema loading.

---

## 2. Goals and Non-Goals

### 2.1 Goals

- Define a single-endpoint HTTP interface that any LLM agent can discover and invoke without out-of-band documentation.
- Define a progressive disclosure model that keeps per-call context cost proportional to usage.
- Define normative request and response shapes that implementations MUST conform to.
- Define a streaming protocol for commands that return item collections.
- Define error response shapes that guide agents to recovery actions.
- Define an async/pending protocol for long-running operations.
- Define risk metadata that lets agents make safe/unsafe decisions without human judgment.
- Provide optional mapping rules from OpenAPI Specification (OAS) operations to CLI commands (Section 9).

### 2.2 Non-Goals

- Prescribing an implementation language or framework.
- Defining authentication or authorization mechanisms.
- Defining how backend logic is implemented.
- Defining multi-service federation or command namespacing (see Section 10).
- Mandating a specific deployment topology.

---

## 3. Core Principles

**P1 — Single endpoint, command dispatch.**
All commands are reachable through one URL. The agent constructs `{"command": "...", "args": {...}}` — no URL templating, no per-tool routes.

**P2 — Progressive disclosure.**
The catalog MUST return only names and one-line summaries by default. Full parameter schemas are only returned on per-command help requests. The agent fetches detail on demand.

**P3 — Help is a first-class command.**
`help` is a reserved command name. Any conformant implementation MUST respond to it. It MUST NOT be registered as a domain command.

**P4 — Schemas are curated, not inferred.**
Parameter schemas MAY include fields (`enum`, `range`, `warning`, `example`) that JSON Schema cannot express. Implementations SHOULD enrich schemas with domain knowledge that reduces agent retry turns.

**P5 — Safety is data.**
Risk metadata SHOULD be included in per-command help. When present, it SHOULD contain enough information for an agent to decide whether to proceed without human confirmation.

**P6 — Read/write separation.**
Destructive or privileged commands MUST NOT be exposed in the CLI registry by default. The CLI registry is the agent-facing safe subset.

**P7 — Streaming is opt-in.**
Non-streaming callers MUST NOT receive streaming responses unless they set `"stream": true`. Streaming MUST use NDJSON over chunked transfer encoding.

**P8 — Errors guide recovery.**
Error responses MUST include a machine-readable `code`, a human-readable `message`, and SHOULD include `next_actions` pointing to the exact follow-up command.

**P9 — Async operations surface their handle before waiting.**
When a command starts a long-running job, the operation ID MUST be returned before the wait begins, not only on success.

**P10 — Execution and presentation are separate.**
Raw backend responses are not agent responses. Implementations MUST shape output for the agent at a presentation layer without modifying execution semantics.

---

## 4. Endpoint Contract

### 4.1 Discovery

```
GET /api/cli
```

Returns the compact catalog. MUST NOT require a request body.

### 4.2 Command Dispatch

```
POST /api/cli
Content-Type: application/json
```

Accepts all command requests including `help`, `operation_status`, and domain commands.

### 4.3 Versioning

Non-streaming JSON responses MUST include `"interface": "cli"` and `"version": "2.0"` at the top level.

Streaming responses are exempt from this requirement at the chunk level. The stream is identified by its `Content-Type: application/x-ndjson` header. The `started` chunk SHOULD include `"interface": "cli"` and `"version": "2.0"` for in-band identification, but subsequent chunks (item, done, result, error) MUST NOT repeat the envelope fields.

---

## 5. Request Shape

```json
{
  "command": "<command_name>",
  "args": {},
  "stream": false
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `command` | string | MUST | Name of the command to invoke. |
| `args` | object | SHOULD | Named arguments. Omit or send `{}` if the command takes no arguments. |
| `stream` | boolean | MAY | If `true`, response is NDJSON chunked. Default: `false`. |

---

## 6. Response Shapes

Non-streaming JSON responses share a common envelope. Streaming NDJSON chunks are exempt — see Section 4.3 and Section 7.

| Field | Type | Non-streaming JSON | Streaming chunks |
|---|---|---|---|
| `status` | string | MUST | Not present (chunk type serves this role). |
| `interface` | string | MUST | SHOULD on `started`; MUST NOT on subsequent chunks. |
| `version` | string | MUST | SHOULD on `started`; MUST NOT on subsequent chunks. |

### 6.1 Catalog Response (`GET /api/cli`)

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "2.0",
  "service": "<service_name>",
  "how_to_invoke": {
    "endpoint": "POST /api/cli",
    "shape": {"command": "<command_name>", "args": {}, "stream": false}
  },
  "how_to_get_help": {
    "all_commands": "GET /api/cli  or  POST /api/cli {\"command\": \"help\"}",
    "one_command": "POST /api/cli {\"command\": \"help\", \"args\": {\"command\": \"<name>\"}}"
  },
  "streaming": {
    "supported": true,
    "enable": "Add \"stream\": true to any command request.",
    "content_type": "application/x-ndjson",
    "chunk_types": {
      "started": "Emitted immediately when the request is accepted.",
      "item": "One chunk per result item.",
      "done": "Final chunk with total item count and result metadata.",
      "result": "Single-chunk response for commands that do not return an items array.",
      "error": "Emitted on tool error or unexpected exception."
    }
  },
  "commands": [
    {"name": "<command_name>", "summary": "<one-line summary>"}
  ],
  "total": 3
}
```

**Rules:**
- `commands` MUST contain only `name` and `summary` — no parameter schemas.
- `summary` MUST be one line. It SHOULD be derived from the first line of the command description.
- `total` MUST equal the length of `commands`.
- A `GET /api/cli?verbose=true` MAY return richer catalog detail but MUST NOT be the default.

### 6.2 Command Help Response

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "2.0",
  "command": {
    "name": "<command_name>",
    "summary": "<one-line summary>",
    "risk": {
      "level": "read",
      "reversible": true,
      "idempotent": true,
      "confirmation_required": false
    },
    "parameters": [
      {
        "name": "<param_name>",
        "required": false,
        "default": null,
        "type": "string",
        "enum": [],
        "range": [0, 100],
        "description": "<parameter description>",
        "example": "<example value>",
        "warning": "<side-effect or gotcha>"
      }
    ],
    "usage": {"command": "<command_name>", "args": {}},
    "examples": [
      {
        "description": "<example description>",
        "request": {"command": "<command_name>", "args": {}}
      }
    ],
    "see_also": ["<related_command>"],
    "streaming": {
      "supported": true,
      "enable": "Add \"stream\": true alongside \"command\" and \"args\"."
    }
  }
}
```

**Parameter fields:**

| Field | Required | Description |
|---|---|---|
| `name` | MUST | Parameter name as accepted in `args`. |
| `required` | MUST | `true` if the command will reject a missing value. |
| `default` | MUST | Default value, or `null` if none. |
| `type` | SHOULD | `"string"`, `"number"`, `"boolean"`, `"array"`, `"object"`. |
| `enum` | MAY | Exhaustive list of valid string values. |
| `range` | MAY | `[min, max]` for numeric parameters. |
| `description` | SHOULD | Domain-specific explanation. |
| `example` | MAY | A concrete value the agent can copy. |
| `warning` | MAY | Side effects, performance notes, or gotchas. |

**Risk metadata fields:**

| Field | Required | Values |
|---|---|---|
| `level` | MUST | `"read"`, `"simulate"`, `"write"`, `"destructive"`, `"admin"` |
| `reversible` | MUST | `true` / `false` |
| `idempotent` | MUST | `true` / `false` |
| `confirmation_required` | MUST | `true` / `false` — agents MUST NOT proceed without human confirmation if `true` |

### 6.3 Invocation Response

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "2.0",
  "command": "<command_name>",
  "result": {},
  "resources": [
    {"type": "<resource_type>", "id": "<id>", "uri": "<uri>"}
  ]
}
```

**Rules:**
- `result` MUST contain the command output. Shape is command-specific.
- `resources` SHOULD be included when the result contains identifiable objects worth referencing in follow-up actions.
- `resources` MUST be omitted when not applicable.

### 6.4 Error Response

```json
{
  "status": "error",
  "interface": "cli",
  "version": "2.0",
  "error": {
    "code": "<machine_readable_code>",
    "message": "<human_readable_message>",
    "retryable": false,
    "suggestions": ["<known_command_1>"],
    "next_actions": [
      {"type": "help", "request": {"command": "help"}}
    ]
  }
}
```

**Required error codes** — MUST be used exactly as named when the described condition occurs:

| Code | When to use |
|---|---|
| `command_not_found` | The requested command name is not in the CLI registry. |
| `missing_required_argument` | A required parameter was omitted. |
| `invalid_argument` | A parameter value failed validation (wrong type, out of range, not in enum). |
| `invalid_arguments` | The `args` field is not a JSON object, or multiple parameter validation failures occurred on a single request. |
| `invalid_request` | The request body is structurally valid JSON but missing required top-level fields, or a top-level field other than `command` or `args` has the wrong type (e.g. `stream` is not a boolean). |
| `invalid_command` | The `command` field is present but is not a non-empty string. |
| `invalid_json` | The request body could not be parsed as JSON. |
| `tool_invocation_failed` | The command was dispatched but the underlying tool raised an unhandled exception. |
| `stream_failed` | An error occurred during a streaming response after the stream was opened. |

Implementations MAY emit additional error codes as extension points. Extension codes MUST be snake_case and MUST NOT shadow any code in the required list.

**Rules:**
- `code` MUST be snake_case, machine-readable.
- `message` MUST describe what went wrong.
- `retryable` MUST be `true` if retrying the request might succeed — either with corrected `args` or with the same request on a transient failure.
- `next_actions` SHOULD include the exact follow-up request the agent should make.
- `suggestions` SHOULD be included for `command_not_found` errors (list of known command names).

### 6.5 Pending Response (Async Operations)

```json
{
  "status": "pending",
  "interface": "cli",
  "version": "2.0",
  "operation": {
    "id": "<operation_id>",
    "status_command": {
      "command": "operation_status",
      "args": {"id": "<operation_id>"}
    },
    "cancel_command": {
      "command": "operation_cancel",
      "args": {"id": "<operation_id>"}
    }
  },
  "message": "<optional progress message>"
}
```

**Rules:**
- The operation ID MUST be returned (or emitted as a streaming `started` chunk) before the implementation begins waiting.
- `operation_status` and `operation_cancel` are reserved command names. Implementations offering async MUST register them.
- A completed operation polled via `operation_status` MUST return its final result, not a 404.

---

## 7. Streaming Protocol

When `"stream": true` is set in the request, the response MUST use:

```
Content-Type: application/x-ndjson
Transfer-Encoding: chunked
```

Each chunk is a single JSON object followed by a newline (`\n`). Chunks MUST be emitted in this order:

| Chunk type | `type` field | When emitted |
|---|---|---|
| Started | `"started"` | Immediately on request acceptance, before execution. |
| Item | `"item"` | Once per item, for commands returning an `items` array. |
| Done | `"done"` | After all items. MUST include `total` count. |
| Result | `"result"` | Single chunk for commands that do not return an `items` array. |
| Error | `"error"` | On tool error or unhandled exception. Terminates the stream. |

**Started chunk:**
```json
{"type": "started", "command": "<command_name>", "interface": "cli", "version": "2.0"}
```

**Item chunk:**
```json
{"type": "item", "data": {}}
```

**Done chunk:**
```json
{"type": "done", "command": "<command_name>", "total": 0}
```

**Result chunk:**
```json
{"type": "result", "command": "<command_name>", "data": {}}
```

**Error chunk:**
```json
{"type": "error", "error": {"code": "<code>", "message": "<message>"}}
```

---

## 8. Reserved Command Names

The following command names MUST NOT be used for domain commands:

| Name | Purpose |
|---|---|
| `help` | Returns the catalog (no args) or full help for one command (`args.command`). |
| `operation_status` | Polls a pending async operation by `args.id`. |
| `operation_cancel` | Cancels a pending async operation by `args.id`. |

---

## 9. OAS-to-CLI Mapping Rules

> **This section is optional.** OAS compliance is not required to implement this spec. Sections 1–8 define the complete wire contract and can be implemented directly without any OAS file. This section only applies when auto-generating a CLI interface from an existing OpenAPI Specification (OAS) file.

These rules are not specific to any API style or domain.

### 9.1 Command Names

| OAS source | CLI mapping rule |
|---|---|
| `operationId` | Convert to `snake_case`. Strip version suffixes (e.g. `_v5`, `V5`, `_v2`). |
| No `operationId` | Derive from path using the algorithm below. |

If two `operationId` values normalize to the same CLI command name after `snake_case` conversion and version-suffix stripping, generation MUST fail with an error identifying the conflicting operations unless the source OAS provides an `x-cli-name` extension field on one or both operations. `x-cli-name` is a string that replaces the derived command name verbatim (no further normalization). After applying all `x-cli-name` overrides, the final command name set MUST still be unique and MUST NOT contain any reserved command name from Section 8. Implementations MUST NOT silently disambiguate normalized `operationId` collisions.

**Fallback naming algorithm** (applied when `operationId` is absent):

For avoidance of doubt: steps 1-6 of the full-name algorithm produce the readable base form, and step 7 is the required disambiguation fallback when two readable full names collide. The final emitted full name is the post-step-7 form when that fallback is needed.

For each operation, compute two names upfront — a **short name** and a **full name**. The full name MUST be unique by construction (injective over valid OAS paths). Use the short name unless it collides; use the full name otherwise. Collisions are resolved in a single pass after all names are computed.

**Short name** (readable, attempt first):

1. Take all path segments. Drop leading `/`.
2. Drop leading non-resource segments (same rule as Section 9.6 step 2).
3. Drop all `{param}` segments.
4. Keep only the last remaining non-param segment.
5. Singularize that segment.
6. Prepend the lowercased HTTP method separated by `_`.
7. Convert to `snake_case`.

**Full name** (unique by construction, used on collision):

1. Take all path segments. Drop leading `/`.
2. Drop leading non-resource segments (same rule as Section 9.6 step 2).
3. Replace each `{param}` segment with `by_<param_name>`, where `<param_name>` is the param name stripped of braces and converted to `snake_case` (e.g. `{id}` → `by_id`, `{orderId}` → `by_order_id`).
4. Singularize the last non-`by_*` segment.
5. Prefix with the lowercased HTTP method.
6. Join all segments with `_`. Convert to `snake_case`.
7. If two operations still produce the same full name, append `__` followed by a path fingerprint: take the complete original path string verbatim, drop the leading `/`, replace `/` with `_`, strip `{` and `}` — but do NOT apply `snake_case` or any case conversion. Since OAS requires all paths to be unique as literal strings, this fingerprint is guaranteed unique for any valid OAS file (e.g. `/orders/{orderId}` → `__orders_orderId`, `/orders/{order_id}` → `__orders_order_id`).
8. If fingerprinted full names still collide, the OAS is malformed. Generation MUST fail with an error identifying the conflicting paths.

**Collision resolution** (single pass):

1. Compute short name and full name for every operation in the spec.
2. Find all short names that appear more than once.
3. For every operation whose short name collides, replace it with its full name.
4. The resolved name set is now the final command name set. No further passes are needed.

Examples:

| Path | Method | Short name | Full name | Resolved |
|---|---|---|---|---|
| `/orders` | `GET` | `get_order` | `get_order` | `get_order` |
| `/orders/{id}` | `GET` | `get_order` | `get_order_by_id` | `get_order_by_id` |
| `/orders/{id}/items` | `GET` | `get_item` | `get_order_by_id_item` | `get_order_by_id_item` |
| `/orders/{id}/items/{itemId}` | `GET` | `get_item` | `get_order_by_id_item_by_item_id` | `get_order_by_id_item_by_item_id` |
| `/users/{id}/orders` | `GET` | `get_order` | `get_user_by_id_order` | `get_user_by_id_order` |

`operationId` SHOULD always be set in the source OAS to avoid this complexity entirely. Flag missing `operationId` as a warning during generation.

`operationId` examples:

- `listOrders` → `list_orders`
- `createInvoice` → `create_invoice`
- `getCustomerById` → `get_customer_by_id`

### 9.2 CLI Registry Inclusion

| HTTP method | Default CLI registry | Rationale |
|---|---|---|
| `GET` | MUST include | Read-only, safe for agents. |
| `POST` | MUST NOT include by default | Creates state; requires deliberate exposure. |
| `PATCH` / `PUT` | MUST NOT include by default | Mutates state. |
| `DELETE` | MUST NOT include by default | Destructive. |

Implementations MAY expose write operations by explicit registry opt-in.

### 9.3 Risk Metadata Derivation

| HTTP method | `level` | `reversible` | `idempotent` | `confirmation_required` |
|---|---|---|---|---|
| `GET` | `"read"` | `true` | `true` | `false` |
| `POST` | `"write"` | `true` | `false` | `false` |
| `PATCH` | `"write"` | `true` | `true` | `false` |
| `PUT` | `"write"` | `true` | `true` | `false` |
| `DELETE` | `"destructive"` | `false` | `true` | `true` |

`"simulate"` cannot be derived from HTTP method alone. Assign it explicitly when an OAS operation is annotated as a dry-run (e.g. via `x-cli-risk: simulate` extension field, or by naming convention such as `dryRun` in the `operationId`).

### 9.4 Parameter Mapping

| OAS parameter field | CLI parameter field |
|---|---|
| `name` | `name` |
| `required` | `required` |
| `schema.default` | `default` |
| `schema.type` | `type` |
| `schema.enum` | `enum` |
| `schema.minimum` + `schema.maximum` | `range: [minimum, maximum]` |
| `description` | `description` |
| `schema.example` | `example` |

OAS `$ref` parameters MUST be resolved before mapping. OAS `allOf` / `anyOf` / `oneOf` parameter schemas SHOULD be flattened to the most specific applicable type.

**Request body mapping:**

- If an operation defines `requestBody.content.application/json.schema` and the schema is an object, each top-level property SHOULD be mapped into a CLI argument under `args` using the same field rules as above.
- Required object properties in the request body MUST be treated as required CLI arguments.
- If `requestBody.required` is `true` and the JSON body is flattened into top-level CLI arguments, the generator MUST ensure the agent cannot omit the body entirely. If the body schema would accept `{}` (no `minProperties`, `oneOf`, or similar constraints), the implementation SHOULD serialize `{}` when no body-derived arguments are provided.
- If the JSON request body schema is not an object (for example, a scalar, array, or polymorphic body that cannot be flattened safely), the implementation MUST expose a single CLI argument named `body` with `type: "object"` or the narrowest safe type available, and pass it through verbatim to the backend.
- Generators MUST NOT invent required CLI arguments heuristically. If a required flattened JSON body would reject `{}` and the OAS schema itself does not already require any flattened body property, generation MUST fail unless the source OAS explicitly marks one or more body properties with `x-cli-required: true`. Each property marked with `x-cli-required: true` becomes a required CLI argument.
- If a non-object request body is exposed as a single `body` argument and `requestBody.required` is `true`, omitting `args.body` MUST be treated as `missing_required_argument`.
- If both OAS parameters and request-body properties map to the same CLI argument name, generation MUST fail with an error identifying the conflicting operation and field name unless the source OAS provides an `x-cli-arg-name` extension field on the conflicting parameter or body property to rename one of them. `x-cli-arg-name` is a string that replaces the derived CLI argument name verbatim.
- Non-JSON request bodies MAY be excluded from the CLI registry by default. If exposed, the implementation MUST document the expected encoding in per-command help.

### 9.5 Summary Derivation

| OAS source | CLI `summary` |
|---|---|
| `summary` field on operation | Use as-is (truncate to 120 chars if needed). |
| `description` field (no `summary`) | Use first sentence, truncated to 120 chars. |
| Neither present | Use `"<resolved_command_name> operation"` as fallback, where `resolved_command_name` is the final CLI command name after applying Section 9.1. |

### 9.6 Command Grouping for Large APIs

When an OAS file contains more than 20 operations, implementations MAY group commands by resource type as a presentation-layer optimization. Grouping MUST NOT replace or rename the flat `commands` list defined in Section 6.1 unless a future revision defines a standard grouped wire format.

**Group name derivation:**

1. Strip path segments that match the OAS `servers[].url` prefix if present.
2. Drop all leading non-resource segments: any segment that matches `api`, matches a version pattern (`v\d+`, `v\d+\.\d+`), or is shared by every path in the spec.
3. Take the first remaining non-param segment.
4. Singularize (e.g. `orders` → `order`).
5. Convert to `snake_case`.

All commands derived from paths sharing the same first resource segment (after prefix stripping) belong to the same group.

If step 2 leaves no non-param segments, fall back to the full path slug: join all non-param segments with `_`, singularize the last, convert to `snake_case`.

Examples:

| Path pattern | Group name |
| --- | --- |
| `/orders`, `/orders/{id}` | `order` |
| `/api/orders`, `/api/orders/{id}` | `order` |
| `/api/v1/orders`, `/api/v1/orders/{id}` | `order` |
| `/api/v1/users`, `/api/v1/users/{id}/addresses` | `user` |
| `/v2/invoices`, `/v2/invoices/{id}` | `invoice` |

Implementations that present groups MAY add a non-normative `groups` field alongside the flat `commands` list for local use, but agents MUST be able to operate correctly from the flat catalog alone.

---

## 10. Groups Extension (Placeholder)

This section is reserved for the multi-service and command-grouping extension. It will define:

- How the catalog represents nested command groups.
- How group-level help works.
- How a federation layer discovers multiple CLI services.

Implementations MUST treat the absence of this section as "flat catalog only." The groups extension, when defined, will be additive and backward-compatible.

---

## 11. Conformance

A conformant implementation MUST:

1. Expose `GET /api/cli` returning a valid compact catalog.
2. Respond to `POST /api/cli {"command": "help"}` with the catalog.
3. Respond to `POST /api/cli {"command": "help", "args": {"command": "<name>"}}` with full parameter schema and risk metadata.
4. Return `command_not_found` error for unknown commands.
5. Return `missing_required_argument` error for missing required parameters.
6. Include `"interface": "cli"` and `"version": "2.0"` in every non-streaming JSON response (catalog, help, invocation, error, and pending).
7. Return NDJSON with `started` as the first chunk when `"stream": true`. The `started` chunk SHOULD include `"interface": "cli"` and `"version": "2.0"`; subsequent chunks MUST NOT.
8. Never include `help`, `operation_status`, or `operation_cancel` as domain commands.
9. Never expose destructive commands in the CLI registry by default.

A conformant implementation SHOULD:

- Include `next_actions` in all error responses.
- Include `risk` metadata in all per-command help responses.
- Include `resources` in invocation responses when the result contains identifiable objects.
- Return a `pending` response (not a timeout error) for long-running operations, with the operation ID emitted before waiting begins.
