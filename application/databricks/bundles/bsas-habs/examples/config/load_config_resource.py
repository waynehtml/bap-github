# Databricks notebook source
# MAGIC %md
# MAGIC ## Load an environment-aware configuration resource
# MAGIC `common.py` initializes `ConfigManager` with the job environment. The
# MAGIC caller-owned manager checks the environment directory first, then falls
# MAGIC back to the shared resource in the package root.

# COMMAND ----------

# MAGIC %run ../../common

# COMMAND ----------

from oeds.domain.utils.config import ConfigManager

config_manager = ConfigManager.get_instance("oeds.config.email")
template_text = config_manager.load_config_resource("template/failure.html")

print(template_text)
