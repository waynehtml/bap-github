catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_market_operation_type_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_market_operation_type_dim as tgt
using (
    select
        cast(a.code_pk as string) as mkt_operation_type_bid
        , a.attribute_en_name as mkt_operation_type_short_en_nm
        , a.attribute_fr_name as mkt_operation_type_short_fr_nm
        , a.attribute_en_desc as mkt_operation_type_long_en_nm
        , a.attribute_fr_desc as mkt_operation_type_long_fr_nm
        , a.attribute_en_desc as mkt_operation_type_en_desc
        , a.attribute_fr_desc as mkt_operation_type_fr_desc
    from raw_db.corporate_code_table a
    inner join raw_db.corporate_code_category_table b
        on a.code_category_fk = b.code_category_pk
    where b.attribute_en_desc = 'Market Operation Type'
) as src
on tgt.mkt_operation_type_bid = src.MKT_OPERATION_TYPE_BID

when matched and (
    not (tgt.mkt_operation_type_long_en_nm <=> src.MKT_OPERATION_TYPE_LONG_EN_NM)
    or not (tgt.mkt_operation_type_short_en_nm <=> src.MKT_OPERATION_TYPE_SHORT_EN_NM)
    or not (tgt.mkt_operation_type_long_fr_nm <=> src.MKT_OPERATION_TYPE_LONG_FR_NM)
    or not (tgt.mkt_operation_type_short_fr_nm <=> src.MKT_OPERATION_TYPE_SHORT_FR_NM)
    or not (tgt.mkt_operation_type_en_desc <=> src.MKT_OPERATION_TYPE_EN_DESC)
    or not (tgt.mkt_operation_type_fr_desc <=> src.MKT_OPERATION_TYPE_FR_DESC)
)
then update set
    mkt_operation_type_long_en_nm = src.MKT_OPERATION_TYPE_LONG_EN_NM
    , mkt_operation_type_short_en_nm = src.MKT_OPERATION_TYPE_SHORT_EN_NM
    , mkt_operation_type_long_fr_nm = src.MKT_OPERATION_TYPE_LONG_FR_NM
    , mkt_operation_type_short_fr_nm = src.MKT_OPERATION_TYPE_SHORT_FR_NM
    , mkt_operation_type_en_desc = src.MKT_OPERATION_TYPE_EN_DESC
    , mkt_operation_type_fr_desc = src.MKT_OPERATION_TYPE_FR_DESC
    , audit_load_id = {job_run_id}
    , audit_last_update_ts = current_timestamp()

when not matched then
insert (
    mkt_operation_type_bid
    , mkt_operation_type_long_en_nm
    , mkt_operation_type_short_en_nm
    , mkt_operation_type_long_fr_nm
    , mkt_operation_type_short_fr_nm
    , mkt_operation_type_en_desc
    , mkt_operation_type_fr_desc
    , audit_load_id
    , audit_last_update_ts
)
values (
    src.MKT_OPERATION_TYPE_BID
    , src.MKT_OPERATION_TYPE_LONG_EN_NM
    , src.MKT_OPERATION_TYPE_SHORT_EN_NM
    , src.MKT_OPERATION_TYPE_LONG_FR_NM
    , src.MKT_OPERATION_TYPE_SHORT_FR_NM
    , src.MKT_OPERATION_TYPE_EN_DESC
    , src.MKT_OPERATION_TYPE_FR_DESC
    , {job_run_id}
    , current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_market_operation_type_dim")
logger.info(sql)
spark.sql(sql)

sql = """
update curated_db.tbl_bo_market_operation_type_dim
set bo_market_operation_type_dkey = bo_market_operation_type_skey
where bo_market_operation_type_dkey is null
"""
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_market_operation_type_dim build")
