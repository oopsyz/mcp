# oa-engine HTTP CLI profile

Canonical ownership moved to the `oa_engine` repository:

[oa-engine CLI-over-HTTP Control-Plane Specification](https://github.com/oopsyz/oa-engine/blob/main/docs/oa-engine-http-cli-spec.md)

The `mcp` repository owns the generic CLI-style HTTP protocol in
[`SPEC.md`](SPEC.md). The engine repository owns the domain-specific profile:
CoordinationService authority, accepted-event semantics, placements, dispatch,
identity, authorization, and replay requirements.
