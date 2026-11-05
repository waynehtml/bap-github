catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_swiftbic_code_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_swiftbic_code_dim as tgt
using (
	select distinct
		settlement_agent_bic_code as swiftbic_code
	from raw_db.habs_security_trade_bus_transaction
	where settlement_agent_bic_code is not null
) as src
on tgt.swiftbic_code = src.SWIFTBIC_CODE

when not matched then
insert (
	swiftbic_code
	, audit_load_id
	, audit_last_update_ts
)
values (
	src.SWIFTBIC_CODE
	, {job_run_id}
	, current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_swiftbic_code_dim")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_swiftbic_code_dim build")
