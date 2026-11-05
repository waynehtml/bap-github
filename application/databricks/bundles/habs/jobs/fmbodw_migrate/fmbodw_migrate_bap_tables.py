# Databricks notebook source
# MAGIC %run ../../common

# COMMAND ----------

from pyspark.sql import functions as F

# COMMAND ----------

# Standard libraries
import logging

# Get logger
logger = logging.getLogger(__name__)

# Get job context
job_ctx = get_job_context()
logger.debug(f"job_ctx: {job_ctx}")

# COMMAND ----------

# Set source catelog and detination catelog and schema
# The source schema and table are in the config file
env=job_ctx["env"]
target_catalog = job_ctx["catalog"]
target_schema  = "curated_db"
source_catalog = f"{env}_ext_ora_fmbodw_cat"
gle_mapping_view = f"{env}_financial_markets_cat.views_db.vw_gle_mapping"
financial_instrument_mapping_view = (
    f"{env}_financial_markets_cat.views_db.vw_financial_instrument_mapping"
)
unmatched_skey = 10000000
job_run_id=job_ctx["job_run_id"]
config_root = job_ctx["config_root"]

config_fmbodw_copy_bap_tables_list = f"dbfs:{config_root}/habs/fmbodw_copy_bap_tables_list.json"
logger.debug(f"config_fmbodw_copy_bap_tables_list: {config_fmbodw_copy_bap_tables_list}")

# COMMAND ----------

import json
def read_json_from_volume(path):
    content = dbutils.fs.head(path)
    return json.loads(content)

def validate_mapping(
    source_schema,
    source_table,
    source_column,
    mapping_view,
    old_key_column,
    mapped_key_column,
):
    mapping_issues = spark.sql(
        f"""
        SELECT
            CAST(src.`{source_column}` AS BIGINT) AS legacy_skey,
            COUNT(mapping.`{old_key_column}`) AS mapping_row_count,
            COUNT(DISTINCT mapping.`{mapped_key_column}`) AS mapped_skey_count
        FROM {source_catalog}.{source_schema}.{source_table} AS src
        LEFT JOIN {mapping_view} AS mapping
          ON mapping.`{old_key_column}` = src.`{source_column}`
        WHERE src.`{source_column}` IS NOT NULL
        GROUP BY CAST(src.`{source_column}` AS BIGINT)
        HAVING COUNT(DISTINCT mapping.`{mapped_key_column}`) <> 1
        ORDER BY legacy_skey
        """
    )
    unmatched_keys = mapping_issues.where(
        "mapping_row_count = 0 OR mapped_skey_count = 0"
    )
    unmatched_count = unmatched_keys.count()
    if unmatched_count:
        samples = [row.asDict() for row in unmatched_keys.limit(1000).collect()]
        logger.warning(
            "Loading %s unmatched reference(s) in %s.%s with SKEY %s: %s",
            unmatched_count,
            source_table,
            source_column,
            unmatched_skey,
            samples,
        )
    ambiguous_keys = mapping_issues.where(
        "mapped_skey_count > 1"
    )
    ambiguous_count = ambiguous_keys.count()
    if ambiguous_count:
        samples = [row.asDict() for row in ambiguous_keys.limit(1000).collect()]
        logger.error(
            "Ambiguous %s reference(s) in %s.%s: %s",
            ambiguous_count,
            source_table,
            source_column,
            samples,
        )
        raise ValueError(
            f"{source_table}.{source_column} has {ambiguous_count} ambiguous legacy "
            "SKEYs. Resolve the mapping view before copying data."
        )

tables = read_json_from_volume(config_fmbodw_copy_bap_tables_list)

for t in tables:
    source_schema, source_table = t.split(".")
    target_table = f"TBL_{source_table}"

    # Check if table exists
    if spark.catalog.tableExists(f"{target_catalog}.{target_schema}.{target_table}"):

        # Create or replace target table directly
        sql = f"""TRUNCATE TABLE {target_catalog}.{target_schema}.{target_table}"""

        # Get source columns
        source_df = spark.table(f"{source_catalog}.{source_schema}.{source_table}")
        source_cols = source_df.columns
        is_fact_table = source_table.upper().endswith("_FACT")
        gle_skey_columns = [
            column
            for column in source_cols
            if is_fact_table and (
                column.upper().endswith("GLE_SKEY")
                or column.upper() == "CLIENT_GLE_KEY"
            )
        ]
        financial_instrument_skey_columns = [
            column
            for column in source_cols
            if is_fact_table and column.upper().endswith("FINANCIAL_INSTRUMENT_SKEY")
        ]

        for column in gle_skey_columns:
            validate_mapping(
                source_schema,
                source_table,
                column,
                gle_mapping_view,
                "old_gle_skey",
                "mapped_new_gle_skey",
            )
        for column in financial_instrument_skey_columns:
            validate_mapping(
                source_schema,
                source_table,
                column,
                financial_instrument_mapping_view,
                "old_financial_instrument_skey",
                "mapped_new_financial_instrument_skey",
            )

        # Replace fact-table GLE and FI foreign keys with their mapped new SKEY values.
        gle_mapping_aliases = {
            column: f"gle_mapping_{index}"
            for index, column in enumerate(gle_skey_columns)
        }
        financial_instrument_mapping_aliases = {
            column: f"financial_instrument_mapping_{index}"
            for index, column in enumerate(financial_instrument_skey_columns)
        }
        select_expr = ",\n ".join(
            f"CASE WHEN src.`{column}` IS NULL THEN NULL "
            f"ELSE COALESCE({gle_mapping_aliases[column]}.mapped_new_gle_skey, "
            f"{unmatched_skey}) END AS `{column}`"
            if column in gle_mapping_aliases
            else (
                f"CASE WHEN src.`{column}` IS NULL THEN NULL "
                f"WHEN src.`{column}` = -1 THEN -1 "
                f"ELSE COALESCE({financial_instrument_mapping_aliases[column]}"
                f".mapped_new_financial_instrument_skey, {unmatched_skey}) "
                f"END AS `{column}`"
                if column in financial_instrument_mapping_aliases
                else f"src.`{column}`"
            )
            for column in source_cols
        )
        mapping_joins = "\n".join(
            f"LEFT JOIN {gle_mapping_view} AS {gle_mapping_aliases[column]}\n"
            f"  ON {gle_mapping_aliases[column]}.old_gle_skey = src.`{column}`"
            for column in gle_skey_columns
        )
        if financial_instrument_skey_columns:
            mapping_joins = "\n".join(
                filter(
                    None,
                    (
                        mapping_joins,
                        "\n".join(
                            f"LEFT JOIN {financial_instrument_mapping_view} AS "
                            f"{financial_instrument_mapping_aliases[column]}\n"
                            f"  ON {financial_instrument_mapping_aliases[column]}"
                            f".old_financial_instrument_skey = src.`{column}`"
                            for column in financial_instrument_skey_columns
                        ),
                    ),
                )
            )

        spark.sql(sql)
        logger.debug(sql)

        sql = f"""
            INSERT INTO {target_catalog}.{target_schema}.{target_table}
            (
                {', '.join(source_cols)},
                audit_load_id,
                audit_create_ts,
                audit_last_update_ts
            )
            SELECT
                {select_expr},
                {job_run_id} as audit_load_id,
                current_timestamp() as audit_create_ts,
                current_timestamp() as audit_last_update_ts
            FROM {source_catalog}.{source_schema}.{source_table} AS src
            {mapping_joins}
            """

        try:
            print(f"Loading table {target_catalog}.{target_schema}.{target_table}")
            spark.sql(sql)
            logger.debug(sql)
        except Exception as e:
            print(f"Error: {e} Table: {target_catalog}.{target_schema}.{target_table}")
            raise


        # Change tbl_bo_allocation_type_dim from SCD type 2 to SCD type 1
        if target_table == "TBL_BO_ALLOCATION_TYPE_DIM":
            # Fully qualified table name for clean code interpolation
            target_fqn = f"{target_catalog}.{target_schema}.{target_table}"

            logger.info(f"Starting SCD Type 2 to Type 1 conversion for: {target_fqn}")

            # Step 1: Delete historical versions where surrogate key does not match natural key
            delete_sql = f"""
                DELETE FROM {target_fqn}
                WHERE allocation_type_skey <> allocation_type_dkey
            """
            logger.debug(f"Executing Delete SQL: {delete_sql.strip()}")
            spark.sql(delete_sql)

            # Step 2: Reset tracking attributes for remaining active records
            update_sql = f"""
                UPDATE {target_fqn}
                SET md_current_ind = 1,
                    md_exp_ts = CAST(NULL AS TIMESTAMP)
                WHERE md_current_ind = 0
            """
            logger.debug(f"Executing Update SQL: {update_sql.strip()}")
            spark.sql(update_sql)

            logger.info(f"Successfully completed SCD Type 1 alignment for: {target_fqn}")


    else:
        print(f"Table {target_catalog}.{target_schema}.{target_table} does not exist")