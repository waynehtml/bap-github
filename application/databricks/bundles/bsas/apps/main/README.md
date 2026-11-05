# DataForge app development

Open this `apps/main` folder in VS Code so `${workspaceFolder}` resolves here.
Install the Microsoft Python and Python Debugger extensions.

## Local setup

Install Conda once using your organization's approved distribution, initialize
your shell for Conda, and open a new terminal. Configure corporate Conda channels
for Python and pip before running setup; the Nexus PyPI repository is not a
Conda channel. No public channels are added by this project.

Run from this folder in Command Prompt:

```cmd
setup-env.cmd
conda activate databriks-app-3.11
```

In PowerShell, use `.\setup-env.cmd`, then the same activation command.
Setup creates or updates the named environment, installs additional requirements,
and runs `pip check`. Run it again after dependency changes. It updates on every
invocation without deleting or pruning your existing environment.

Setup uses the corporate Nexus endpoint already configured in the bundle for
both pip indexes, overriding any public extra index. This applies to pip packages
in both dependency files. Like the cluster setup, pip trusts the corporate Nexus
host without certificate verification. These settings apply only while the script
runs; offline settings are preserved. Conda's certificate configuration is separate
and is not changed by pip's trusted-host setting.

Copy the example only on first setup; preserve an existing `.env`:

```powershell
Copy-Item .env.example .env
```

Fill in `.env` with your workspace settings and credentials. All 10 fields read by
`Environment` are listed; blank values remain unset. `JOB_ID`, if supplied, must be
a positive OPERATION job ID. The example includes non-secret dev workspace,
warehouse, and catalog settings. SPN credentials and the
deployment-specific `JOB_ID` remain blank. Clients validate settings when used.

## VS Code interpreter

Run **Python: Select Interpreter** and select `databriks-app-3.11`. If it is not
listed, use **Enter interpreter path** with the path printed by:

```cmd
conda run -n databriks-app-3.11 python -c "import sys; print(sys.executable)"
```

The existing debug configuration uses the selected interpreter. Do not commit a
developer-specific interpreter path. Terminal activation is not required for F5.
This environment name is shared with DataPort; changes affect both local apps.

## Dependencies and deployment

- `environment.yml` is for local Conda development only. It specifies Python 3.11,
  pip, and the three runtime libraries used by this app: Streamlit 1.38.0,
  Databricks SDK 0.33.0, and SQL connector 3.4.0.
- These versions match the [Databricks Apps preinstalled library documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/dependencies),
  checked on October 19, 2026. Pandas, requests, and pyarrow are installed as
  dependencies of these libraries; their exact transitive versions are not locked.
- `requirements.txt` contains only additional application packages, each pinned
  with `==`. It currently contains only comments because no additions are needed.
  Do not duplicate the runtime package declarations.
- Databricks installs `requirements.txt` on top of its preinstalled libraries.
  Deployment does not execute `setup-env.cmd` or consume `environment.yml`.
  Existing deployment Nexus/wheelhouse configuration remains unchanged; the local
  script's Nexus settings do not configure the deployed app.

To add or upgrade an additional library, change its exact pin in
`requirements.txt`, rerun setup, and test the app. Change runtime library pins in
`environment.yml` only after checking the official Apps versions and deployment
compatibility. Do not replace either file with a full `pip freeze` export.

## Troubleshooting

- **Conda unavailable or activation fails:** open a terminal initialized for your
  Conda installation and verify `conda --version`.
- **Package download fails:** check corporate network access, channel
  configuration and Nexus package availability. For Conda's `ssl_verify does not
  contain a valid file path` error, correct the certificate-bundle path in your
  Conda configuration. Pip's trusted-host setting cannot fix that error.
  Do not add a public repository fallback.
- **Offline setup:** set `PIP_NO_INDEX=1` and `PIP_FIND_LINKS` to an approved local
  wheelhouse before setup. It must contain all required packages and transitive
  dependencies, with Python 3.11 Windows-compatible wheels. Conda also needs
  cached Conda packages and offline mode configured separately.
- **Dependency conflict:** inspect the resolver or `pip check` error, select an
  additional-package version compatible with the runtime pins, and rerun setup.
  Avoid independently upgrading the preinstalled libraries. Removing a declaration
  does not automatically uninstall a previously installed package.
- **Wrong interpreter:** reselect the named environment in VS Code and restart
  debugging. After setup succeeds, run
  `conda run -n databriks-app-3.11 python -m pip check` to recheck compatibility.

## Debug

Set breakpoints, choose **DataForge: Debug Streamlit** in Run and Debug, and press
**F5**. The launch configuration runs `python -m streamlit run app.py` with this
folder as its working directory and loads `.env` into the debug process. Open the
local URL printed by Streamlit. Stop debugging to stop the app; restart after
changing environment settings.

The checked-in launch configuration and `.env.example` contain no credentials or
machine-specific interpreter paths. `.env` is ignored by Git and excluded from
bundle synchronization. Do not force-add it or put secrets in `launch.json`.

Ordinary local requests do not have Databricks Apps' forwarded user headers or OBO
token. This starter does not emulate those headers or change authentication.
Bundle `resources/apps/main.yml` values are not automatically loaded locally.
Launching from a terminal without VS Code also does not automatically load `.env`.

Run Databricks bundle validation/deployment from the bundle root two directories
above this folder after initializing the bundle template. See the
[app template guide](../../docs/guide/G401-app-template-guide.md).
