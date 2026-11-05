# App core clients

| Module | Purpose |
|---|---|
| `workspace` | `create_workspace_client`: explicit AAD or current-user token authentication. |
| `job` | `DatabricksJobClient`: job operations using a supplied workspace client. |
| `sql` | SQL connector operations with independent AAD/OBO authentication. |
| `utils` | Existing app utility functions. |

See the [workspace client guide](../../../../../docs/guide/G401-app-template-guide.md)
for authentication arguments, ownership, and job-client examples.
