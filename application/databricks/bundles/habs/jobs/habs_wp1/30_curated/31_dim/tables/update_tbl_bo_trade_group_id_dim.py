catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_trade_group_id_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_trade_group_id_dim as tgt
using (
    select distinct
        src_reference_num as trade_group_id
    from
        raw_db.habs_business_transaction
    where
        src_reference_num is not null
) as src
on tgt.trade_group_id = src.TRADE_GROUP_ID

when not matched then
insert (
        trade_group_id,
        audit_load_id,
        audit_last_update_ts
)
values (
        src.TRADE_GROUP_ID,
        {job_run_id},
        current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_trade_group_id_dim")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_trade_group_id_dim build")