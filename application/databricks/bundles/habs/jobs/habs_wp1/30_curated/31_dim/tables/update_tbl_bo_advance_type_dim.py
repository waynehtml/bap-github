catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_advance_type_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_advance_type_dim as tgt
using (
    select
        a.code_pk as advance_type_bid,
        a.attribute_en_desc as advance_type_long_en_nm,
        a.attribute_en_name as advance_type_short_en_nm,
        a.attribute_fr_desc as advance_type_long_fr_nm,
        a.attribute_fr_name as advance_type_short_fr_nm,
        a.attribute_en_desc as advance_type_en_desc,
        a.attribute_fr_desc as advance_type_fr_desc
    from raw_db.corporate_code_table as a
    inner join raw_db.corporate_code_category_table as b
        on a.code_category_fk = b.code_category_pk
    where upper(b.attribute_en_name) = 'ADVANCETYPE'
) as src
on tgt.advance_type_bid = src.advance_type_bid

when matched and (
    not (tgt.advance_type_long_en_nm <=> src.advance_type_long_en_nm)
    or not (tgt.advance_type_short_en_nm <=> src.advance_type_short_en_nm)
    or not (tgt.advance_type_long_fr_nm <=> src.advance_type_long_fr_nm)
    or not (tgt.advance_type_short_fr_nm <=> src.advance_type_short_fr_nm)
    or not (tgt.advance_type_en_desc <=> src.advance_type_en_desc)
    or not (tgt.advance_type_fr_desc <=> src.advance_type_fr_desc)
) then update set
    advance_type_long_en_nm = src.advance_type_long_en_nm,
    advance_type_short_en_nm = src.advance_type_short_en_nm,
    advance_type_long_fr_nm = src.advance_type_long_fr_nm,
    advance_type_short_fr_nm = src.advance_type_short_fr_nm,
    advance_type_en_desc = src.advance_type_en_desc,
    advance_type_fr_desc = src.advance_type_fr_desc,
    audit_load_id = {job_run_id},
    audit_last_update_ts = current_timestamp()

when not matched then insert (
    advance_type_bid,
    advance_type_long_en_nm,
    advance_type_short_en_nm,
    advance_type_long_fr_nm,
    advance_type_short_fr_nm,
    advance_type_en_desc,
    advance_type_fr_desc,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
) values (
    src.advance_type_bid,
    src.advance_type_long_en_nm,
    src.advance_type_short_en_nm,
    src.advance_type_long_fr_nm,
    src.advance_type_short_fr_nm,
    src.advance_type_en_desc,
    src.advance_type_fr_desc,
    {job_run_id},
    current_timestamp(),
    current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_advance_type_dim")
logger.info(sql)
spark.sql(sql)

spark.sql("""
update curated_db.tbl_bo_advance_type_dim
set bo_advance_type_dkey = bo_advance_type_skey
where bo_advance_type_dkey is null
""")

logger.info("Completed tbl_bo_advance_type_dim build")
