# OpenAPI-to-CLI Mapping Companion Specification

Status: Draft v1 companion to `SPEC.md`

This document defines optional mapping rules and practical guidance for generating a CLI-style HTTP API from an existing OpenAPI Specification (OAS) document.

It is not required for core conformance. A service can implement `SPEC.md` directly without any OpenAPI file.

---

## 1. Purpose and Scope

Use this document when:

- you already have an OAS-described HTTP API and want to generate a CLI service instead of hand-authoring commands
- you want repeatable command naming and argument mapping across teams
- you need a stable policy for deriving risk metadata from HTTP operations

Do not treat this document as a substitute for product design. Generated commands are a starting point. Teams SHOULD still curate summaries, examples, warnings, and registry inclusion.

---

## 2. General Guidance

### 2.1 Prefer curation over blind generation

OpenAPI captures transport semantics well, but it rarely captures agent-facing ergonomics completely. A good generator SHOULD allow hand-authored overrides for command names, summaries, warnings, and exposure policy.

### 2.2 Treat `operationId` as the primary command source

If you control the source OAS, set stable, descriptive `operationId` values. Path-derived fallback naming should be a recovery mechanism, not the normal path.

### 2.3 Do not expose every generated command by default

Generating a CLI command and exposing it in the default registry are different decisions. Read operations are usually safe defaults. Mutating operations usually need explicit opt-in, additional warnings, or approval policy.

### 2.4 Flatten request bodies conservatively

Flatten only when the result is simple, stable, and clearly better for agents. For complex, broad, or deeply nested bodies, keeping one or more properties as structured JSON arguments is often safer than inventing a brittle pseudo-CLI surface. See §6.1 and §6.2 for detailed flattening and mixed-property guidance.

### 2.5 Preserve stability across regenerations

Once a command name is published to agents, changing it has compatibility cost. Prefer explicit overrides and collision rules that produce deterministic results across regenerations.

### 2.6 Generated help should still be enriched

Even when names and parameters come from OAS, the CLI layer SHOULD add:

- concise one-line summaries
- examples the agent can copy directly
- warnings about side effects or expensive calls
- risk metadata suitable for agent decision-making

---

## 3. Command Names

| OAS source | CLI mapping rule |
|---|---|
| `operationId` | Convert to `snake_case`. Strip version suffixes (e.g. `_v5`, `V5`, `_v2`). |
| No `operationId` | Derive from path using the algorithm below. |

If two `operationId` values normalize to the same CLI command name after `snake_case` conversion and version-suffix stripping, generation MUST fail with an error identifying the conflicting operations unless the source OAS provides an `x-cli-name` extension field on one or both operations. `x-cli-name` is a string that replaces the derived command name verbatim, with no further normalization.

After applying all `x-cli-name` overrides, the final command name set MUST still be unique and MUST NOT contain any reserved command name from `SPEC.md`.

Implementations MUST NOT silently disambiguate normalized `operationId` collisions.

### 3.1 Fallback Naming Algorithm

For avoidance of doubt: steps 1-6 of the full-name algorithm produce the readable base form, and step 7 is the required disambiguation fallback when two readable full names collide. The final emitted full name is the post-step-7 form when that fallback is needed.

For each operation, compute two names upfront - a **short name** and a **full name**. The full name MUST be unique by construction (injective over valid OAS paths). Use the short name unless it collides; use the full name otherwise. Collisions are resolved in a single pass after all names are computed.

**Short name** (readable, attempt first):

1. Take all path segments. Drop leading `/`.
2. Drop leading non-resource segments:
   - any segment equal to `api`
   - any segment matching a version pattern such as `v1` or `v2.1`
   - any segment shared by every path in the spec
3. Drop all `{param}` segments.
4. Keep only the last remaining non-param segment.
5. Singularize that segment.
6. Prepend the lowercased HTTP method separated by `_`.
7. Convert to `snake_case`.

**Full name** (unique by construction, used on collision):

1. Take all path segments. Drop leading `/`.
2. Drop leading non-resource segments using the same rule as above.
3. Replace each `{param}` segment with `by_<param_name>`, where `<param_name>` is the parameter name stripped of braces and converted to `snake_case`.
4. Singularize the last non-`by_*` segment.
5. Prefix with the lowercased HTTP method.
6. Join all segments with `_`. Convert to `snake_case`.
7. If two operations still produce the same full name, append `__` followed by a path fingerprint: take the complete original path string verbatim, drop the leading `/`, replace `/` with `_`, strip `{` and `}`, and do not apply case conversion.
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

`operationId` SHOULD always be set in the source OAS to avoid this complexity entirely. Missing `operationId` SHOULD be emitted as a generation warning.

Examples of normalized `operationId` values:

- `listOrders` -> `list_orders`
- `createInvoice` -> `create_invoice`
- `getCustomerById` -> `get_customer_by_id`

---

## 4. CLI Registry Inclusion

| HTTP method | Default CLI registry | Rationale |
|---|---|---|
| `GET` | MUST include | Read-only, safe for agents. |
| `POST` | MUST NOT include by default | Creates state; requires deliberate exposure. |
| `PATCH` / `PUT` | MUST NOT include by default | Mutates state. |
| `DELETE` | MUST NOT include by default | Destructive. |

Implementations MAY expose write operations by explicit registry opt-in.

---

## 5. Risk Metadata Derivation

| HTTP method | `level` | `reversible` | `idempotent` | `confirmation_required` |
|---|---|---|---|---|
| `GET` | `"read"` | `true` | `true` | `false` |
| `POST` | `"write"` | `true` | `false` | `false` |
| `PATCH` | `"write"` | `true` | `true` | `false` |
| `PUT` | `"write"` | `true` | `true` | `false` |
| `DELETE` | `"destructive"` | `false` | `true` | `true` |

`"simulate"` cannot be derived from HTTP method alone. Assign it explicitly when an OAS operation is annotated as a dry-run, for example via `x-cli-risk: simulate` or a similarly explicit source convention.

---

## 6. Parameter Mapping

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

### 6.1 Request Body Mapping

- If an operation defines `requestBody.content.application/json.schema` and the schema is an object, each top-level property SHOULD be mapped into a CLI argument under `args` using the same field rules as above.
- Required object properties in the request body MUST be treated as required CLI arguments.
- If `requestBody.required` is `true` and the JSON body is flattened into top-level CLI arguments, the generator MUST ensure the agent cannot omit the body entirely. If the body schema would accept `{}`, the implementation SHOULD serialize `{}` when no body-derived arguments are provided.
- If the JSON request body schema is not an object, the implementation MUST expose a single CLI argument named `body` with `type: "object"` or the narrowest safe type available, and pass it through verbatim to the backend.
- Generators MUST NOT invent required CLI arguments heuristically. If a required flattened JSON body would reject `{}` and the OAS schema itself does not already require any flattened body property, generation MUST fail unless the source OAS explicitly marks one or more body properties with `x-cli-required: true`.
- If a non-object request body is exposed as a single `body` argument and `requestBody.required` is `true`, omitting `args.body` MUST be treated as `missing_required_argument`.
- If both OAS parameters and request-body properties map to the same CLI argument name, generation MUST fail with an error identifying the conflicting operation and field name unless the source OAS provides an `x-cli-arg-name` extension field on the conflicting parameter or body property to rename one of them.
- Non-JSON request bodies MAY be excluded from the CLI registry by default. If exposed, the implementation MUST document the expected encoding in per-command help.
- Implementations SHOULD stop flattening when a top-level property would require the generator to invent nested pseudo-CLI arguments for arrays of objects, recursive structures, or broad object graphs with context-dependent usage. In those cases, the property SHOULD remain a structured JSON argument under its source field name when practical.

### 6.2 Practical Mapping Guidance

Teams SHOULD prefer the narrowest stable CLI surface that still preserves agent usability:

- query parameters usually map cleanly to CLI arguments
- path parameters usually map cleanly to required CLI arguments
- simple JSON object bodies often map cleanly to top-level CLI arguments
- nested objects, arrays of objects, recursive schemas, and broad object schemas with context-dependent usage usually deserve a structured JSON argument rather than aggressive flattening

When a request body mixes simple top-level scalar properties with one nested property that carries most of the schema complexity, implementations SHOULD expose the simple scalars as normal CLI arguments and keep the complex property structured. For example, a create command can expose top-level fields such as `category`, `description`, or `priority` as normal arguments while accepting the complex array or object property as a structured JSON argument when that subtree contains nested required objects, arrays of objects, or recursion.

If the generated command would require extensive explanation to use safely, the generator SHOULD prefer a less clever mapping and rely on richer help text.

---

## 7. Summary Derivation

| OAS source | CLI `summary` |
|---|---|
| `summary` field on operation | Use as-is, truncating to 120 chars if needed. |
| `description` field, when `summary` is absent | Use the first sentence, truncated to 120 chars. |
| Neither present | Use `"<resolved_command_name> operation"` as fallback. |

Generators SHOULD warn when both `summary` and `description` are absent.

---

## 8. Node Tree Derivation for Large APIs

When an OAS file produces a large number of operations, typically more than 20, implementations SHOULD introduce group nodes when doing so meaningfully reduces root discovery cost.

The resulting node tree remains part of the core discovery model defined in `SPEC.md`. Group nodes are not a presentation-only add-on.

### 8.1 Group Name Derivation

1. Strip path segments that match the OAS `servers[].url` prefix if present.
2. Drop all leading non-resource segments:
   - any segment that matches `api`
   - any segment matching a version pattern such as `v1` or `v2.1`
   - any segment shared by every path in the spec
3. Take the first remaining non-param segment.
4. Singularize.
5. Convert to `snake_case`.

All commands derived from paths sharing the same first resource segment after prefix stripping SHOULD belong to the same group node.

If step 2 leaves no non-param segments, fall back to the full path slug: join all non-param segments with `_`, singularize the last, and convert to `snake_case`.

Examples:

| Path pattern | Group name |
|---|---|
| `/orders`, `/orders/{id}` | `order` |
| `/api/orders`, `/api/orders/{id}` | `order` |
| `/api/v1/orders`, `/api/v1/orders/{id}` | `order` |
| `/api/v1/users`, `/api/v1/users/{id}/addresses` | `user` |
| `/v2/invoices`, `/v2/invoices/{id}` | `invoice` |

Implementations SHOULD expose these groupings as `group` nodes in the root or intermediate discovery tree, with leaf operations exposed as `command` nodes.

---

## 9. When to Use This Companion

Use `SPEC.md` alone when:

- you are hand-authoring a CLI service
- your service is small enough that naming and parameter design are deliberate and manual

Use `SPEC.md` plus this companion when:

- your service is generated from OpenAPI
- you want deterministic naming and mapping rules
- you expect multiple teams or generators to produce compatible CLI surfaces
