import os
import io
import base64
import datetime

import dash
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output, State
from flask import request as flask_request
from databricks.sdk import WorkspaceClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def _build_workspace_client() -> WorkspaceClient:
    """Sign in as the shared app account lake-{env}-oedataservices-app.

    The bundle injects its tenant ID, client ID and secret (SPN_TENANTID,
    SPN_ID, SPN_SECRET) from the app secret scope. Without them (for example
    a manual deploy), fall back to the app's own service principal.
    """
    tenant_id = os.getenv("SPN_TENANTID")
    client_id = os.getenv("SPN_ID")
    client_secret = os.getenv("SPN_SECRET")
    if tenant_id and client_id and client_secret:
        host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        print(f"Signing in as shared app account {client_id}", flush=True)
        return WorkspaceClient(
            host=host or None,
            auth_type="azure-client-secret",
            azure_tenant_id=tenant_id,
            azure_client_id=client_id,
            azure_client_secret=client_secret,
        )
    print("Shared app account not configured; using the app service principal", flush=True)
    return WorkspaceClient()


w = _build_workspace_client()
WORKSPACE_HOST = (w.config.host or "").rstrip("/")

# Environment: set by the bundle (ENV_NAME); otherwise worked out from the
# workspace the app runs in, so a manual deploy still uses the right volume.
_WORKSPACE_ENV = {
    "1700301391505163": "dev",
    "13344226264609": "stg",
    "642333651898149": "prd",
}
ENV_NAME = os.getenv("ENV_NAME") or next(
    (env for ws_id, env in _WORKSPACE_ENV.items() if f"adb-{ws_id}." in WORKSPACE_HOST), ""
)
if ENV_NAME not in ("dev", "stg", "prd"):
    raise RuntimeError(f"Unknown environment for workspace {WORKSPACE_HOST!r}; set ENV_NAME")

DEFAULT_VOLUME_PATH = (
    os.getenv("VOLUME_PATH") or f"/Volumes/{ENV_NAME}_raw_cat/restricted_db/vol_internal_swift"
).rstrip("/")
BAP_CATALOG = os.getenv("BAP_CATALOG") or f"{ENV_NAME}_banking_and_payments_cat"

# Catalog Explorer link for the volume (rejected-file location in results).
_vol_parts = DEFAULT_VOLUME_PATH.split("/")[2:5]  # catalog, schema, volume
VOLUME_URL = f"{WORKSPACE_HOST}/explore/data/volumes/{'/'.join(_vol_parts)}"

# Predefined subfolder choices inside the landing-zone volume.
# Override via SUBFOLDERS env var (comma-separated).
_sub_env = os.getenv("SUBFOLDERS", "")
SUBFOLDER_OPTIONS: list[dict] = (
    [{"label": s.strip(), "value": s.strip()} for s in _sub_env.split(",") if s.strip()]
    if _sub_env
    else [
        {"label": "inbox",    "value": "inbox"},
        {"label": "archive",  "value": "archive"},
        {"label": "rejected", "value": "rejected"},
    ]
)
ALLOWED_SUBFOLDERS = {option["value"].strip("/") for option in SUBFOLDER_OPTIONS}

# Swift DVR uploads accept Excel workbooks and CSV files.
ALLOWED_EXTENSIONS: set[str] = {".xlsx", ".xls", ".csv"}

# Filename validation — reject non-DVR files at upload time.
# Only check the prefix; the pipeline does strict date validation later.
import re
import json
DVR_FILENAME_PATTERN = re.compile(
    # Extension check is case-insensitive (.csv, .CSV, .xlsx, .XLSX ...).
    r"^Activity Reports_(inbound|outbound)_Entity_.+\.(?i:xlsx|xls|csv)$"
)

# The destination is governed by deployment configuration.  Keep the base
# path out of the request so an uploader cannot redirect files to another
# catalog, schema, or volume.
if not DEFAULT_VOLUME_PATH.startswith("/Volumes/"):
    raise RuntimeError("VOLUME_PATH must be a Unity Catalog volume path")

app = dash.Dash(__name__)
app.title = "Swift DVR File Upload"

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
app.layout = html.Div(
    [
        # Hidden components for user identity
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="user-store"),
        # Header
        html.Div(
            [
                html.Div(
                    [
                        html.H1(
                            "Swift DVR File Upload",
                            style={"margin": "0", "color": "#FFFFFF", "fontSize": "30px", "fontWeight": "700"},
                        ),
                        html.Div(
                            "BAP • ARM OPERATIONS",
                            style={"fontSize": "11px", "fontWeight": "700", "letterSpacing": "1.4px", "color": "#A9D5FF", "marginTop": "6px"},
                        ),
                        html.P(
                            "Securely submit Swift DVR workbooks for daily reconciliation.",
                            style={"margin": "6px 0 0", "color": "#D8E7F7", "fontSize": "15px"},
                        ),
                    ],
                    style={"flex": "1"},
                ),
                html.Div(
                    id="user-badge",
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "8px",
                        "padding": "8px 16px",
                        "backgroundColor": "rgba(255,255,255,0.14)",
                        "borderRadius": "20px",
                        "fontSize": "13px",
                        "color": "#FFFFFF",
                        "whiteSpace": "nowrap",
                    },
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "padding": "28px 5% 26px",
                "background": "linear-gradient(115deg, #123B5D 0%, #0B2740 65%, #174D73 100%)",
                "boxShadow": "0 2px 10px rgba(10, 39, 64, 0.18)",
            },
        ),
        # Body
        html.Div(
            [
                # ---- Volume base path + subfolder selector ----
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label(
                                    "Landing-zone volume",
                                    style={"fontWeight": "700", "marginBottom": "7px", "color": "#183B56"},
                                ),
                                dcc.Input(
                                    id="volume-path",
                                    type="text",
                                    value=DEFAULT_VOLUME_PATH,
                                    disabled=True,
                                    style={
                                        "width": "100%",
                                        "padding": "10px",
                                        "border": "1px solid #D5DFEA",
                                        "borderRadius": "8px",
                                        "fontSize": "14px",
                                        "color": "#496278",
                                        "backgroundColor": "#F7F9FC",
                                        "boxSizing": "border-box",
                                    },
                                ),
                            ],
                            style={"flex": "2", "marginRight": "12px"},
                        ),
                        html.Div(
                            [
                                html.Label(
                                    "Subfolder",
                                    style={"fontWeight": "700", "marginBottom": "7px", "color": "#183B56"},
                                ),
                                dcc.Dropdown(
                                    id="subfolder",
                                    options=SUBFOLDER_OPTIONS,
                                    value=(
                                        next(
                                            (option["value"] for option in SUBFOLDER_OPTIONS if option["value"].strip("/") == "inbox"),
                                            SUBFOLDER_OPTIONS[0]["value"] if SUBFOLDER_OPTIONS else None,
                                        )
                                    ),
                                    clearable=False,
                                    placeholder="(root)",
                                    style={"fontSize": "14px"},
                                ),
                            ],
                            style={"flex": "1"},
                        ),
                    ],
                    style={
                        "display": "flex",
                        "alignItems": "flex-start",
                        "marginBottom": "8px",
                    },
                ),
                # Resolved path preview
                html.Div(
                    id="resolved-path",
                    style={
                        "fontSize": "12px",
                        "color": "#496278",
                        "fontFamily": "monospace",
                        "marginBottom": "20px",
                        "padding": "6px 10px",
                        "backgroundColor": "#F1F6FB",
                        "border": "1px solid #E0EAF3",
                        "borderRadius": "7px",
                    },
                ),
                # Upload area
                dcc.Upload(
                    id="upload-data",
                    children=html.Div(
                        [
                            html.Div(
                                "\u2B06",
                                style={"fontSize": "42px", "fontWeight": "300", "color": "#1769AA", "lineHeight": "1"},
                            ),
                            html.Div(
                                [
                                    "Drag & drop files here, or ",
                                    html.Span(
                                        "browse",
                                        style={
                                            "color": "#1769AA",
                                            "fontWeight": "700",
                                            "textDecoration": "underline",
                                            "cursor": "pointer",
                                        },
                                    ),
                                ],
                                style={"fontSize": "15px", "color": "#304D64"},
                            ),
                            html.Div(
                                "Format: Activity Reports_inbound_Entity_YYYYMMDD.xlsx/.csv  |  Activity Reports_outbound_Entity_YYYYMMDD.xlsx/.csv",
                                style={
                                    "fontSize": "11px",
                                    "color": "#1769AA",
                                    "marginTop": "4px",
                                    "fontFamily": "monospace",
                                    "fontWeight": "700",
                                },
                            ),
                        ],
                        style={"textAlign": "center"},
                    ),
                    style={
                        "width": "100%",
                        "padding": "42px 20px",
                        "borderWidth": "2px",
                        "borderStyle": "dashed",
                        "borderRadius": "10px",
                        "borderColor": "#8DB9DC",
                        "backgroundColor": "#F5FAFF",
                        "cursor": "pointer",
                        "boxSizing": "border-box",
                    },
                    multiple=True,
                ),
                # Status banner
                html.Div(id="upload-status", style={"marginTop": "20px"}),
                # Upload history table
                html.Div(id="upload-history", style={"marginTop": "16px"}),
                # --- Run Pipeline button ---
                html.Div(
                    [
                        html.Button(
                            "\u25B6  Run Pipeline",
                            id="run-pipeline-btn",
                            n_clicks=0,
                            style={
                                "padding": "10px 28px",
                                "fontSize": "14px",
                                "fontWeight": "700",
                                "border": "none",
                                "borderRadius": "8px",
                                "backgroundColor": "#1769AA",
                                "color": "#FFFFFF",
                                "cursor": "pointer",
                                "letterSpacing": "0.3px",
                            },
                        ),
                        html.Span(
                            "Runs automatically after upload. Use this button to re-run if needed.",
                            style={"fontSize": "12px", "color": "#71869A", "marginLeft": "12px"},
                        ),
                    ],
                    style={"marginTop": "20px", "display": "flex", "alignItems": "center"},
                ),
                # Pipeline run tracking
                dcc.Store(id="pipeline-run-store", data=None),
                # Set by handle_upload after a successful upload; starts the pipeline automatically
                dcc.Store(id="upload-trigger-store", data=None),
                dcc.Interval(id="pipeline-poll-interval", interval=10000, disabled=True),
                html.Div(id="pipeline-run-result", style={"marginTop": "12px"}),
            ],
            style={
                "maxWidth": "1080px",
                "margin": "32px auto",
                "padding": "30px 34px 34px",
                "backgroundColor": "#FFFFFF",
                "border": "1px solid #E3EAF1",
                "borderRadius": "14px",
                "boxShadow": "0 8px 28px rgba(22, 55, 82, 0.08)",
            },
        ),
    ],
    style={"fontFamily": "'Segoe UI', Roboto, sans-serif", "backgroundColor": "#F4F7FB", "minHeight": "100vh", "color": "#183B56"},
)


# ---------------------------------------------------------------------------
# Callback: resolved-path preview
# ---------------------------------------------------------------------------
@app.callback(
    Output("resolved-path", "children"),
    [Input("volume-path", "value"), Input("subfolder", "value")],
)
def update_resolved_path(base, sub):
    sub = (sub or "").strip("/")
    full = f"{DEFAULT_VOLUME_PATH.rstrip('/')}/{sub}" if sub else DEFAULT_VOLUME_PATH
    return f"Target: {full}/"


# ---------------------------------------------------------------------------
# Callback: resolve user identity on page load
# ---------------------------------------------------------------------------
@app.callback(
    [Output("user-store", "data"), Output("user-badge", "children")],
    Input("url", "pathname"),
)
def identify_user(_pathname):
    """Read identity headers injected by the Databricks Apps proxy."""
    email = (
        flask_request.headers.get("X-Forwarded-Email")
        or flask_request.headers.get("X-Forwarded-Preferred-Username")
        or flask_request.headers.get("X-Forwarded-User")
        or "unknown"
    )
    display = email.split("@")[0] if "@" in email else email
    badge = [
        html.Span("\U0001F464", style={"fontSize": "16px"}),
        html.Span(display, style={"fontWeight": "600"}),
    ]
    return {"email": email, "display": display}, badge


# ---------------------------------------------------------------------------
# Callback: handle uploads
# ---------------------------------------------------------------------------
@app.callback(
    [Output("upload-status", "children"), Output("upload-history", "children"),
     Output("upload-trigger-store", "data")],
    Input("upload-data", "contents"),
    [
        State("upload-data", "filename"),
        State("volume-path", "value"),
        State("subfolder", "value"),
        State("user-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_upload(contents_list, filenames, volume_path, subfolder, user_data):
    if not contents_list:
        return "", "", dash.no_update

    uploader = (user_data or {}).get("email", "unknown")

    # Ignore the client-supplied volume path.  The app identity must only be
    # able to write to the deployment-controlled volume.
    base = DEFAULT_VOLUME_PATH.rstrip("/")
    subfolder = (subfolder or "").strip("/")
    if subfolder and subfolder not in ALLOWED_SUBFOLDERS:
        return (
            html.Div("Upload rejected: invalid destination subfolder.", style={"color": "#721c24"}),
            "",
            dash.no_update,
        )
    dest = f"{base}/{subfolder}" if subfolder else base
    results = []
    rejected = []
    rejected_names = []

    for raw_content, fname in zip(contents_list, filenames):
        # --- file-type gate ---
        stem, raw_ext = os.path.splitext(fname)
        ext = raw_ext.lower()
        if ext not in ALLOWED_EXTENSIONS:
            rejected.append(fname)
            continue
        # Store the extension in lower case (.CSV -> .csv) so the pipeline's
        # file discovery and validation pick the file up.
        fname = f"{stem}{ext}"

        # --- filename format gate ---
        if not DVR_FILENAME_PATTERN.match(fname):
            rejected_names.append(fname)
            continue

        try:
            _header, b64_data = raw_content.split(",", 1)
            file_bytes = base64.b64decode(b64_data)
            target = f"{dest}/{fname}"

            # Do not silently replace a previously uploaded DVR workbook.
            try:
                w.files.get_status(target)
                results.append(
                    {
                        "File": fname,
                        "Status": "Rejected: file already exists",
                        "Size": "-",
                        "Uploaded By": uploader,
                        "Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Volume Path": target,
                    }
                )
                continue
            except Exception:
                # A missing file is the expected path for a new upload.
                pass

            w.files.upload(target, io.BytesIO(file_bytes), overwrite=False)

            results.append(
                {
                    "File": fname,
                    "Status": "Uploaded",
                    "Size": f"{len(file_bytes):,} bytes",
                    "Uploaded By": uploader,
                    "Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Volume Path": target,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "File": fname,
                    "Status": f"Error: {exc}",
                    "Size": "-",
                    "Uploaded By": uploader,
                    "Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Volume Path": "-",
                }
            )

    # Summary banner
    ok = sum(1 for r in results if r["Status"] == "Uploaded")
    fail = len(results) - ok

    parts = []

    # Rejected-file warning (wrong extension)
    if rejected:
        parts.append(
            html.Div(
                [
                    html.Strong(f"{len(rejected)} file(s) rejected "),
                    html.Span(
                        f"(unsupported type): {', '.join(rejected)}. "
                        f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                    ),
                ],
                style={
                    "padding": "12px 16px",
                    "backgroundColor": "#f8d7da",
                    "border": "1px solid #f5c6cb",
                    "borderRadius": "6px",
                    "color": "#721c24",
                    "marginBottom": "8px",
                },
            )
        )

    # Rejected-file warning (wrong filename format)
    if rejected_names:
        parts.append(
            html.Div(
                [
                    html.Strong(f"{len(rejected_names)} file(s) rejected "),
                    html.Span(f"(invalid filename): {', '.join(rejected_names)}"),
                    html.Div(
                        "Expected format: Activity Reports_inbound_Entity_YYYYMMDD.xlsx/.csv "
                        "or Activity Reports_outbound_Entity_YYYYMMDD.xlsx/.csv",
                        style={"fontSize": "12px", "marginTop": "4px"},
                    ),
                ],
                style={
                    "padding": "12px 16px",
                    "backgroundColor": "#f8d7da",
                    "border": "1px solid #f5c6cb",
                    "borderRadius": "6px",
                    "color": "#721c24",
                    "marginBottom": "8px",
                },
            )
        )

    if ok + fail == 0 and (rejected or rejected_names):
        return parts, "", dash.no_update

    if fail == 0:
        # Build file location links
        uploaded_paths = [r["Volume Path"] for r in results if r["Status"] == "Uploaded"]
        location_children = []
        volume_url = VOLUME_URL
        for vpath in uploaded_paths:
            # Derive subfolder from actual upload path
            rel = vpath.replace(DEFAULT_VOLUME_PATH.rstrip('/') + '/', '')
            sub_display = ' / '.join(rel.rsplit('/', 1)[:-1]) or 'root'
            location_children.append(
                html.Div(
                    [
                        html.Span("\U0001F4C2 Location: ", style={"fontWeight": "600"}),
                        html.A(
                            "vol_internal_swift",
                            href=volume_url,
                            target="_blank",
                            style={"color": "#1769AA", "textDecoration": "underline", "fontWeight": "600"},
                        ),
                        html.Span(
                            f" / {sub_display} /",
                            style={"fontFamily": "monospace", "fontWeight": "600", "color": "#304D64"},
                        ),
                    ],
                    style={"fontSize": "12px", "marginTop": "4px"},
                )
            )

        banner = html.Div(
            [
                html.Div(f"\u2705  {ok} file(s) uploaded successfully.", style={"fontWeight": "600"}),
                html.Div(
                    "Processing started automatically. Results appear below in a few minutes.",
                    style={"fontSize": "12px", "marginTop": "4px", "color": "#1B5E20"},
                ),
            ] + location_children,
            style={
                "padding": "12px 16px",
                "backgroundColor": "#d4edda",
                "border": "1px solid #c3e6cb",
                "borderRadius": "6px",
                "color": "#155724",
            },
        )
    else:
        banner = html.Div(
            f"\u26A0  {ok} succeeded, {fail} failed.",
            style={
                "padding": "12px 16px",
                "backgroundColor": "#fff3cd",
                "border": "1px solid #ffeeba",
                "borderRadius": "6px",
                "color": "#856404",
            },
        )

    table = dash_table.DataTable(
        data=results,
        columns=[{"name": c, "id": c} for c in ["File", "Status", "Size", "Uploaded By", "Time", "Volume Path"]],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "10px 12px", "fontSize": "13px"},
        style_header={
            "fontWeight": "bold",
            "backgroundColor": "#f1f3f5",
            "borderBottom": "2px solid #dee2e6",
        },
        style_data_conditional=[
            {
                "if": {"filter_query": '{Status} contains "Error"'},
                "color": "#dc3545",
            },
            {
                "if": {"filter_query": '{Status} = "Uploaded"'},
                "color": "#28a745",
            },
        ],
    )

    parts.append(banner)
    # Start the pipeline automatically when at least one file was uploaded
    trigger = (
        {"uploaded": ok, "ts": datetime.datetime.now().isoformat()} if ok > 0 else dash.no_update
    )
    return parts, table, trigger


# ---------------------------------------------------------------------------
# Error code guidance for users
# ---------------------------------------------------------------------------
ERROR_GUIDANCE = {
    "DVRFNERR001": "Rename the file to match: Activity Reports_inbound_Entity_YYYYMMDD.xlsx/.csv or Activity Reports_outbound_Entity_YYYYMMDD.xlsx/.csv",
    "DVRVALERR001": "Check the file has the required columns (for Excel files, a worksheet named 'Activity Report - Transactions').",
    "DVRVALERR002": "The date in the filename does not match the dates inside the file. Verify you downloaded the correct day's report.",
    "DVRVALERR003": "One or more required fields are blank. Check Input Day, Message type, Transaction Reference, and Amount received columns.",
}

PROCESSING_LOG_TABLE = f"{BAP_CATALOG}.derived_db.tbl_dvr_file_processing_log"



# ---------------------------------------------------------------------------
# Pipeline job ID
# ---------------------------------------------------------------------------
DVR_PIPELINE_JOB_NAME = "DVR Swift Pipeline"
_job_id_cache: dict = {}


def get_pipeline_job_id() -> int:
    """Job ID from the bundle (DVR_PIPELINE_JOB_ID app resource), else looked up by name."""
    if os.getenv("DVR_PIPELINE_JOB_ID"):
        return int(os.environ["DVR_PIPELINE_JOB_ID"])
    if "id" not in _job_id_cache:
        matches = [j.job_id for j in w.jobs.list(name=DVR_PIPELINE_JOB_NAME)]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one job named {DVR_PIPELINE_JOB_NAME!r}, found {len(matches)}"
            )
        _job_id_cache["id"] = matches[0]
    return _job_id_cache["id"]


# ---------------------------------------------------------------------------
# Callback: trigger pipeline run
# ---------------------------------------------------------------------------
@app.callback(
    [Output("pipeline-run-store", "data"),
     Output("pipeline-poll-interval", "disabled"),
     Output("pipeline-run-result", "children", allow_duplicate=True)],
    [Input("run-pipeline-btn", "n_clicks"),
     Input("upload-trigger-store", "data")],
    State("pipeline-run-store", "data"),
    prevent_initial_call=True,
)
def trigger_pipeline(_n_clicks, upload_trigger, existing_run):
    triggered = dash.callback_context.triggered_id
    if triggered == "run-pipeline-btn" and not _n_clicks:
        return dash.no_update, dash.no_update, ""
    if triggered == "upload-trigger-store" and not (upload_trigger or {}).get("uploaded"):
        return dash.no_update, dash.no_update, dash.no_update
    # Prevent duplicate triggers: skip only while the previous run is still active.
    # (The store keeps the last run_id after it finishes, so a finished run must not block.)
    if existing_run and existing_run.get("run_id"):
        try:
            prev = w.jobs.get_run(run_id=existing_run["run_id"])
            prev_state = str(prev.state.life_cycle_state) if prev.state else ""
        except Exception:
            prev_state = "TERMINATED"
        if not any(s in prev_state for s in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR")):
            return (
                dash.no_update,
                False,  # keep polling the active run
                html.Div(
                    "Pipeline already running. The new file will be processed in the next run; "
                    "click Run Pipeline after this run finishes.",
                    style={
                        "padding": "12px 16px",
                        "backgroundColor": "#fff3cd",
                        "border": "1px solid #ffeeba",
                        "borderRadius": "6px",
                        "color": "#856404",
                    },
                ),
            )
    # Do not start a run (and a job cluster) when there is nothing to process.
    if triggered == "run-pipeline-btn":
        try:
            inbox_files = [
                f.name for f in w.files.list_directory_contents(f"{DEFAULT_VOLUME_PATH.rstrip('/')}/inbox/")
                if f.name and os.path.splitext(f.name)[1].lower() in ALLOWED_EXTENSIONS
            ]
        except Exception:
            inbox_files = None  # Could not check; start the run as before.
        if inbox_files == []:
            return (
                dash.no_update,
                True,
                html.Div(
                    "No files in the inbox, so the pipeline was not started. "
                    "Upload a file first; the pipeline starts automatically after upload.",
                    style={
                        "padding": "12px 16px",
                        "backgroundColor": "#fff3cd",
                        "border": "1px solid #ffeeba",
                        "borderRadius": "6px",
                        "color": "#856404",
                    },
                ),
            )
    try:
        run = w.jobs.run_now(job_id=get_pipeline_job_id())
        return (
            {"run_id": run.run_id},
            False,  # enable polling
            html.Div(
                [
                    html.Span("\u23F3 ", style={"fontSize": "16px"}),
                    html.Span("Pipeline running...", style={"fontWeight": "600"}),
                    html.Span(
                        f"  Run ID: {run.run_id}",
                        style={"fontSize": "12px", "color": "#71869A", "marginLeft": "8px"},
                    ),
                ],
                style={
                    "padding": "12px 16px",
                    "backgroundColor": "#e3f2fd",
                    "border": "1px solid #90caf9",
                    "borderRadius": "6px",
                    "color": "#0d47a1",
                },
            ),
        )
    except Exception as e:
        return (
            None,
            True,
            html.Div(
                f"Failed to start pipeline: {e}",
                style={
                    "padding": "12px 16px",
                    "backgroundColor": "#f8d7da",
                    "border": "1px solid #f5c6cb",
                    "borderRadius": "6px",
                    "color": "#721c24",
                },
            ),
        )


# ---------------------------------------------------------------------------
# Callback: poll pipeline run status
# ---------------------------------------------------------------------------
@app.callback(
    [Output("pipeline-run-result", "children"),
     Output("pipeline-poll-interval", "disabled", allow_duplicate=True)],
    Input("pipeline-poll-interval", "n_intervals"),
    State("pipeline-run-store", "data"),
    prevent_initial_call=True,
)
def poll_pipeline_status(_n_intervals, run_data):
    if not run_data or "run_id" not in run_data:
        return "", True

    try:
        run = w.jobs.get_run(run_id=run_data["run_id"])
        state = str(run.state.life_cycle_state)
        result = str(run.state.result_state) if run.state.result_state else None

        if "TERMINATED" not in state and "SKIPPED" not in state and "INTERNAL_ERROR" not in state:
            # Still running
            task_summary = []
            for t in (run.tasks or []):
                tr = str(t.state.result_state) if t.state and t.state.result_state else ""
                if "SUCCESS" in tr:
                    icon, label = "\u2705", "Passed"
                elif "FAILED" in tr:
                    icon, label = "\u274C", "Failed"
                else:
                    icon, label = "\u23F3", "Running"
                task_summary.append(html.Div(f"{icon} {t.task_key}: {label}", style={"fontSize": "12px"}))

            return (
                html.Div(
                    [
                        html.Div(
                            [html.Span("\u23F3 "), html.Span("Pipeline running...", style={"fontWeight": "600"})],
                        ),
                        html.Div(task_summary, style={"marginTop": "8px"}),
                    ],
                    style={
                        "padding": "12px 16px",
                        "backgroundColor": "#e3f2fd",
                        "border": "1px solid #90caf9",
                        "borderRadius": "6px",
                        "color": "#0d47a1",
                    },
                ),
                False,  # keep polling
            )

        # --- Run finished — check folders via Files API for file outcomes ---
        import csv as _csv
        import io as _io

        base = DEFAULT_VOLUME_PATH.rstrip("/")
        volume_url = VOLUME_URL

        # Read error logs so we can show real error details for rejected files
        error_log_map = {}  # filename_stem -> list of {Error_Code, Description, Additional_Details}
        try:
            for f in w.files.list_directory_contents(f"{base}/error_logs/"):
                if f.name and f.name.endswith(".csv"):
                    resp = w.files.download(f"{base}/error_logs/{f.name}")
                    text = resp.contents.read().decode("utf-8", errors="replace")
                    reader = _csv.DictReader(_io.StringIO(text))
                    rows = list(reader)
                    if rows:
                        error_log_map[f.name] = rows
        except Exception:
            pass

        # Collect files in archive and rejected
        archived_files = []
        rejected_files = []
        try:
            for f in w.files.list_directory_contents(f"{base}/archive/"):
                if f.name and f.name.endswith((".xlsx", ".xls", ".csv")):
                    archived_files.append(f.name)
        except Exception:
            pass
        try:
            for f in w.files.list_directory_contents(f"{base}/rejected/"):
                if f.name and f.name.endswith((".xlsx", ".xls", ".csv")):
                    rejected_files.append(f.name)
        except Exception:
            pass

        # --- Per-task outcome and this run's own file list ---
        # The archive keeps files from earlier runs, so only show the files the
        # validate task handled in this run.
        task_states = {}
        run_valid, run_invalid = None, None
        recon_summary = {}
        for t in (run.tasks or []):
            state_value = t.state.result_state if t.state and t.state.result_state else None
            task_states[t.task_key] = str(state_value).split(".")[-1] if state_value else "NOT_RUN"
            if t.task_key == "validate_swift_files":
                try:
                    output = w.jobs.get_run_output(run_id=t.run_id)
                    payload = (
                        json.loads(output.notebook_output.result)
                        if output.notebook_output and output.notebook_output.result
                        else {}
                    )
                    run_valid = {f.get("filename") for f in payload.get("valid_files", []) if isinstance(f, dict)}
                    run_invalid = {
                        (f.get("filename") if isinstance(f, dict) else str(f))
                        for f in payload.get("invalid_files", [])
                    }
                except Exception:
                    pass
            elif t.task_key == "reconcile" and task_states[t.task_key] == "SUCCESS":
                # Reconciliation counts and HABS freshness for the result message.
                try:
                    output = w.jobs.get_run_output(run_id=t.run_id)
                    recon_summary = (
                        json.loads(output.notebook_output.result)
                        if output.notebook_output and output.notebook_output.result
                        else {}
                    )
                except Exception:
                    recon_summary = {}
        if run_valid is not None:
            archived_files = [f for f in archived_files if f in run_valid]
            rejected_files = [f for f in rejected_files if f in (run_invalid or set())]

        core_tasks = ["validate_swift_files", "parse_load_swift", "load_habs_message", "reconcile", "generate_reports"]
        # EXCLUDED: the job's has_files gate stopped the run because the inbox was empty.
        ok_states = ("SUCCESS", "EXCLUDED")
        core_failed = [k for k in core_tasks if k in task_states and task_states[k] not in ok_states]
        side_failed = [k for k, s in task_states.items()
                       if k not in core_tasks and k != "has_files" and s not in ok_states]
        side_labels = {"notify": "the email notification", "copy_legacy_r_drive": "the R: drive copy"}
        habs_stale = recon_summary.get("habs_not_refreshed_dates") or []
        if core_failed:
            header_text, box_bg, box_border, box_color = "\u274C Pipeline did not complete", "#f8d7da", "#f5c6cb", "#721c24"
            processed_text = "File passed validation, but processing did not complete. Support has been notified."
        elif side_failed:
            # A side task (email or R: drive copy) failed: the file was processed,
            # but say which step did not finish instead of "No problems found".
            failed_steps = " and ".join(side_labels.get(k, k) for k in side_failed)
            header_text, box_bg, box_border, box_color = "\u26A0\uFE0F Pipeline completed with errors", "#fff3cd", "#ffeeba", "#856404"
            processed_text = (
                f"File passed validation and has been processed, but {failed_steps} did not complete. "
                "Support has been notified."
            )
        elif habs_stale:
            header_text, box_bg, box_border, box_color = "\u26A0\uFE0F HABS not refreshed yet", "#fff3cd", "#ffeeba", "#856404"
            processed_text = (
                "File passed validation and has been processed, but HABS has not been refreshed for "
                f"{', '.join(habs_stale)} yet (BAP-HABS-WORKPACKAGE1), so transactions show as warnings. "
                "Upload the file again after HABS is refreshed."
            )
        else:
            header_text, box_bg, box_border, box_color = "\u2705 Pipeline completed", "#d4edda", "#c3e6cb", "#155724"
            processed_text = "File passed validation and has been processed."
        if recon_summary and not core_failed:
            processed_text += (
                f" Reconciliation: {recon_summary.get('success', 0)} matched, "
                f"{recon_summary.get('warnings', 0)} warning(s). "
                + ("Reports are in vol_internal_swift / reports." if "notify" in side_failed
                   else "Details are in the emailed report.")
            )

        task_rows = []
        if core_failed or side_failed:
            for task_key, task_state in task_states.items():
                icon = "\u2705" if task_state == "SUCCESS" else ("\u23ED\uFE0F" if "UPSTREAM" in task_state or task_state == "NOT_RUN" else "\u274C")
                task_rows.append(html.Div(f"{icon} {task_key}: {task_state}", style={"fontSize": "12px"}))

        if task_states:
            file_cards = []

            # --- Archived (passed) files ---
            for fname in archived_files:
                full_path = f"{base}/archive/{fname}"
                file_cards.append(
                    html.Div(
                        [
                            html.Div(f"\u2705 {fname}", style={"fontWeight": "700", "fontSize": "14px"}),
                            html.Div(
                                processed_text,
                                style={"fontSize": "13px", "color": "#1B5E20", "marginTop": "4px"},
                            ),
                            html.Div(
                                [
                                    html.Span("\U0001F4C2 Location: ", style={"fontWeight": "600"}),
                                    html.A(
                                        "vol_internal_swift",
                                        href=volume_url,
                                        target="_blank",
                                        style={"color": "#1769AA", "textDecoration": "underline", "fontWeight": "600"},
                                    ),
                                    html.Span(
                                        " / archive /",
                                        style={"fontFamily": "monospace", "fontWeight": "600", "color": "#304D64"},
                                    ),
                                ],
                                style={"fontSize": "12px", "marginTop": "6px"},
                            ),
                        ],
                        style={
                            "padding": "12px 14px",
                            "backgroundColor": "#e8f5e9",
                            "border": "1px solid #c8e6c9",
                            "borderRadius": "8px",
                            "marginBottom": "8px",
                        },
                    )
                )

            # --- Rejected (failed) files ---
            for fname in rejected_files:
                full_path = f"{base}/rejected/{fname}"
                # Find matching error log
                errors_found = []
                for log_name, log_rows in error_log_map.items():
                    # Match by filename stem overlap
                    if any(part in fname.lower() for part in log_name.lower().replace("_validation_error.csv", "").split("_") if len(part) > 3):
                        errors_found = log_rows
                        break
                if not errors_found:
                    # Fallback: take the most recent error log
                    for log_rows in error_log_map.values():
                        errors_found = log_rows
                        break

                error_children = []
                for err in errors_found:
                    code = err.get("Error_Code", "")
                    desc = err.get("Description", "")
                    details = err.get("Additional_Details", "")
                    guidance = ERROR_GUIDANCE.get(code, "")
                    error_children.append(
                        html.Div(
                            [
                                html.Div(f"{code}: {desc}", style={"fontWeight": "600"}),
                                html.Div(details, style={"fontSize": "12px", "marginTop": "2px"}) if details else None,
                                html.Div(
                                    f"\u27A1 How to fix: {guidance}",
                                    style={"fontSize": "12px", "marginTop": "2px", "color": "#b71c1c"},
                                ) if guidance else None,
                            ],
                            style={"marginBottom": "4px"},
                        )
                    )

                file_cards.append(
                    html.Div(
                        [
                            html.Div(f"\u274C {fname}", style={"fontWeight": "700", "fontSize": "14px"}),
                            html.Div(
                                "File failed validation. Please fix the issue(s) below and re-upload.",
                                style={"fontSize": "13px", "marginTop": "4px"},
                            ),
                            html.Div(
                                [
                                    html.Span("\U0001F4C2 Location: ", style={"fontWeight": "600"}),
                                    html.A(
                                        "vol_internal_swift",
                                        href=volume_url,
                                        target="_blank",
                                        style={"color": "#1769AA", "textDecoration": "underline", "fontWeight": "600"},
                                    ),
                                    html.Span(
                                        " / rejected /",
                                        style={"fontFamily": "monospace", "fontWeight": "600", "color": "#304D64"},
                                    ),
                                ],
                                style={"fontSize": "12px", "marginTop": "6px"},
                            ),
                            html.Div(
                                error_children,
                                style={
                                    "marginTop": "8px",
                                    "padding": "8px 12px",
                                    "backgroundColor": "#fff3f0",
                                    "borderRadius": "6px",
                                    "border": "1px solid #ffcdd2",
                                },
                            ) if error_children else None,
                        ],
                        style={
                            "padding": "12px 14px",
                            "backgroundColor": "#fce4ec",
                            "border": "1px solid #f8bbd0",
                            "borderRadius": "8px",
                            "marginBottom": "8px",
                            "color": "#721c24",
                        },
                    )
                )

            return (
                html.Div(
                    [
                        html.Div(
                            header_text,
                            style={"fontWeight": "700", "fontSize": "15px", "marginBottom": "10px", "color": box_color},
                        ),
                    ] + ([html.Div(task_rows, style={"marginBottom": "10px"})] if task_rows else []) + (file_cards if file_cards else [
                        # Validation did not finish, so no file was checked or moved.
                        html.Div(
                            "Validation could not run, so your file(s) were not processed and are "
                            "still in the inbox. Support has been notified. Click Run Pipeline to "
                            "try again once the issue is fixed; you do not need to upload again.",
                            style={"fontSize": "13px"},
                        )
                        if task_states.get("validate_swift_files") != "SUCCESS"
                        else html.Div("No files were in the inbox to process.", style={"fontSize": "13px", "color": "#71869A"}),
                    ]),
                    style={
                        "padding": "14px 16px",
                        "backgroundColor": box_bg,
                        "border": f"1px solid {box_border}",
                        "borderRadius": "6px",
                        "color": box_color,
                    },
                ),
                True,  # stop polling
            )
        else:
            return (
                html.Div(
                    f"\u274C Pipeline finished with result: {result}",
                    style={
                        "padding": "12px 16px",
                        "backgroundColor": "#f8d7da",
                        "border": "1px solid #f5c6cb",
                        "borderRadius": "6px",
                        "color": "#721c24",
                        "fontWeight": "600",
                    },
                ),
                True,  # stop polling
            )

    except Exception as e:
        return (
            html.Div(f"Error checking pipeline status: {e}", style={"color": "#721c24", "fontSize": "13px"}),
            True,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
