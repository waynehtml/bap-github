catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_shipment_fact build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(application_update_ts), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_shipment_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""

with cte_source_data as (
    select
        sm.shipment_pk                          as rk_shipment_fk,
        sm.shipment_status_fk                   as shipment_status_fk,
        sm.region_fk                            as region_fk,
        sm.reconciliation_unit_fk               as reconciliation_unit_fk,
        sm.acknowledged_rec_ind                 as acknowledged_rec_ind,
        sm.confirmed_ind                        as confirmed_ind,
        coalesce(sm.shipment_par_value_amt, 0)  as shipment_par_value_amt,  
        sm.shipment_total_amt                   as shipment_total_amt,
        sm.shipment_volume_of_items_num         as shipment_volume_of_items_num,
        sm.effective_date                       as effective_dt,
        sm.creation_date                        as creation_dt,
        sm.inactive_date                        as inactive_dt,
        sm.application_user_name                as application_user_nm,
        sm.application_update_timestamp         as application_update_ts,
        sm.audit_creation_user                  as audit_creation_user_nm,
        sm.audit_creation_date                  as audit_creation_date_ts,
        sm.audit_last_update_user               as audit_last_update_user_nm,
        sm.audit_last_update_date               as audit_last_update_date_ts
    from 
        raw_db.habs_shipment sm join raw_db.corporate_code_table reg
          on reg.code_pk = sm.region_fk
        join raw_db.corporate_code_table reconu
          on reconu.code_pk = sm.reconciliation_unit_fk
    where 
        sm.application_update_timestamp > timestamp('{last_process_ts}')
),

cte_region as (
    select 
      coalesce(reg.bo_region_skey, -1)  as bo_region_skey,
      region_bid                        as region_bid
    from 
      curated_db.tbl_bo_region_dim reg
),

cte_reconciliation_unit as (
    select
        coalesce(recon.bo_reconciliation_unit_skey, -1)   as bo_reconciliation_unit_skey,
        reconciliation_unit_bid                           as bo_reconciliation_unit_bid
    from 
        curated_db.tbl_bo_reconciliation_unit_dim recon
    where   
        bo_reconciliation_unit_skey > 0
),

cte_shipment_status as (
    select 
        a.code_pk                               as code_pk, 
        coalesce(b.bo_shipment_status_skey, -1) as bo_shipment_status_skey
    from 
      raw_db.corporate_code_table a JOIN curated_db.tbl_bo_shipment_status_dim b
        ON a.code_constant_id = b.shipment_status_bid
    where 
      a.code_constant_id IN ('Confirmed', 'Created', 'Received')
      AND a.code_category_fk = 4400
)

insert into curated_db.tbl_bo_shipment_fact
(
  bo_shipment_status_skey,    bo_region_skey,             bo_reconciliation_unit_skey,
  effective_dt,               creation_dt,                inactive_dt,
  rk_shipment_pk,             acknowledged_rec_ind,       confirmed_ind,
  shipment_par_value_amt,     shipment_total_amt,         shipment_volume_of_items_num,
  application_user_nm,        application_update_ts,      audit_creation_user_nm,
  audit_creation_date_ts,     audit_last_update_user_nm,  audit_last_update_date_ts,
  optlock,                    md_workflow_execution_skey, md_create_ts,
  md_last_update_ts,          md_chksum,                  audit_load_id,
  audit_create_ts,            audit_last_update_ts

)
select
    stat.bo_shipment_status_skey              as bo_shipment_status_skey,
    reg.bo_region_skey                        as bo_region_skey,
    recon.bo_reconciliation_unit_skey         as bo_reconciliation_unit_skey,
    s.effective_dt                            as effective_dt,
    s.creation_dt                             as creation_dt,
    s.inactive_dt                             as inactive_dt,
    s.rk_shipment_fk                          as rk_shipment_pk,
    s.acknowledged_rec_ind                    as acknowledged_rec_ind,
    s.confirmed_ind                           as confirmed_ind,
    coalesce(s.shipment_par_value_amt, 0)     as shipment_par_value_amt,
    s.shipment_total_amt                      as shipment_total_amt,
    s.shipment_volume_of_items_num            as shipment_volume_of_items_num,
    s.application_user_nm                     as application_user_nm,
    s.application_update_ts                   as application_update_ts,
    s.audit_creation_user_nm                  as audit_creation_user_nm,
    s.audit_creation_date_ts                  as audit_creation_date_ts,
    s.audit_last_update_user_nm               as audit_last_update_user_nm,        
    s.audit_last_update_date_ts               as audit_last_update_date_ts,
    1                                         as optlock,
    null                                      as md_workflow_execution_skey,
    null                                      as md_create_ts,
    null                                      as md_last_update_ts,
    null                                      as md_chksum,
    {job_run_id}                              as audit_load_id,
    current_timestamp()                       as audit_create_ts,
    current_timestamp()                       as audit_last_update_ts 
from 
    cte_source_data s left join cte_region reg on s.region_fk = reg.region_bid
    left join cte_reconciliation_unit recon ON s.reconciliation_unit_fk = recon.bo_reconciliation_unit_bid
    left join cte_shipment_status stat  ON s.shipment_status_fk = stat.code_pk

"""

logger.info("Executing INSERT for curated_db.tbl_bo_shipment_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_shipment_fact build")