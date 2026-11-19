---
applyTo: "**/*.py,**/*.ipynb"
---

# Shared API Selection

Before adding processing or utility code, use these references:

- Start with the [DataKit package API reference](../../docs/reference/datakit/README.md), select the owning `oeds.core` module, and read its page under `../../docs/reference/datakit/api/` for the complete public inventory, exact signatures, and source docstrings.
- Use the [DataForge domain utilities reference](../../src/oeds/domain/utils/README.md) to locate `oeds.domain.utils` capabilities, then inspect the linked local source and docstrings for exact signatures and behavior.
- Use the [DataForge configuration catalog](../../conf/oeds/config/README.md)
  to locate project-owned definitions under `oeds.config`; do not treat those
  definitions as reusable APIs.
- Check examples, tests, and existing DataForge usage when available. Confirm that the documented DataKit version is compatible with `../../cluster/requirements.txt`.

## Selection order

1. Reuse an existing `oeds.domain.utils` public API for DataForge-specific or business-pipeline behavior.
2. Reuse an existing documented `oeds.core` public API for generic, domain-neutral behavior.
3. Extend an existing API in its owning project when the change fits its contract and preserves compatibility.
4. Create a new local implementation only after confirming that no suitable public API exists.

Generic shared behavior belongs in DataKit. In a standalone DataForge project, propose that change for the DataKit repository instead of copying or reimplementing DataKit functionality locally. Keep DataForge integration and pipeline behavior in `oeds.domain.utils`.

## Discovery and implementation

- Identify the requested capability and search both reference catalogs before writing a new implementation.
- For `oeds.core`, confirm the selected API and signature in its generated module page; inspect DataKit source only when it is available in the workspace.
- For `oeds.domain.utils`, inspect the selected local source and docstrings before use.
- For `oeds.config`, inspect the selected local definition, its owning guide,
  and the configuration catalog before changing its contract.
- Import DataKit APIs only through their documented `oeds.core` package paths and DataForge utilities through their documented `oeds.domain.utils` package paths.
- Import project configuration only through `oeds.config.<area>`; never add
  configuration modules under `src/oeds/domain`.
- Do not guess names, signatures, parameters, return values, exceptions, or runtime assumptions.
- Do not use members whose names begin with `_`, import directly from a DataKit source tree, copy shared implementations into DataForge, or create wrappers that merely forward arguments without meaningful DataForge behavior.
- Report unclear, conflicting, missing, stale, or deprecated contracts rather than selecting or inventing an API.

Before a material implementation change, briefly state the understood requirement, selected module and API, confirmed signature, why it fits, references or source inspected, and any unresolved requirement.

## When no API fits

Explain which modules and APIs were considered, why they do not meet the requirement, whether the new behavior is generic or DataForge-specific, and which owning project should contain it. Do not claim that no API exists until both reference catalogs and the relevant linked module documentation or source have been checked.
