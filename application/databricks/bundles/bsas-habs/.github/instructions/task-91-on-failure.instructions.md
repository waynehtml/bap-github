---
applyTo: "jobs/dataflow/task_91_on_failure.py"
---

# Task 91: On Failure

Before modifying this task:

1. Follow the [DataForge instructions](../../AGENTS.md).
2. Inspect the [DATAFLOW workflow definition](../../resources/jobs/dataflow.yml).
3. Read the [Dataflow Job Guide](../../docs/guide/G201-dataflow-job-guide.md).
4. When implementing notifications, read the [Email Module Developer Guide](../../docs/guide/G303-email-developer-guide.md) and inspect the [DataForge email example](../../examples/email/send_email.py).
5. Inspect [task_91_on_failure.py](../../jobs/dataflow/task_91_on_failure.py).

## Documentation status

There is no dedicated failure-handler process guide or separate sample task notebook. The current task notebook is an intentional placeholder.

## Source-of-truth rules

- Treat `resources/jobs/dataflow.yml` as authoritative for which failed stages can trigger this task.
- Use the workflow guide for failure-stage boundaries and the email guide for notification APIs.
- Preserve the original processing failure as the primary troubleshooting signal.
- Do not infer notification recipients, incident targets, audit destinations, or cleanup policies.

## Implementation behavior

- Limit work to failure notification, incident or audit recording, and cleanup that is safe after partial processing.
- Use `EmailManager` and configured registries when email is requested; do not build transport payloads directly.
- Do not retry or reimplement failed processing stages here.
- Do not let notification or cleanup failures obscure the original pipeline failure.
- Ask for clarification when the required notification, incident, audit, or cleanup behavior cannot be resolved from the request and repository context.
