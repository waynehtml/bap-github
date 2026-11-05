catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_bus_trans_service_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_bus_trans_service_dim as tgt
using (
    select
        a.BUS_TRANS_SERVICE_NAME as bus_trans_service_nm
    from raw_db.habs_business_transaction a
) as src
on tgt.bus_trans_service_nm = src.BUS_TRANS_SERVICE_NM

when not matched then
insert (
    bus_trans_service_nm
    , audit_load_id
    , audit_last_update_ts
)
values (
    src.BUS_TRANS_SERVICE_NM
    , {job_run_id}
    , current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_bus_trans_service_dim")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_bus_trans_service_dim build")
