catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_bus_trans_attribute_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

source_table = "raw_db.habs_business_transaction"
target_table = "curated_db.tbl_bo_bus_trans_attribute_dim"
source_columns = {
    field.name.lower(): field.name for field in spark.table(source_table).schema.fields
}
target_fields = [
    field
    for field in spark.table(target_table).schema.fields
    if field.name not in {
        "bo_bus_trans_attribute_skey",
        "audit_load_id",
        "audit_create_ts",
        "audit_last_update_ts",
    }
]
target_columns = [field.name for field in target_fields]

select_columns = []
for field in target_fields:
    source_column = "business_trans_pk" if field.name == "rk_business_trans_pk" else field.name
    if source_column in source_columns:
        select_columns.append(f"src.`{source_columns[source_column]}`")
    else:
        select_columns.append(f"CAST(NULL AS {field.dataType.simpleString()})")

sql = f"""
INSERT INTO {target_table} (
    {', '.join(target_columns)}, audit_load_id, audit_last_update_ts
)
SELECT
    {', '.join(select_columns)}, {job_run_id}, current_timestamp()
FROM {source_table} AS src
where not exists (
	select 1
	from {target_table} as tgt
	where tgt.rk_business_trans_pk = src.BUSINESS_TRANS_PK
)
"""

logger.info("Executing INSERT for curated_db.tbl_bo_bus_trans_attribute_dim")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_bus_trans_attribute_dim build")
