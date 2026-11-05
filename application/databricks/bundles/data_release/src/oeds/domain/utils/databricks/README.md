# Databricks Utilities

This package exposes DataForge-owned helpers for Databricks platform metadata.
It uses the Databricks SDK and the runtime's standard workspace authentication.

## Public API

```python
from oeds.domain.utils.databricks import (
    get_job_run_page_url,
    get_job_run_trigger_user,
)
```

- `get_job_run_trigger_user(job_run_id)` returns the trimmed SDK
  `creator_user_name` or `None` when the property is unavailable.
- `get_job_run_page_url(job_run_id)` returns the trimmed SDK `run_page_url` or
  `None` when the property is unavailable.

Both functions require a positive numeric string or integer job-run ID. Input
validation, SDK, authentication, permission, network, and run-lookup failures
propagate to the caller. The helpers return raw Databricks metadata and do not
apply notification or environment-specific transformations.
