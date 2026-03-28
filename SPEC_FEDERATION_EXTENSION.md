# CLI Service Federation Extension Draft

Status: Draft v1 companion to `SPEC.md`

This document scopes the draft extension space for multi-service discovery and namespace-aware federation for CLI-style HTTP APIs.

It is not required for core conformance. Single-service hierarchical discovery is defined in `SPEC.md`. This companion is only about discovery and routing once more than one service boundary matters.

---

## 1. Purpose and Scope

Use this document when:

- you need to combine multiple CLI services behind one agent-facing surface
- you need explicit namespace or routing behavior between services
- you need service-aware discovery rather than a single service tree

This document does not yet define a normative wire format. It records extension boundaries, constraints, and compatibility goals so teams do not overfit local experiments into the core spec.

---

## 2. Why This Is Separate

The core spec already defines the best single-service design:

- one endpoint
- hierarchical node discovery
- one help mechanism for root, group, and command nodes
- leaf-command invocation

Federation introduces a different class of problems:

- multiple services with overlapping command names
- service-aware routing
- namespace selection
- cross-service versioning and capability negotiation
- determining when a discovery node belongs to one service vs a federated surface

Those concerns are real, but they should not distort the single-service core model.

---

## 3. Design Constraints

Any future federation extension MUST preserve the following:

- the core single-service node model remains valid inside each service
- routing is explicit rather than inferred from naming conventions
- service boundaries are visible in discovery metadata
- help remains the primary navigation mechanism, even when federation is added
- clients can distinguish local nodes from federated nodes without guesswork

---

## 4. Likely Extension Areas

### 4.1 Federated Root Discovery

Potential future capabilities:

- one root catalog spanning multiple services
- service summaries at the top layer before node-level traversal
- explicit service IDs and service-scoped node IDs

Constraint:

- a federated surface MUST not hide which service owns a command.

### 4.2 Service-Aware Routing

Potential future capabilities:

- command invocation with explicit service targeting
- routing metadata in discovery responses
- conflict resolution when two services expose similarly named commands

Constraint:

- the federation layer MUST make routing deterministic and inspectable.

### 4.3 Namespace-Aware Discovery

Potential future capabilities:

- namespace filters in discovery
- namespace-level help
- policy or approval controls scoped by namespace or service

Constraint:

- namespace mechanisms SHOULD reduce ambiguity, not introduce another hidden naming layer.

---

## 5. Compatibility Guidance for Current Implementers

If you are building before this extension is standardized:

- keep each service individually conformant to `SPEC.md`
- do not overload single-service node IDs with undocumented cross-service meaning
- use explicit local routing metadata if you experiment with federation
- avoid designs where a client must reverse-engineer service ownership from command names alone

In other words: experiment locally, but do not make cross-service routing semantics look like settled core protocol.

---

## 6. Relationship to the OpenAPI Mapping Companion

`SPEC_OPENAPI_MAPPING.md` describes how one service can derive its command tree from an OAS file.

This document addresses what happens after that, when:

- multiple generated services need to coexist
- command naming alone is not enough to prevent ambiguity
- a client needs to navigate a federated surface before choosing a service

Generated command grouping inside one service belongs to the core spec. Federation begins when more than one service boundary matters to discovery or routing.

---

## 7. When to Use This Companion

Use `SPEC.md` alone when:

- you have one service, regardless of whether its tree is shallow or deep

Use `SPEC.md` plus `SPEC_OPENAPI_MAPPING.md` when:

- you are generating a single CLI service from OpenAPI

Use this extension draft as well when:

- you are combining multiple services
- you need explicit namespace or federation behavior
