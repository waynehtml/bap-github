catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_reconciliation_unit_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_reconciliation_unit_dim as tgt
using (
    select
        a.code_pk as reconciliation_unit_bid,
        a.attribute_en_name as reconciliation_unit_short_en_nm,
        a.attribute_fr_name as reconciliation_unit_short_fr_nm,
        a.attribute_en_desc as reconciliation_unit_long_en_nm,
        a.attribute_fr_desc as reconciliation_unit_long_fr_nm,
        a.attribute_en_desc as reconciliation_unit_en_desc,
        a.attribute_fr_desc as reconciliation_unit_fr_desc
    from raw_db.corporate_code_table as a
    inner join raw_db.corporate_code_category_table as b
        on a.code_category_fk = b.code_category_pk
    where b.attribute_en_name = 'RECONUNIT'
) as src
on tgt.reconciliation_unit_bid = src.reconciliation_unit_bid

when matched and (
    not (tgt.reconciliation_unit_short_en_nm <=> src.reconciliation_unit_short_en_nm)
    or not (tgt.reconciliation_unit_short_fr_nm <=> src.reconciliation_unit_short_fr_nm)
    or not (tgt.reconciliation_unit_long_en_nm <=> src.reconciliation_unit_long_en_nm)
    or not (tgt.reconciliation_unit_long_fr_nm <=> src.reconciliation_unit_long_fr_nm)
    or not (tgt.reconciliation_unit_en_desc <=> src.reconciliation_unit_en_desc)
    or not (tgt.reconciliation_unit_fr_desc <=> src.reconciliation_unit_fr_desc)
) then update set
    reconciliation_unit_short_en_nm = src.reconciliation_unit_short_en_nm,
    reconciliation_unit_short_fr_nm = src.reconciliation_unit_short_fr_nm,
    reconciliation_unit_long_en_nm = src.reconciliation_unit_long_en_nm,
    reconciliation_unit_long_fr_nm = src.reconciliation_unit_long_fr_nm,
    reconciliation_unit_en_desc = src.reconciliation_unit_en_desc,
    reconciliation_unit_fr_desc = src.reconciliation_unit_fr_desc,
    audit_load_id = {job_run_id},
    audit_last_update_ts = current_timestamp()

when not matched then insert (
    reconciliation_unit_bid,
    reconciliation_unit_short_en_nm,
    reconciliation_unit_short_fr_nm,
    reconciliation_unit_long_en_nm,
    reconciliation_unit_long_fr_nm,
    reconciliation_unit_en_desc,
    reconciliation_unit_fr_desc,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
) values (
    src.reconciliation_unit_bid,
    src.reconciliation_unit_short_en_nm,
    src.reconciliation_unit_short_fr_nm,
    src.reconciliation_unit_long_en_nm,
    src.reconciliation_unit_long_fr_nm,
    src.reconciliation_unit_en_desc,
    src.reconciliation_unit_fr_desc,
    {job_run_id},
    current_timestamp(),
    current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_reconciliation_unit_dim")
logger.info(sql)
spark.sql(sql)

spark.sql("""
update curated_db.tbl_bo_reconciliation_unit_dim
set bo_reconciliation_unit_dkey = bo_reconciliation_unit_skey
where bo_reconciliation_unit_dkey is null
""")

logger.info("Completed tbl_bo_reconciliation_unit_dim build")
