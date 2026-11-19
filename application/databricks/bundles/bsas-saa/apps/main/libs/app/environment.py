"""Optional application settings, independent of Streamlit request context."""

import os
from dataclasses import dataclass, field

__all__ = ["ENV", "Environment"]


def _optional_string(value: object, name: str) -> str | None:
    """Treat absent or blank values as unset without exposing invalid values."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or null.")
    return value if value.strip() else None


@dataclass(frozen=True)
class Environment:
    """Optional startup settings; clients validate their own requirements.

    Unset backend properties are None. Settings are read from individual
    environment variables. Credentials are excluded from repr; user identity
    and tokens belong to the current request, never this snapshot.
    """

    DATABRICKS_WORKSPACE_ID: str | None = None
    DATABRICKS_HOST: str | None = None
    JOB_ID: int | None = None
    ENV_NAME: str | None = None
    DATABRICKS_WAREHOUSE_ID: str | None = None
    UC_CATALOG_NAME: str | None = None
    AZURE_WORKSPACE_RESOURCE_ID: str | None = None
    SPN_TENANTID: str | None = field(default=None, repr=False)
    SPN_ID: str | None = field(default=None, repr=False)
    SPN_SECRET: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "Environment":
        """Load available settings and validate only supplied values.

        SQL authentication is selected explicitly when constructing each client.
        Missing workspace configuration or credentials do not prevent startup.
        """
        values = dict(os.environ)
        workspace_id = _optional_string(
            values.get("DATABRICKS_WORKSPACE_ID"), "DATABRICKS_WORKSPACE_ID"
        )
        settings = {
            name: _optional_string(values.get(name), name)
            for name in (
                "ENV_NAME",
                "DATABRICKS_WAREHOUSE_ID",
                "UC_CATALOG_NAME",
                "AZURE_WORKSPACE_RESOURCE_ID",
            )
        }
        raw_job_id = _optional_string(values.get("JOB_ID"), "JOB_ID")
        job_id = None
        if raw_job_id is not None:
            try:
                job_id = int(raw_job_id)
            except ValueError:
                raise ValueError("JOB_ID must be a positive integer.") from None
            if job_id <= 0:
                raise ValueError("JOB_ID must be a positive integer.")

        return cls(
            DATABRICKS_WORKSPACE_ID=workspace_id,
            DATABRICKS_HOST=_optional_string(
                values.get("DATABRICKS_HOST"), "DATABRICKS_HOST"
            ),
            JOB_ID=job_id,
            ENV_NAME=settings["ENV_NAME"],
            DATABRICKS_WAREHOUSE_ID=settings["DATABRICKS_WAREHOUSE_ID"],
            UC_CATALOG_NAME=settings["UC_CATALOG_NAME"],
            AZURE_WORKSPACE_RESOURCE_ID=settings["AZURE_WORKSPACE_RESOURCE_ID"],
            SPN_TENANTID=_optional_string(values.get("SPN_TENANTID"), "SPN_TENANTID"),
            SPN_ID=_optional_string(values.get("SPN_ID"), "SPN_ID"),
            SPN_SECRET=_optional_string(values.get("SPN_SECRET"), "SPN_SECRET"),
        )


ENV = Environment.from_env()
