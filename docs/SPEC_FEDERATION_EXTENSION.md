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
- descriptive deployment prefixes such as `/cli/tmf620/catalogmgt` MAY help humans or agents find a service entrypoint, but they SHOULD be treated only as bootstrap hints
- avoid designs where a client must reverse-engineer service ownership from command names alone
- avoid designs where a client must reverse-engineer service ownership from URI naming alone

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

---

## 8. Federation and Routing Model

### 8.1 Objective

Define a deterministic and scalable mechanism for:

- locating CLI endpoints across ODA components
- routing agent requests to the correct domain or component
- reducing ambiguity in multi-component environments
- complementing semantic discovery with structural addressing

### 8.2 Namespace-Based Routing

A practical federation pattern is to expose each CLI instance under a structured URI namespace derived from:

- TMF API identifier
- business or domain context

Examples:

```text
/cli/tmf620/catalogmgt
/cli/tmf622/productorder
/cli/tmf641/serviceorder
```

These prefixes can make service entrypoints easier to locate, but they do not replace explicit routing metadata, service ownership metadata, or discovery-time identification.

Within a namespace, the CLI contract remains the same as the core spec:

```text
/cli/<namespace>
```

### 8.3 Design Principle

Namespace is the externalized identity of an ODA component capability.

In this model, each namespace:

- maps to a specific ODA component or tightly bounded domain capability
- represents a bounded execution context
- acts as a routing anchor for agents

To remain compatible with this draft's earlier constraints, the namespace SHOULD be reinforced by explicit service identity and routing metadata rather than treated as the only source of truth.

### 8.4 Routing Flow

```text
Agent
  ->
Query registry (resolve namespace by intent)
  ->
Select namespace or service target
  ->
Discover commands within that namespace
  ->
Invoke command
  ->
ODA component execution
```

The selection step should be deterministic and inspectable. Implementations SHOULD be able to explain why a request was routed to a given namespace.

The registry query step is optional when the agent already knows the target namespace. It is required when the agent must discover which namespace handles a given capability.

### 8.5 Hybrid Discovery Model

Federation can combine two complementary mechanisms.

#### 8.5.1 Structural Routing

- namespace selection such as `/cli/tmf620/*` or `/cli/tmf622/*`
- deterministic and predictable routing
- reduced ambiguity across services

#### 8.5.2 Semantic Discovery

- vector search, intent matching, or other semantic narrowing
- used before or within a constrained namespace
- assists command selection without replacing explicit routing

A conformant pattern for semantic narrowing is a **service registry**: a separately addressable CLI service that accepts natural language queries and returns ranked namespace endpoints. The registry holds `handles`, `use_when`, and `dependencies` metadata per service, and exposes the same CLI discovery contract as any other service (`GET /cli/registry`, `POST /cli/registry`). Agents query the registry before namespace selection; the registry does not replace namespace-level discovery.

One practical interaction pattern is:

```text
Intent
  ->
Semantic narrowing (optional)
  ->
Namespace selection (deterministic)
  ->
Command discovery
  ->
Invocation
```

### 8.6 Benefits

#### 8.6.1 Deterministic Federation

- reduces reliance on unconstrained global search
- enables predictable routing behavior

#### 8.6.2 Reduced Command Collision

- commands are scoped per namespace
- ambiguity across domains is reduced

#### 8.6.3 Alignment with TMF Standards

- preserves TMF API identity such as `TMF620` or `TMF622`
- maintains traceability to OpenAPI contracts and ODA capabilities

#### 8.6.4 Improved Agent Efficiency

- smaller discovery space
- lower token usage
- faster reasoning

### 8.7 Governance Integration

Namespaces can also serve as authorization boundaries.

Example:

```text
Agent A:
  Allowed -> /cli/tmf620/*
  Denied  -> /cli/tmf622/*
```

This supports:

- domain isolation
- fine-grained access control
- secure multi-agent environments

### 8.8 Relationship to ODA Components

Each namespace SHOULD correspond to:

- one ODA component
- or one tightly bounded capability within a domain

This helps preserve:

- clear ownership
- minimal cross-component ambiguity
- consistent execution boundaries

### 8.9 Federation Control Requirements

Namespace routing alone is not sufficient. A federated implementation should also support:

- service ownership resolution
- explicit routing rules
- command provenance tracking
- audit of routing decisions

These controls support auditability and deterministic behavior expectations.

### 8.10 Namespace Design Guidelines

#### 8.10.1 Use TMF API Identity Plus a Domain Hint

Preferred:

```text
/cli/tmf620/catalog
/cli/tmf622/productorder
```

Avoid opaque or overly technical naming where possible.

#### 8.10.2 Keep Names Stable

- avoid frequent namespace changes
- treat the namespace as an external contract

#### 8.10.3 Avoid Version in the URI When Possible

Avoid exposing prefixes such as:

```text
/cli/tmf622/v4
```

When feasible, version handling should be internal to the component so federation routing stays stable for agents.

#### 8.10.4 Maintain Business Readability

Namespaces should be:

- understandable by humans
- meaningful to agents
- aligned with business capabilities

### 8.11 Multi-Component Domain Considerations

Some domains span multiple TMF APIs. Two patterns are common.

Option A: API-aligned namespaces

```text
/cli/tmf622/productorder
/cli/tmf641/serviceorder
```

Option B: aggregated domain namespaces

```text
/cli/order/*
```

Recommendation:

- start with API-aligned namespaces for clarity and traceability
- introduce aggregated namespaces only when strong domain abstraction is required

### 8.12 Discovery Contract Per Namespace

Each namespace should expose the same CLI discovery contract as the core spec.

Examples:

```text
GET  /cli/<namespace>
POST /cli/<namespace> {"command":"help"}
```

The response can then describe:

- available commands
- summaries and descriptions
- input arguments and constraints
- service or namespace identity metadata

This preserves progressive discovery and agent self-navigation while keeping the per-namespace contract uniform.

### 8.13 Positioning

Namespace-based routing can provide the structural backbone for federation, while semantic discovery adds flexibility within controlled boundaries.

This approach aims to preserve:

- deterministic routing
- strong governance
- alignment with the ODA component model
- agent-optimized interaction

### 8.14 Registry Pattern

A service registry is a conformant implementation of the hybrid discovery model described in 8.5.

The registry is itself a CLI service. It satisfies the following federation concerns:

**Routing flow (8.4):** The registry fills the namespace selection step. An agent with an intent but no known namespace queries the registry first, receives ranked namespace endpoints, then proceeds with standard command discovery.

**Semantic narrowing (8.5.2):** The registry matches natural language queries against `handles` and `use_when` metadata per service. Matching MAY be LLM-powered (when a language model runtime is available) or keyword-scored (as a degraded fallback). The resolved response includes a `resolved_by` field so callers can distinguish the two.

**Service ownership resolution (8.9):** The registry carries a `dependencies` field per service entry. When a service depends on another (e.g. an order service requires a catalog service to resolve a ProductOfferingRef), the resolver surfaces this as a `prerequisites` array in the resolve response. This satisfies the ownership resolution requirement without requiring the calling agent to know inter-service contracts in advance.

**Operational status (8.9):** Each registry entry carries a `status` field (`live`, `degraded`, `maintenance`). Any agent or monitor that cannot reach a service MAY call `setstatus` on the registry to record the degraded state. The registry does not probe services itself — status is reported by observers.

**Compatibility:** The registry does not replace namespace-level discovery. After resolving a namespace, the agent queries that service's own CLI endpoint for command discovery. The registry only answers "which service?" not "which command?".

A registry entry links the governance layer (`domain-implementations.yml`, `implementation_id`) to the runtime layer (live CLI endpoint, operational status). Services register themselves on deployment; the registry does not require a separate provisioning step.
