# DataForge Domain Catalog

Use this page to locate the package that owns a DataForge domain concern. Keep
detailed capability and API documentation beside the package it describes.

| Area | Purpose | Context |
|---|---|---|
| [`config/databench`](config/databench/) | DataBench configuration assets published during dev pre-deploy. | See the [DataBench configuration README](config/databench/README.md). |
| [`utils`](utils/) | Reusable domain capabilities for operation status, ingestion, files, schemas, permissions, email, reference data, and time series. | See the [domain utility catalog](utils/README.md). |
| [`exceptions.py`](exceptions.py) | Shared workflow exception hierarchy for orchestration and pipeline-task failures. | Import exceptions from `oeds.domain.exceptions`; inspect the source for the available task-specific types. |

## Adding a domain package

When adding another package under `oeds.domain`:

1. Give the package its own README when it exposes capabilities that developers
   or AI agents need to discover.
2. Add the package to this index with a concise purpose and a relative link to
   its detailed context.
3. Keep exact signatures and behavior in source docstrings rather than
   duplicating API-reference documentation here.
