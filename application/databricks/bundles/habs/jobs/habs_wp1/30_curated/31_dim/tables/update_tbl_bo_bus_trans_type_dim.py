catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_bus_trans_type_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_bus_trans_type_dim as tgt
using (
    select
        a.code_constant_id  as bus_trans_type_bid,
        a.attribute_en_desc as bus_trans_type_long_en_nm,
        a.attribute_en_name as bus_trans_type_short_en_nm,
        a.attribute_fr_desc as bus_trans_type_long_fr_nm,
        a.attribute_fr_name as bus_trans_type_short_fr_nm,
        a.attribute_en_desc as bus_trans_type_en_desc,
        a.attribute_fr_desc as bus_trans_type_fr_desc,
        null                as audit_load_id,
        null                as audit_last_update_ts
    from
        raw_db.corporate_code_table a join raw_db.corporate_code_category_table b
            on a.code_category_fk  = b.code_category_pk
    where
        b.attribute_en_name = 'BUSTRANSTYPE'
) as src
on tgt.bus_trans_type_bid = src.BUS_TRANS_TYPE_BID

when matched then update
set
        bus_trans_type_bid              =   src.BUS_TRANS_TYPE_BID,
        bus_trans_type_long_en_nm       =   src.BUS_TRANS_TYPE_LONG_EN_NM,
        bus_trans_type_short_en_nm      =   src.BUS_TRANS_TYPE_SHORT_EN_NM,
        bus_trans_type_long_fr_nm       =   src.BUS_TRANS_TYPE_LONG_FR_NM,
        bus_trans_type_short_fr_nm      =   src.BUS_TRANS_TYPE_SHORT_FR_NM,
        bus_trans_type_en_desc          =   src.BUS_TRANS_TYPE_EN_DESC,
        bus_trans_type_fr_desc          =   src.BUS_TRANS_TYPE_FR_DESC,
        audit_load_id                      =   {job_run_id},
        audit_last_update_ts                   =   current_timestamp()

when not matched then
insert(
        bus_trans_type_bid,
        bus_trans_type_long_en_nm,
        bus_trans_type_short_en_nm,
        bus_trans_type_long_fr_nm,
        bus_trans_type_short_fr_nm,
        bus_trans_type_en_desc,
        bus_trans_type_fr_desc,
        md_current_ind,
        md_eff_ts,
        md_exp_ts,
        md_workflow_execution_skey,
        md_create_ts,
        md_last_update_ts,
        audit_load_id,
        audit_last_update_ts
)
values(
    src.BUS_TRANS_TYPE_BID,
    src.BUS_TRANS_TYPE_LONG_EN_NM,
    src.BUS_TRANS_TYPE_SHORT_EN_NM,
    src.BUS_TRANS_TYPE_LONG_FR_NM,
    src.BUS_TRANS_TYPE_SHORT_FR_NM,
    src.BUS_TRANS_TYPE_EN_DESC,
    src.BUS_TRANS_TYPE_FR_DESC,
    1,
    current_date(),
    date '9999-12-31',
    0,
    current_timestamp(),
    current_timestamp(),
    {job_run_id},
    current_timestamp()
)
"""
logger.info("Executing MERGE for curated_db.tbl_bo_bus_trans_type_dim")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_bus_trans_type_dim build")