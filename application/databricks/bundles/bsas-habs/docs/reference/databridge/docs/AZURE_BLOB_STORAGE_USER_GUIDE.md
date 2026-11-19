# Azure Blob Storage

Handlers:

- `oedis.handler.azureblobstorage.download`
- `oedis.handler.azureblobstorage.upload`

These handlers transfer files directly through the Azure Blob Storage SDK. They
do not use Spark or `dbutils.fs`, so they work with flat-namespace Blob Storage
accounts and do not require hierarchical namespace (HNS). HNS-enabled accounts
are also supported through their Blob endpoint.

## Authentication and authorization

The handlers support explicit Microsoft Entra service-principal credentials in
`connection`:

```json
{
  "connection": {
    "uri": "wasbs://container@account.blob.core.windows.net",
    "tenant_id": "{{ keyvault(scope='oedis-kv', key='azure-tenant-id') }}",
    "client_id": "{{ keyvault(scope='oedis-kv', key='azure-blob-client-id') }}",
    "client_secret": "{{ keyvault(scope='oedis-kv', key='azure-blob-client-secret') }}"
  }
}
```

All three fields must be supplied together as non-empty strings. The handler
uses `ClientSecretCredential` when they are present. Resolve the values through
the DataBridge `keyvault()` template function; never store a literal client secret
in checked-in configuration.

When these fields are omitted, the handler uses `DefaultAzureCredential` from
the Databricks runtime. The runtime identity must be available to the Azure
Identity credential chain and must have data-plane access to the target account
or container.

Databricks job `run_as` does not by itself make that principal available to
Azure Identity inside notebook Python. Configure and verify one of the
credential sources supported by `DefaultAzureCredential`. On Databricks
Runtime 16.2 or later, one option for classic compute is a Unity Catalog
service credential selected through the cluster environment variable
`DATABRICKS_DEFAULT_SERVICE_CREDENTIAL_NAME`; the task principal must have
`ACCESS` on that credential. Standard Azure Identity environment, workload,
or managed-identity configuration can also be used when available. Validate
the selected identity on each target cluster before enabling production jobs.

- Downloads require a role such as **Storage Blob Data Reader**.
- Uploads require a role such as **Storage Blob Data Contributor**.

An Azure management-plane role alone does not grant Blob data access. Network
routing, firewall rules, DNS, and private endpoints must also allow the cluster
to reach the account's Blob endpoint.

`connection.uri` must not contain a query string or fragment. SAS tokens and
other credentials embedded in the URI are explicitly rejected. Azure Storage
shared account keys are not supported. Use the explicit service-principal
fields or configure the runtime identity used by `DefaultAzureCredential`.

## Supported URI forms

For Blob accounts without HNS, prefer the HTTPS Blob endpoint:

```text
https://account.blob.core.windows.net/container/optional/base-prefix
```

The following storage URI forms are also accepted:

```text
wasbs://container@account.blob.core.windows.net/optional/base-prefix
wasb://container@account.blob.core.windows.net/optional/base-prefix
abfss://container@account.dfs.core.windows.net/optional/base-prefix
abfs://container@account.dfs.core.windows.net/optional/base-prefix
```

For `abfss`, `abfs`, or HTTPS DFS URLs, the handler converts the
`.dfs.core.windows.net` host to `.blob.core.windows.net` and uses the Blob SDK.
The URI must identify a container. Its path after the container is the optional
base prefix used by every request in the task.

Hosts are restricted to recognized Azure Storage DNS suffixes before a bearer
credential is created. Custom domains, emulators, and Azure Stack-specific
endpoints are not accepted by this handler.

## Storage-compatible configuration

The configuration shape and file-selection behavior match
`oedis.handler.storage`.

### Task fields

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `connection.uri` | Yes | none | Azure Blob container URI with an optional base prefix. Query strings and fragments are rejected. |
| `connection.tenant_id` | No | runtime identity | Microsoft Entra tenant ID. Required when either other service-principal field is supplied. |
| `connection.client_id` | No | runtime identity | Microsoft Entra application client ID. Required when either other service-principal field is supplied. |
| `connection.client_secret` | No | runtime identity | Microsoft Entra application client secret. Required when either other service-principal field is supplied. Resolve it through `keyvault()`. |
| `requests` | Yes | none | One or more transfer request objects. |

### Common request fields

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `include` | No | `["*"]` | Glob pattern or list of patterns to include. |
| `exclude` | No | `[]` | Glob pattern or list of patterns to exclude. Exclusion takes precedence. |
| `recursive` | No | `false` | Include nested virtual directories or local directories. |

`include` and `exclude` accept either a string or a list of strings. With
`recursive: false`, only direct child files are considered and patterns match
file names. With `recursive: true`, patterns match both file names and paths
relative to the resolved source root. A matching included directory includes
its descendants, while a matching excluded directory excludes its descendants.

Use `recursive: true` with simple patterns such as `"*.csv"` when all matching
files below the source root should be selected. Selected files retain their
path relative to that source root beneath the destination root.

Request `src_dir` and `dst_dir` values must be relative. Absolute paths, full
URIs, Windows drive paths, and paths containing `..` are rejected. An omitted
or empty value resolves directly to the applicable inbox or Blob base prefix.

## Download

`oedis.handler.azureblobstorage.download` resolves each request as follows:

- Remote source prefix = `connection.uri` base prefix + `src_dir`
- Local destination root = `ctx.inbox` + `dst_dir`

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `src_dir` | No | `""` | Blob source prefix relative to the URI base prefix. |
| `dst_dir` | No | `""` | Destination directory relative to `ctx.inbox`. |
| `include` | No | `["*"]` | Blob selection pattern or patterns. |
| `exclude` | No | `[]` | Blob exclusion pattern or patterns. |
| `recursive` | No | `false` | When false, nested blob names are skipped. |

The handler creates required local directories, overwrites an existing local
destination file, and verifies the downloaded size against Blob metadata.

See
[`azureblobstorage_download_basic.json`](../examples/azureblobstorage_download_basic.json).

## Upload

If an upload request's source directory is missing while the runtime inbox is
valid, the request is logged at INFO and skipped. Empty directories and filters
matching no files also succeed with zero uploads. Other requests continue normally.
Invalid source paths, permission errors, and subsequent listing or transfer errors
still fail. Connection setup is unchanged and may fail even when no files exist.

`oedis.handler.azureblobstorage.upload` resolves each request as follows:

- Local source root = `ctx.inbox` + `src_dir`
- Remote destination prefix = `connection.uri` base prefix + `dst_dir`

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `src_dir` | No | `""` | Source directory relative to `ctx.inbox`. |
| `dst_dir` | No | `""` | Blob destination prefix relative to the URI base prefix. |
| `include` | No | `["*"]` | Local file selection pattern or patterns. |
| `exclude` | No | `[]` | Local file exclusion pattern or patterns. |
| `recursive` | No | `false` | When false, nested local files are skipped. |

Uploads use `overwrite=True`; an existing blob with the resolved destination
name is replaced. A non-directory local source root raises an error.

See
[`azureblobstorage_upload_basic.json`](../examples/azureblobstorage_upload_basic.json).

## Results and failures

Both handlers return the standard `TaskResult`:

- `status` is `success` when every selected transfer completes.
- `outputs` contains one item per file with `src`, `dest`, sizes, and
  `duration_sec`.
- Blob paths in results use secret-free HTTPS Blob URLs.
- `metrics.total_items` is the number of transferred files.
- `metrics.total_duration_sec` is total handler duration.

A request that matches no files succeeds with `total_items` equal to zero.
Invalid configuration, authentication or authorization failures, listing
errors, transfer errors, and size mismatches are raised so the DataBridge engine can
record the task failure with its normal error contract.
