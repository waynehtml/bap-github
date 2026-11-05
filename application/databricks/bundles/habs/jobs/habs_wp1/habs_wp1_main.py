# Databricks notebook source
# MAGIC %md
# MAGIC ## Parameters
# MAGIC - **build_raw** (string, allowed values: "1" or "0")
# MAGIC   - Controls whether the raw build task is executed in this run.
# MAGIC   - "1" → Execute the raw table build process
# MAGIC   - "0" → Skip the raw table build process (use existing raw data)
# MAGIC
# MAGIC - **build_dim** (string, allowed values: "1" or "0")
# MAGIC   - Controls whether the Dimension table build task is executed in this run.
# MAGIC   - "1" → Execute the dimension table build process
# MAGIC   - "0" → Skip the dimension table build process (use existing raw data)
# MAGIC
# MAGIC - **build_fact** (string, allowed values: "1" or "0")
# MAGIC   - Controls whether the Fact table build task is executed in this run.
# MAGIC   - "1" → Execute the fact table build process
# MAGIC   - "0" → Skip the fact table build process (use existing raw data)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ---
# MAGIC ## Processing Logic
# MAGIC
# MAGIC ### 1. Business Day Validation
# MAGIC - Validate whether **rundate** is a business day based on the enterprise calendar.  
# MAGIC - If the date is **not a business day**, the job exits gracefully without further processing.  
# MAGIC
# MAGIC ### 2. Data Pipeline Execution *(Business Days Only)*
# MAGIC - **Raw Layer**  
# MAGIC   - Ingest and prepare source data into **raw tables**.  
# MAGIC   - Target schema: `raw_db`.  
# MAGIC
# MAGIC - **Dimension Layer**  
# MAGIC   - Build and update **dimension tables**.  
# MAGIC   - Target schema: `curated_db`.  
# MAGIC   - All dimension table names end with `_DIM`.  
# MAGIC
# MAGIC - **Fact Layer**  
# MAGIC   - Populate **fact tables** for analytical consumption.  
# MAGIC   - Target schema: `curated_db`.  
# MAGIC   - All fact table names end with `_FACT`.  

# COMMAND ----------

# MAGIC %run ../../common

# COMMAND ----------

# Standard libraries
import logging

# Get logger
logger = logging.getLogger(__name__)

# Get job context
job_ctx = get_job_context()
logger.debug(f"job_ctx: {job_ctx}")

catalog = job_ctx["catalog"]


# COMMAND ----------

## Parameters
build_raw = dbutils.widgets.get("build_raw")
build_dim = dbutils.widgets.get("build_dim")
build_fact = dbutils.widgets.get("build_fact")

# COMMAND ----------

def is_business_day(date_str: str) -> bool:
## waiting for Julian OEBST-247    
    return True



# COMMAND ----------

from datetime import datetime
rundate = datetime.today().strftime("%Y-%m-%d")

if not is_business_day(rundate):
    logger.warning("%s is not a business day. Skipping pipeline.", rundate)
    dbutils.jobs.taskValues.set("run_pipeline", "0")
    dbutils.notebook.exit("SKIP")

logger.info("%s is a business day. Proceeding.", rundate)
dbutils.jobs.taskValues.set("run_pipeline", "1")