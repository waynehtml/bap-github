catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_pcss_type_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_pcss_type_dim as tgt
using (
    select
        cast(a.code_pk as string) as pcss_type_bid
        , a.attribute_en_desc as pcss_type_long_en_nm
        , a.attribute_en_name as pcss_type_short_en_nm
        , a.attribute_fr_desc as pcss_type_long_fr_nm
        , a.attribute_fr_name as pcss_type_short_fr_nm
        , a.attribute_en_desc as pcss_type_en_desc
        , a.attribute_fr_desc as pcss_type_fr_desc
    from raw_db.corporate_code_table a
    inner join raw_db.corporate_code_category_table b
        on a.code_category_fk = b.code_category_pk
    where b.attribute_en_name = 'PCSSTYPE'
) as src
on tgt.pcss_type_bid = src.PCSS_TYPE_BID

when matched and (
    not (tgt.pcss_type_long_en_nm <=> src.PCSS_TYPE_LONG_EN_NM)
    or not (tgt.pcss_type_short_en_nm <=> src.PCSS_TYPE_SHORT_EN_NM)
    or not (tgt.pcss_type_long_fr_nm <=> src.PCSS_TYPE_LONG_FR_NM)
    or not (tgt.pcss_type_short_fr_nm <=> src.PCSS_TYPE_SHORT_FR_NM)
    or not (tgt.pcss_type_en_desc <=> src.PCSS_TYPE_EN_DESC)
    or not (tgt.pcss_type_fr_desc <=> src.PCSS_TYPE_FR_DESC)
)
then update set
    pcss_type_long_en_nm = src.PCSS_TYPE_LONG_EN_NM
    , pcss_type_short_en_nm = src.PCSS_TYPE_SHORT_EN_NM
    , pcss_type_long_fr_nm = src.PCSS_TYPE_LONG_FR_NM
    , pcss_type_short_fr_nm = src.PCSS_TYPE_SHORT_FR_NM
    , pcss_type_en_desc = src.PCSS_TYPE_EN_DESC
    , pcss_type_fr_desc = src.PCSS_TYPE_FR_DESC
    , audit_load_id = {job_run_id}
    , audit_last_update_ts = current_timestamp()

when not matched then
insert (
    pcss_type_bid
    , pcss_type_long_en_nm
    , pcss_type_short_en_nm
    , pcss_type_long_fr_nm
    , pcss_type_short_fr_nm
    , pcss_type_en_desc
    , pcss_type_fr_desc
    , audit_load_id
    , audit_last_update_ts
)
values (
    src.PCSS_TYPE_BID
    , src.PCSS_TYPE_LONG_EN_NM
    , src.PCSS_TYPE_SHORT_EN_NM
    , src.PCSS_TYPE_LONG_FR_NM
    , src.PCSS_TYPE_SHORT_FR_NM
    , src.PCSS_TYPE_EN_DESC
    , src.PCSS_TYPE_FR_DESC
    , {job_run_id}
    , current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_pcss_type_dim")
logger.info(sql)
spark.sql(sql)

sql = """
update curated_db.tbl_bo_pcss_type_dim
set bo_pcss_type_dkey = bo_pcss_type_skey
where bo_pcss_type_dkey is null
"""
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_pcss_type_dim build")
