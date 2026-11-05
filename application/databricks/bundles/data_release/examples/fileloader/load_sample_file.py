# Databricks notebook source
# MAGIC %md
# MAGIC ## Load sample file example
# MAGIC This example loads `examples/fixtures/tbl_sample.csv` using the packaged `load_sample` file load mapping.
# MAGIC It recreates `tbl_sample` from the current schema definition and removes
# MAGIC any existing sample data.

# COMMAND ----------

# MAGIC %run ../../common

# COMMAND ----------

import logging
from pathlib import PurePosixPath

from oeds.core.file_utils import workspace_url
from oeds.domain.utils.fileloader import FileLoader
from oeds.domain.utils.schema.schema_deployment_utils import (
    SchemaDeploymentManager,
)
from oeds.domain.utils.schema.schema_utils import SchemaManager

logger = logging.getLogger(__name__)

job_ctx = get_job_context()
logger.debug("Initialized job context")

# COMMAND ----------

bundle_root = PurePosixPath(job_ctx.get("bundle_root"))
sample_file_dir = workspace_url(str(bundle_root / "examples" / "fixtures"))

file_loader = FileLoader.initialize(job_ctx.get("env")).get_instance()

print("sample file dir:", sample_file_dir)
print("fileloader module map:", file_loader.get_module_map())

# COMMAND ----------

# Recreate the sample target so schema changes are applied before the file write.
logger.warning("Recreating sample target table 'tbl_sample' ...")
SchemaDeploymentManager.initialize(job_ctx.get("env")).get_instance().create_table(
    "tbl_sample", replace=True
)

# COMMAND ----------

file_loader.load_file(
    ref="load_sample",
    file_base_uri=sample_file_dir,
    mode="overwrite",
    context=job_ctx,
)

print("Loaded file mapping: load_sample")

# COMMAND ----------

target_table = SchemaManager.get_instance().find("tbl_sample").full_name
display(spark.table(target_table))
