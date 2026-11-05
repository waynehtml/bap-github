"""Create and remove Unity Catalog resources described by a Testbench case.

Resource definitions form a catalog, schema, table, volume, and file hierarchy.
This module applies that hierarchy in creation order and reverses it for safe
teardown while respecting per-resource ``create`` ownership flags.
"""

from __future__ import annotations

import logging
import posixpath
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from pyspark.sql import SparkSession

from databricks_tools_core.unity_catalog import (
    create_catalog,
    create_schema,
    create_volume,
    delete_catalog,
    delete_from_volume,
    delete_schema,
    delete_table,
    delete_volume,
    get_catalog,
    get_schema,
    get_table,
    get_volume,
    list_schemas,
    upload_to_volume,
)

logger = logging.getLogger(__name__)

_TABLE_SOURCE_FORMAT = "parquet"


class ResourceUtils:
    """Manage the configured environment for one Testbench execution.

    A resource with ``create: false`` is treated as shared: setup may populate
    its managed children, but normal teardown does not delete the shared parent.
    The helper acquires Spark locally so lifecycle orchestration remains runtime
    independent.
    """

    def __init__(self, case_root: str) -> None:
        """Initialize integration-test environment management.

        Args:
            case_root: Unity Catalog Volume directory containing the test data
                referenced by relative paths in the selected case.

        Returns:
            None.
        """
        self.case_root = self._validate_case_root(case_root)
        self.spark = (
            SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        )

    def create_resources(self, test_config: dict[str, Any]) -> None:
        """Create the Unity Catalog environment defined by a test case.

        Args:
            test_config: Integration test config loaded from JSON.

        Returns:
            None.
        """
        setup_config = self._lifecycle_step(test_config, "setup")
        if setup_config.get("enabled") is False:
            logger.info("Integration test resource setup is disabled.")
            return

        for catalog_config in self._catalog_configs(test_config):
            self.create_catalog_resources(catalog_config)

    def drop_resources(self, test_config: dict[str, Any]) -> None:
        """Drop the Unity Catalog environment defined by a test case.

        Args:
            test_config: Integration test config loaded from JSON.

        Returns:
            None.
        """
        teardown_config = self._lifecycle_step(test_config, "teardown")
        if teardown_config.get("enabled") is False:
            logger.info("Integration test resource teardown is disabled.")
            return

        # Children and later declarations are removed first, mirroring stack
        # unwinding and avoiding parent-before-child deletion failures.
        for catalog_config in reversed(self._catalog_configs(test_config)):
            self.drop_catalog_resources(catalog_config)

    def drop_all(self, test_config: dict[str, Any]) -> None:
        """Drop test catalogs or all schemas in configured shared catalogs.

        If a catalog is configured with ``create: false``, the
        catalog is treated as shared and every schema in the catalog is dropped.
        Otherwise, the catalog is deleted with force enabled.

        Args:
            test_config: Integration test config loaded from JSON.

        Returns:
            None.
        """
        teardown_config = self._lifecycle_step(test_config, "teardown")
        if teardown_config.get("enabled") is False:
            logger.info("Integration test resource teardown is disabled.")
            return

        for catalog_config in reversed(self._catalog_configs(test_config)):
            self.drop_catalog_all(catalog_config)

    def create_catalog_resources(self, catalog_config: dict[str, Any]) -> None:
        """Create one catalog and its configured schemas.

        Args:
            catalog_config: Catalog environment configuration from the test case.

        Returns:
            None.
        """
        if not isinstance(catalog_config, dict):
            raise ValueError(
                "Each integration test environment catalog must be an object."
            )

        catalog_name = self._text_field(
            catalog_config, "name", "environment.catalogs.name"
        )
        if catalog_config.get("create") is False:
            logger.info("Skipping catalog creation for %s", catalog_name)
        elif self._exists(get_catalog, catalog_name):
            logger.info("Catalog already exists: %s", catalog_name)
        else:
            logger.info("Creating managed catalog: %s", catalog_name)
            create_catalog(name=catalog_name, comment=catalog_config.get("comment"))

        for schema_config in self._list_field(
            catalog_config,
            "schemas",
            label=f"environment.catalogs.{catalog_name}.schemas",
        ):
            self.create_schema_resources(catalog_name, schema_config)

    def drop_catalog_resources(self, catalog_config: dict[str, Any]) -> None:
        """Drop one catalog and its configured schemas.

        Args:
            catalog_config: Catalog environment configuration from the test case.

        Returns:
            None.
        """
        if not isinstance(catalog_config, dict):
            raise ValueError(
                "Each integration test environment catalog must be an object."
            )

        catalog_name = self._text_field(
            catalog_config, "name", "environment.catalogs.name"
        )
        schema_configs = self._list_field(
            catalog_config,
            "schemas",
            label=f"environment.catalogs.{catalog_name}.schemas",
        )
        for schema_config in reversed(schema_configs):
            self.drop_schema_resources(catalog_name, schema_config)

        if catalog_config.get("create") is False:
            logger.info("Skipping catalog deletion for %s", catalog_name)
        elif self._exists(get_catalog, catalog_name):
            logger.info("Deleting managed catalog: %s", catalog_name)
            delete_catalog(catalog_name)
        else:
            logger.info("Catalog already absent: %s", catalog_name)

    def drop_catalog_all(self, catalog_config: dict[str, Any]) -> None:
        """Drop one catalog or every schema when the catalog is shared.

        Args:
            catalog_config: Catalog environment configuration from the test case.

        Returns:
            None.
        """
        if not isinstance(catalog_config, dict):
            raise ValueError(
                "Each integration test environment catalog must be an object."
            )

        catalog_name = self._text_field(
            catalog_config, "name", "environment.catalogs.name"
        )
        # Managed catalogs can be deleted as one unit. A shared catalog must be
        # retained, so drop_all removes its schemas instead.
        if catalog_config.get("create") is not False:
            if self._exists(get_catalog, catalog_name):
                logger.info(
                    "Deleting managed catalog and all children: %s", catalog_name
                )
                delete_catalog(catalog_name, force=True)
            else:
                logger.info("Catalog already absent: %s", catalog_name)
            return

        self.drop_all_schemas_in_catalog(catalog_name)

    def drop_all_schemas_in_catalog(self, catalog_name: str) -> None:
        """Drop every schema in a shared Unity Catalog catalog.

        Args:
            catalog_name: Parent Unity Catalog catalog name.

        Returns:
            None.
        """
        if not self._exists(get_catalog, catalog_name):
            logger.info("Catalog already absent: %s", catalog_name)
            return

        schemas = list_schemas(catalog_name)
        for schema in reversed(schemas):
            schema_name = getattr(schema, "name", None)
            full_schema_name = getattr(schema, "full_name", None) or (
                f"{catalog_name}.{schema_name}" if schema_name else None
            )
            if not full_schema_name:
                logger.warning(
                    "Skipping schema with missing name in catalog %s: %s",
                    catalog_name,
                    schema,
                )
                continue

            logger.info("Deleting schema from shared catalog: %s", full_schema_name)
            delete_schema(full_schema_name)

    def create_schema_resources(
        self, catalog_name: str, schema_config: dict[str, Any]
    ) -> None:
        """Create one schema and its configured table and volume resources.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_config: Schema resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(schema_config, dict):
            raise ValueError("Each integration test schema resource must be an object.")

        schema_name = self._text_field(schema_config, "name", "schema.name")
        full_schema_name = f"{catalog_name}.{schema_name}"

        if schema_config.get("create") is False:
            logger.info("Skipping schema creation for %s", full_schema_name)
        elif self._exists(get_schema, full_schema_name):
            logger.info("Schema already exists: %s", full_schema_name)
        else:
            logger.info("Creating schema: %s", full_schema_name)
            create_schema(
                catalog_name=catalog_name,
                schema_name=schema_name,
                comment=schema_config.get("comment"),
            )

        for table_config in self._list_field(
            schema_config, "tables", label=f"{full_schema_name}.tables"
        ):
            self.create_table(catalog_name, schema_name, table_config)

        for volume_config in self._list_field(
            schema_config, "volumes", label=f"{full_schema_name}.volumes"
        ):
            self.create_volume_resources(catalog_name, schema_name, volume_config)

    def drop_schema_resources(
        self, catalog_name: str, schema_config: dict[str, Any]
    ) -> None:
        """Drop one schema and its configured table and volume resources.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_config: Schema resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(schema_config, dict):
            raise ValueError("Each integration test schema resource must be an object.")

        schema_name = self._text_field(schema_config, "name", "schema.name")
        full_schema_name = f"{catalog_name}.{schema_name}"

        table_configs = self._list_field(
            schema_config, "tables", label=f"{full_schema_name}.tables"
        )
        for table_config in reversed(table_configs):
            self.drop_table(catalog_name, schema_name, table_config)

        volume_configs = self._list_field(
            schema_config, "volumes", label=f"{full_schema_name}.volumes"
        )
        for volume_config in reversed(volume_configs):
            self.drop_volume_resources(catalog_name, schema_name, volume_config)

        if schema_config.get("create") is False:
            logger.info("Skipping schema deletion for %s", full_schema_name)
        elif self._exists(get_schema, full_schema_name):
            logger.info("Deleting schema: %s", full_schema_name)
            delete_schema(full_schema_name)
        else:
            logger.info("Schema already absent: %s", full_schema_name)

    def drop_schema_all(self, catalog_name: str, schema_config: dict[str, Any]) -> None:
        """Drop one configured schema and all configured child resources.

        This coarse teardown mode ignores resource-level ``create`` flags under
        the schema because the whole schema is being removed.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_config: Schema resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(schema_config, dict):
            raise ValueError("Each integration test schema resource must be an object.")

        schema_name = self._text_field(schema_config, "name", "schema.name")
        full_schema_name = f"{catalog_name}.{schema_name}"

        table_configs = self._list_field(
            schema_config, "tables", label=f"{full_schema_name}.tables"
        )
        for table_config in reversed(table_configs):
            self.drop_table_all(catalog_name, schema_name, table_config)

        volume_configs = self._list_field(
            schema_config, "volumes", label=f"{full_schema_name}.volumes"
        )
        for volume_config in reversed(volume_configs):
            self.drop_volume_all(catalog_name, schema_name, volume_config)

        if self._exists(get_schema, full_schema_name):
            logger.info("Deleting schema and configured children: %s", full_schema_name)
            delete_schema(full_schema_name)
        else:
            logger.info("Schema already absent: %s", full_schema_name)

    def create_table(
        self, catalog_name: str, schema_name: str, table_config: dict[str, Any]
    ) -> None:
        """Create or replace a managed table from a configured Parquet source.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            table_config: Table resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(table_config, dict):
            raise ValueError(
                f"Each table resource in schema '{schema_name}' must be an object."
            )

        table_name = self._text_field(table_config, "name", "table.name")
        full_table_name = f"{catalog_name}.{schema_name}.{table_name}"
        if table_config.get("create") is False:
            logger.info("Skipping table creation for %s", full_table_name)
            return

        source_config = self._dict_field(
            table_config, "source", label=f"{full_table_name}.source"
        )
        source_format = self._text_field(
            source_config, "format", f"{full_table_name}.source.format"
        ).lower()
        if source_format != _TABLE_SOURCE_FORMAT:
            raise ValueError(
                f"Table source format for '{full_table_name}' must be "
                f"'{_TABLE_SOURCE_FORMAT}', got '{source_format}'."
            )
        source_path = self.resolve_test_path(source_config.get("path"))
        source_options = self._dict_field(
            source_config,
            "options",
            label=f"{full_table_name}.source.options",
            required=False,
        )
        table_mode = str(table_config.get("mode") or "overwrite").strip()
        table_format = str(table_config.get("table_format") or "delta").strip()

        logger.info("Creating managed table %s from %s", full_table_name, source_path)
        reader = self.spark.read.format(source_format)
        for option_name, option_value in source_options.items():
            reader = reader.option(
                str(option_name), self.spark_option_value(option_value)
            )

        dataframe = reader.load(self.spark_source_path(source_path))
        dataframe.write.mode(table_mode).format(table_format).saveAsTable(
            full_table_name
        )

    def drop_table(
        self, catalog_name: str, schema_name: str, table_config: dict[str, Any]
    ) -> None:
        """Drop one configured managed table.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            table_config: Table resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(table_config, dict):
            raise ValueError(
                f"Each table resource in schema '{schema_name}' must be an object."
            )

        table_name = self._text_field(table_config, "name", "table.name")
        full_table_name = f"{catalog_name}.{schema_name}.{table_name}"
        if table_config.get("create") is False:
            logger.info("Skipping table deletion for %s", full_table_name)
        elif self._exists(get_table, full_table_name):
            logger.info("Deleting managed table: %s", full_table_name)
            delete_table(full_table_name)
        else:
            logger.info("Table already absent: %s", full_table_name)

    def drop_table_all(
        self, catalog_name: str, schema_name: str, table_config: dict[str, Any]
    ) -> None:
        """Drop one configured table regardless of its resource create flag.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            table_config: Table resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(table_config, dict):
            raise ValueError(
                f"Each table resource in schema '{schema_name}' must be an object."
            )

        table_name = self._text_field(table_config, "name", "table.name")
        full_table_name = f"{catalog_name}.{schema_name}.{table_name}"
        if self._exists(get_table, full_table_name):
            logger.info("Deleting managed table: %s", full_table_name)
            delete_table(full_table_name)
        else:
            logger.info("Table already absent: %s", full_table_name)

    def create_volume_resources(
        self, catalog_name: str, schema_name: str, volume_config: dict[str, Any]
    ) -> None:
        """Create one managed volume and upload its configured files.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            volume_config: Volume resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(volume_config, dict):
            raise ValueError(
                f"Each volume resource in schema '{schema_name}' must be an object."
            )

        volume_name = self._text_field(volume_config, "name", "volume.name")
        full_volume_name = f"{catalog_name}.{schema_name}.{volume_name}"

        if volume_config.get("create") is False:
            logger.info("Skipping volume creation for %s", full_volume_name)
        elif self._exists(get_volume, full_volume_name):
            logger.info("Volume already exists: %s", full_volume_name)
        else:
            logger.info("Creating managed volume: %s", full_volume_name)
            create_volume(
                catalog_name=catalog_name,
                schema_name=schema_name,
                name=volume_name,
                comment=volume_config.get("comment"),
            )

        # A shared volume may still receive files owned by this test case.
        for file_config in self._list_field(
            volume_config, "files", label=f"{full_volume_name}.files"
        ):
            self.upload_volume_file(catalog_name, schema_name, volume_name, file_config)

    def drop_volume_resources(
        self, catalog_name: str, schema_name: str, volume_config: dict[str, Any]
    ) -> None:
        """Drop one configured managed volume or its configured files.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            volume_config: Volume resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(volume_config, dict):
            raise ValueError(
                f"Each volume resource in schema '{schema_name}' must be an object."
            )

        volume_name = self._text_field(volume_config, "name", "volume.name")
        full_volume_name = f"{catalog_name}.{schema_name}.{volume_name}"

        if volume_config.get("create") is False:
            logger.info("Skipping volume deletion for %s", full_volume_name)
            # Remove only files owned by the case when the parent volume is
            # shared with other workloads.
            file_configs = self._list_field(
                volume_config, "files", label=f"{full_volume_name}.files"
            )
            for file_config in reversed(file_configs):
                self.drop_volume_file(
                    catalog_name, schema_name, volume_name, file_config
                )
        elif self._exists(get_volume, full_volume_name):
            logger.info("Deleting managed volume: %s", full_volume_name)
            delete_volume(full_volume_name)
        else:
            logger.info("Volume already absent: %s", full_volume_name)

    def drop_volume_all(
        self, catalog_name: str, schema_name: str, volume_config: dict[str, Any]
    ) -> None:
        """Drop one configured volume regardless of its resource create flag.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            volume_config: Volume resource configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(volume_config, dict):
            raise ValueError(
                f"Each volume resource in schema '{schema_name}' must be an object."
            )

        volume_name = self._text_field(volume_config, "name", "volume.name")
        full_volume_name = f"{catalog_name}.{schema_name}.{volume_name}"
        if self._exists(get_volume, full_volume_name):
            logger.info("Deleting managed volume: %s", full_volume_name)
            delete_volume(full_volume_name)
        else:
            logger.info("Volume already absent: %s", full_volume_name)

    def upload_volume_file(
        self,
        catalog_name: str,
        schema_name: str,
        volume_name: str,
        file_config: dict[str, Any],
    ) -> None:
        """Upload one configured file or glob into a Unity Catalog volume.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            volume_name: Parent Unity Catalog volume name.
            file_config: File upload configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(file_config, dict):
            raise ValueError(
                f"Each file resource in volume '{volume_name}' must be an object."
            )

        source = self._text_field(file_config, "from", "file.from")
        source_path = self.local_source_path(self.resolve_test_path(source))
        volume_path = self.volume_file_path(
            catalog_name, schema_name, volume_name, file_config, source_path
        )

        if file_config.get("create") is False:
            logger.info("Skipping file upload from %s to %s", source_path, volume_path)
            return

        logger.info("Uploading file resource from %s to %s", source_path, volume_path)
        upload_result = upload_to_volume(source_path, str(volume_path))
        if upload_result.success:
            return

        failed = [
            {
                "local_path": result.local_path,
                "volume_path": result.volume_path,
                "error": result.error,
            }
            for result in upload_result.results
            if not result.success
        ]
        raise ValueError(
            f"Failed to upload one or more files to {volume_path}: {failed}"
        )

    def drop_volume_file(
        self,
        catalog_name: str,
        schema_name: str,
        volume_name: str,
        file_config: dict[str, Any],
    ) -> None:
        """Drop one configured file or folder from a shared Unity Catalog volume.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            volume_name: Parent Unity Catalog volume name.
            file_config: File upload configuration from the test config.

        Returns:
            None.
        """
        if not isinstance(file_config, dict):
            raise ValueError(
                f"Each file resource in volume '{volume_name}' must be an object."
            )

        source = self._text_field(file_config, "from", "file.from")
        source_path = self.local_source_path(self.resolve_test_path(source))
        volume_path = self.volume_file_path(
            catalog_name, schema_name, volume_name, file_config, source_path
        )

        if file_config.get("create") is False:
            logger.info("Skipping file deletion for %s", volume_path)
            return

        logger.info("Deleting file resource at %s", volume_path)
        delete_result = delete_from_volume(str(volume_path), recursive=True)
        if delete_result.success:
            return

        error = delete_result.error or ""
        if "Path not found" in error or "does not exist" in error:
            logger.info("File resource already absent: %s", volume_path)
            return
        raise ValueError(f"Failed to delete file resource at {volume_path}: {error}")

    def volume_file_path(
        self,
        catalog_name: str,
        schema_name: str,
        volume_name: str,
        file_config: dict[str, Any],
        source_path: str,
    ) -> PurePosixPath:
        """Build the destination path for a configured volume file.

        Args:
            catalog_name: Parent Unity Catalog catalog name.
            schema_name: Parent Unity Catalog schema name.
            volume_name: Parent Unity Catalog volume name.
            file_config: File upload configuration from the test config.
            source_path: Resolved source path for the file upload.

        Returns:
            Absolute Unity Catalog volume path.
        """
        source = self._text_field(file_config, "from", "file.from")
        destination = self._text_field(file_config, "to", "file.to").lstrip("/")
        volume_path = (
            PurePosixPath("/Volumes") / catalog_name / schema_name / volume_name
        )
        if destination:
            volume_path = volume_path / destination
        # Upload helpers treat a trailing destination slash as a directory for
        # a single file. Globs already determine their destination filenames.
        if not any(token in source for token in ("*", "?")) and (
            not destination or destination.endswith("/")
        ):
            volume_path = volume_path / PurePosixPath(source_path).name
        return volume_path

    def resolve_test_path(self, path: str) -> str:
        """Resolve a relative source path beneath the test-data Volume root.

        Args:
            path: Source path from the test config.

        Returns:
            Absolute Unity Catalog Volume path usable by Spark or the Files API.
        """
        if not isinstance(path, str):
            raise TypeError("Resource source path must be a string.")

        path_text = path.strip()
        if not path_text:
            raise ValueError("Resource source path is required.")
        parsed_path = urlsplit(path_text)
        relative_path = PurePosixPath(path_text)
        if (
            parsed_path.scheme
            or parsed_path.netloc
            or parsed_path.query
            or parsed_path.fragment
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or "\\" in path_text
            or "\x00" in path_text
        ):
            raise ValueError(
                "Resource source path must be a relative POSIX path beneath "
                "case_root."
            )
        return posixpath.normpath(str(self.case_root / relative_path))

    def spark_source_path(self, path: str) -> str:
        """Convert a local workspace path into Spark-readable form.

        Args:
            path: Source path resolved from the test config.

        Returns:
            Spark-readable source path.
        """
        if path.startswith("/Workspace/"):
            return f"file:{path}"
        return path

    def local_source_path(self, path: str) -> str:
        """Convert file URI paths into local paths for volume uploads.

        Args:
            path: Source path resolved from the test config.

        Returns:
            Local path string for the Databricks Files API helper.
        """
        if path.startswith("file://"):
            return path.removeprefix("file://")
        if path.startswith("file:"):
            return path.removeprefix("file:")
        return path

    def spark_option_value(self, value: Any) -> str:
        """Convert Spark reader option values into string form.

        Args:
            value: Option value from the table source config.

        Returns:
            String value accepted by Spark reader options.
        """
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)

    @staticmethod
    def _validate_case_root(case_root: str) -> PurePosixPath:
        """Require an absolute Unity Catalog Volume data root."""
        if not isinstance(case_root, str):
            raise TypeError("case_root must be a string")

        case_root_value = case_root.strip()
        if not case_root_value:
            raise ValueError("case_root is required")

        case_root_path = PurePosixPath(case_root_value)
        case_root_parts = case_root_path.parts
        parsed_root = urlsplit(case_root_value)
        if (
            parsed_root.scheme
            or parsed_root.netloc
            or parsed_root.query
            or parsed_root.fragment
            or not case_root_path.is_absolute()
            or case_root_parts[0] != "/"
            or len(case_root_parts) < 5
            or case_root_parts[1] != "Volumes"
            or ".." in case_root_parts
            or "*" in case_root_value
            or "\\" in case_root_value
            or "\x00" in case_root_value
        ):
            raise ValueError(
                "case_root must be an absolute "
                "/Volumes/<catalog>/<schema>/<volume>/... path"
            )
        return case_root_path

    def _lifecycle_step(
        self, test_config: dict[str, Any], step_name: str
    ) -> dict[str, Any]:
        """Read one optional top-level lifecycle step."""
        return self._dict_field(
            test_config,
            step_name,
            label=step_name,
            required=False,
        )

    def _catalog_configs(
        self, test_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Read the required environment catalog configurations."""
        environment_config = self._dict_field(test_config, "environment")
        catalog_configs = self._list_field(
            environment_config,
            "catalogs",
            label="environment.catalogs",
        )
        if not catalog_configs:
            raise ValueError(
                "Integration test config field 'environment.catalogs' is required."
            )
        return catalog_configs

    def _dict_field(
        self,
        parent: dict[str, Any],
        key: str,
        *,
        label: str | None = None,
        required: bool = True,
    ) -> dict[str, Any]:
        """Read an object field from a config mapping.

        Args:
            parent: Config mapping that contains the field.
            key: Field key to read.
            label: Optional user-facing field label for errors.
            required: Whether an empty or missing object should raise.

        Returns:
            The config object field value.
        """
        field_label = label or key
        value = parent.get(key) or {}
        if not isinstance(value, dict):
            raise ValueError(
                f"Integration test config field '{field_label}' must be an object."
            )
        if required and not value:
            raise ValueError(
                f"Integration test config field '{field_label}' is required."
            )
        return value

    def _list_field(
        self, parent: dict[str, Any], key: str, *, label: str | None = None
    ) -> list[Any]:
        """Read an optional list field from a config mapping.

        Args:
            parent: Config mapping that contains the field.
            key: Field key to read.
            label: Optional user-facing field label for errors.

        Returns:
            The config list field value, or an empty list when omitted.
        """
        field_label = label or key
        value = parent.get(key) or []
        if not isinstance(value, list):
            raise ValueError(
                f"Integration test config field '{field_label}' must be a list."
            )
        return value

    def _text_field(self, parent: dict[str, Any], key: str, label: str) -> str:
        """Read a required non-empty text field from a config mapping.

        Args:
            parent: Config mapping that contains the field.
            key: Field key to read.
            label: User-facing field label for errors.

        Returns:
            Trimmed string value.
        """
        value = str(parent.get(key) or "").strip()
        if not value:
            raise ValueError(f"Integration test config field '{label}' is required.")
        return value

    def _exists(self, getter: Callable[..., Any], *args: Any) -> bool:
        """Check whether a Unity Catalog object exists.

        Args:
            getter: Databricks getter function for the object type.
            *args: Arguments to pass to the getter.

        Returns:
            True when the getter succeeds, otherwise False.
        """
        try:
            getter(*args)
            return True
        except Exception:
            return False
