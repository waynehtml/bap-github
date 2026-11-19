# Project Configuration Instructions

- Before changing a configuration contract, consult the [catalog](README.md),
  its linked guide, the loader, and current callers. Keep project configuration
  from becoming a parallel utility library; keep static resources beside the
  package that loads them.
- Validate the complete contract before execution where possible. Update the
  catalog, relevant examples, and affected tests when contracts change.
  In the canonical template, maintain the owning guide; in generated projects,
  document differences under `docs/project/` without editing inherited guides.
  Documentation destinations are relative to the bundle root.

## Ingestion configuration under `ingest/`

- Use version-matched DataBridge pipeline and handler contracts from the
  [vendored reference](../../../docs/reference/databridge/docs/README.md) and
  [examples](../../../docs/reference/databridge/examples). Consult the
  [client guide](../../../docs/guide/G220-ingest-client-guide.md) for client
  behavior. Report unavailable or conflicting contracts instead of inventing
  fields. Inspect matching source schemas when available.
- Preserve DataForge `[[ ... ]]` and DataBridge `{{ ... }}` template ownership.
- Examples show supported patterns. Matching test configurations, when
  available, are test evidence, not production templates; standalone projects
  do not require sibling test sources.
- Do not copy credentials, environment-specific paths, workspace identifiers,
  or secret values from examples or tests.
