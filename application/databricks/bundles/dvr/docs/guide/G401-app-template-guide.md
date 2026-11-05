# App Template Guide

The [main app](../../apps/main) is a self-contained Streamlit starter with a Home
page and reusable SQL, job, date, and confirmation utilities. All environment settings are optional.
Home starts without backend configuration and makes no backend calls. Replace its welcome content as the project grows.

## Ownership and layout

| Location under `apps/main` | Responsibility |
| --- | --- |
| `app.py` | Page configuration, sidebar navigation, and current user display. |
| `pages/home.py` | Initial page; add project pages alongside it. |
| `libs/app/environment.py` | Immutable workspace and backend settings. |
| `libs/app/context.py` | Current forwarded user metadata and token. |
| `libs/common/core/sql.py` | Explicitly configured `DatabricksSQLClient`. |
| `libs/common/core/job.py` | Explicitly configured `DatabricksJobClient`. |
| `libs/common/core/utils.py` | Date formatting, parsing, and previous-weekday helpers. |
| `libs/common/ui/confirm_dialog.py` | Confirmation callbacks with one execution per opening. |

Common libraries do not import project settings or request context. Project code
may import common libraries. Keep business services under `libs/app` as needed;
do not add placeholder service classes. The common code is copied into each
project, with no runtime dependency on a sibling bundle or central package.

## Local startup and settings

Run from the generated project's `apps/main` directory using PowerShell:

```powershell
python -m venv .venv
& .venv/Scripts/python.exe -m pip install streamlit
```

Use Streamlit 1.38.0 or a compatible later version for the navigation, dialog,
and request-header APIs used here. Match the deployed runtime when validating
project changes. The shell needs only Streamlit and its dependencies. Projects
that use the backend clients also need these packages locally:

```powershell
& .venv/Scripts/python.exe -m pip install databricks-sdk databricks-sql-connector pandas pyarrow requests
```

The hosted [requirements file](../../apps/main/requirements.txt) intentionally
installs no packages. Check that the target Databricks Apps runtime supplies the
libraries required by the features you enable; local execution does not verify hosted
package availability.

`Environment.from_env()` loads optional settings when the module initializes and
creates the immutable `ENV` snapshot. Restart the app after changing settings.
Validation does not authenticate, connect to SQL, or check that resources exist.
Missing or blank settings are unset. Invalid supplied values still fail validation.

| Source | Optional properties |
| --- | --- |
| Process environment | `DATABRICKS_WORKSPACE_ID`, `DATABRICKS_HOST`, `JOB_ID`, `SPN_TENANTID`, `SPN_ID`, `SPN_SECRET` |
| Process environment | `ENV_NAME`, `DATABRICKS_WAREHOUSE_ID`, `UC_CATALOG_NAME`, `AZURE_WORKSPACE_RESOURCE_ID` |

Backend properties default to `None`. A supplied nonblank `JOB_ID` must parse as a positive integer.
The bundle template does not bind a job or inject `JOB_ID`; projects that need
job operations can supply that optional setting explicitly.
SQL authentication is selected explicitly for each client using its `auth_mode`
argument: `aad` or `obo`. There is no application-wide authentication
mode. SQL and job clients validate the properties required for their operation when constructed.

The loader reads each setting directly from its process environment variable.
Missing or blank settings remain `None`, and the workspace ID does not select
configuration. Legacy `ENV_<workspace_id>` JSON variables are ignored; migrate
local launchers and existing app configurations to the individual variables
when adopting this loader. Errors name the invalid setting without including
its value. SPN fields are excluded from `repr(ENV)`, but the settings
object still contains credentials: never serialize or log it. User identity and
tokens remain in the separate request context.

Streamlit does not load `app.yml` for a local launch. Home needs no environment
variables; after installing Streamlit, run:

```powershell
& .venv/Scripts/python.exe -m streamlit run app.py
```

Configure only the settings needed by your project features. The optional example
below shows workspace configuration. Supply credentials through your secure local
launcher when constructing a service-principal client:

```powershell
$env:DATABRICKS_WORKSPACE_ID = '<workspace-id>'
$env:DATABRICKS_HOST = '<workspace-hostname-without-https>'
$env:JOB_ID = '<positive-job-id>'
$env:ENV_NAME = 'local'
$env:DATABRICKS_WAREHOUSE_ID = '<warehouse-id>'
$env:UC_CATALOG_NAME = '<catalog-name>'
$env:AZURE_WORKSPACE_RESOURCE_ID = '<azure-workspace-resource-id>'
& .venv/Scripts/python.exe -m streamlit run app.py
```

Hosted settings come from `resources.apps.MAIN.config` in the
[app resource template](../../resources/apps/main.yml) and the Databricks runtime.
The source [app.yml](../../apps/main/app.yml) is an empty placeholder. Configure
the catalog before enabling app deployment. The warehouse ID
and Azure workspace resource ID are injected from OEDS secrets identified by
`sql_warehouse_serverless_large_id_key` and `internal_databricks_resource_id_key`.
Do not store credential values in YAML or source files.

## Pages and request context

Create a page in `pages/` and register it with `st.Page` in `app.py`. Keep Home as
the default page and use `st.navigation` for routing. Use `st.text` for forwarded
user metadata, so it is not interpreted as markup. Avoid displaying process
environment variables or raw backend exception messages.

Call `RequestContext.current()` during each page execution that needs user
metadata. It reads the current forwarded username, email, user ID, and token;
missing headers remain `None`. Do not store this context, its token, or an OBO
client in session state, a global variable shared across requests, or a Streamlit
resource cache. The token is excluded from the context's representation, but is
still sensitive and must not be serialized or logged.

Forwarded display identity does not grant application permissions. This starter
has no role model or authorization database. Before adding privileged actions,
implement project-specific authorization in the backend service as well as page
access checks. Local headers are not evidence of a trusted hosted identity.

## Backend clients

Construct clients explicitly inside project services when a feature needs them.
Do not instantiate them at shell startup. Supply a hostname without `https://`
and obtain secrets from deployment resources or your local credential provider.

`DatabricksSQLClient` takes `host`, `warehouse_id`, optional `catalog`, and an
explicit `auth_mode`:

- `aad`: Entra client credentials using `tenant_id`, `client_id`, and
  `client_secret`. Use `aad` for Azure Active Directory (Entra) authentication.
- `obo`: the current request's Databricks access token in `user_token`. Enable
  the required hosted user authorization and SQL permissions for this feature.
  There is no fallback to service credentials if user authentication fails.

The SQL constructor validates settings without connecting. `query(statement,
parameters=...)` returns a pandas DataFrame; `execute(statement, parameters=...)`
executes one command. Bind values through parameters rather than interpolating
SQL. Each call owns its connection; multiple calls do not share a transaction.
`query` does not enforce read-only SQL. Query sessions use UTC timestamps.

`DatabricksJobClient` takes `host`, positive integer `job_id`, Azure workspace
`resource_id`, `tenant_id`, `client_id`, and `client_secret`. It initializes the
SDK client at construction and always uses Entra service credentials. It does not
inherit SQL authentication mode or use the current user's token.

`run(job_parameters=..., idempotency_token=...)` returns a submitted run ID;
reuse the token when retrying the same logical submission. `cancel` requests
asynchronous cancellation. Run lookup/status methods preserve the copied client
contract: `RUNNING`, `FAILED`, or `SUCCESS`, original parameter names and values,
millisecond timing fields, and available task failure details. A
`SUCCESS_WITH_FAILURES` result maps to `SUCCESS` and may include `task_error`.
Treat task errors and parameters as potentially sensitive; do not display or log
them indiscriminately. SDK and SQL failures propagate to the caller.

The date helpers retain their existing behavior. `get_last_weekday` returns the
previous Monday-to-Friday date strictly before the supplied date, without holiday
calendar handling.

For confirmations, call `confirm_dialog.show` only inside the action branch that
opens the dialog. Provide a stable key and an `on_confirm` callback. Explicit
Cancel may invoke `on_cancel`; dismissing the dialog does not. A callback is
consumed before execution, so failures propagate without executing it twice in
the same opening. This UI behavior is not backend idempotency or authorization.

## Bundle app configuration and activation

The [app resource template](../../resources/apps/main.yml) owns the app's command,
environment, and resource bindings. It uses the name `${bundle.name}-app` and
points to `apps/main`. Choose a bundle name that yields a valid Databricks App
name, or customize the app name in the generated project.

Target-specific app permissions grant `CAN_MANAGE` to
`lake_aeengsupport_rusr_inda` in dev and `lake_aeengsupport_rusr_inpa` in staging
and production. These grants are defined under each target's `resources.apps.MAIN`
in the app resource template.

Ordinary environment settings use `value` with bundle variable substitutions.
Named resource bindings use `value_from` in the bundle configuration. The
`valueFrom` spelling used in standalone app configuration does not apply here.
Remove unused bindings and resources in generated projects that do not need
them. Optional Python settings do not provision deployment resources:

| App resource | Environment variable | Permission |
| --- | --- | --- |
| `spn-tenantid` | `SPN_TENANTID` | `READ` on the configured secret |
| `spn-id` | `SPN_ID` | `READ` on the configured secret |
| `spn-secret` | `SPN_SECRET` | `READ` on the configured secret |
| `azure-workspace-resource-id` | `AZURE_WORKSPACE_RESOURCE_ID` | `READ` on the configured OEDS secret |
| `sql-warehouse-id` | `DATABRICKS_WAREHOUSE_ID` | `READ` on the configured OEDS secret |

Before enabling app deployment, configure `resources/apps/main.yml`:

- `UC_CATALOG_NAME` uses `${var.catalog}`, and `ENV_NAME`
  comes from `${bundle.target}`. Databricks supplies the host and workspace ID at
  runtime. The loader does not use the workspace ID to choose settings, so deploy
  the target to its intended workspace.
- `DATABRICKS_WAREHOUSE_ID` uses the `sql-warehouse-id` secret binding. It reads
  `${var.sql_warehouse_serverless_large_id_key}` from `${var.oeds_secrete_scope}`,
  defaulting to `databricks-sql-warehouse-serverless-large` in
  `lake-kv-oedataservices-scope`. Ensure the secret contains the target warehouse
  ID and that the app-managed principal can read it.
- `AZURE_WORKSPACE_RESOURCE_ID` uses the `azure-workspace-resource-id` secret
  binding. It reads the key `${var.internal_databricks_resource_id_key}` from
  `${var.oeds_secrete_scope}`. The defaults are
  `databricks-uc01-workspace-resource-id` in `lake-kv-oedataservices-scope`.
  Ensure that secret contains the resource ID for the target workspace and that
  the app-managed principal can read it. No resource ID is hardcoded in the app
  resource configuration.
- Replace `{{app_spn_tenantid_key}}`, `{{app_spn_id_key}}`, and
  `{{app_spn_secret_key}}` for the project and target. These remain initialization
  placeholders, not bundle variable expressions. Use existing secret key names,
  never secret values.
- Provision the existing secrets in the scope referenced by `app_secrete_scope`.
  Its default is `lake-kv-${var.project.tag}app-scope`, for example
  `lake-kv-tritonapp-scope`. The variable follows the template's existing
  `secrete_scope` spelling. It is defined after `oeds_secrete_scope` in
  `default.databricks.yml` and is not passed to job context. Declaring it does
  not create a Databricks secret scope or Azure Key Vault.

The default job bundle does not activate the app: `apps/**` and
`resources/apps/**` remain excluded from synchronization, and no app resource
include is added. Project initialization must later select the app resource,
allow its source files to sync, and resolve its placeholders. The existing
initialization workflow is unchanged. The v3 pipeline selects `start_app` after
successful deployment to start configured apps. An empty `app.yml`
does not provide a standalone launch command; hosted deployment must supply the
bundle configuration. A bundle deployment provisions the resource and syncs
files; `databricks bundle run MAIN --target <target>` starts or restarts the app.

## Starting Bundle Apps

The `start_app` script in [resources/scripts/app.yml](../../resources/scripts/app.yml)
is selected by `post_deploy_scripts` for dev, staging, and production. It receives
`DEPLOY_TARGET`, validates the bundle with JSON output, and invokes
`databricks bundle run <resource-key> --target <target>` for each configured app,
in alphabetical resource-key order. The resource key can differ from the deployed
app name. Each command starts or restarts the app with its latest deployed code.

No configured apps is a successful no-op. Validation, JSON parsing, or command
failures stop execution without retrying or rolling back earlier requests.
Success confirms submission of all start/restart requests; it does not verify
app health or poll startup status. The deployment agent's CLI and inherited
authentication are used without a Python Databricks SDK dependency.

The v3 pipeline invokes the post-deploy hook only after successful deployment;
plain `bundle deploy` does not invoke it. Startup selection does not include app
resources or enable source synchronization. Use target configuration or inherited
`BUNDLE_VAR_*` overrides; outer `--var` arguments are not forwarded to nested
validation or run commands. To invoke startup explicitly:

```powershell
databricks bundle run start_app --target dev
```

## Restoring app secret-scope access

The optional `restore_app_secret_access` script in
[resources/scripts/app.yml](../../resources/scripts/app.yml) runs inline Python on the
deployment agent using the installed Databricks CLI and its authentication.
No Python Databricks SDK is required. Use a CLI version supporting `scripts.env`
(the v3 pipeline requires 1.8.0 or later).

The script resolves the selected bundle with `bundle validate --output json`,
finds all configured apps by their resolved names, and reads the workspace app
inventory through `apps list --output json`. The CLI follows all inventory pages.
For each matching app, it uses `service_principal_client_id` to apply `READ` to
`APP_SECRET_SCOPE`, supplied from `${var.app_secrete_scope}`. It does not query
existing ACLs or retrieve secret values. Apps absent from the inventory are
skipped, allowing first-time deployment; a bundle without app resources is a
successful no-op. The deployment identity must retain visibility of all bundle
apps so an inaccessible app is not mistaken for an absent one.

Bundle validation, inventory, invalid principal metadata, and permission-grant
failures stop the script. An earlier successful grant is not rolled back if a
later app fails. The deployment identity needs `MANAGE` on the secret scope.
`READ` replaces the app principal's existing explicit scope permission, even if
it was `WRITE` or `MANAGE`, and applies to all secrets in that scope. Keep only
app-appropriate credentials in the app scope.

The repair script only handles `app_secrete_scope`. It does not restore access
to the OEDS secrets used by `azure-workspace-resource-id` and
`sql-warehouse-id`; maintain that access separately. Each declared OEDS secret
binding requests `READ` on its configured secret.

The template selects `restore_app_secret_access` in `pre_deploy_scripts` for
dev, staging, and production. Dev runs `deploy_databench_config` first; all
three targets select `start_app` after deployment. Selection variables and target overrides
are centralized in [default.databricks.yml](../../default.databricks.yml).
This selection does not enable app deployment: repair is a successful no-op
when no apps are configured. In initialized projects, edit the active
`databricks.yml`, preserving the full ordered list when adding scripts because
overrides replace the whole list. To invoke the repair explicitly:

```powershell
databricks bundle run restore_app_secret_access --target dev
```

Use target configuration or inherited `BUNDLE_VAR_*` environment variables for
overrides needed by the nested bundle validation; an outer command's `--var`
arguments are not forwarded. Repair happens only when invoked; later platform
cleanup can remove the grant again. A new app is skipped until its managed
service principal exists; keep the declared secret resources for initial setup.

The app-managed Databricks principal reads the credential secrets. The injected
Entra service principal remains the backend client identity. Resource bindings
and scope repair do not grant that Entra principal warehouse, catalog, job, or
Azure resource permissions. Configure those permissions separately. Before
promotion, test initial deployment, re-deployment after ACL removal, runtime
secret injection, and enabled backend features in a development workspace.

## Local verification

Launch the app locally without backend settings and confirm that Home renders
with the fixed `DataForge` title. Configure the optional workspace values,
restart the app, and confirm that the environment label reflects `ENV_NAME`.
Customize the title directly in `app.py` and `pages/home.py` when needed.

Verify backend features in a development workspace using the authentication mode
and permissions intended for each client. Existing generated projects need their
own reviewed migration from the legacy app imports.
