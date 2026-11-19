"""Databricks SQL access with explicit user or service authentication."""

import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import pandas as pd
import requests
from databricks import sql
from databricks.sql.client import Connection

logger = logging.getLogger(__name__)


class DatabricksSQLClient:
    """Run individual SQL statements using configuration supplied by the caller.

    In aad mode, supply all three Entra service-principal fields. In obo mode,
    supply a current Databricks user access token; the client passes it through
    without a token exchange.
    Authentication parameters unrelated to the selected mode are ignored.
    User-token clients belong to the current request and must not be shared
    globally. The caller is responsible for supplying refreshed user tokens.

    Supply host as the SQL connector server hostname, without a URL scheme.
    Construction performs no authentication or network I/O. Each method opens
    its own connection, so session state and transactions do not span calls.
    """

    def __init__(
        self,
        *,
        host: str,
        warehouse_id: str,
        catalog: str | None = None,
        auth_mode: Literal["aad", "obo"],
        user_token: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        """Validate configuration without opening a connection.

        Args:
            host: SQL warehouse server hostname, without an HTTPS prefix.
                The supplied value is stored unchanged.
            warehouse_id: Warehouse identifier used to build the SQL HTTP path.
            catalog: Optional catalog selected before each statement. When
                omitted, the connection's default catalog applies.
            auth_mode: Case-insensitive authentication mode: aad uses an Entra
                service principal, and obo uses a supplied user access token.
                Unrelated credentials are ignored.
            user_token: Access token already valid for Databricks, required for
                obo. Pass the current request's token, without a Bearer prefix.
            tenant_id: Entra tenant identifier, required for aad.
            client_id: Entra application client ID, required for aad.
            client_secret: Entra application secret value, required for aad.

        Raises:
            ValueError: A required value is missing, malformed, or unsupported.
        """
        if not isinstance(host, str) or not host.strip():
            raise ValueError("host must be a nonempty string.")
        self.host = host

        if not isinstance(warehouse_id, str) or not re.fullmatch(
            r"[a-zA-Z0-9_-]+", warehouse_id
        ):
            raise ValueError("warehouse_id must be a nonempty warehouse identifier.")
        self.warehouse_id = warehouse_id

        if catalog is not None and (
            not isinstance(catalog, str) or not catalog.strip()
        ):
            raise ValueError("catalog must be a nonempty SQL identifier.")
        self.catalog = catalog

        if not isinstance(auth_mode, str) or auth_mode.lower() not in (
            "aad",
            "obo",
        ):
            raise ValueError("auth_mode must be aad or obo.")
        self.auth_mode = auth_mode.lower()

        if self.auth_mode == "obo":
            if not isinstance(user_token, str) or not user_token.strip():
                raise ValueError("obo mode requires a nonempty user_token string.")
            self._user_token = user_token
        elif self.auth_mode == "aad":
            if not isinstance(tenant_id, str) or not tenant_id.strip():
                raise ValueError("aad mode requires a nonempty tenant_id string.")
            self._tenant_id = tenant_id
            if not isinstance(client_id, str) or not client_id.strip():
                raise ValueError("aad mode requires a nonempty client_id string.")
            self._client_id = client_id
            if not isinstance(client_secret, str) or not client_secret.strip():
                raise ValueError("aad mode requires a nonempty client_secret string.")
            self._client_secret = client_secret

    def _get_service_token(self) -> str:
        """Request a Databricks access token using the client-credentials flow.

        Called only in aad mode, once per connection. Tokens are not cached.
        The request verifies TLS certificates, uses a 20-second timeout, and
        rejects redirects. Error messages omit the token response body.

        Returns:
            The access_token field from the Entra response.

        Raises:
            RuntimeError: The token endpoint returns a status other than 200.
            requests.RequestException: The HTTP request or JSON decoding fails.
            KeyError: The response does not contain access_token.
        """
        url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
            "scope": "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default",
        }
        with requests.post(
            url, data=data, timeout=20, verify=True, allow_redirects=False
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(
                    f"Token request failed: HTTP {response.status_code}."
                )
            body = response.json()
            return body["access_token"]

    def _connect(self) -> Connection:
        """Open a new connection using the selected authentication mode.

        OBO passes the supplied user token through without exchanging or
        refreshing it. AAD obtains a new service-principal token. No mode falls
        back to another mode on failure.

        Returns:
            An open connection that the caller must close, preferably with a
            context manager. Authentication and connector errors propagate.
        """
        connection_options = {
            "server_hostname": self.host,
            "http_path": f"/sql/1.0/warehouses/{self.warehouse_id}",
        }
        if self.auth_mode == "obo":
            return sql.connect(**connection_options, access_token=self._user_token)
        if self.auth_mode == "aad":
            return sql.connect(
                **connection_options, access_token=self._get_service_token()
            )
        raise ValueError("auth_mode must be aad or obo.")

    def query(
        self,
        statement: str,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> pd.DataFrame:
        """Execute one statement and load its complete result into a DataFrame.

        Args:
            statement: SQL for a single statement; scripts are not split.
            parameters: A dict or other Mapping for named placeholders such as
                :job_id, or a sequence for positional ? placeholders. Values
                are bound by the connector, not interpolated into SQL. Omit
                this argument when the statement has no parameters.

        Returns:
            An Arrow-converted pandas DataFrame, retaining column names when
            no rows match. All returned rows are loaded into memory.

        Raises:
            ValueError: The statement is blank or returns no result set.
                The latter is detected after execution, so query does not
                enforce read-only access or undo a statement's effects.

        Authentication, execution, and conversion errors propagate. Connection
        and cursor context managers handle cleanup, including on failure.

        Example:
            df = client.query(
                "SELECT * FROM jobs WHERE id = :job_id",
                parameters={"job_id": 123},
            )
        """
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError("statement must be a nonempty SQL string.")
        # The connector accepts dict, but not every Mapping implementation.
        if isinstance(parameters, Mapping):
            parameters = dict(parameters)
        logger.info("Executing a SQL query on warehouse %s.", self.warehouse_id)
        with self._connect() as connection, connection.cursor() as cursor:
            if self.catalog is not None:
                # Catalog names are identifiers, not bound parameter values.
                catalog = self.catalog.replace("`", "``")
                cursor.execute(f"USE CATALOG `{catalog}`")
            cursor.execute("SET TIME ZONE 'UTC'")
            cursor.execute(statement, parameters=parameters)
            if cursor.description is None:
                raise ValueError("The statement returned no result set; use execute().")
            result = cursor.fetchall_arrow().to_pandas()
        logger.info("SQL query completed on warehouse %s.", self.warehouse_id)
        return result

    def execute(
        self,
        statement: str,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
    ) -> None:
        """Execute one command synchronously and discard any returned result set.

        Args:
            statement: One SQL statement, such as INSERT, UPDATE, or CREATE.
            parameters: A dict or other Mapping for :name placeholders, a
                sequence for ? placeholders, or None when no values are bound.

        Returns:
            None after successful execution; no affected-row count is reported.

        Raises:
            ValueError: The statement is empty or contains only whitespace.

        Authentication and connector errors propagate. Each call owns its
        connection and cursor; transactions and session state do not span
        calls. This method does not add retries or split SQL scripts.

        Example:
            client.execute(
                "UPDATE jobs SET enabled = :enabled WHERE id = :job_id",
                parameters={"enabled": True, "job_id": 123},
            )
        """
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError("statement must be a nonempty SQL string.")
        # The connector accepts dict, but not every Mapping implementation.
        if isinstance(parameters, Mapping):
            parameters = dict(parameters)
        logger.info("Executing a SQL command on warehouse %s.", self.warehouse_id)
        with self._connect() as connection, connection.cursor() as cursor:
            if self.catalog is not None:
                # Catalog names are identifiers, not bound parameter values.
                catalog = self.catalog.replace("`", "``")
                cursor.execute(f"USE CATALOG `{catalog}`")
            cursor.execute(statement, parameters=parameters)
        logger.info("SQL command completed on warehouse %s.", self.warehouse_id)
