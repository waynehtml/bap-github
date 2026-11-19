# DataBridge Client User Guide

This guide covers the complete DataForge ingestion workflow, the lower-level
`DisClient` API, and the ingestion result models.

The implementation and runnable bundle examples are:

- [DataBridge client](../../src/oeds/domain/utils/ingest/client/dis_client.py)
- [ingestion utilities](../../src/oeds/domain/utils/ingest/ingest_utils.py)
- [ingest result](../../src/oeds/domain/utils/ingest/client/ingest_result.py)
- [verification result](../../src/oeds/domain/utils/ingest/client/verify_result.py)
- [DataForge ingest task](../../jobs/dataflow/task_10_ingest.py)
- [default ingestion config](../../conf/oeds/config/ingest/default.json)
- [outbound delivery config](../../conf/oeds/config/ingest/outbound.json)

## Overview

`DisClient` submits a Databricks job that runs the DataBridge ingestion service.

What it does:

1. Checks that the submitted DataBridge config is a non-empty, syntactically valid JSON string.
2. Calls the configured Databricks job with string job parameters.
3. Optionally waits for completion.
4. Returns an `IngestResult` with normalized status and available run metadata.
5. Optionally verifies landed files by path and size with `verify_file_by_file_size(...)`.

The client does not validate the DataBridge pipeline or handler schema. That contract
is validated by the service after submission. A JSON document can therefore pass
client validation and still produce a failed DataBridge job.

For normal DataForge workflows, prefer `run_ingest(...)`. It creates the client,
loads and renders the packaged configuration, waits for a terminal status,
converts unsuccessful statuses into `IngestTaskError`, and verifies landed
files by default. Use `DisClient` directly when configuration content,
submission, and verification must be controlled separately.

Notebook output can be returned either as plain JSON text or as a compressed
`zlib:<base64>` payload. `IngestResult` handles both forms when you call
`get_task_notebook_output()`.

## Prerequisites

You need:

- Databricks workspace host URL
- Azure tenant ID
- Azure client ID
- Azure client secret
- Azure Databricks workspace resource ID
- DataBridge Databricks job ID
- The DataForge `oeds.domain` package available in the runtime that will call the client

The DataForge cluster installs the required Databricks SDK, Pydantic, Jinja,
JMESPath, and `oeds-common` dependencies through
[cluster/requirements.txt](../../cluster/requirements.txt).

## Run The Complete Workflow

`run_ingest(...)` owns the synchronous DataForge workflow while keeping
Databricks widgets, task values, and job context outside the reusable function.
Supply exactly one configuration source:

- `config_file` loads a relative filename or path from the packaged
  `oeds.config.ingest` resources.
- `config_template` accepts raw JSON template text supplied by the caller.

Passing both or neither raises `IngestTaskError`. Separate parameters avoid
guessing whether an arbitrary string contains a path or JSON.

```python
from oeds.domain.utils.ingest.ingest_utils import (
    DisConnectionOptions,
    FileVerificationOptions,
    run_ingest,
)

service_spn_id = dbutils.secrets.get(
    scope=job_ctx["secrete_scope"],
    key=job_ctx["service_spn_id_key"],
)
service_spn_secret = dbutils.secrets.get(
    scope=job_ctx["secrete_scope"],
    key=job_ctx["service_spn_secrete_key"],
)
connection = DisConnectionOptions(
    host=job_ctx["internal_databricks_workspace_url"],
    azure_tenant_id=job_ctx["azure_tenant_id"],
    azure_client_id=service_spn_id,
    azure_client_secret=service_spn_secret,
    azure_workspace_resource_id=job_ctx["internal_databricks_resource_id"],
    dis_job_id=int(job_ctx["internal_dis_job_id"]),
)

result = run_ingest(
    connection=connection,
    config_file="default.json",
    template_params={
        "env": job_ctx["env"],
        "file_date": file_date,
        "land_dir": land_dir,
    },
)
```

The workflow helper defaults `debug` to `True`, waits up to 1,800 seconds while polling
every 10 seconds, and verifies the `upload` task output for up to 300 seconds.
Pass `debug=False` for normal production behavior. Pass `verification=None` to
skip file verification.

Use raw template content when the caller already owns loading or generation:

```python
result = run_ingest(
    connection=connection,
    config_template=raw_config_template,
    template_params=ingestion_params,
)
```

External ingestion uses the external DataBridge connection and remaps antivirus paths
to the final landing paths during verification:

```python
external_connection = DisConnectionOptions(
    host=job_ctx["external_databricks_workspace_url"],
    azure_tenant_id=job_ctx["azure_tenant_id"],
    azure_client_id=service_spn_id,
    azure_client_secret=service_spn_secret,
    azure_workspace_resource_id=job_ctx["external_databricks_resource_id"],
    dis_job_id=int(job_ctx["external_dis_job_id"]),
)

result = run_ingest(
    connection=external_connection,
    config_file="default.json",
    template_params=external_ingestion_params,
    verification=FileVerificationOptions(
        dest_root=job_ctx["dis_av_root"],
        land_root=job_ctx["land_root"],
    ),
)
```

The function returns `IngestTaskResult`, containing the successful
`IngestResult` and either a successful `VerifyResult` or `None`. Client creation,
template rendering, submission failures, `FAILED`, `TIMEOUT`, unexpected
statuses, and verification failures raise `IngestTaskError` with the originating
exception retained as its cause when applicable.

## Identify DataBridge file-validation failures

With a DataBridge server supporting validation markers, `file.validate` count
and size failures include `DATABRIDGE_VALIDATION_COUNT_ERROR:` or
`DATABRIDGE_VALIDATION_SIZE_ERROR:` followed by
`request_index=<index>; matched_count=<count>;`.
`run_ingest` preserves this message in its existing `IngestTaskError` and does
not run landed-file verification after a failed ingestion. No task-result
fields or statuses change.

Put a required `file.validate` task after download and before upload, with a
count rule whose `min` is 1. Match the upload's source and selection settings.
To distinguish no files from other count failures, check the rule marker and matched count:

```python
try:
    result = run_ingest(
        connection=connection,
        config_file="default.json",
        template_params=ingestion_params,
    )
except IngestTaskError as exc:
    message = str(exc)
    no_files = (
        "DATABRIDGE_VALIDATION_COUNT_ERROR:" in message
        and "matched_count=0;" in message
    )
    if not no_files:
        raise
    logger.info("No matching input files; skip subsequent processing.")
```

Import `IngestTaskError` from `oeds.domain.exceptions`. The caller must explicitly
return or branch after handling this case to prevent subsequent processing.
The DataBridge job remains failed and runs its failure/completion hooks.
The count marker alone identifies any count mismatch, not just zero files.
Older servers do not emit these markers; their failures remain ordinary
`IngestTaskError`s. Vendored DataBridge references may describe older behavior
until an explicitly requested reference synchronization.

## Prepare One Outbound CSV File

Spark CSV writes normally create a directory containing generated part files.
Use the shared DataKit `write_csv_file(...)` helper when a DataBridge delivery requires
one predictable filename:

```python
from oeds.core.file_utils import write_csv_file

outbound_file_path = write_csv_file(
    dataframe=outbound_df,
    destination_path=(
        f"{job_ctx['outbound_root']}/{file_date}/"
        f"{job_ctx['dataset']}_{file_date}.csv"
    ),
    include_header=True,
)
```

The helper writes a single Spark partition to a unique sibling staging
directory, requires exactly one `part-*.csv`, moves that part to the requested
destination, and removes the staging directory. Existing destinations are
replaced by default. Replacement is retry-friendly but not atomic. See the
[DataKit file utility API](../reference/datakit/api/file_utils.md) for the
complete signature, supported paths, CSV options, and failure behavior.

The reference curation integrate task passes `outbound.json` to `run_ingest`
after preparing the file. `run_ingest` loads it from `oeds.config.ingest` before
rendering. Internal DataBridge downloads the dated source file into its inbox, uploads
it to `outbound_root/delivered/<file_date>`, and verifies the delivered byte
size. Generated projects can replace the demo upload task with an appropriate
external delivery handler.

## Create The Client

```python
from oeds.domain.utils.ingest.client.dis_client import DisClient

client = DisClient(
    host="https://adb-xxxxxxxxxxxx.x.azuredatabricks.net",
    azure_tenant_id="<tenant-id>",
    azure_client_id="<client-id>",
    azure_client_secret="<client-secret>",
    azure_workspace_resource_id="/subscriptions/.../resourceGroups/.../providers/Microsoft.Databricks/workspaces/...",
    dis_job_id=123456789,
)
```

When the job ID comes from the shared context, convert it at the client boundary:

```python
dis_job_id = int(job_ctx["internal_dis_job_id"])
```

## DataBridge Config Shape

`DisClient.ingest(...)` expects `config` to be a valid JSON string. The client
checks JSON syntax only; the JSON must also match the server-side DataBridge contract.

Top-level shape:

```json
{
  "pipeline": "storage_volume_to_volume",
  "tasks": [
    {
      "id": "download",
      "handler": "oedis.handler.storage.download",
      "params": {
        "connection": {
          "uri": "/Volumes/dev_application_cat/oedisint_db/land-oedataservices/dis/data/"
        },
        "requests": [
          {
            "recursive": true
          }
        ]
      }
    },
    {
      "id": "upload",
      "handler": "oedis.handler.storage.upload",
      "params": {
        "connection": {
          "uri": "/Volumes/dev_application_cat/oedisint_db/land-oedataservices/dis/data-copy/"
        },
        "requests": [
          {
            "recursive": true
          }
        ]
      }
    }
  ]
}
```

Notes:

- `tasks` is an array, not an object.
- Each task requires `id`, `handler`, and `params`.
- A task may also define `active`, `optional`, and `when`. Supported `when`
  values are `on_success`, `on_failure`, and `on_complete`.
- Unknown top-level and task-level properties are rejected by the server schema.
- `params` is handler-specific and should follow the handler schema under
  `src/oedis/schema/` in the source or documentation for the deployed DataBridge
  version.
- The authoritative top-level contract is `src/oedis/schema/config.json` in
  that version-matched DataBridge source.
- A standalone generated DataForge project does not contain the DataBridge service
  schemas. If the matching DataBridge source or documentation is unavailable, do
  not infer handler fields; request the deployed DataBridge version and reference
  source.

## Minimal Synchronous Usage

```python
from datetime import date
from oeds.domain.utils.ingest.client.dis_client import DisClient

client = DisClient(
    host="https://adb-xxxxxxxxxxxx.x.azuredatabricks.net",
    azure_tenant_id="<tenant-id>",
    azure_client_id="<client-id>",
    azure_client_secret="<client-secret>",
    azure_workspace_resource_id="/subscriptions/.../resourceGroups/.../providers/Microsoft.Databricks/workspaces/...",
    dis_job_id=123456789,
)

config = """
{
  "pipeline": "storage_volume_to_volume",
  "tasks": [
    {
      "id": "upload",
      "handler": "oedis.handler.storage.upload",
      "params": {
        "connection": {
          "uri": "/Volumes/dev_application_cat/oedisint_db/land-oedataservices/dis/data-copy/"
        },
        "requests": [
          {
            "recursive": true
          }
        ]
      }
    }
  ]
}
""".strip()

ingest_result = client.ingest(
    config=config,
    rundate=date(2026, 3, 20),
    params={"batch": "daily"},
)

print(ingest_result.status)
print(ingest_result.get_job_run_id())
print(ingest_result.get_job_run_page_url())
print(ingest_result.get_task_notebook_output())
```

## Two-Stage Template Rendering

`DisClient.resolve_config_template(...)` renders a config template before you
submit it.

Client-side template markers:

- variables: `[[ ... ]]`
- blocks: `[% ... %]`
- comments: `[# ... #]`

```python
from oeds.domain.utils.ingest.client.dis_client import DisClient

config_template = """
{
  "pipeline": "storage_volume_to_volume",
  "tasks": [
    {
      "id": "upload",
      "handler": "oedis.handler.storage.upload",
      "params": {
        "connection": {
          "uri": "[[ landing_dir ]]"
        },
        "requests": [
          {
            "dst_dir": "[[ rundate ]]",
            "recursive": true
          }
        ]
      }
    }
  ]
}
""".strip()

resolved_config = DisClient.resolve_config_template(
    config_template=config_template,
    template_params={
        "landing_dir": "/Volumes/dev_application_cat/oedisint_db/land-oedataservices/dis/data-copy",
        "rundate": "2026-03-20"
    },
)
```

The resolved string must still be valid JSON before it is passed to `ingest()`.

This client-side pass is separate from DataBridge server-side templating:

| Stage | Markers | Values available |
| --- | --- | --- |
| DataForge client | `[[ ... ]]`, `[% ... %]`, `[# ... #]` | `template_params` passed to `resolve_config_template(...)` |
| DataBridge service | `{{ ... }}`, `{% ... %}`, `{# ... #}` | `runtime`, including `runtime.rundate` and `runtime.job_params`, plus DataBridge template functions |

Use client-side markers for values DataForge already knows before submission.
Leave server-known values in server-side markers inside JSON string values. The
custom client markers prevent the first rendering pass from consuming DataBridge
markers. Both stages use strict undefined handling, so a missing value fails the
stage that owns it.

For example, this value combines a client-selected root with a server-selected
run date:

```json
{
  "path": "[[ landing_root ]]/{{ runtime.rundate }}"
}
```

## ingest(...) Parameters

`DisClient.ingest(...)` accepts:

| Parameter | Default | Behavior |
| --- | --- | --- |
| `config` | required | Non-empty, syntactically valid JSON string submitted to DataBridge. |
| `rundate` | `None` | A `datetime.date` sent as `YYYY-MM-DD`; `None` is sent as an empty string and DataBridge defaults it to the current date in its runtime timezone. |
| `params` | `None` | JSON-serializable dictionary sent to DataBridge as `runtime.job_params`; `None` becomes an empty object on the server. |
| `debug` | `False` | Sent as `"true"` or `"false"`; DataBridge debug mode increases logging and preserves its staging directories. Keep it `False` for normal production runs. |
| `compress_notebook_output` | `False` | Sent as the `zip` parameter and requests a compressed notebook exit payload. |
| `wait` | `True` | Wait for a terminal job state when true; return immediately after submission when false. |
| `wait_timeout_sec` | `3600` | Maximum client wait in seconds; must be greater than zero. |
| `wait_poll_sec` | `10` | Job polling interval in seconds; must be greater than zero. |

`params` values must be JSON serializable. Pass a dictionary, not a pre-encoded
JSON string.

Job parameters sent to Databricks are:

- `config`
- `rundate`
- `params`
- `debug`
- `zip`

## Waiting vs Non-Waiting

When `wait=True`:

- the method waits for terminal state
- the returned status can be `SUCCESS`, `FAILED`, or `TIMEOUT`
- `job_run_output` and `task_run_output` are populated when available
- a completed failed job returns `FAILED`; it is not raised as an `IngestServiceError`
- `TIMEOUT` means the client stopped waiting and has not fetched job or task
  output; it does not cancel the underlying Databricks run

When `wait=False`:

- the returned `IngestResult.status` is `RUNNING`
- `job_run_id` is available
- `job_run_output`, `task_run_output`, and notebook output are not available yet
- the returned object does not refresh itself; monitor the run separately or use
  synchronous submission when a terminal result is required

Example:

```python
ingest_result = client.ingest(
    config=config,
    wait=False,
)

print(ingest_result.status)
print(ingest_result.get_job_run_id())
```

## Reading Results

`client.ingest(...)` returns an `IngestResult`.

Useful fields:

- `ingest_result.status`
- `ingest_result.job_id`
- `ingest_result.job_parameters`
- `ingest_result.job_run_output`
- `ingest_result.task_run_output`

Useful helper methods on `IngestResult`:

- `get_status()`
- `get_job_id()`
- `get_job_parameters()`
- `get_job_run_id()`
- `get_job_run_output()`
- `get_job_run_page_url()`
- `get_task_run_id()`
- `get_task_run_output()`
- `get_task_run_error()`
- `get_task_run_error_trace()`
- `get_task_notebook_output()`
- `get_nb_task_result(task_id)`
- `get_nb_task_result_dst(task_id)`
- `get_nb_task_result_dst_path(task_id)`

Example:

```python
ingest_result = client.ingest(config=config)

print("status:", ingest_result.status)
print("job run id:", ingest_result.get_job_run_id())
print("page url:", ingest_result.get_job_run_page_url())
print("task run id:", ingest_result.get_task_run_id())
print("task error:", ingest_result.get_task_run_error())
print("notebook output:", ingest_result.get_task_notebook_output())
print("upload result:", ingest_result.get_nb_task_result("upload"))
print("upload dest objects:", ingest_result.get_nb_task_result_dst("upload"))
print("upload dest paths:", ingest_result.get_nb_task_result_dst_path("upload"))
```

Result availability depends on how the call finished:

| Status | Run ID | Job/task output | Notebook output |
| --- | --- | --- | --- |
| `RUNNING` | Available | Not available | Not available |
| `TIMEOUT` | Available | Not available | Not available |
| `SUCCESS` | Available | Available when returned by Databricks | Parsed from task output when valid |
| `FAILED` | Available | Available when returned by Databricks | Usually absent; inspect the task error and trace |

`get_task_notebook_output()` parses plain JSON or `zlib:<base64>` output and
caches a successfully parsed dictionary. It returns `None` when output is absent,
malformed, or not a JSON object. The task-result helpers also return `None` when
the requested task or result shape is unavailable; destination helpers return an
empty list when the task exists but has no destinations.

Expected notebook output pattern:

```json
{
  "status": "success",
  "task_results": {
    "upload": {
      "task_id": "upload",
      "handler": "oedis.handler.storage.upload",
      "status": "success",
      "outputs": [
        {
          "dest": {
            "type": "file",
            "path": "/Volumes/dev_application_cat/oedisint_db/land-oedataservices/dis/data-copy/file.csv",
            "size": 12031
          }
        }
      ],
      "metrics": {
        "total_items": 1,
        "total_duration_sec": 0.123
      }
    }
  }
}
```

The lowercase `status` in this notebook payload is the DataBridge response contract.
It is distinct from the uppercase Databricks run status on `IngestResult`.

## File Verification

`DisClient` verifies landed files with `verify_file_by_file_size(...)`.
This method uses destination records from a prior successful `IngestResult`,
or from an explicit `expected_files` list supplied by the caller.

Verification checks exact path and byte size only. It does not compare content,
hashes, modification times, or directory contents beyond the expected paths.

Requirements:

- when `expected_files` is not supplied, `client.ingest(...)` must already have completed successfully
- when `expected_files` is not supplied, the target task must have file destinations in `outputs[].dest`
- every expected item must include a non-empty `path` and a non-negative,
  int-like `size`
- `expected_files` must not be empty
- `dest_dir_path` and `land_dir_path` must be supplied together or both omitted
- remapped expected paths must be below `dest_dir_path`
- use canonical absolute paths such as `/Volumes/...`; returned `dbfs:/` listing
  paths are normalized for comparison, but caller-supplied expected paths are not

```python
ingest_result = client.ingest(config=config)

verify_result = client.verify_file_by_file_size(
    dest_dir_path="/Volumes/dev_application_cat/oedisint_db/land-oedataservices/dis/data-copy",
    land_dir_path="/Volumes/dev_application_cat/oedisint_db/land-oedataservices/dis/data-final",
    timeout_sec=300,
    poll_sec=10,
    upload_task_key="upload",
)

print(verify_result.status)
print(verify_result.is_success)
print(verify_result.matched)
print(verify_result.unmatched)
```

To verify with known destination records without relying on the current client
`ingest_result`, pass the `outputs[].dest` list directly:

```python
verify_result = client.verify_file_by_file_size(
    expected_files=[
        {"type": "file", "path": "/Volumes/dev_application_cat/oedisint_db/land-oedataservices/dis/data-final/a.csv", "size": 12031},
    ],
    timeout_sec=300,
    poll_sec=10,
)
```

Behavior:

- expected metadata is copied, paths are stripped, and sizes are converted to integers
- when both base paths are present, the `dest_dir_path` prefix is replaced by
  `land_dir_path` before polling
- each distinct parent directory is listed once per poll attempt
- a directory-listing error is treated as no match for that attempt and is retried
- if every expected file appears with the expected size, status is `SUCCESS`
- if polling reaches the timeout first, status is `TIMEOUT`
- `VerifyResult.expected` contains the normalized and, when requested, remapped
  records used for verification
- `matched` and `unmatched` contain the final poll's records
- the returned object is also stored on `client.verify_result`

Calling `ingest(...)` starts a new client cycle and clears both the prior
`client.ingest_result` and `client.verify_result`. Verification without explicit
`expected_files` therefore always uses the most recent successful ingest call.

## Exceptions

The client defines these explicit exception types:

- `IngestBaseError`
- `IngestValueError`
- `IngestServiceError`
- `IngestVerifyError`

Typical guidance:

- catch `IngestValueError` for client-detected value errors such as empty or
  malformed JSON and invalid verification arguments
- catch `IngestServiceError` for Databricks submission, wait, or task retrieval
  failures; a Databricks run that completes unsuccessfully is returned as
  `IngestResult(status="FAILED", ...)` instead
- catch `IngestVerifyError` when verification cannot use the current ingest state

Outbound file preparation uses `oeds.core.file_utils` and propagates its input,
Spark, and storage exceptions rather than adding a DataBridge-specific exception.

Public methods use strict Pydantic call validation. A wrong argument type can
raise `pydantic.ValidationError` before the method body runs, so it is not wrapped
in `IngestBaseError`. Likewise, a non-JSON-serializable value in `params` can
raise a serialization error. Catch those separately when inputs are not already
trusted and type checked.

## Troubleshooting

`config must be a valid JSON string`

- render templates first
- confirm the final string is valid JSON
- confirm it matches the DataBridge pipeline shape

`wait_timeout_sec must be greater than 0` or `wait_poll_sec must be greater than 0`

- pass positive integers only

`No ingest_result is available. Call ingest() before verification.`

- run `client.ingest(...)` before `verify_file_by_file_size(...)`, or pass `expected_files`

`ingest_result status must be SUCCESS before verification`

- when `expected_files` is not supplied, verification only runs against a completed successful ingest result

The call returned `FAILED` without raising an exception

- this is expected for a Databricks job that reached a failed terminal state
- inspect `get_task_run_error()` and `get_task_run_error_trace()`, then raise the
  workflow-specific exception if failure should stop the caller

The call returned `TIMEOUT` but the Databricks run is still active

- client timeout does not cancel the run
- use `get_job_run_id()` to inspect or monitor it in Databricks

Notebook output is missing or cannot be parsed

- confirm the Databricks notebook returned JSON through `dbutils.notebook.exit(...)`
- if compression was requested, confirm the payload was returned as `zlib:<base64>`

File verification always reaches `TIMEOUT`

- confirm every expected record has the correct byte size
- confirm expected paths use `/Volumes/...` or another canonical absolute path
- when upload output and final landing roots differ, pass matching
  `dest_dir_path` and `land_dir_path` values
- check the Databricks logs for directory-listing failures, which are retried until timeout

## Recommended Usage Pattern

1. Build or render the final config JSON string.
2. Call `client.ingest(...)` with `debug=False` for normal production runs.
3. Check the returned status explicitly and handle `SUCCESS`, `FAILED`, and `TIMEOUT`.
4. Read notebook output only after `SUCCESS`.
5. If needed, call `client.verify_file_by_file_size(...)` and require
   `verify_result.is_success`.
6. Catch the custom ingestion exceptions plus Pydantic or serialization errors
   when caller input is not already validated.
