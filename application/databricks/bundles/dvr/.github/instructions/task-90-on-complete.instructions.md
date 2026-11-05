---
applyTo: "jobs/dataflow/task_90_on_complete.py"
---

# Task 90: On Complete

Before modifying this task:

1. Follow the [DataForge instructions](../../AGENTS.md).
2. Inspect the [DATAFLOW workflow definition](../../resources/jobs/dataflow.yml).
3. Read the [Dataflow Job Guide](../../docs/guide/G201-dataflow-job-guide.md).
4. When implementing notifications, read the [Email Module Developer Guide](../../docs/guide/G303-email-developer-guide.md) and inspect the [DataForge email example](../../examples/email/send_email.py).
5. Inspect [task_90_on_complete.py](../../jobs/dataflow/task_90_on_complete.py).

## Documentation status

There is no dedicated completion-handler process guide or separate sample task notebook. The current task notebook is an intentional placeholder.

## Source-of-truth rules

- Treat `resources/jobs/dataflow.yml` as authoritative for the success and early-completion paths that can reach this task.
- Use the workflow guide for completion-stage responsibilities and the email guide for notification APIs.
- Do not infer notification recipients, audit targets, cleanup behavior, or downstream triggers.

## Implementation behavior

- Keep completion actions idempotent because this task can run after a normal finish, a stage skip, or graceful early completion.
- Use `EmailManager` and configured registries when email is requested; do not build transport payloads directly.
- Do not add failure recovery or core business transformations to this task.
- Ask for clarification when the requested completion action, recipients, audit destination, cleanup scope, or downstream trigger cannot be resolved from the request and repository context.
