# TMF API Reference Catalog

Use this reference when a registry response mentions a TMF API and you need to
validate that the TMF ID and name are real and correctly paired.

## Boundary

- `registry.md` is the source of truth for registry service discovery.
- This TMF catalog is `reference_only`.
- Do not use this catalog as a service registry.
- Do not use this catalog for general service discovery.
- Use it only to validate TMF API IDs and names that appear in a registry
  response or a TMF-specific recommendation.

## Validation Rule

When a response includes a TMF API ID or TMF API name:

1. Confirm the ID exists in the TMF catalog.
2. Confirm the ID and name belong together.
3. Prefer the registry service entry for the actual recommendation.
4. If the TMF pair is not in the catalog, do not return it as a valid TMF API
   suggestion.

## Suggested Agent Behavior

- Resolve against `registry.md` first.
- If the candidate answer mentions TMF APIs, validate those identifiers against
  the TMF catalog before responding.
- Keep customer-facing answers grounded in registry services, not in the TMF
  catalog itself.
- If the user is not asking about TMF APIs, ignore the TMF catalog entirely.
