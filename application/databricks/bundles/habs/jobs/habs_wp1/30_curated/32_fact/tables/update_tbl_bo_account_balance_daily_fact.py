catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_ACCOUNT_BALANCE_DAILY_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
select coalesce(max(opening_balance_date), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_account_balance_daily_fact
"""

row = spark.sql(sql).first()
last_process_ts = row["max_date"]

sql = f"""
insert into curated_db.tbl_bo_account_balance_daily_fact
    (
        bo_account_skey,
        bo_account_bal_type_skey,
        opening_balance_date,
        client_gle_skey,
        account_opening_bal_amt, 
        audit_load_id, 
        audit_create_ts,
        audit_last_update_ts
    )
select
    ac.bo_account_skey              AS bo_account_skey,
    abl.bo_account_bal_type_skey    AS bo_account_bal_type_skey,
    aob.opening_balance_date        AS opening_balance_date,
    g.global_legal_entity_skey      AS client_gle_skey,
    aob.account_opening_bal_amt     AS account_opening_bal_amt,
    {job_run_id}                    AS audit_load_id,
    current_timestamp()             AS audit_create_ts,
    current_timestamp()             AS audit_last_update_ts 
from 
    raw_db.habs_account_opening_balance aob
    join raw_db.habs_account a on a.account_pk = aob.account_pk
    join raw_db.habs_client c on c.client_pk = a.client_fk
    left join view_db.vwu_global_legal_entity_dim g on g.client_id=c.client_id
    left join curated_db.tbl_bo_account_dim ac on ac.rk_account_pk=aob.account_pk
    left join curated_db.tbl_bo_account_bal_type_dim abl on cast(abl.account_bal_type_bid as int) =aob.account_bal_type_pk
 where 
        aob.opening_balance_date > timestamp '{last_process_ts}'
    and g.global_legal_entity_skey > 0
    and ac.bo_account_skey > 0
    and abl.bo_account_bal_type_skey>0
"""

logger.info("Executing INSERT for curated_db.tbl_bo_account_balance_daily_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_account_balance_daily_fact build")
