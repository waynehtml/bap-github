# adf

Handler: `oedis.handler.adf.run`

Triggers one Azure Data Factory pipeline run through the Azure Resource Manager REST API.

The handler supports one ADF pipeline run per DataBridge task. To run multiple ADF pipelines, add multiple top-level DataBridge tasks so each run has its own task result and failure boundary.

## Configuration

### Task parameters (`params`)

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `connection.tenant_id` | Yes | string | none | Microsoft Entra tenant ID. |
| `connection.client_id` | Yes | string | none | Service-principal application client ID. |
| `connection.client_secret` | Yes | string | none | Service-principal client secret. |
| `connection.subscription_id` | Yes | string | none | Azure subscription containing the Data Factory. |
| `connection.resource_group` | Yes | string | none | Resource group containing the Data Factory. |
| `connection.factory_name` | Yes | string | none | Azure Data Factory name. |
| `connection.timeout_sec` | No | number | `60` | HTTP request timeout for token, submit, and status requests. |
| `connection.management_endpoint` | No | string | `https://management.azure.com` | Azure Resource Manager endpoint override. |
| `pipeline_name` | Yes | string | none | ADF pipeline name to run. |
| `parameters` | No | object | `{}` | ADF pipeline parameters sent to `createRun`. |
| `mode` | No | string | `wait` | Use `submit` to return after creating the run, or `wait` to poll until terminal status. |
| `wait.poll_interval_seconds` | No | number | `30` | Delay between status checks in wait mode. |
| `wait.timeout_seconds` | No | number | `3600` | Maximum wait duration. |
| `wait.success_status` | No | list[string] | `["Succeeded"]` | ADF statuses treated as success. |
| `wait.fail_on_status` | No | list[string] | `["Failed", "Cancelled"]` | ADF statuses that fail the task. |

## Wait Mode Example

`mode` defaults to `wait`, so this example can omit it. It is included here for readability.

```json
{
  "pipeline": "trigger_adf_pipeline",
  "tasks": [
    {
      "id": "run_adf_pipeline",
      "handler": "oedis.handler.adf.run",
      "params": {
        "connection": {
          "tenant_id": "{{ keyvault(scope='oedis-kv', key='azure-tenant-id') }}",
          "client_id": "{{ keyvault(scope='oedis-kv', key='adf-spn-client-id') }}",
          "client_secret": "{{ keyvault(scope='oedis-kv', key='adf-spn-client-secret') }}",
          "subscription_id": "00000000-0000-0000-0000-000000000000",
          "resource_group": "rg-datafactory-dev",
          "factory_name": "adf-enterprise-ingestion-dev"
        },
        "pipeline_name": "pl_ingest_vendor_file",
        "parameters": {
          "provider": "paycan",
          "dataset": "daily_positions",
          "business_date": "{{ runtime.job_params.business_date }}",
          "source_run_id": "{{ runtime.job_run_id }}"
        },
        "mode": "wait",
        "wait": {
          "poll_interval_seconds": 30,
          "timeout_seconds": 3600,
          "success_status": ["Succeeded"],
          "fail_on_status": ["Failed", "Cancelled"]
        }
      }
    }
  ]
}
```

## Submit Mode Example

```json
{
  "pipeline": "submit_adf_pipeline",
  "tasks": [
    {
      "id": "submit_adf_pipeline",
      "handler": "oedis.handler.adf.run",
      "params": {
        "connection": {
          "tenant_id": "{{ keyvault(scope='oedis-kv', key='azure-tenant-id') }}",
          "client_id": "{{ keyvault(scope='oedis-kv', key='adf-spn-client-id') }}",
          "client_secret": "{{ keyvault(scope='oedis-kv', key='adf-spn-client-secret') }}",
          "subscription_id": "00000000-0000-0000-0000-000000000000",
          "resource_group": "rg-datafactory-dev",
          "factory_name": "adf-enterprise-ingestion-dev"
        },
        "pipeline_name": "pl_ingest_vendor_file",
        "parameters": {
          "provider": "paycan",
          "dataset": "daily_positions"
        },
        "mode": "submit"
      }
    }
  ]
}
```

## Outputs

Successful runs return one output item:

```json
{
  "src": {
    "type": "request",
    "path": "adf://adf-enterprise-ingestion-dev/pl_ingest_vendor_file"
  },
  "dest": {
    "type": "response",
    "path": "<adf_pipeline_run_id>"
  },
  "duration_sec": 12.3
}
```

The ADF run ID is also available in `TaskResult.extras.run_id`.

## Errors and Troubleshooting

- Authentication failures raise an exception and do not return a synthetic success result.
- `submit` mode fails when `createRun` does not return `runId`.
- `wait` mode succeeds only when the status is in `wait.success_status`.
- `wait` mode fails when the status is in `wait.fail_on_status`.
- `wait` mode raises `TimeoutError` if the configured timeout is reached before success or failure.
- Logs include lifecycle details such as factory, pipeline, run ID, status changes, and poll counts. They do not log client secrets, tokens, or parameter values.
