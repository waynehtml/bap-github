catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_BUS_TRANS_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(business_value_dt), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_bus_trans_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""
with source_trans_fact as
(
    select
        bt.business_value_date                                      as  business_value_dt,
        gle.global_legal_entity_skey                                as  financial_institution_skey,
        trans_type_dim.bo_bus_trans_type_skey                       as  bo_bus_trans_type_skey,
        trans_status_dim.bo_bus_trans_status_skey                   as  bo_bus_trans_status_skey,
        trans_service_dim.bo_bus_trans_service_skey                 as  bo_bus_trans_service_skey,
        bt.business_trans_pk                                        as  rk_habs_business_trans_pk,
        bt.business_value_amt                                       as  business_value_amt,
        null                                                        as  bo_bus_trans_skey,
        null                                                        as  md_workflow_execution_skey,
        null                                                        as  md_create_ts,
        null                                                        as  md_last_update_ts,
        null                                                        as  md_chksum,
        bt.application_update_timestamp                             as  application_update_ts
    from
        raw_db.habs_business_transaction bt join raw_db.corporate_code_table btt
            on bt.business_trans_type_fk = btt.code_pk
        join raw_db.corporate_code_table bts
            on bt.business_trans_status_fk =bts.code_pk
        /* trans type */
        join curated_db.tbl_bo_bus_trans_type_dim trans_type_dim
            on trans_type_dim.bus_trans_type_bid = trim(btt.code_constant_id)
        /* trans status */
        join curated_db.tbl_bo_bus_trans_status_dim trans_status_dim
            on trans_status_dim.bus_trans_status_bid = trim(bts.code_constant_id)
        /* service */
        join curated_db.tbl_bo_bus_trans_service_dim trans_service_dim
            on trans_service_dim.bus_trans_service_nm = bt.bus_trans_service_name
        /* gle - client */
        join view_db.vwu_global_legal_entity_dim gle
            on bt.client_fk = gle.client_id
    where
        bt.business_trans_type_fk in (444,453)
        and (bt.bus_trans_service_name = 'Incoming Payment' and bt.business_trans_status_fk = 420
        or
        bt.bus_trans_service_name = 'Outgoing Payment' and bt.business_trans_status_fk in (429, 439, 10666, 426, 423))
        and (bt.business_value_date > timestamp('{last_process_ts}'))
)

insert into curated_db.tbl_bo_bus_trans_fact
(
    business_value_dt,
    financial_institution_skey,
    bo_bus_trans_type_skey,
    bo_bus_trans_status_skey,
    bo_bus_trans_service_skey,
    rk_habs_business_trans_pk,
    business_value_amt,
    md_workflow_execution_skey,
    md_create_ts,
    md_last_update_ts,
    md_chksum,
    application_update_ts,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
)

select
    stf.business_value_dt,
    stf.financial_institution_skey,
    stf.bo_bus_trans_type_skey,
    stf.bo_bus_trans_status_skey,
    stf.bo_bus_trans_service_skey,
    stf.rk_habs_business_trans_pk,
    stf.business_value_amt,
    stf.md_workflow_execution_skey,
    stf.md_create_ts,
    stf.md_last_update_ts,
    stf.md_chksum,
    stf.application_update_ts,
    {job_run_id},
    current_timestamp(),
    current_timestamp()
from
    source_trans_fact stf left anti join curated_db.tbl_bo_bus_trans_fact btf
        on stf.rk_habs_business_trans_pk = btf.rk_habs_business_trans_pk
"""

logger.info("Executing INSERT for curated_db.TBL_BO_BUS_TRANS_FACT")
logger.info(sql)
spark.sql(sql)

logger.info("Completed TBL_BO_BUS_TRANS_FACT build")