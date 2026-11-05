catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_settlement_agent_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_settlement_agent_dim as tgt
using (
    select
        coalesce(settlement_agent_cuid_code, '') as settlement_agent_cuid_code,
        coalesce(settlement_agent_bic_code, '') as settlement_agent_bic_code,
        coalesce(settlement_agent_desc, '') as settlement_agent_desc
    from raw_db.habs_security_trade_bus_transaction
) as src
on tgt.settlement_agent_cuid_code = src.SETTLEMENT_AGENT_CUID_CODE
and tgt.settlement_agent_bic_code = src.SETTLEMENT_AGENT_BIC_CODE
and tgt.settlement_agent_desc = src.SETTLEMENT_AGENT_DESC

when not matched then
insert (
    settlement_agent_cuid_code,
    settlement_agent_bic_code,
    settlement_agent_desc,
    audit_load_id,
    audit_last_update_ts
)
values (
    src.SETTLEMENT_AGENT_CUID_CODE,
    src.SETTLEMENT_AGENT_BIC_CODE,
    src.SETTLEMENT_AGENT_DESC,
    {job_run_id},
    current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_settlement_agent_dim")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_settlement_agent_dim build")
