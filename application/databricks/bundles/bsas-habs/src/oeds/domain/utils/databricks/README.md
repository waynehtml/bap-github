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

## Job task keys

`get_job_task_keys(job_id: str | int) -> list[str]` is available from
`oeds.domain.utils.databricks`. It converts the job ID with `int()` and lets
Databricks validate the lookup. It returns top-level configured task keys in
API order. Intended for jobs with at most 100 tasks; the helper does not request
additional pages. Referenced jobs and nested loop tasks are not expanded.

An empty task list returns `[]`. Missing settings or malformed task keys raise
`RuntimeError`. Integer conversion failures raise `ValueError` with the original
cause. SDK, authentication, permission, network, and job-lookup errors propagate.
