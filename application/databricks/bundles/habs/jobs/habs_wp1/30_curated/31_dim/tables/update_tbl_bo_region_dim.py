catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_region_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_region_dim as tgt
using (
    select
        a.code_pk as region_bid,
        a.attribute_en_name as region_short_en_nm,
        a.attribute_fr_name as region_short_fr_nm,
        a.attribute_en_desc as region_long_en_nm,
        a.attribute_fr_desc as region_long_fr_nm,
        a.attribute_en_desc as region_en_desc,
        a.attribute_fr_desc as region_fr_desc
    from raw_db.corporate_code_table as a
    inner join raw_db.corporate_code_category_table as b
        on a.code_category_fk = b.code_category_pk
    where b.attribute_en_name = 'REGION'
) as src
on tgt.region_bid = src.region_bid

when matched and (
    not (tgt.region_short_en_nm <=> src.region_short_en_nm)
    or not (tgt.region_short_fr_nm <=> src.region_short_fr_nm)
    or not (tgt.region_long_en_nm <=> src.region_long_en_nm)
    or not (tgt.region_long_fr_nm <=> src.region_long_fr_nm)
    or not (tgt.region_en_desc <=> src.region_en_desc)
    or not (tgt.region_fr_desc <=> src.region_fr_desc)
) then update set
    region_short_en_nm = src.region_short_en_nm,
    region_short_fr_nm = src.region_short_fr_nm,
    region_long_en_nm = src.region_long_en_nm,
    region_long_fr_nm = src.region_long_fr_nm,
    region_en_desc = src.region_en_desc,
    region_fr_desc = src.region_fr_desc,
    audit_load_id = {job_run_id},
    audit_last_update_ts = current_timestamp()

when not matched then insert (
    region_bid,
    region_short_en_nm,
    region_short_fr_nm,
    region_long_en_nm,
    region_long_fr_nm,
    region_en_desc,
    region_fr_desc,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
) values (
    src.region_bid,
    src.region_short_en_nm,
    src.region_short_fr_nm,
    src.region_long_en_nm,
    src.region_long_fr_nm,
    src.region_en_desc,
    src.region_fr_desc,
    {job_run_id},
    current_timestamp(),
    current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_region_dim")
logger.info(sql)
spark.sql(sql)

spark.sql("""
update curated_db.tbl_bo_region_dim
set bo_region_dkey = bo_region_skey
where bo_region_dkey is null
""")

logger.info("Completed tbl_bo_region_dim build")
