catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_interest_facility_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_interest_facility_dim as tgt
using (
    select
        a.code_pk as interest_facility_bid,
        a.attribute_en_desc as interest_facility_long_en_nm,
        a.attribute_en_name as interest_facility_short_en_nm,
        a.attribute_fr_desc as interest_facility_long_fr_nm,
        a.attribute_fr_name as interest_facility_short_fr_nm,
        a.attribute_en_desc as interest_facility_en_desc,
        a.attribute_fr_desc as interest_facility_fr_desc
    from raw_db.corporate_code_table as a
    inner join raw_db.corporate_code_category_table as b
        on a.code_category_fk = b.code_category_pk
    where b.attribute_en_desc = 'Interest Facility'
) as src
on tgt.interest_facility_bid = src.interest_facility_bid

when matched and (
    not (tgt.interest_facility_long_en_nm <=> src.interest_facility_long_en_nm)
    or not (tgt.interest_facility_short_en_nm <=> src.interest_facility_short_en_nm)
    or not (tgt.interest_facility_long_fr_nm <=> src.interest_facility_long_fr_nm)
    or not (tgt.interest_facility_short_fr_nm <=> src.interest_facility_short_fr_nm)
    or not (tgt.interest_facility_en_desc <=> src.interest_facility_en_desc)
    or not (tgt.interest_facility_fr_desc <=> src.interest_facility_fr_desc)
) then update set
    interest_facility_long_en_nm = src.interest_facility_long_en_nm,
    interest_facility_short_en_nm = src.interest_facility_short_en_nm,
    interest_facility_long_fr_nm = src.interest_facility_long_fr_nm,
    interest_facility_short_fr_nm = src.interest_facility_short_fr_nm,
    interest_facility_en_desc = src.interest_facility_en_desc,
    interest_facility_fr_desc = src.interest_facility_fr_desc,
    audit_load_id = {job_run_id},
    audit_last_update_ts = current_timestamp()

when not matched then insert (
    interest_facility_bid,
    interest_facility_long_en_nm,
    interest_facility_short_en_nm,
    interest_facility_long_fr_nm,
    interest_facility_short_fr_nm,
    interest_facility_en_desc,
    interest_facility_fr_desc,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
) values (
    src.interest_facility_bid,
    src.interest_facility_long_en_nm,
    src.interest_facility_short_en_nm,
    src.interest_facility_long_fr_nm,
    src.interest_facility_short_fr_nm,
    src.interest_facility_en_desc,
    src.interest_facility_fr_desc,
    {job_run_id},
    current_timestamp(),
    current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_interest_facility_dim")
logger.info(sql)
spark.sql(sql)

spark.sql("""
update curated_db.tbl_bo_interest_facility_dim
set bo_interest_facility_dkey = bo_interest_facility_skey
where bo_interest_facility_dkey is null
""")

logger.info("Completed tbl_bo_interest_facility_dim build")
