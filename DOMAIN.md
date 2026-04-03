# DOMAIN — CLI API Protocol

CLI-style HTTP API specification for LLM agent-facing services, with reference implementations and tooling.

Domain architecture repo entrypoint. Owns domain design baselines and produces a job catalog for developer routing.

## Read First

1. This file - domain context and navigation

## Parent

- [ENTERPRISE](https://github.com/oopsyz/tincan-ea/blob/main/ENTERPRISE.md)

## Critical File Contract

- Keep required section headings from this template.
- Do not rename or delete required sections.
- Keep this file concise: identity, routing semantics, and links.
- Put detailed/mutable operational values in canonical artifacts and link them here.
- If a required section has no content, keep it and write `Not applicable`.

## Knowledge Store Layout

```text
DOMAIN.md                                          <- you are here
AGENTS.md                                          <- repo-specific agent instructions
ROADMAP.md                                         <- (optional) DA-owned developer-facing plan
domain-implementations.yml                         <- canonical implementation catalog (implementation_id routing)
.openarchitect/
`-- cascade-state.yml                              <- (optional) governance gates + pinned refs
architecture/
`-- domains/
    `-- <domain_id>/
        |-- domain-design.md                       <- (optional) narrative design
        |-- domain-design.yml                      <- (optional) structured design
        |-- component-specs.yml                    <- refined component specs
        `-- interface-contracts.yml                <- (optional) domain-level interfaces
inputs/
|-- workstreams/
|   `-- <WORKSTREAM_ID>/
|       |-- source.yml                             <- upstream provenance + lineage
|       `-- artifacts/                             <- delivered artifacts
`-- initiatives/                                   <- optional fallback grouping
    `-- <initiative_id>/...
```

## Canonical Artifacts

- `domain-implementations.yml` (canonical implementation_id routing selector)
- `architecture/domains/<domain>/*.yml` (domain design, component specs, data/workflow details)
- `inputs/workstreams/<WORKSTREAM_ID>/source.yml` + `artifacts/` (upstream handoff provenance and payloads)

## Routing

`implementation_id` -> `domain-implementations.yml` -> `repo.url` + `repo.paths` + optional `repo.entrypoint` + optional `repo.git_ref`

## DA Identity

This domain's runtime and session identity is `domain_id`. Inbound workstreams
(`workstream_id`) are demand units that attach to this domain-scoped ownership
boundary — they do not create separate DA runtimes. `workstream_repo_url` in
`domain-workstreams.yml` is the handoff context location; `domain_repo_url` in
`domain-registry.yml` is the authoritative DA target.

## Upstream Inputs

- Prefer `inputs/workstreams/<WORKSTREAM_ID>/` because `WORKSTREAM_ID` is the
  selector/routing key for DA startup.
- `source.yml` identifies upstream repo URL + commit/tag + captured_at + reason,
  and should include `solution_key`, `initiative_id`, `workstream_id`, and
  `handoff_ref` when available.
- Keep only the current upstream feed in each workstream folder; use Git history
  for prior states unless explicit snapshot/version folders are later required.

## Policy

- Treat selector inputs as authoritative (`WORKSTREAM_ID`, `implementation_id`).
- Fail-closed on inactive status by default.
