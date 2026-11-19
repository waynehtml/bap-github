"""CORRA startup example. Reuse the runtime across requests/Streamlit reruns.

Map LOGGING_ENTRA_CLIENT_SECRET to an approved App secret resource. Disable
native App Telemetry separately. Do not shut down after a request or rerun;
use a process-stop hook when available. atexit is a graceful-exit fallback only.
"""
import os

from oeds.domain.utils.otel_logging.otel_logging_utils import (
    ZerobusLoggingConfig, configure_logging,
)


def get_app_logging():
    return configure_logging(
        tenant_id=os.environ["LOGGING_ENTRA_TENANT_ID"],
        client_id=os.environ["LOGGING_ENTRA_CLIENT_ID"],
        client_secret=os.environ["LOGGING_ENTRA_CLIENT_SECRET"],
        workspace_url=os.environ["ZEROBUS_WORKSPACE_URL"],
        table_name=os.environ["ZEROBUS_TABLE_NAME"],
        config=ZerobusLoggingConfig(
            endpoint=os.environ["ZEROBUS_ENDPOINT"],
            service_name=os.environ.get("LOGGING_SERVICE_NAME", "corra"),
            environment=os.environ.get("LOGGING_ENVIRONMENT"),
        ),
    )


# In the app entry point:
# runtime = get_app_logging()
# logger = logging.getLogger("corra")
# logger.info("Request completed", extra={"request_id": request_id})
# Per-request/user/job context belongs in extra, not shared resource attributes.
