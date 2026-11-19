"""Utilities for packaged timeseries resources and registration workflows."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date
from typing import Any, TypedDict

import oeds.core.time_utils as timeutils
import oeds.domain.utils.config.config_utils as config_utils
from oeds.core.auth_utils import AuthUtils

from .time_series_manager import Freq, TimeSeriesCollection, TimeSeriesManager

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_FILE = "default.json"
_DEFAULT_CONFIG_PACKAGE = "oeds.config.timeseries"


class _OptionalTimeSeriesObservation(TypedDict, total=False):
    date: date | None
    missing_value_label: str | None


class TimeSeriesObservation(_OptionalTimeSeriesObservation):
    """One time-series observation accepted by :meth:`write_observations`."""

    time_series_name: str
    value: float | int | None


class TimeSeriesUtils:
    """Manage timeseries registration, observation writes, and publishing."""

    def __init__(
        self,
        *,
        tsm_ctx: Mapping[str, Any],
    ) -> None:
        """Initialize the facade and its time-series manager.

        Args:
            tsm_ctx: Pipeline and job metadata used to configure
                :class:`TimeSeriesManager`.

        Raises:
            TypeError: If ``tsm_ctx`` is not a mapping.
        """
        if not isinstance(tsm_ctx, Mapping):
            raise TypeError("tsm_ctx must be a mapping")

        self.tsm_ctx = dict(tsm_ctx)
        self._config_manager = config_utils.ConfigManager.get_instance(
            _DEFAULT_CONFIG_PACKAGE
        )
        self._tsm = TimeSeriesManager(
            metadata_catalog=self.tsm_ctx.get("metadata_catalog"),
            pipeline_name=self.tsm_ctx.get("pipeline_name"),
            notebook_path=self.tsm_ctx.get("notebook_path"),
            current_user=self.tsm_ctx.get("current_user"),
            job_id=self.tsm_ctx.get("job_id"),
            job_runid=self.tsm_ctx.get("job_runid"),
            job_trigger_type=self.tsm_ctx.get("job_trigger_type"),
        )

        logger.info(
            "Initialized TimeseriesUtils for pipeline '%s'",
            self.tsm_ctx.get("pipeline_name"),
        )

    def _get_registry(
        self,
        config_file: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Load, render, and validate a packaged timeseries registry.

        Args:
            config_file: JSON template filename within the fixed timeseries
                configuration package.
            params: Values used to render the template. A non-empty
                ``destination_uc_table`` value is required.

        Returns:
            Rendered registry containing a non-empty provider list.

        Raises:
            TypeError: If ``params`` is not a dictionary or contains non-string keys.
            ValueError: If required input is missing, template rendering fails,
                or the rendered registry is invalid.
        """
        if not config_file or not str(config_file).strip():
            raise ValueError("config_file is required")
        if not isinstance(params, dict):
            raise TypeError("params must be a dict")

        destination_uc_table = params.get("destination_uc_table")
        if (
            not isinstance(destination_uc_table, str)
            or not destination_uc_table.strip()
        ):
            raise ValueError(
                "params must include a non-empty destination_uc_table string"
            )

        config_name = str(config_file).strip()
        logger.info(
            "Loading timeseries config '%s' from package '%s'",
            config_name,
            _DEFAULT_CONFIG_PACKAGE,
        )

        registry_text = self._config_manager.load_config_resource(
            config_name, params=params
        )

        try:
            registry = json.loads(registry_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Rendered timeseries config '{config_name}' must be valid JSON"
            ) from exc

        if not isinstance(registry, dict):
            raise ValueError("Timeseries registry must be a JSON object.")

        providers = registry.get("providers")
        if not isinstance(providers, list) or not providers:
            raise ValueError(
                "Timeseries registry must define providers as a non-empty list."
            )

        logger.debug(
            "Loaded timeseries registry '%s' with %s provider(s)",
            config_name,
            len(providers),
        )
        return registry

    def write_observations(
        self,
        *,
        observations: Sequence[TimeSeriesObservation],
        full_table_name: str,
        default_date: date | None = None,
        default_missing_value_label: str = "ND",
    ) -> int:
        """Append new observations and changed versions from one batch.

        Compare numeric and string values against the latest stored version of
        each series/UTC calendar-date pair, ignoring the stored time of day.
        Calendar-date extraction uses the existing Spark session timezone,
        expected to be UTC. Store supplied dates at UTC midnight. Skip unchanged
        observations and preserve historical timestamps.
        Only series with appended rows receive transaction-log entries.

        Args:
            observations: Sequence of observation mappings. Each mapping requires
                ``time_series_name`` and ``value``. Optional ``date`` and
                ``missing_value_label`` values override the batch defaults.
            full_table_name: Fully qualified destination table name.
            default_date: Date used when an observation omits ``date`` or sets
                it to ``None``. Defaults to the current local date.
            default_missing_value_label: Label used for a ``None`` value when an
                observation omits ``missing_value_label`` or sets it to ``None``.
                Defaults to ``"ND"``.

        Returns:
            Metadata audit surrogate key, including for an unchanged batch.

        Raises:
            TypeError: If the sequence, a record, or a field has an invalid type.
            ValueError: If the sequence is empty, the table name is missing, or
                a record is missing a required property or has an invalid value.
        """
        # Strings and bytes satisfy the Sequence protocol but cannot represent
        # an observation batch, so exclude them explicitly from the public input.
        if not isinstance(observations, Sequence) or isinstance(
            observations, (str, bytes, bytearray)
        ):
            raise TypeError("observations must be a sequence of mappings")
        # Reject an empty batch before the manager can create an audit record
        # for a write that has no observations.
        if not observations:
            raise ValueError("observations must not be empty")

        # Validate batch-scoped options once before examining individual records.
        if not full_table_name or not str(full_table_name).strip():
            raise ValueError("full_table_name is required")
        if default_date is not None and not isinstance(default_date, date):
            raise TypeError("default_date must be a date or None")
        if not isinstance(default_missing_value_label, str):
            raise TypeError("default_missing_value_label must be a string")

        normalized_observations: list[
            tuple[str, float | int | None, date | None, str | None]
        ] = []

        # Normalize the complete batch before calling the manager so malformed
        # input cannot create an audit record or partially reach storage. The
        # TypedDict helps static analysis, but callers still pass ordinary runtime
        # objects that must be checked here.
        for index, record in enumerate(observations):
            if not isinstance(record, Mapping):
                raise TypeError(f"observations[{index}] must be a mapping")

            # Check required properties by name so the failure identifies the
            # exact property the caller needs to supply.
            if "time_series_name" not in record:
                raise ValueError(
                    f"observations[{index}].time_series_name is required"
                )
            if "value" not in record:
                raise ValueError(f"observations[{index}].value is required")

            # Only the four named contract properties participate in the write;
            # unrelated fields in the caller's mapping are left untouched.
            # Normalize surrounding whitespace once so collection records and
            # transaction-log identities use the same series name.
            time_series_name = record["time_series_name"]
            if not isinstance(time_series_name, str) or not time_series_name.strip():
                raise ValueError(
                    f"observations[{index}].time_series_name must be a "
                    "non-empty string"
                )

            # Validate the public numeric contract before TimeSeriesCollection
            # converts non-null values to float.
            value = record["value"]
            if value is not None and not isinstance(value, (float, int)):
                raise TypeError(
                    f"observations[{index}].value must be numeric or None"
                )

            # A missing date key and an explicit None have identical fallback
            # behavior; a concrete date always overrides the batch default.
            record_date = record.get("date")
            if record_date is not None and not isinstance(record_date, date):
                raise TypeError(
                    f"observations[{index}].date must be a date or None"
                )

            # The label is optional because it is relevant only when value is
            # None. A missing key or explicit None selects the batch default.
            missing_value_label = record.get("missing_value_label")
            if missing_value_label is not None and not isinstance(
                missing_value_label, str
            ):
                raise TypeError(
                    f"observations[{index}].missing_value_label must be a "
                    "string or None"
                )

            # Copy validated values into an internal representation instead of
            # trimming names or applying defaults in the caller's dictionaries.
            normalized_observations.append(
                (
                    time_series_name.strip(),
                    value,
                    record_date,
                    missing_value_label,
                )
            )

        # Resolve local today only when at least one record needs it, and resolve
        # it at most once so every undated record receives the same batch date.
        resolved_default_date = default_date
        if resolved_default_date is None and any(
            record_date is None
            for _, _, record_date, _ in normalized_observations
        ):
            resolved_default_date = timeutils.today_local()

        normalized_table_name = str(full_table_name).strip()
        collection = TimeSeriesCollection()

        # Translate the public record shape into the manager's collection schema.
        # Missing-value labels are stored only when the numeric value is absent.
        for time_series_name, value, record_date, missing_value_label in (
            normalized_observations
        ):
            # Validation guarantees that an undated record has a resolved batch
            # fallback by this point.
            resolved_date = record_date or resolved_default_date

            # The destination schema separates numeric observations from string
            # missing-value markers. Numeric values therefore keep
            # observation_str as None even when a label was supplied.
            observation_str = None
            if value is None:
                observation_str = (
                    missing_value_label
                    if missing_value_label is not None
                    else default_missing_value_label
                )

            collection.add(
                time_series_name=time_series_name,
                date=resolved_date,
                observation=value,
                observation_str=observation_str,
            )

        logger.info(
            "Inserting %s time-series observation(s) into '%s'",
            len(normalized_observations),
            normalized_table_name,
        )
        # This manager call is the first persistence boundary: it creates the
        # audit record, appends the observations, and updates the transaction log.
        metadata_audit_skey = self._tsm.insert_observations(
            series_collection=collection,
            full_table_name=normalized_table_name,
        )
        logger.info(
            "Wrote observations with metadata audit skey '%s'", metadata_audit_skey
        )
        return metadata_audit_skey

    def publish_to_webmart(
        self,
        metadata_audit_skey: int,
        datamart_endpoints: Any,
        azure_tenant_id: str,
        service_spn_id: str,
        service_spn_secrete: str,
        timeout: int = 600,
    ) -> Any:
        """Publish one observation batch to the supplied datamart endpoints.

        Args:
            metadata_audit_skey: Audit key identifying the batch to publish.
            datamart_endpoints: Endpoint definitions containing URL and scope
                values.
            azure_tenant_id: Azure tenant used for service-principal auth.
            service_spn_id: Service-principal client identifier.
            service_spn_secrete: Service-principal client secret.
            timeout: HTTP request timeout in seconds.

        Returns:
            Response from the first successful Datamart endpoint.

        Raises:
            ValueError: If a required argument is missing or no endpoint
                succeeds.
        """
        if metadata_audit_skey is None:
            raise ValueError("metadata_audit_skey is required.")
        if datamart_endpoints is None:
            raise ValueError("datamart_endpoints is required.")
        for parameter_name, credential_value in (
            ("azure_tenant_id", azure_tenant_id),
            ("service_spn_id", service_spn_id),
            ("service_spn_secrete", service_spn_secrete),
        ):
            if not isinstance(credential_value, str) or not credential_value.strip():
                raise ValueError(f"{parameter_name} is required.")

        # Keep publishing credentials scoped to this operation and off the facade.
        auth = AuthUtils(
            tenant_id=azure_tenant_id,
            client_id=service_spn_id,
            client_secret=service_spn_secrete,
        )

        logger.info(
            "Publishing metadata audit skey '%s' to datamart with timeout=%s",
            metadata_audit_skey,
            timeout,
        )
        return self._tsm.publish_batch_to_datamart(
            endpoints=datamart_endpoints,
            auth=auth,
            audit_skey=metadata_audit_skey,
            timeout=timeout,
        )

    def register_time_series(
        self,
        *,
        config_file: str = _DEFAULT_CONFIG_FILE,
        params: dict[str, Any],
    ) -> int:
        """Replace providers, datasets, and series from a packaged registry.

        Existing matching entries are deleted before registration. Provider,
        dataset, and series entries may set ``create`` to ``false`` to skip
        their registration independently.

        Args:
            config_file: JSON template filename within the fixed timeseries
                configuration package.
            params: Template values, including the fully qualified
                ``destination_uc_table``.

        Returns:
            Audit surrogate key created for the final registered provider.

        Raises:
            TypeError: If a provider, dataset, or series entry has the wrong
                structure.
            ValueError: If required registry fields or values are invalid.
        """
        registry = self._get_registry(config_file=config_file, params=params)
        providers = registry["providers"]
        audit_log_skey: int | None = None

        for provider in providers:
            if not isinstance(provider, dict):
                raise TypeError(
                    "Each provider in the timeseries registry must be an object."
                )

            provider_payload = deepcopy(provider)
            provider_name = str(provider_payload.get("short_name_en") or "").strip()
            if not provider_name:
                raise ValueError("Each provider must define short_name_en.")

            datasets = provider_payload.pop("datasets")
            if not isinstance(datasets, list):
                raise ValueError(
                    f"Provider '{provider_name}' must define datasets as a list."
                )

            create_provider = provider_payload.pop("create", True)
            if not isinstance(create_provider, bool):
                raise ValueError(
                    f"Provider '{provider_name}' must define create as a boolean."
                )
            if create_provider and not provider_payload.get("name_en"):
                raise ValueError(
                    f"Provider '{provider_name}' must define name_en when "
                    "create is true."
                )

            logger.info(
                "Registering %s timeseries dataset(s) for provider '%s'",
                len(datasets),
                provider_name,
            )
            audit_log_skey = self._tsm.create_audit_log()
            logger.info(
                "Created audit log skey '%s' for provider '%s'",
                audit_log_skey,
                provider_name,
            )

            if create_provider:
                provider_payload["short_name_en"] = provider_name
                provider_payload["audit_log_skey"] = audit_log_skey
                self._tsm.delete_data_provider(provider_name)
                registered_provider = self._tsm.register_data_provider(
                    **provider_payload
                )
                logger.info("Registered provider '%s'", provider_name)
                logger.debug(
                    "Registered provider '%s': %s",
                    provider_name,
                    registered_provider,
                )
            else:
                logger.info(
                    "Skipping provider '%s' because create is false",
                    provider_name,
                )

            for dataset in datasets:
                if not isinstance(dataset, dict):
                    raise TypeError(
                        "Each dataset in the timeseries registry must be an object."
                    )

                # A name-only entry documents a dataset without registering it.
                if set(dataset.keys()) == {"name_en"}:
                    logger.info(
                        "Skipping dataset '%s' for provider '%s' because it only defines name_en",
                        dataset["name_en"],
                        provider_name,
                    )
                    continue

                dataset_payload = deepcopy(dataset)
                data_set_name_en = dataset_payload.get("name_en")
                if not data_set_name_en:
                    raise ValueError("Each dataset must define name_en.")

                create_dataset = dataset_payload.pop("create", True)
                if not isinstance(create_dataset, bool):
                    raise ValueError(
                        f"Dataset '{data_set_name_en}' must define create as a boolean."
                    )

                # Series are registered separately from their parent dataset.
                series_list = dataset_payload.pop("series", [])
                if not isinstance(series_list, list):
                    raise ValueError(
                        f"Dataset '{data_set_name_en}' must define series as a list."
                    )

                if create_dataset:
                    destination_uc_tables = dataset_payload.get(
                        "destination_uc_tables"
                    )
                    if (
                        not isinstance(destination_uc_tables, dict)
                        or not destination_uc_tables
                    ):
                        raise ValueError(
                            f"Dataset '{data_set_name_en}' must define "
                            "destination_uc_tables as a non-empty dict."
                        )
                    for table_ref, full_table_name in destination_uc_tables.items():
                        if not isinstance(table_ref, str) or not table_ref.strip():
                            raise ValueError(
                                "destination_uc_tables keys must be non-empty "
                                "strings."
                            )
                        if (
                            not isinstance(full_table_name, str)
                            or not full_table_name.strip()
                        ):
                            raise ValueError(
                                "destination_uc_tables values must be non-empty "
                                "strings."
                            )

                    dataset_payload["data_provider_short_name_en"] = provider_name
                    dataset_payload["audit_log_skey"] = audit_log_skey

                    logger.info(
                        "Registering dataset '%s' with %s series for provider '%s'",
                        data_set_name_en,
                        len(series_list),
                        provider_name,
                    )
                    # Registration replaces an existing dataset with the same identity.
                    self._tsm.delete_data_set(
                        data_provider_short_name_en=provider_name,
                        name_en=data_set_name_en,
                    )
                    registered_dataset = self._tsm.register_data_set(
                        **dataset_payload
                    )
                    logger.debug(
                        "Registered dataset '%s': %s",
                        data_set_name_en,
                        registered_dataset,
                    )
                else:
                    logger.info(
                        "Skipping dataset '%s' for provider '%s' because "
                        "create is false",
                        data_set_name_en,
                        provider_name,
                    )

                for series in series_list:
                    if not isinstance(series, dict):
                        raise TypeError(
                            f"Dataset '{data_set_name_en}' contains a non-object series definition."
                        )

                    series_payload = deepcopy(series)
                    provider_series_name = series_payload.get("provider_series_name")
                    if not provider_series_name:
                        raise ValueError(
                            f"Dataset '{data_set_name_en}' contains a series without provider_series_name."
                        )

                    create_series = series_payload.pop("create", True)
                    if not isinstance(create_series, bool):
                        raise ValueError(
                            f"Series '{provider_series_name}' must define create "
                            "as a boolean."
                        )
                    if not create_series:
                        logger.info(
                            "Skipping timeseries '%s#%s' because create is false",
                            provider_series_name,
                            provider_name,
                        )
                        continue

                    destination_uc_table = series_payload.get("destination_uc_table")
                    if (
                        not isinstance(destination_uc_table, str)
                        or not destination_uc_table.strip()
                    ):
                        raise ValueError(
                            f"Series '{provider_series_name}' in dataset "
                            f"'{data_set_name_en}' must define destination_uc_table "
                            "as a non-empty string."
                        )

                    frequency = series_payload.get("frequency")
                    if isinstance(frequency, str):
                        try:
                            series_payload["frequency"] = Freq(frequency.strip())
                        except ValueError as exc:
                            raise ValueError(
                                f"Series '{provider_series_name}' has invalid frequency "
                                f"'{frequency}'."
                            ) from exc

                    series_payload["data_provider_short_name_en"] = provider_name
                    series_payload["data_set_name_en"] = data_set_name_en

                    time_series_name = f"{provider_series_name}#{provider_name}".lower()
                    self._tsm.delete_time_series(time_series_name)
                    registered_series = self._tsm.register_time_series(**series_payload)
                    logger.info("Registered timeseries '%s'", time_series_name)
                    logger.debug(
                        "Registered timeseries payload '%s': %s",
                        time_series_name,
                        registered_series,
                    )

        if audit_log_skey is None:
            raise ValueError("Timeseries registry must define at least one provider.")

        return audit_log_skey
