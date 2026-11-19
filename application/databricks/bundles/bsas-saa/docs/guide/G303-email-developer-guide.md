# Email Module Developer Guide

This guide explains how Dataforge developers send registry-based or direct HTML
email through `oeds.domain.utils.email.email_utils.EmailManager`. The manager
owns the developer-facing composition workflow; the DataKit Logic App and
Microsoft Graph clients remain transport-only. The optional DataBridge provider
submits a synchronous email job using the same composition interface.

## Mental Model

`EmailManager` supports two composition workflows:

1. `send_email` selects configured recipients, subject, and an HTML template
   from the email registry, then renders its variables.
2. `send_direct_email` accepts recipient addresses, a subject, and a raw HTML
   body directly without loading the registry or a template.

Both workflows convert optional transport-neutral attachments and send through
the configured provider.

Keep reusable notification policy in the registry and use direct messages only
when the recipients and content are intentionally caller-owned. Do not build
Logic App or Graph payloads in workflow notebooks. Dataforge application code
should use `EmailManager`; call the DataKit clients directly only when
developing or testing the transport layer.

## Key Locations

- [email_utils.py](../../src/oeds/domain/utils/email/email_utils.py): `EmailManager`, registry resolution, rendering, DataFrame conversion, and attachment conversion.
- [default.json](../../conf/oeds/config/email/default.json): packaged email registry.
- [template directory](../../conf/oeds/config/email/template/): packaged HTML templates.
- [send_email.py](../../examples/email/send_email.py): runnable Dataforge example.
- [common.py](../../common.py): shared Logic App configuration bootstrap.
- [send_email_databridge.py](../../examples/email/send_email_databridge.py): opt-in DataBridge initialization and sending.
- [ingest/email.json](../../conf/oeds/config/ingest/email.json): DataBridge email pipeline template.
- [DataKit Logic App email API](../reference/datakit/api/email_client.md): Logic App transport.
- [DataKit Microsoft Graph email API](../reference/datakit/api/email_graph_client.md): Microsoft Graph transport.

## Developer Interface

Configure one provider and create a caller-owned manager through
`EmailManager.initialize(...).get_instance()`.
`EmailProvider` is the public `Literal["logicapp", "graph", "databridge"]` type alias; callers
pass the corresponding string value at runtime.

| API | Purpose |
| --- | --- |
| `EmailManager.initialize(...)` | Store normalized configuration and return the manager class for optional chaining. |
| `EmailManager.get_instance()` | Create a caller-owned manager from the active configuration. |
| `get_email_registry(template_ref)` | Reload and resolve one registry entry and its mapped recipient addresses. |
| `df_to_email_table(dataframe)` | Convert a pandas or PySpark DataFrame into a styled HTML table. |
| `send_email(...)` | Resolve, render, attach, and send one configured message. |
| `send_direct_email(...)` | Attach and send caller-supplied recipients, subject, and raw HTML body. |

Both send methods are keyword-only and return `None`. Configuration,
rendering, attachment, authentication, and transport failures are raised to
the caller.

## Quick Start With A Caller-Owned Manager

The common notebook eagerly resolves the configured service URL secret and
configures the Logic App provider with `email_mappings`. After loading the
common notebook, create a manager through `EmailManager`:

```python
# Databricks notebook: %run ../../common

import pandas as pd

from oeds.domain.utils.email import EmailManager

email_manager = EmailManager.get_instance()

failure_details = pd.DataFrame(
    [
        {"step": "extract", "status": "completed"},
        {"step": "load", "status": "failed"},
    ]
)

email_manager.send_email(
    template_ref="failure",
    variables={
        "ENV": job_ctx.get("env", "dev").upper(),
        "audit_skey": "123456789",
        "code": "LOAD_FAILED",
        "state": "FAILED",
        "message": "The standardized load failed.",
        "email_table_html": failure_details,
    },
    attachments=[
        {
            "name": "failure-details.csv",
            "content": failure_details,
            "content_type": "text/csv",
        }
    ],
)
```

When a variable value is a pandas or PySpark DataFrame, the manager automatically renders it as an HTML table. When an attachment value is a DataFrame, the manager automatically converts it to UTF-8 CSV.

## Direct HTML Email

Use `send_direct_email` when the caller owns the recipients and complete HTML
body and no registry entry is appropriate:

```python
email_manager.send_direct_email(
    recipients=["analyst@example.org", "support@example.org"],
    subject="Daily processing status",
    body="""
        <html>
        <body>
          <h2>Processing completed</h2>
          <p>The daily pipeline completed successfully.</p>
        </body>
        </html>
    """,
)
```

Direct sending uses the same initialized manager and provider connection as a
configured send. The current bootstrap requirements still apply, including
prior `ConfigManager` initialization and `recipient_mappings` supplied to
`EmailManager.initialize()`.

- `recipients` accepts a comma- or semicolon-delimited string or a sequence of
  non-empty address strings.
- Addresses are stripped but are not syntax-validated. Order and duplicates
  are preserved.
- `subject` is stripped and must be non-empty.
- `body` must contain non-whitespace content and is sent unchanged as HTML.
  Dollar signs are literal; direct content is not template-rendered or escaped.
  The DataBridge server trims surrounding whitespace from inline body content.
- Only To recipients are supported; CC, BCC, and reply-to fields are not
  modeled.
- Registry JSON, recipient mappings, and template resources are not read while
  composing a direct message.

## Email Registry

The registry is a JSON object packaged under `oeds.config.email`. Each top-level key is a stable `template_ref` used by application code:

```json
{
  "failure": {
    "template": "template/failure.html",
    "subject": "$ENV - JOB FAILURE",
    "recipients": ["OPERATIONS", "DATA_SUPPORT"]
  },
  "daily_summary": {
    "template": "template/daily_summary.html",
    "subject": "$ENV - Daily summary for $business_date",
    "recipients": ["OPERATIONS"]
  }
}
```

Every entry must define:

| Field | Contract |
| --- | --- |
| `template` | Non-empty path relative to the packaged email config directory. |
| `subject` | Non-empty `string.Template` subject. |
| `recipients` | Non-empty list of recipient mapping keys. |

Use registry keys for message intent, such as `failure`, `success`, or `daily_summary`. Keep environment-specific addresses outside the registry.

### Use Another Registry File

Pass `config_file` during initialization when a project packages another JSON
registry beside `default.json`:

```python
email_manager = EmailManager.initialize(
    provider="logicapp",
    connection={"logicapp_url": logicapp_url},
    config_file="operations.json",
    recipient_mappings=recipient_mappings,
).get_instance()
```

The config package is fixed at `oeds.config.email`. Registry files and
referenced templates must be included in that package at deployment time.
Provider initialization stores the selected registry filename without reading
it. Every `get_email_registry` call reloads and validates the registry, and
every `send_email` call reloads both the registry and referenced template.
Missing resources, malformed JSON, and invalid definitions therefore fail at
lookup or send time rather than during initialization.

### Inspect A Registry Entry

Use `get_email_registry` to load and validate the current configuration or preview resolved metadata:

```python
definition = email_manager.get_email_registry("failure")
print(definition["template"])
print(definition["subject"])
print("recipient count:", len(definition["recipients"]))
```

The returned dictionary contains the template path, configured subject, and resolved addresses. Avoid printing or logging the actual address list in normal pipeline runs.

## Recipient Mappings

Recipient mappings separate stable registry keys from environment-specific addresses:

```python
recipient_mappings = {
    "OPERATIONS": "operations@example.org",
    "DATA_SUPPORT": "data-support@example.org",
}
```

In the template bundle, `email_mappings` remains a JSON string in `job_ctx`.
`common.py` parses it during provider configuration and logs only the number of
configured entries.

Resolution behavior is intentional:

- Keys and addresses must be non-empty strings.
- Keys are case-sensitive after surrounding whitespace is removed.
- Addresses are not syntax-validated by EmailManager; invalid addresses may be rejected by the provider.
- Recipient keys missing from the mapping are skipped and logged at `debug` level.
- At least one configured key must resolve, or `get_email_registry` raises `ValueError`.
- `send_email` does not accept ad hoc recipients; use `send_direct_email` when
  the caller intentionally owns the address list.
- The current interface has one recipient collection and does not model separate To, CC, or BCC lists.

Do not put service credentials or endpoint URLs in recipient mappings.

## HTML Templates And Variables

Templates are body-only HTML resources loaded from the packaged config directory. Subjects live in the registry, although callers may override them.

```html
<html>
<body>
  <h2>$ENV processing failure</h2>
  <p>Batch: <strong>${audit_skey}</strong></p>
  <p>$message</p>
  $email_table_html
</body>
</html>
```

Subject and body rendering use Python `string.Template.safe_substitute`:

- Use `$name` or `${name}` for variables.
- Use `$$` for a literal dollar sign.
- `None` becomes an empty string.
- DataFrame values become HTML tables.
- Other values are substituted as supplied.
- An invalid placeholder expression raises `ValueError`.
- A missing variable remains as its literal placeholder; it does not fail automatically.

Because missing variables remain visible, test every registry entry with its expected variables before deployment. Application code should build a complete variable mapping for the chosen `template_ref`.

Raw string variables are not HTML-escaped by `EmailManager`. Escape untrusted text before inserting it into HTML. Cell values rendered through pandas `to_html` use pandas HTML escaping by default.

### Override The Subject

Pass `subject` to replace the registry subject for one send. The override uses the same variables:

```python
email_manager.send_email(
    template_ref="daily_summary",
    subject="$ENV - Reprocessed summary for $business_date",
    variables={
        "ENV": "DEV",
        "business_date": "2026-07-21",
    },
)
```

An empty rendered subject or body raises `ValueError`.

## DataFrames As HTML Tables

Convert a DataFrame explicitly when the HTML is needed before the send:

```python
html_table = email_manager.df_to_email_table(summary_df)

email_manager.send_email(
    template_ref="daily_summary",
    variables={
        "ENV": "DEV",
        "business_date": "2026-07-21",
        "email_table_html": html_table,
    },
)
```

Or pass the DataFrame directly as the variable value and let `_normalize_variables` call `df_to_email_table`.

The rendered table has no index and uses inline borders and cell padding. PySpark DataFrames are converted with `toPandas()`, which collects every selected row to the driver. Select only required columns and use a deliberate row limit before rendering large or unbounded Spark results.

## Attachments

Both send methods accept the same transport-neutral attachment definitions:

```python
attachments = [
    {
        "name": "summary.csv",
        "content": summary_df,
        "content_type": "text/csv",
    },
    {
        "name": "notes.txt",
        "content": "The batch completed with warnings.",
        "content_type": "text/plain",
    },
]

email_manager.send_email(
    template_ref="daily_summary",
    variables={
        "ENV": "DEV",
        "business_date": "2026-07-21",
    },
    attachments=attachments,
)
```

Supported `content` types are:

| Content | Conversion |
| --- | --- |
| `str` | UTF-8 bytes. |
| `bytes` | Used directly. |
| `bytearray` | Converted to bytes. |
| pandas DataFrame | UTF-8 CSV with headers and no index. |
| PySpark DataFrame | Collected with `toPandas()`, then converted to UTF-8 CSV. |

The manager base64-encodes attachment bytes and builds the provider payload.
Attachment names and content must be non-empty. File paths are not attachment
content; read a file into bytes before calling either send method.

`content_type` is optional. Graph uses it or infers a MIME type from the filename. The Logic App payload contains only `Name` and `ContentBytes`, so `content_type` does not change that transport payload.

### Attachment Limits

- Graph direct attachments must be smaller than 3 MiB before base64 encoding.
- The complete Graph request must not exceed 4 MiB.
- Larger Graph attachments require an upload-session workflow, which `EmailManager` does not implement.
- `EmailManager` does not impose a Logic App attachment-size limit; the deployed Logic App and its downstream connector may impose their own limits.
- Spark attachments collect data to the driver. Export large datasets to governed storage and email a link instead.

## Choose An Email Provider

| Concern | Logic App | Microsoft Graph | DataBridge |
| --- | --- | --- | --- |
| Connection | `logicapp_url` | Graph credentials and sender | `DisConnectionOptions`, staging settings, Graph secret references, and sender |
| Credentials | Secret Logic App URL | Entra tenant, client ID, and client secret | Job-access credentials; Graph credentials resolved inside DataBridge |
| Success | Any HTTP 2xx response | HTTP 202 Accepted | Successful job, validated by `run_ingest` |
| Transport error | `EmailSendError` | `GraphEmailSendError` | `IngestTaskError` with chained underlying errors |
| Attachments | Inline base64 | Inline base64 with MIME type | Shared Volume to inbox; generic MIME type |
| Send method return | `None` | `None` | `None` |

### Logic App

The shared `common.py` path configures Logic Apps. In a standalone driver,
configure the provider explicitly:

```python
from oeds.domain.utils.email import EmailManager

logicapp_url = dbutils.secrets.get(
    scope=secret_scope,
    key="email-logicapp-url",
)

email_manager = EmailManager.initialize(
    provider="logicapp",
    connection={"logicapp_url": logicapp_url},
    recipient_mappings=recipient_mappings,
).get_instance()
```

The DataKit client posts JSON containing `to`, `subject`, `htmlBody`, and `attachments`. A non-2xx response or request failure raises `EmailSendError`.

### Microsoft Graph

Initialize Graph in a standalone driver, or customize the project common
notebook to initialize Graph instead of Logic Apps:

```python
from oeds.domain.utils.email import EmailManager

email_manager = EmailManager.initialize(
    provider="graph",
    connection={
        "tenant_id": dbutils.secrets.get(scope=secret_scope, key="graph-tenant-id"),
        "client_id": dbutils.secrets.get(scope=secret_scope, key="graph-client-id"),
        "client_secret": dbutils.secrets.get(
            scope=secret_scope,
            key="graph-client-secret",
        ),
        "sender_email": dbutils.secrets.get(
            scope=secret_scope,
            key="graph-sender-email",
        ),
        "request_timeout_sec": 30,
    },
    recipient_mappings=recipient_mappings,
).get_instance()
```

Each initialization replaces the configuration used by future managers without
modifying existing managers. Calling `get_instance()` before initialization
raises `RuntimeError`. Every send constructs a fresh Graph client and Azure
credential, so Azure Identity's in-memory token cache is not reused between
sends and credential cleanup relies on normal object finalization.

The service principal must be authorized to send through the configured sender mailbox. A successful Graph response means the request was accepted; it does not guarantee final delivery. EmailManager send methods return `None`, so the underlying Graph request ID is available through transport logs or `GraphEmailSendError`, not as the manager result.

Do not hardcode tenant IDs, application IDs, client secrets, sender addresses, access tokens, or Logic App URLs in notebooks or repository files.

## Error Handling

Configuration and composition problems raise `TypeError` or `ValueError`. A
missing registry or template, malformed registry JSON, or invalid registry
definition is reported by the first lookup or send that uses it, not by
`EmailManager.initialize()`. Provider failures propagate from the DataKit
clients:

```python
from oeds.core.email_client import EmailSendError
from oeds.core.email_graph_client import GraphEmailSendError

try:
    email_manager.send_email(
        template_ref="failure",
        variables=variables,
        attachments=attachments,
    )
except (TypeError, ValueError) as exc:
    logger.exception("Invalid email configuration or content")
    raise NotificationError("Unable to compose notification email") from exc
except (EmailSendError, GraphEmailSendError) as exc:
    logger.exception("Email provider rejected the notification")
    raise NotificationError("Unable to send notification email") from exc
```

Use the project-specific exception type that owns the notification workflow; `NotificationError` above is illustrative. Preserve exception causes and stack traces.

The transport clients do not provide an idempotency key. Automatic retries after an ambiguous network failure can send duplicate messages, so retry only with an explicit workflow policy.

When email runs inside a failure handler, do not let a notification exception hide the original pipeline failure. Log the notification failure and preserve the original task error as the primary failure.

## Operational And Security Guidance

- Keep service URLs and credentials in the configured secret store.
- Keep environment-specific configured-send addresses in recipient mappings,
  not registry files or templates.
- Log template references, provider names, recipient counts, and attachment counts instead of complete payloads.
- Do not log secrets, rendered bodies, attachment contents, access tokens, or full recipient mappings.
- Treat rendered body variables and validation samples as potentially sensitive.
- Keep email tables and attachments small enough for driver memory and provider limits.
- Validate registry JSON and template variables during deployment or release testing.
- Prefer stable registry keys so workflow code does not depend on filenames or addresses.
- Use direct sends only when the caller is intended to own the recipient list
  and complete HTML content.

## Developer Checklist

- The chosen registry file is packaged under `oeds.config.email`.
- Every registry entry has a template, subject, and non-empty recipient key list.
- Every template path exists and the expected variables are documented.
- Recipient mappings resolve at least one address for every deployed environment.
- Secrets are read from the configured secret store and never logged.
- The provider configuration matches the intended transport.
- Spark DataFrames are bounded before HTML or CSV conversion.
- Graph attachments and total request size stay within direct-send limits.
- Provider errors are wrapped without losing the original cause.
- Failure-notification errors do not replace the original pipeline failure.

## Related Guides

- [Common Notebook Guide](G203-common-notebook-guide.md): configure the Logic App email provider.
- [Dataflow Job Guide](G201-dataflow-job-guide.md): integrate notifications into completion and failure stages.
- [Init Project Guide](G101-init-project-guide.md): configure bundle variables, secret keys, and JSON recipient mappings.


## DataBridge Provider

Use `provider="databridge"` to send through the existing DataBridge job. The
common notebook still initializes Logic App by default; opt in after loading
it. Both send methods retain their existing parameters and return `None`.
The sender belongs to the configured service identity and has no per-message
override.

Configure the following bundle variables under **Email service settings**,
after `email_service_url_key` and the `DataBridge email service` comment:

| Job-context field | Meaning / default |
| --- | --- |
| `oeds_secrete_scope` | Existing OEDS scope, used directly for Graph secret references. Must exist in the target DataBridge workspace. |
| `databridge_email_tenant_id_key` | Secret key for the Graph tenant ID; default empty. |
| `databridge_email_client_id_key` | Secret key for the Graph client ID; default empty. |
| `databridge_email_client_secret_key` | Secret key for the Graph client secret; default empty. |
| `databridge_email_sender_account` | Approved sender mailbox; default empty. |
| `tmp_root` | Shared staging root, default `/Volumes/${var.catalog}/reference_db/vol_${var.project.tag}_land/tmp/${var.project.dataset}`. |

Blank email-service values are rejected only when initializing DataBridge.
Scope and key names are secret references, not secret values. They are checked
for nonblank text but are inserted directly into quoted Jinja expressions, so
configure identifiers without quotes or template syntax. Graph credentials are
resolved by DataBridge, separately from the SPN used to call its job.

Create `dis_connection` using `DisConnectionOptions` and the target workspace
host, Azure tenant/client credentials, `azure_workspace_resource_id`, and job
ID. The [complete notebook example](../../examples/email/send_email_databridge.py)
uses the internal DataBridge connection from `job_ctx`.

```python
EmailManager.initialize(
    provider="databridge",
    connection={
        "dis_connection": dis_connection,
        "ingest_config_file": "email.json",
        "tmp_root": job_ctx["tmp_root"],
        "job_run_id": job_ctx["job_run_id"],
        "sender_email": job_ctx["databridge_email_sender_account"],
        "graph_secret_scope": job_ctx["oeds_secrete_scope"],
        "graph_tenant_id_key": job_ctx["databridge_email_tenant_id_key"],
        "graph_client_id_key": job_ctx["databridge_email_client_id_key"],
        "graph_client_secret_key": job_ctx["databridge_email_client_secret_key"],
    },
    config_file="default.json",
    recipient_mappings=recipient_mappings,
)
email_manager = EmailManager.get_instance()
email_manager.send_direct_email(
    recipients="alice@example.com;bob@example.com",
    subject='Daily "Sales" report',
    body="<p>The report is attached.</p>",
    attachments=[{"name": "report.csv", "content": "account,total\nA,100\n"}],
)
```

The two filenames select different resources:

- `config_file` selects the existing registry in `oeds.config.email`.
- `connection.ingest_config_file` selects the ingestion template in
  `oeds.config.ingest` and defaults to `email.json`. It is loaded on each send,
  with ConfigManager's environment override and shared-fallback behavior.

Optional connection settings are `wait_timeout_sec=1800`, `wait_poll_sec=10`,
and `max_total_attachment_bytes=10485760`. Waiting settings must be positive
integers; the byte cap is a nonnegative integer. The provider uses `run_ingest`
with `debug=True` and `verification=None`; the helper submits the job with
`wait=True`. Debug mode enables additional logging and retains DataBridge
inbox directories separately from the caller's staging files.

### Staging and template contract

EmailManager renders registry subjects and bodies locally and normalizes To
recipients to an array. The body is passed in `message.body.content`, not saved
as a file. JSON serialization preserves quotes, backslashes, Unicode, and
embedded newlines. Literal server template markers in composed messages are
protected through both DataBridge rendering stages.

Attachments are converted to bytes and written directly under
`<tmp_root>/<caller-job-run-id>/<guid>/<filename>`. Both jobs need access to the
existing Volume; the caller also needs write access. The DataBridge transport
rejects duplicate filenames, path components in names, and totals above the
configured cap. It has no separate per-file size or empty-content check.
EmailManager still rejects empty content and files at or above 3 MiB before
passing attachments to this transport.

The template receives `src_dir` (the full staging directory, or `None`),
`secret_scope`, `tenant_id_key`, `client_id_key`, `client_secret_key`,
`sender_literal`, `recipient_literals`, `subject_literal`, `body_literal`, and
`max_total_attachment_bytes`. Use `tojson` for the message values without extra
quotes. Secret references use the separate server-side `keyvault()` expressions.
The template is Jinja text and only becomes valid JSON after rendering.

The supplied pipeline downloads all staged files directly into the inbox and
then sends inbox files as attachments, excluding Hadoop checksum sidecars
matching `.*.crc` that may be created during download. It has no file-validation task.
With no attachments it sends only the email task and creates no staging folder.
Custom templates must run the email handler and propagate its failures to the
job. The provider does not inspect task IDs or individual task results. Keep
the inbox exclusive to the intended attachments.

### Completion and retention

The provider relies on `run_ingest` to require a successful job. The helper
handles config loading, rendering, submission, job failures, and waiting
timeouts; its `IngestTaskError` exceptions propagate with their original causes.
No individual email-task result is checked. Success confirms job completion,
not recipient delivery. The provider does not automatically resubmit emails.

Staged files remain in place after success, failure, timeout, or partial staging.
An externally managed lifecycle policy is responsible for deleting those files
and directories; the provider does not configure that policy. A timeout or
submission error may leave the job running, so inspect its status before retrying.
Config-loading or rendering failures can also leave staged attachments in place.

Existing server limitations apply: unreadable attachments may be skipped,
attachment MIME types are `application/octet-stream` even when `content_type`
is supplied, and inline body edges are trimmed. The raw-byte cap is not a
Graph request-size guarantee. DataBridge currently logs resolved email task
parameters, including credentials and message content; this provider does not
change that server behavior. Sender authorization is enforced by the service's
mailbox permissions, not by bundle configuration alone.
