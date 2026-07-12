# oa-engine CLI-over-HTTP Control-Plane Specification

**Status:** Draft v1

This specification defines the authenticated HTTP adapter for a centralized
`oa-engine` control plane. It lets remote Codex threads and trusted host
processes use the engine without sharing SQLite or running a second authority.

This document extends the repository's generic CLI-style HTTP protocol in
[`SPEC.md`](SPEC.md); it does not replace that discovery and invocation
envelope.

## 1. Scope and authority

The service is a thin transport adapter over `CoordinationService` and the
existing engine CLI contracts:

```text
remote Codex host
        │ authenticated HTTPS / private tunnel
        ▼
central oa-engine HTTP adapter
        │
CoordinationService → accepted events → SQLite projections
```

Accepted events remain authoritative. The HTTP service MUST NOT expose SQLite,
JSON snapshots, or direct projection writes. Every mutation MUST use the same
service validation, expected-sequence checks, idempotency rules, and reducer
replay path as the local CLI.

The adapter is intended for:

- remote Codex threads that need to read a plan or submit an envelope;
- trusted host workers that need to register placements, dispatch work, or
  record receipts; and
- founder/operator tooling that cannot run the local CLI process.

It is not an unrestricted remote shell, raw database API, or generic proxy to
arbitrary Python functions.

## 2. Endpoint and envelope

The canonical deployment endpoint is:

```text
/cli/oa-engine
```

It follows the generic CLI API envelope:

```json
{
  "command": "work-item next-step",
  "args": {"work_item_id": "wi-123"},
  "stream": false
}
```

Responses use the generic `status`, `interface`, `version`, `command`,
`result`, and machine-readable `error` fields. The service MUST advertise
`service: "oa-engine"` and an API version independent of the event payload
version.

## 3. Discovery surface

`GET /cli/oa-engine` and `POST {"command":"help"}` MUST return a compact
catalog. Detailed help MUST identify risk, idempotency, required identity
context, and whether the command creates accepted events.

The initial catalog SHOULD be divided into these groups:

| Group | Examples | Default risk |
| --- | --- | --- |
| `health` | `health`, `version` | read |
| `work-item` | `show`, `status`, `next-step` | read |
| `projection` | `founder-brief`, `cell-projection`, `wait-graph` | read |
| `watchdog` | `watchdog` | read |
| `thread` | `register`, `delivery-record` | write |
| `dispatch` | `plan`, `record`, `evidence` | write |
| `action` | `apply` | write; confirmation/capability required |
| `guidance` | `record`, `withdraw` | write |
| `placement` | `register`, `replace-thread` | write; capability required |

The service MAY expose additional commands, but every command needs an explicit
registry entry, help payload, risk classification, and authorization rule.

## 4. Identity and authorization context

Every request MUST carry or derive an authenticated caller context. The
transport identity is separate from the engine's cooperative `actor_role`.

The normalized context MUST include:

```json
{
  "principal_id": "founder-or-agent-123",
  "principal_kind": "human|agent|host",
  "actor_role": "founder|ea|sa|da|dev|reviewer",
  "host_id": "host-codex-b",
  "placement_id": "placement-codex-b",
  "runtime_thread_id": "thread-sa-42",
  "work_item_id": "wi-123",
  "request_id": "req-uuid",
  "idempotency_key": "optional-write-key"
}
```

The adapter MUST bind capabilities to the authenticated principal, host,
placement, and allowed work-item scope. A caller MUST NOT choose an arbitrary
`actor_role` or placement merely by changing JSON fields. The engine may retain
the existing self-declared role for replay compatibility, but the HTTP adapter
must authenticate the surrounding identity before accepting external writes.

Recommended transport options, in descending preference:

1. mTLS with host/client certificates;
2. OIDC/service tokens with short expiry and audience binding; or
3. an SSH tunnel to a loopback-bound HTTP listener.

Plain unauthenticated network HTTP is non-conformant for write commands.

## 5. Read command contracts

Read commands MUST be side-effect free and MUST return rebuildable projections,
never mutable database rows as authority. Examples:

```json
{
  "command": "work-item next-step",
  "args": {"work_item_id": "wi-123"}
}
```

```json
{
  "command": "projection founder-brief",
  "args": {"cursor": ""}
}
```

Read responses SHOULD include the accepted sequence or watermark used to build
the result. A caller MUST treat a stale or incomplete projection as a finding,
not as a mutation precondition.

## 6. Write command contracts

Write commands MUST be curated operations over `CoordinationService`, not a
generic `event_type` plus arbitrary payload endpoint. Each write MUST:

- validate its request body against the canonical schema;
- carry `request_id` and, where applicable, an idempotency key;
- enforce the caller's capability and work-item scope;
- enforce expected accepted sequence when the operation is conditional;
- return the accepted event ID, accepted sequence, and projected result; and
- return a conflict without retrying the mutation when the sequence is stale.

Example envelope submission:

```json
{
  "command": "action apply",
  "args": {
    "work_item_id": "wi-123",
    "action_type": "submit_sa_alignment_response",
    "actor_role": "sa",
    "envelope": {"...": "schema-valid envelope"},
    "expected_sequence": 18,
    "request_id": "req-uuid",
    "idempotency_key": "action:wi-123:dispatch-42"
  }
}
```

The response MUST distinguish:

- accepted event;
- idempotent replay of an already accepted event;
- stale sequence/conflict;
- schema or authorization rejection; and
- transport/backend failure before acceptance.

The adapter MUST never report an accepted event if the SQLite commit and replay
check did not complete successfully.

## 7. Dispatch and asynchronous work

Dispatch is a two-phase operation:

1. record the intent and dispatch metadata through the central engine;
2. execute the Codex side effect through the selected placement and record the
   returned receipt/evidence through the central engine.

The HTTP API SHOULD return a stable `dispatch_id`, `intent_dispatch_id`,
`placement_id`, and deadline. A remote host MAY poll a read command for the
dispatch result or submit evidence through a separate write command. Webhooks
are optional; if added, they are notifications only and never become a second
authority.

Detached Codex turns MUST retain the existing `dispatched`/harvest/deadline
semantics. A transport timeout is not a failed work result; the watchdog and
tick expiry path remain responsible for liveness.

## 8. Error mapping

The adapter uses the generic CLI error envelope and adds these engine-specific
codes:

| Code | Meaning | Retry guidance |
| --- | --- | --- |
| `unauthenticated` | caller identity missing or invalid | refresh credentials |
| `forbidden_capability` | identity lacks command/scope capability | do not retry unchanged |
| `work_item_scope_forbidden` | caller is outside the work-item scope | select an authorized item |
| `sequence_conflict` | accepted sequence advanced | re-read state and re-plan |
| `idempotency_conflict` | key reused with different payload | stop and investigate |
| `placement_unavailable` | target host/placement unavailable | use explicit replacement policy |
| `dispatch_in_doubt` | intent exists without a final receipt | reconcile; do not blindly retry |
| `engine_unavailable` | no accepted event was written | retry with backoff |

HTTP status mapping SHOULD be:

- `401` for `unauthenticated`;
- `403` for capability/scope failures;
- `409` for sequence or idempotency conflicts;
- `422` for schema/argument rejection;
- `503` for engine or placement unavailability.

## 9. Security and operations

The service MUST:

- bind request identity to an authenticated transport credential;
- log principal, host, placement, runtime thread, command, request ID, result,
  and accepted event ID without logging secrets;
- rate-limit reads and writes independently;
- set bounded request, dispatch, and response timeouts;
- reject direct database paths and shell commands in request arguments;
- preserve audit correlation across retries; and
- provide health/readiness endpoints that do not reveal event payloads.

The central service SHOULD run behind a private ingress or SSH tunnel until
enterprise identity and capability enforcement are deployed. Remote Codex
hosts remain execution placements; they do not receive database credentials.

## 10. Versioning and compatibility

The HTTP API version (`v1`) and accepted event payload versions are separate.
Adding optional command arguments is compatible. Changing command meaning,
required arguments, authorization semantics, or response shape requires a new
HTTP API version or an explicit compatibility extension.

The adapter MUST preserve the local CLI's replay behavior. A request accepted
over HTTP MUST produce the same event and projection as the equivalent local
CLI invocation.

## 11. Conformance checklist

An implementation is conformant when it can demonstrate:

- [ ] compact discovery and per-command help;
- [ ] authenticated read access from a remote Codex host;
- [ ] authenticated envelope submission through `CoordinationService`;
- [ ] sequence conflict and idempotency-conflict behavior;
- [ ] dispatch intent/receipt correlation;
- [ ] detached-turn deadline and watchdog behavior;
- [ ] no direct database or shell access through HTTP;
- [ ] audit correlation from HTTP request to accepted event; and
- [ ] replay equivalence between local CLI and HTTP invocation.

## 12. Roadmap fit

This adapter is the enterprise bridge for the current centralized topology. It
does not make remote hosts authoritative. It adds authenticated transport,
capabilities, and placement-scoped access around the existing event authority.

The implementation should follow the enterprise roadmap: harden ADR-0003's
trust boundary first, then add placement-aware routing, durable multi-host
scheduling, and failover. The solo local CLI and scheduler remain valid and do
not depend on this HTTP service.
