catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_bus_trans_status_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_bus_trans_status_dim as tgt
using (
    select
        cast(a.code_constant_id as string)                as bus_trans_status_bid,
        a.attribute_en_name                               as bus_trans_status_short_en_nm,
        a.attribute_fr_name                               as bus_trans_status_short_fr_nm,
        a.attribute_en_desc                               as bus_trans_status_long_en_nm,
        a.attribute_fr_desc                               as bus_trans_status_long_fr_nm,
        a.attribute_en_desc                               as bus_trans_status_en_desc,
        a.attribute_fr_desc                               as bus_trans_status_fr_desc
    from
        raw_db.corporate_code_table a join raw_db.corporate_code_category_table b
            on a.code_category_fk  = b.code_category_pk
    where
        b.attribute_en_name = 'BUSTRANSSTAT'
) as src
on tgt.bus_trans_status_bid = src.BUS_TRANS_STATUS_BID

when matched and (
    not (tgt.bus_trans_status_short_en_nm <=> src.BUS_TRANS_STATUS_SHORT_EN_NM)
    or not (tgt.bus_trans_status_short_fr_nm <=> src.BUS_TRANS_STATUS_SHORT_FR_NM)
    or not (tgt.bus_trans_status_long_en_nm <=> src.BUS_TRANS_STATUS_LONG_EN_NM)
    or not (tgt.bus_trans_status_long_fr_nm <=> src.BUS_TRANS_STATUS_LONG_FR_NM)
    or not (tgt.bus_trans_status_en_desc <=> src.BUS_TRANS_STATUS_EN_DESC)
    or not (tgt.bus_trans_status_fr_desc <=> src.BUS_TRANS_STATUS_FR_DESC)
)
then update
set
    bus_trans_status_bid            =   src.BUS_TRANS_STATUS_BID,
    bus_trans_status_short_en_nm    =   src.BUS_TRANS_STATUS_SHORT_EN_NM,
    bus_trans_status_short_fr_nm    =   src.BUS_TRANS_STATUS_SHORT_FR_NM,
    bus_trans_status_long_en_nm     =   src.BUS_TRANS_STATUS_LONG_EN_NM,
    bus_trans_status_long_fr_nm     =   src.BUS_TRANS_STATUS_LONG_FR_NM,
    bus_trans_status_en_desc        =   src.BUS_TRANS_STATUS_EN_DESC,
    bus_trans_status_fr_desc        =   src.BUS_TRANS_STATUS_FR_DESC

when not matched then
insert(
    bo_bus_trans_status_dkey,
    bus_trans_status_bid,
    bus_trans_status_short_en_nm,
    bus_trans_status_short_fr_nm,
    bus_trans_status_long_en_nm,
    bus_trans_status_long_fr_nm,
    bus_trans_status_en_desc,
    bus_trans_status_fr_desc,
    md_current_ind,
    md_eff_ts,
    md_exp_ts,
    md_workflow_execution_skey,
    md_create_ts,
    md_last_update_ts
)
values(
    null,
    src.BUS_TRANS_STATUS_BID,
    src.BUS_TRANS_STATUS_SHORT_EN_NM,
    src.BUS_TRANS_STATUS_SHORT_FR_NM,
    src.BUS_TRANS_STATUS_LONG_EN_NM,
    src.BUS_TRANS_STATUS_LONG_FR_NM,
    src.BUS_TRANS_STATUS_EN_DESC,
    src.BUS_TRANS_STATUS_FR_DESC,
    1,
    current_date(),
    date '9999-12-31',
    0,
    current_timestamp(),
    current_timestamp()
)
"""
logger.info("Executing MERGE for curated_db.tbl_bo_bus_trans_status_dim")
logger.info(sql)
spark.sql(sql)

sql = """
update curated_db.tbl_bo_bus_trans_status_dim
set bo_bus_trans_status_dkey = bo_bus_trans_status_skey
where bo_bus_trans_status_dkey is null
"""
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_bus_trans_status_dim build")