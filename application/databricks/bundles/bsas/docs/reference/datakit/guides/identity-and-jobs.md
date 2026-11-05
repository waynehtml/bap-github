# Azure identity and Databricks jobs

## When to use this capability

Use `AuthUtils` when a workload needs an Azure access token for a supported resource or custom scope. Use `DatabricksJobManager` to resolve, start, inspect, wait for, or cancel Databricks Jobs through the workspace SDK.

## Choose the public API

| Need | Choose |
| --- | --- |
| Storage, Key Vault, Graph, or Azure SQL token | The matching `AuthUtils.get_*_token` method |
| Token for another Azure resource | `AuthUtils.get_token_with_scope` |
| Resolve exactly one job by name | `DatabricksJobManager.get_job_id` |
| Start or cancel a job run | `run_now` or `cancel` |
| Poll until the library recognizes termination | `wait_for_job_terminated` |
| Normalize Jobs API 2.1/2.2 payloads | The `normalize_*` and `extract_*` static methods |

## Restrictions and side effects

Both clients receive credential values from the caller; neither reads a secret store. Retrieve values only at runtime from an approved provider. Do not print or log secrets or returned access tokens.

Token acquisition performs external authentication and uses Azure Identity defaults for transport, retry, and timeout behavior. `get_token_with_scope` appends `/.default` when absent.

`DatabricksJobManager` uses the Databricks SDK defaults. `run_now` starts an external job and `cancel` requests cancellation; both are side effects. Job-name matching is case-insensitive and exact, with distinct errors for zero and multiple matches. Waiting polls until the literal `TERMINATED` state, adds its own wall-clock timeout, and does not treat other lifecycle states as terminal. Only a plain success code normalizes to `SUCCESS`; all other terminated outcomes normalize to `FAILED`.

## Short example

```python
from oeds.core.job_utils import DatabricksJobManager

manager = DatabricksJobManager(
    host=get_secret("workspace_host"),
    resource_id=get_secret("workspace_resource_id"),
    spn_tenantid=get_secret("tenant_id"),
    spn_id=get_secret("client_id"),
    spn_secret=get_secret("client_secret"),
)
job_id = manager.get_job_id("daily-ingestion")
run_id = manager.run_now(job_id, job_parameters={"mode": "validate"})
completed = manager.wait_for_job_terminated(run_id, timeout_s=1800)
if manager.normalize_job_run_state(completed) != "SUCCESS":
    raise RuntimeError(manager.normalize_job_run_error(completed))
```

`get_secret` represents the workload's approved secret-provider integration; it is not supplied by this library.

## Related examples

- [Job lifecycle pattern in this guide](#short-example)
- [Configuration and environment guide](configuration-and-environment.md)
