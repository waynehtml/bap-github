# Email

## When to use this capability

Use `EmailClient` when the approved transport is an Azure Logic App endpoint. Use `GraphEmailClient` when the workload sends directly through Microsoft Graph with service-principal authentication.

## Choose the public API

| Need | Choose |
| --- | --- |
| Logic App delivery, HTML templates, or DataFrame-to-HTML/CSV conversion | `EmailClient` |
| Direct Graph delivery with a sender mailbox and raw-byte attachments | `GraphEmailClient` |
| Distinguish accepted Graph requests from failures | `GraphEmailSendResult` and `GraphEmailSendError` |
| Handle Logic App composition or submission failures | `EmailSendError` |

## Restrictions and side effects

Both clients send external email. They make one request with no retry or idempotency key, so retrying an ambiguous failure can create duplicate messages. The Logic App client treats any HTTP 2xx response as success. Graph requires HTTP 202, which means accepted for processing rather than confirmed delivery.

Resolve endpoint URLs and service-principal values from an approved secret provider. Never place them in source, examples, or logs. Recipient syntax is not validated. The Graph client does not support CC, BCC, automatic retry, or upload sessions; direct attachments must be smaller than 3 MiB and the compact request must not exceed 4 MiB.

Logic App attachment and HTML helpers fully collect a PySpark DataFrame to the driver through `toPandas`, so use only bounded data. Template reads support Workspace, Volume, and ADLS locations through the file utilities. Template substitution leaves missing placeholders unchanged. Debug logging from template sends includes resolved recipients and a body prefix; do not enable it for sensitive content.

## Short example

```python
from oeds.core.email_graph_client import GraphEmailClient

client = GraphEmailClient(
    tenant_id=get_secret("mail_tenant_id"),
    client_id=get_secret("mail_client_id"),
    client_secret=get_secret("mail_client_secret"),
    sender="sender@example.org",
)
result = client.send_email(
    recipients=["recipient@example.org"],
    subject="Pipeline completed",
    body="<p>The pipeline completed successfully.</p>",
)
print(result.status)
```

`get_secret` represents the workload's approved secret-provider integration; it is not supplied by this library.

## Related examples

- [Graph usage pattern in this guide](#short-example)
- [File templates and paths](files.md)
