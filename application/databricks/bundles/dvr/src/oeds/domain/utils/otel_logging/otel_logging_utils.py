"""One owned OTLP/gRPC logging bridge per Python process.

Uses public gRPC call credentials and the standard OpenTelemetry exporter.
Does not replace Databricks' global OpenTelemetry provider.
"""
from __future__ import annotations

import atexit
import logging
import math
import os
import re
import sys
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

import grpc
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor, LogRecordExporter, LogRecordExportResult,
)
from opentelemetry.sdk.resources import Resource

from oeds.domain.utils.otel_logging.zerobus_auth import (
    EntraClientSecretTokenProvider, OAuthHttpClient, ZerobusTokenProvider,
    https_origin,
)

_AZURE_DATABRICKS_SCOPE = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default"
_AZURE_WORKSPACE_HOST_RE = re.compile(
    r"^adb-(\d+)\.[^.]+\.azuredatabricks\.net$"
)

# Only this handler filters these namespaces. Existing local handlers still see them.
_EXCLUDED_NAMESPACES = (
    "opentelemetry", "grpc", "oeds.domain.utils.otel_logging",
    "urllib3", "requests", "azure.identity", "msal",
)
_diagnostic_lock = threading.Lock()
_diagnostic_times: dict[str, float] = {}


def _diagnostic(key: str, safe_message: str) -> None:
    """Rate-limited, token-free local diagnostics; never recurse into logging."""
    now = time.monotonic()
    with _diagnostic_lock:
        previous = _diagnostic_times.get(key, -math.inf)
        if now - previous < 30:
            return
        _diagnostic_times[key] = now
    try:
        sys.stderr.write(f"[otel_logging] {safe_message}\n")
    except Exception:
        pass


class DynamicBearerAuth(grpc.AuthMetadataPlugin):
    """Supply current credentials for every RPC without rebuilding the exporter."""

    def __init__(self, token_provider: ZerobusTokenProvider):
        self._tokens = token_provider

    def __call__(self, context: Any, callback: Any) -> None:
        try:
            token = self._tokens.get_token()
        except Exception:
            _diagnostic(
                "auth",
                "Token acquisition failed. Check federation, UC grants, "
                "the source-token supplier, and connectivity.",
            )
            callback((), RuntimeError("Unable to obtain a Zerobus access token"))
            return
        callback((("authorization", f"Bearer {token}"),), None)


@dataclass(frozen=True)
class ZerobusLoggingConfig:
    endpoint: str
    service_name: str | None = None
    environment: str | None = None
    logger_name: str = ""  # Empty string = root logger.
    level: int = logging.INFO
    resource_attributes: Mapping[str, str | bool | int | float] = field(
        default_factory=dict
    )
    queue_size: int = 4096
    batch_size: int = 256
    schedule_delay_millis: int = 2000
    export_timeout_seconds: float = 15
    tls_root_certificates: bytes | None = field(default=None, repr=False)
    excluded_namespaces: tuple[str, ...] = _EXCLUDED_NAMESPACES

    def __post_init__(self) -> None:
        origin = https_origin(self.endpoint, "OTLP/gRPC endpoint")
        object.__setattr__(self, "endpoint", origin)
        for name, value in (("service_name", self.service_name), ("environment", self.environment)):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be nonempty or None")
        if not isinstance(self.logger_name, str):
            raise TypeError("logger_name must be a string")
        if not isinstance(self.level, int) or isinstance(self.level, bool) or self.level < 0:
            raise ValueError("level must be a nonnegative logging-level integer")
        for name, value in (
            ("queue_size", self.queue_size),
            ("batch_size", self.batch_size),
            ("schedule_delay_millis", self.schedule_delay_millis),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.batch_size > self.queue_size:
            raise ValueError("batch_size cannot exceed queue_size")
        if (
            not math.isfinite(self.export_timeout_seconds)
            or self.export_timeout_seconds <= 0
        ):
            raise ValueError("export_timeout_seconds must be positive and finite")
        attributes = dict(self.resource_attributes)
        reserved = {
            "service.name", "deployment.environment.name",
            "service.instance.id", "process.pid",
        }
        if reserved.intersection(attributes):
            raise ValueError("resource_attributes must not override reserved identity keys")
        for key, value in attributes.items():
            if not isinstance(key, str) or not key:
                raise TypeError("Resource attribute keys must be nonempty strings")
            if not isinstance(value, (str, bool, int, float)):
                raise TypeError("Resource attributes must have scalar values")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Resource attributes cannot be NaN or infinite")
        object.__setattr__(self, "resource_attributes", MappingProxyType(attributes))
        object.__setattr__(self, "excluded_namespaces", tuple(self.excluded_namespaces))


@dataclass(frozen=True)
class ExportStats:
    """SDK outcomes, NOT proof of Delta materialization or exactly-once delivery."""
    received_records: int
    rpc_success_records: int
    failed_records: int
    bridge_errors: int
    unaccounted_records: int

    @property
    def ok(self) -> bool:
        # In-flight/pending records also count as unaccounted until they complete.
        return not (self.failed_records or self.bridge_errors or self.unaccounted_records)


class _Counters:
    def __init__(self):
        self.lock = threading.Lock()
        self.received = self.success = self.failed = self.bridge_errors = 0

    def snapshot(self) -> ExportStats:
        with self.lock:
            return ExportStats(
                self.received, self.success, self.failed, self.bridge_errors,
                max(0, self.received - self.success - self.failed),
            )


class _ObservedExporter(LogRecordExporter):
    """Observe exporter failures without making business log calls raise."""

    def __init__(self, delegate: LogRecordExporter, counters: _Counters):
        self.delegate = delegate
        self.counters = counters

    def export(self, batch):
        try:
            result = self.delegate.export(batch)
        except Exception:
            result = LogRecordExportResult.FAILURE
            _diagnostic(
                "export_exception",
                "OTLP export raised an exception; the batch could not be confirmed.",
            )
        with self.counters.lock:
            if result == LogRecordExportResult.SUCCESS:
                self.counters.success += len(batch)
            else:
                self.counters.failed += len(batch)
        if result != LogRecordExportResult.SUCCESS:
            _diagnostic(
                "export_failure",
                "OTLP export failed after the exporter's retry policy. "
                "These records are not durably buffered by this library.",
            )
        return result

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.delegate.force_flush(timeout_millis)

    def shutdown(self, timeout_millis: float = 30000):
        # Delegate is the pinned OTLP/gRPC exporter, whose public method accepts
        # timeout_millis. Tests use a compatible exporter.
        self.delegate.shutdown(timeout_millis=timeout_millis)


class _InfrastructureFilter(logging.Filter):
    def __init__(self, names: tuple[str, ...]):
        super().__init__()
        self.names = names

    def filter(self, record: logging.LogRecord) -> bool:
        return not any(
            record.name == name or record.name.startswith(name + ".")
            for name in self.names
        )


class _BridgeHandler(LoggingHandler):
    def __init__(self, *, provider: LoggerProvider, level: int, counters: _Counters):
        super().__init__(level=level, logger_provider=provider)
        self.counters = counters
        self.accepting = True
        self._local = threading.local()

    def emit(self, record: logging.LogRecord) -> None:
        if not self.accepting or getattr(self._local, "inside", False):
            return
        self._local.inside = True
        try:
            super().emit(record)
            with self.counters.lock:
                self.counters.received += 1
        except Exception:
            with self.counters.lock:
                self.counters.bridge_errors += 1
            _diagnostic(
                "bridge",
                "Could not encode a Python log record as OTLP. "
                "Use supported scalar attributes and keep secrets out of logs.",
            )
        finally:
            self._local.inside = False

    def flush(self) -> None:
        # Flush explicitly through runtime.flush()/shutdown(), not under logging's
        # handler locks or via a new thread during interpreter finalization.
        return None


_registry_lock = threading.RLock()
_active_runtime: ZerobusLoggingRuntime | None = None


class ZerobusLoggingRuntime:
    """Owned resources for one task/process; close after producers stop."""

    def __init__(
        self,
        config: ZerobusLoggingConfig,
        token_provider: ZerobusTokenProvider,
        provider: LoggerProvider,
        handler: _BridgeHandler,
        target: logging.Logger,
        counters: _Counters,
        original_level: int,
        installed_level: int | None,
    ):
        self.config = config
        self.token_provider = token_provider
        self._provider = provider
        self._handler = handler
        self._target = target
        self._counters = counters
        self._original_level = original_level
        self._installed_level = installed_level
        self._pid = os.getpid()
        self._closed = False
        self.entra_token_provider: EntraClientSecretTokenProvider | None = None
        self._lifecycle_lock = threading.RLock()

    @property
    def closed(self) -> bool:
        return self._closed

    def stats(self) -> ExportStats:
        return self._counters.snapshot()

    def invalidate_tokens(self) -> None:
        """Clear both caches after a revocation or corrected federation setup.

        Normal expiry needs no intervention. An OTLP failure does not expose its
        gRPC status through LogRecordExportResult, so this library does not
        blindly remint/replay batches on every network or permission failure.
        """
        if self._closed:
            raise RuntimeError("This logging runtime is closed")
        if self.entra_token_provider is not None:
            self.entra_token_provider.invalidate()
        self.token_provider.invalidate()

    def flush(self) -> ExportStats:
        """Flush pending batches and return a snapshot of SDK outcomes.

        Stop concurrent producers for a meaningful final snapshot. In OTel
        1.42.1, BatchLogRecordProcessor.force_flush does not enforce a hard
        total timeout; individual export calls have the configured timeout.
        """
        if os.getpid() != self._pid:
            raise RuntimeError("Do not use an inherited logging runtime after fork")
        with self._lifecycle_lock:
            if not self._closed:
                try:
                    self._provider.force_flush()
                except Exception:
                    _diagnostic("flush", "OpenTelemetry flush did not complete cleanly.")
            return self.stats()

    def shutdown(self) -> ExportStats:
        """Detach only our handler; let OTel drain and shut down its batch worker.

        Best effort on graceful exit. No guarantee on SIGKILL, process crashes,
        queue overflow, rejected records, or network outages. This is not an
        audit-log delivery guarantee.
        """
        global _active_runtime
        if os.getpid() != self._pid:
            # Read an approximate snapshot without touching inherited locks.
            c = self._counters
            return ExportStats(
                c.received, c.success, c.failed, c.bridge_errors,
                max(0, c.received - c.success - c.failed),
            )
        with _registry_lock, self._lifecycle_lock:
            if self._closed:
                return self.stats()
            self._closed = True
            self._target.removeHandler(self._handler)
            self._handler.acquire()
            try:
                self._handler.accepting = False
            finally:
                self._handler.release()
            try:
                # BatchLogRecordProcessor.shutdown already drains the queue.
                # Avoid an extra, potentially long synchronous force_flush here.
                self._provider.shutdown()
            except Exception:
                _diagnostic("shutdown", "OpenTelemetry shutdown did not complete cleanly.")
            finally:
                self._handler.close()
                if (
                    self._installed_level is not None
                    and self._target.level == self._installed_level
                ):
                    self._target.setLevel(self._original_level)
                atexit.unregister(self.shutdown)
                if _active_runtime is self:
                    _active_runtime = None
            report = self.stats()
            if not report.ok:
                _diagnostic(
                    "shutdown_loss",
                    "Logging stopped with failed or unaccounted records. "
                    "Inspect runtime.stats() and verify the destination table.",
                )
            return report

    def __enter__(self) -> ZerobusLoggingRuntime:
        if self._closed:
            raise RuntimeError("This logging runtime is already closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.shutdown()
        return False


def initialize_logging(
    config: ZerobusLoggingConfig,
    token_provider: ZerobusTokenProvider,
    *,
    preflight_auth: bool = True,
) -> ZerobusLoggingRuntime:
    """Initialize once per task/process, reusing only an identical active setup.

    Repeated calls with the same config and provider object return the same
    runtime. Changed config/identity requires shutdown first. The preflight only
    checks token issuance; it does not prove that Zerobus or the table is usable.
    """
    global _active_runtime
    if _active_runtime is not None and _active_runtime._pid != os.getpid():
        raise RuntimeError("Do not inherit a running gRPC logging setup across fork")
    with _registry_lock:
        current = _active_runtime
        if current is not None and not current.closed:
            if current._pid != os.getpid():
                raise RuntimeError(
                    "Do not fork after starting gRPC logging; start a fresh process"
                )
            if current.config == config and current.token_provider is token_provider:
                return current
            raise RuntimeError(
                "Logging is already active with another config/provider; "
                "reuse that setup or shut it down before reinitializing"
            )
        if preflight_auth:
            token_provider.get_token()

        credentials = grpc.composite_channel_credentials(
            grpc.ssl_channel_credentials(
                root_certificates=config.tls_root_certificates
            ),
            grpc.metadata_call_credentials(
                DynamicBearerAuth(token_provider), name="zerobus-federation"
            ),
        )
        exporter = OTLPLogExporter(
            endpoint=config.endpoint,
            insecure=False,
            credentials=credentials,
            headers=((
                "x-databricks-zerobus-table-name", token_provider.table_name
            ),),
            timeout=config.export_timeout_seconds,
            compression=grpc.Compression.Gzip,
            meter_provider=NoOpMeterProvider(),
        )
        counters = _Counters()
        observed = _ObservedExporter(exporter, counters)
        attrs = {
            **dict(config.resource_attributes),
            "service.name": config.service_name or "unknown_service",
            "service.instance.id": str(uuid.uuid4()),
            "process.pid": os.getpid(),
        }
        if config.environment is not None:
            attrs["deployment.environment.name"] = config.environment
        provider = LoggerProvider(
            resource=Resource(attrs),
            shutdown_on_exit=False,
            meter_provider=NoOpMeterProvider(),
        )
        try:
            provider.add_log_record_processor(BatchLogRecordProcessor(
                observed,
                max_queue_size=config.queue_size,
                max_export_batch_size=config.batch_size,
                schedule_delay_millis=config.schedule_delay_millis,
                export_timeout_millis=int(config.export_timeout_seconds * 1000),
            ))
            handler = _BridgeHandler(
                provider=provider, level=config.level, counters=counters
            )
            handler.addFilter(_InfrastructureFilter(config.excluded_namespaces))
            target = logging.getLogger(config.logger_name)
            original_level = target.level
            installed_level = None
            if target.getEffectiveLevel() > config.level:
                target.setLevel(config.level)
                installed_level = config.level
            target.addHandler(handler)
        except Exception:
            provider.shutdown()
            raise

        runtime = ZerobusLoggingRuntime(
            config, token_provider, provider, handler, target, counters,
            original_level, installed_level,
        )
        _active_runtime = runtime
        atexit.register(runtime.shutdown)
        return runtime


def _azure_workspace_id(workspace_url: str) -> tuple[str, str]:
    """Return normalized Azure Databricks workspace URL and numeric workspace ID."""
    origin = https_origin(workspace_url, "workspace_url")
    hostname = urlsplit(origin).hostname or ""
    match = _AZURE_WORKSPACE_HOST_RE.fullmatch(hostname)
    if not match:
        raise ValueError(
            "workspace_url must use the standard Azure Databricks host format "
            "https://adb-<workspace-id>.<shard>.azuredatabricks.net"
        )
    return origin, match.group(1)


@dataclass(frozen=True)
class _Connection:
    """Used only to compare repeated setup calls; secrets never appear in repr."""
    tenant_id: str
    client_id: str
    client_secret: str | Callable[[], str] = field(repr=False)
    workspace_url: str
    workspace_id: str
    table_name: str
    oauth_timeout_seconds: float
    oauth_ca_file: str | None


def configure_logging(
    *,
    tenant_id: str,
    client_id: str,
    client_secret: str | Callable[[], str],
    workspace_url: str,
    table_name: str,
    config: ZerobusLoggingConfig,
    oauth_timeout_seconds: float = 5.0,
    oauth_ca_file: str | None = None,
    preflight_auth: bool = True,
) -> ZerobusLoggingRuntime:
    """Complete Azure Entra client-credentials -> exchange -> OTLP logging setup.

    The same application/client ID is used for the Entra service principal and
    the corresponding Databricks service principal. The numeric Databricks
    workspace ID is derived from the validated standard Azure Databricks host.
    Authentication behavior is otherwise unchanged: the source Entra token uses
    the Azure Databricks resource scope, then RFC 8693 exchange mints a
    table-scoped Zerobus token for that workspace.

    No token helper is required from the caller. The approved Databricks target
    principal must already have a workload federation policy and UC grants.
    There is deliberately no lookup of DATABRICKS_* credentials, native App
    Telemetry, Azure ARM resource IDs, or PATs.

    Repeated calls with equal configuration and the same credentials return the
    active runtime. A changed secret/identity/configuration requires shutdown
    first (or a stable callable secret supplier may read a rotating secret).
    Construct only after worker processes have started, never before forking.
    """
    if not isinstance(config, ZerobusLoggingConfig):
        raise TypeError("config must be a ZerobusLoggingConfig")
    if not isinstance(client_id, str) or not client_id.strip():
        raise ValueError("client_id for the approved Entra/Databricks SP is required")
    normalized_workspace_url, workspace_id = _azure_workspace_id(workspace_url)
    connection = _Connection(
        tenant_id, client_id, client_secret, normalized_workspace_url,
        workspace_id, table_name, oauth_timeout_seconds, oauth_ca_file,
    )
    if _active_runtime is not None and _active_runtime._pid != os.getpid():
        raise RuntimeError("Initialize logging separately after starting each process")
    with _registry_lock:
        current = _active_runtime
        if current is not None and not current.closed:
            if current.config == config and getattr(current, "_connection", None) == connection:
                return current
            raise RuntimeError(
                "Logging is active with different credentials or configuration; "
                "shut it down before changing the setup"
            )
        http = OAuthHttpClient(oauth_timeout_seconds, ca_file=oauth_ca_file)
        entra = EntraClientSecretTokenProvider(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            scope=_AZURE_DATABRICKS_SCOPE,
            http_client=http,
            minimum_validity_seconds=30,
        )
        zerobus = ZerobusTokenProvider(
            workspace_url=connection.workspace_url,
            workspace_id=workspace_id,
            table_name=table_name,
            get_subject_token=entra.get_token,
            databricks_client_id=client_id,
            http_client=http,
            minimum_validity_seconds=30,
        )
        runtime = initialize_logging(config, zerobus, preflight_auth=preflight_auth)
        runtime.entra_token_provider = entra
        runtime._connection = connection
        return runtime
