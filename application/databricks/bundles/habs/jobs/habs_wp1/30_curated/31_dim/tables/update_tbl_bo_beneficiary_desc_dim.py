catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_beneficiary_desc_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_beneficiary_desc_dim as tgt
using (
    select distinct beneficiary_desc
    from raw_db.habs_payment_bus_transaction
    where beneficiary_desc is not null

    union

    select distinct beneficiary_payee_desc as beneficiary_desc
    from raw_db.habs_security_trade_bus_transaction
    where beneficiary_payee_desc is not null
) as src

on tgt.beneficiary_desc = src.BENEFICIARY_DESC

when not matched then
insert (
      beneficiary_desc
    , audit_load_id
    , audit_last_update_ts
)
values (
      src.BENEFICIARY_DESC
    , {job_run_id}
    , current_timestamp()
)
"""

logger.info(
    "Executing MERGE for curated_db.tbl_bo_beneficiary_desc_dim"
)
logger.info(sql)

spark.sql(sql)

logger.info("Completed tbl_bo_beneficiary_desc_dim build")