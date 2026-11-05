catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_SHIPMENT_BUNDLE_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
select coalesce(max(application_update_ts), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_shipment_bundle_fact
"""

row = spark.sql(sql).first()
last_process_ts = row["max_date"]

sql = f"""

with shipment_bundle_source as (
    select
        smb.shipment_bundle_pk                  as rk_shipment_bundle_pk,
        smb.shipment_fk                         as rk_shipment_fk,
        smb.bundle_total_amt                    as bundle_total_amt,
        smb.bundle_volume_of_items_num          as bundle_volume_of_items_num,
        coalesce(smb.bundle_par_value_amt, 0)   as bundle_par_value_amt,
        smb.gov_banking_cat_fk                  as gov_banking_cat_fk,
        smb.client_fk                           as client_fk,
        smb.application_user_name               as application_user_name,
        smb.application_update_timestamp        as application_update_timestamp,
        smb.audit_creation_user                 as audit_creation_user,
        smb.audit_creation_date                 as audit_creation_date,
        smb.audit_last_update_user              as audit_last_update_user,
        smb.audit_last_update_date              as audit_last_update_date
    from
        raw_db.habs_shipment_bundle smb
    where
        smb.application_update_timestamp > timestamp('{last_process_ts}')
),

dim_client as (
    select
        case
            when global_legal_entity_skey is null or global_legal_entity_skey = 0 then -1
            else global_legal_entity_skey
            end                                 as client_gle_key,
        rk_habs_client_pk                       as rk_habs_client_pk
    from view_db.vwu_global_legal_entity_dim
    where
        global_legal_entity_skey > 0
        and rk_habs_client_pk is not null
),

gov_bank_code as (
    select
        code_pk             as code_pk,
        attribute_en_name   as attribute_en_name
    from raw_db.corporate_code_table
),

dim_gov_bank_category as (
    select
        case
            when bo_gov_bank_category_skey is null or bo_gov_bank_category_skey = 0 then -1
            else bo_gov_bank_category_skey
            end                                 as bo_gov_bank_category_skey,
        gov_bank_category_short_en_nm           as gov_bank_category_short_en_nm
    from
        curated_db.tbl_bo_gov_bank_category_dim
    where
        bo_gov_bank_category_skey > 0
)

insert into curated_db.tbl_bo_shipment_bundle_fact (
    bo_gov_bank_category_skey,
    client_gle_key,
    rk_shipment_bundle_pk,
    rk_shipment_pk,
    bundle_par_value_amt,
    bundle_total_amt,
    bundle_volume_of_items_num,
    application_user_nm,
    application_update_ts,
    audit_creation_user_nm,
    audit_creation_date_ts,
    audit_last_update_user_nm,
    audit_last_update_date_ts,
    optlock,
    md_workflow_execution_skey,
    md_create_ts,
    md_last_update_ts,
    md_chksum,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
)

select
    gbc.bo_gov_bank_category_skey       as bo_gov_bank_category_skey,
    gle.client_gle_key                  as client_gle_key,
    src.RK_SHIPMENT_BUNDLE_PK           as rk_shipment_bundle_pk,
    src.RK_SHIPMENT_FK                  as rk_shipment_pk,
    src.BUNDLE_PAR_VALUE_AMT            as bundle_par_value_amt,
    src.BUNDLE_TOTAL_AMT                as bundle_total_amt,
    src.BUNDLE_VOLUME_OF_ITEMS_NUM      as bundle_volume_of_items_num,
    src.APPLICATION_USER_NAME           as application_user_nm,
    src.APPLICATION_UPDATE_TIMESTAMP    as application_update_ts,
    src.AUDIT_CREATION_USER             as audit_creation_user_nm,
    src.AUDIT_CREATION_DATE             as audit_creation_date_ts,
    src.AUDIT_LAST_UPDATE_USER          as audit_last_update_user_nm,
    src.AUDIT_LAST_UPDATE_DATE          as audit_last_update_date_ts,
    1                                   as optlock,
    null                                as md_workflow_execution_skey,
    null                                as md_create_ts,
    null                                as md_last_update_ts,
    cast(null as string)                as md_chksum,
    {job_run_id}                        as audit_load_id,
    current_timestamp()                 as audit_create_ts,
    current_timestamp()                 as audit_last_update_ts
from
    shipment_bundle_source src left join dim_client gle
        on src.CLIENT_FK = gle.rk_habs_client_pk
    left join gov_bank_code gbcd
        on src.GOV_BANKING_CAT_FK = gbcd.code_pk
    left join dim_gov_bank_category gbc
        on gbcd.attribute_en_name = gbc.gov_bank_category_short_en_nm
"""

logger.info("Executing INSERT for curated_db.tbl_bo_shipment_bundle_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_shipment_bundle_fact build")