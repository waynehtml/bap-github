catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_account_impact_type_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_account_impact_type_dim as tgt
using (
    select
        cast(a.code_pk as string) as account_impact_type_bid
        , a.attribute_en_name as account_impact_type_short_en_nm
        , a.attribute_fr_name as account_impact_type_short_fr_nm
        , a.attribute_en_desc as account_impact_type_long_en_nm
        , a.attribute_fr_desc as account_impact_type_long_fr_nm
        , a.attribute_en_desc as account_impact_type_en_desc
        , a.attribute_fr_desc as account_impact_type_fr_desc
    from raw_db.corporate_code_table a
    inner join raw_db.corporate_code_category_table b
        on a.code_category_fk = b.code_category_pk
    where b.attribute_en_desc = 'Account Impact Type'
) as src
on tgt.account_impact_type_bid = src.ACCOUNT_IMPACT_TYPE_BID

when matched and (
    not (tgt.account_impact_type_short_en_nm <=> src.ACCOUNT_IMPACT_TYPE_SHORT_EN_NM)
    or not (tgt.account_impact_type_short_fr_nm <=> src.ACCOUNT_IMPACT_TYPE_SHORT_FR_NM)
    or not (tgt.account_impact_type_long_en_nm <=> src.ACCOUNT_IMPACT_TYPE_LONG_EN_NM)
    or not (tgt.account_impact_type_long_fr_nm <=> src.ACCOUNT_IMPACT_TYPE_LONG_FR_NM)
    or not (tgt.account_impact_type_en_desc <=> src.ACCOUNT_IMPACT_TYPE_EN_DESC)
    or not (tgt.account_impact_type_fr_desc <=> src.ACCOUNT_IMPACT_TYPE_FR_DESC)
)
then update set
    account_impact_type_short_en_nm = src.ACCOUNT_IMPACT_TYPE_SHORT_EN_NM
    , account_impact_type_short_fr_nm = src.ACCOUNT_IMPACT_TYPE_SHORT_FR_NM
    , account_impact_type_long_en_nm = src.ACCOUNT_IMPACT_TYPE_LONG_EN_NM
    , account_impact_type_long_fr_nm = src.ACCOUNT_IMPACT_TYPE_LONG_FR_NM
    , account_impact_type_en_desc = src.ACCOUNT_IMPACT_TYPE_EN_DESC
    , account_impact_type_fr_desc = src.ACCOUNT_IMPACT_TYPE_FR_DESC
    , audit_load_id = {job_run_id}
    , audit_last_update_ts = current_timestamp()

when not matched then
insert (
    account_impact_type_bid
    , account_impact_type_short_en_nm
    , account_impact_type_short_fr_nm
    , account_impact_type_long_en_nm
    , account_impact_type_long_fr_nm
    , account_impact_type_en_desc
    , account_impact_type_fr_desc
    , audit_load_id
    , audit_last_update_ts
)
values (
    src.ACCOUNT_IMPACT_TYPE_BID
    , src.ACCOUNT_IMPACT_TYPE_SHORT_EN_NM
    , src.ACCOUNT_IMPACT_TYPE_SHORT_FR_NM
    , src.ACCOUNT_IMPACT_TYPE_LONG_EN_NM
    , src.ACCOUNT_IMPACT_TYPE_LONG_FR_NM
    , src.ACCOUNT_IMPACT_TYPE_EN_DESC
    , src.ACCOUNT_IMPACT_TYPE_FR_DESC
    , {job_run_id}
    , current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_account_impact_type_dim")
logger.info(sql)
spark.sql(sql)

sql = """
update curated_db.tbl_bo_account_impact_type_dim
set bo_account_impact_type_dkey = bo_account_impact_type_skey
where bo_account_impact_type_dkey is null
"""
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_account_impact_type_dim build")
