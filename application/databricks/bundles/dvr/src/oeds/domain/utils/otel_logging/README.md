# Direct OTLP logging with end-to-end Entra authentication

Python source for CORRA and DataForge. Put DataForge's `src` directory on
each workload's Python path and import the `oeds.domain.utils.otel_logging`
package. No wheel or package build is required.
No Zerobus SDK, Databricks SDK, MSAL, Collector, or native App Telemetry dependency.

```
Python logging -> OTel handler -> batch processor -> OTLP/gRPC -> Zerobus
                                                      ^
Entra tenant/client/secret -> Entra token -> scoped Databricks token
                              cached              cached
```

## Scope and prerequisites

The helper implements both token requests, separate thread-safe caches, early
renewal, failure backoff, dynamic gRPC credentials, batched logs, and cleanup.
No caller-supplied token helper is needed. It never selects the injected
`DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, a PAT, or an app-local identity.
Disable native App Telemetry separately. Existing handlers are preserved, so this
helper does not disable other telemetry paths you have already enabled.

This is custom integration, not an official Databricks exporter. The scoped
exchange matches the source of Databricks SDK PR #760 (still open when checked
September 17, 2026); this implementation does not depend on merging that PR.
Local tests are not a live workspace validation. Complete a DEV smoke test before
production use.

Required administrative setup:

1. An approved Entra service principal with a current client secret.
2. The same Entra application/client ID must identify the approved Databricks
   service principal used for workload identity federation. This implementation
   assumes the Entra `appId` equals the Databricks service principal `application_id`
   (verified for the intended deployment). The principal must have a federation
   policy matching the source token's issuer, audience, and subject. No Databricks
   OAuth secret is needed. Jobs/SQL access with an Entra token alone does not
   establish the federation policy.
3. A managed Delta table with the OTLP logs v2 schema and explicit USE CATALOG,
   USE SCHEMA, SELECT, and MODIFY grants. See `setup.sql`; it is not auto-executed.
4. Supported workspace/region and TLS connectivity to Entra, the workspace token
   endpoint, and Zerobus. gRPC requires an HTTP/2-capable network path.

A federation policy is an administrator action, not something a client secret can
create or bypass. A template to populate from securely verified claims:

```json
{
  "oidc_policy": {
    "issuer": "<actual-iss-claim>",
    "audiences": ["<actual-aud-claim>"],
    "subject": "<actual-sub-claim>"
  }
}
```

The source Entra token uses the Azure Databricks resource scope
`2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default` internally. The resulting token
claims still must match the configured federation policy. Never paste tokens into
public JWT tools or log them.

## Usage

Resolve capitalized values from approved deployment configuration/secret storage:

```python
import logging
from oeds.domain.utils.otel_logging.otel_logging_utils import (
    ZerobusLoggingConfig, configure_logging,
)

runtime = configure_logging(
    tenant_id=ENTRA_TENANT_ID,
    client_id=ENTRA_CLIENT_ID,
    client_secret=ENTRA_CLIENT_SECRET,
    workspace_url=WORKSPACE_URL,
    table_name="application.oedataservices_db.otel_logs",
    config=ZerobusLoggingConfig(
        endpoint=ZEROBUS_ENDPOINT,
        service_name="corra",               # optional label
        environment="DEV",                  # optional label, not routing
        resource_attributes={"dataset": "corra"},  # optional
    ),
)
logger = logging.getLogger("corra")
logger.info("Processing completed", extra={"row_count": 42})
```

Use the standard Azure Databricks workspace host format, for example
`https://adb-1234567890123456.12.azuredatabricks.net`. The helper extracts the
numeric workspace ID (`1234567890123456`) from that validated host only to build
the unchanged Zerobus OAuth resource. No Azure ARM resource ID or caller-supplied
workspace ID is required. The OTLP/gRPC endpoint is separate, for example
`https://1234567890123456.zerobus.eastus.azuredatabricks.net:443`. These are
examples, not your deployed values. No `/v1/logs` path is used for gRPC.

Only `endpoint` is required in `ZerobusLoggingConfig`. Missing service name becomes
`unknown_service`; missing environment means no environment attribute. Custom
resource attributes support scalar strings/numbers/booleans. The helper does not
replace the global OTel provider or import ambient resource attributes. It attaches
its own handler to the root logger by default; `logger_name` restricts it to a
namespace. Existing handlers remain. Non-propagating loggers need explicit setup
on their namespace. Set `level=logging.DEBUG` when DEBUG records are wanted.
This captures Python logging, not arbitrary print output or Spark executor logs.

`preflight_auth=True` (default) acquires both tokens at initialization, failing
visibly on bad credentials/policy. It is not a test of the table-write path.
Subsequent background export failures are reported locally and in SDK counters;
they do not replace business exceptions.

## CORRA App

`example_app.py` uses these explicit environment settings:

```
LOGGING_ENTRA_TENANT_ID
LOGGING_ENTRA_CLIENT_ID
LOGGING_ENTRA_CLIENT_SECRET     # approved App secret resource, not a Git literal
ZEROBUS_WORKSPACE_URL
ZEROBUS_ENDPOINT
ZEROBUS_TABLE_NAME
LOGGING_SERVICE_NAME            # optional; example defaults to corra
LOGGING_ENVIRONMENT             # optional
```

Call `get_app_logging()` at process startup. Equal repeated configuration returns
the same runtime, including Streamlit reruns. Do not shut down after each user
request or rerun. Use a process-stop hook when available; atexit is a graceful-exit
fallback only. Per-request IDs and submitted-job context go in `extra`, not shared
process resource attributes. Initialize after worker processes start, not before
forking. Secret rotation requires a new configured secret/restart, or a stable,
thread-safe, bounded callable secret supplier.

## DataForge tasks

Initialize in every task's Python process, including retries. Close that runtime
in a `finally` block around the actual task body. Do not pass it to Spark workers.
`example_notebook.py` reads non-secret values from widgets and the secret from
`dbutils.secrets.get` on the notebook thread. Configure task base parameters:

```yaml
job_id: "{{job.id}}"
job_run_id: "{{job.run_id}}"
task_name: "{{task.name}}"
task_run_id: "{{task.run_id}}"
```

Also supply `logging_entra_tenant_id`, `logging_entra_client_id`,
`logging_secret_scope`, `logging_secret_key`, `zerobus_workspace_url`,
`zerobus_endpoint`, and `zerobus_table_name`. Never pass a secret as a task
parameter. Job and task run IDs are distinct. The example rejects unresolved
`{{...}}` values. Do not put cleanup only in a final cell that may never run.

## Token lifecycle and operational limits

The secret is sent only to Microsoft's token endpoint. Databricks receives the
subject token, plus `scope=all-apis`, the unchanged workspace `zerobusDirectWriteApi` resource,
and table-scoped `authorization_details` with `operations=["zerobuswrite"]`.
Neither secret nor token is stored in the log table by this helper.

Both caches use reported expiry and a monotonic clock. Renewal is lazy on the next
export, up to five minutes early (clamped to 10% for short-lived tokens), with a
30-second minimum-validity margin in the high-level initializer. Unverified JWT
`exp` only shortens cache lifetime; it is never used to authorize. Databricks token
lifetime is capped at the source token's remaining life. Entra client credentials
produce no refresh token: renewal makes another client-credentials request.

A lock serializes concurrent renewal. Transient errors can reuse an older token
only while still valid, with short backoff. Expired tokens are never fallback.
Normal renewal does not rebuild the exporter. `runtime.invalidate_tokens()` clears
both caches after early revocation or corrected trust configuration. The standard
OTLP export result does not expose an authentication-specific failure status, so
this wrapper does not blindly refresh/replay every failed batch.

HTTPS certificate validation stays enabled and OAuth redirects are refused.
Response bodies/tokens are not logged. `oauth_timeout_seconds` bounds socket
operations, not the full wall-clock duration. A slow refresh can delay a batch.
Use `oauth_ca_file` and `config.tls_root_certificates` for corporate CA trust;
there is no disable-TLS-verification option. A callable secret supplier runs on
the auth thread: it must not invoke notebook-only APIs there.

This is best-effort asynchronous logging, not durable queuing or exactly-once audit
logging. Queue overflow, retries, remote partial rejection, outages, and abrupt
termination can lose or duplicate records. SDK SUCCESS is not proof of every
record's persistence or Delta materialization. `runtime.stats()`, `flush()`, and
`shutdown()` return SDK outcome counters; unaccounted records can be pending or
dropped. The pinned batch flush is not a hard wall-clock deadline. Stop producers
before final shutdown. Exporter/auth-library namespaces are excluded from this
sink to avoid recursion; existing local handlers still see them. Keep secrets and
sensitive data out of application log messages.

## Dependencies and verification

Install `requirements.txt` through your approved process. The OTel API and SDK
alone are insufficient: the OTLP/gRPC exporter and grpcio must be present. The
source does not install dependencies automatically. OTel 1.42.1 provides the SDK
LoggingHandler used here but emits deprecation warnings; review this bridge before
upgrading, and keep OTel package versions aligned.

For DEV, with DataForge's `src` on the Python path, configure the notebook
example as a task. Query its printed `smoke_test_id` with `setup.sql`.
Verify message visibility, run metadata, and authorized identity. No live workspace
validation has been performed as part of this implementation.

## Primary references (checked September 17, 2026)

- Entra client credentials:
  https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow
- Federation policy and exchange:
  https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-federation-policy
  https://learn.microsoft.com/en-us/azure/databricks/dev-tools/auth/oauth-federation-exchange
- OTLP endpoint, headers, schema, grants:
  https://learn.microsoft.com/en-us/azure/databricks/ingestion/opentelemetry/configure
- SDK exchange reference (PR source, not a released API):
  https://github.com/databricks/zerobus-sdk/pull/760
  https://github.com/databricks/zerobus-sdk/blob/72aad55bd227d8255d7e0e70826878fe2b39c433/rust/sdk/src/default_token_factory.rs
- gRPC call credentials:
  https://grpc.io/docs/guides/auth/
- OTel exporter API:
  https://opentelemetry-python.readthedocs.io/en/latest/_modules/opentelemetry/exporter/otlp/proto/grpc/_log_exporter.html
- Job metadata:
  https://learn.microsoft.com/en-us/azure/databricks/jobs/dynamic-value-references
