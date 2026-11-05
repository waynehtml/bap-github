catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_gov_bus_trans_fact build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(business_value_dt), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_gov_bus_trans_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""

with src_data as (
    select distinct
           bt.business_trans_pk                                 as rk_business_trans_pk,
           bt.business_value_date                               as business_value_dt,
           bt.client_fk                                         as client_fk,
           bt.business_trans_status_fk                          as business_trans_status_fk,
           bt.bus_trans_service_name                            as bus_trans_service_name,
           gbt.gov_banking_trans_type_fk                        as gov_banking_trans_type_fk,
           govbankcat.attribute_en_name                         as gov_banking_cat,
           orggovbankcat.attribute_en_name                      as org_gov_banking_cat,
           coalesce(govbankcat.attribute_en_name,
           orggovbankcat.attribute_en_name)                     as gov_banking_cat_fk,
           gbt.par_value_amt                                    as par_value_amt,
           bt.business_value_amt                                as business_value_amt,
           i.instruction_source_fk                              as instruction_source_fk,
           i.instruction_service_fk                             as instruction_service_fk,
           bt.src_reference_num                                 as src_reference_num,
           coalesce(cast(bt.confirmation_ind as string), '')    as confirmation_ind,
           coalesce(cast(bt.override_ind as string), '')        as override_ind,
           coalesce(cast(bt.status_override_ind as string), '') as status_override_ind,
           coalesce(cast(bt.was_in_repair_ind as string), '')   as was_in_repair_ind,
           bt.authorizing_user_name                             as authorizing_user_name,
           gbt.application_user_name                            as application_user_name,
           bt.application_update_timestamp                      as p_timestamp,
           gbt.application_update_timestamp                     as c_timestamp,
           gbt.audit_creation_user                              as audit_creation_user,
           CAST(gbt.audit_creation_date as date)                as audit_creation_date,
           gbt.audit_last_update_user                           as audit_last_update_user,
           CAST(gbt.audit_last_update_date as date)             as audit_last_update_date,
           coalesce(gbt.narrative_desc, ' ')                    as narrative_desc,
           coalesce(gbt.region_fk, 0)                           as region_fk,
           gbt.revenue_account_desc                             as revenue_account_desc,
           coalesce(gbt.revenue_account_date, date'1900-01-01') as revenue_account_date,
           gbt.volume_of_items_num                              as volume_of_items_num,
           coalesce(cast(gbt.shipment_ind as string), '')       as shipment_ind,
           gbt.shipment_bundle_fk                               as shipment_bundle_fk,
           gbt.inc_payment_bus_trans_fk                         as inc_payment_bus_trans_fk,
           gbt.out_payment_bus_trans_fk                         as out_payment_bus_trans_fk,
           gbt.payment_adv_bus_trans_fk                         as payment_adv_bus_trans_fk,
           gbt.reconciliation_unit_fk                           as reconciliation_unit_fk,
           coalesce(pbt.payment_type_fk,
                    pbtt.payment_type_fk,
                    pad.payment_type_fk)                        as payment_type_fk,
           coalesce(pbt.pcss_type_fk,
                    pbtt.pcss_type_fk,
                    pad.pcss_type_fk)                           as pcss_type_fk,
           coalesce(cast(i.manual_interventation_ind as string), '') as manual_interventation_ind,
           coalesce(gbt.inc_payment_bus_trans_fk, gbt.out_payment_bus_trans_fk) as rk_habs_associated_payment_pk,
           coalesce(gbt.application_update_timestamp, bt.application_update_timestamp)  as application_update_ts,
           coalesce(gbt.application_update_timestamp, bt.application_update_timestamp)  as instruction_end_time
    from
            raw_db.habs_business_transaction bt join raw_db.habs_government_bus_transaction gbt
                on bt.business_trans_pk = gbt.business_trans_pk
        left join  raw_db.habs_instruction i
            on bt.business_trans_pk = i.business_trans_fk
        join raw_db.corporate_code_table instructionsource  on instructionsource.code_pk = i.instruction_source_fk
        join raw_db.corporate_code_table instructionservice on instructionservice.code_pk = i.instruction_service_fk
        left join raw_db.corporate_code_table govbankcat    on govbankcat.code_pk = gbt.gov_banking_cat_fk
        left join raw_db.corporate_code_table orggovbankcat on orggovbankcat.code_pk = gbt.original_gov_banking_cat_fk
        left join raw_db.corporate_code_table rg            on rg.code_pk = gbt.region_fk
        left join raw_db.habs_payment_bus_transaction pbt   on gbt.inc_payment_bus_trans_fk = pbt.business_trans_pk
        left join raw_db.habs_payment_bus_transaction pbtt  on gbt.out_payment_bus_trans_fk = pbtt.business_trans_pk
        left join raw_db.habs_payment_advice_bus_transaction pad on gbt.payment_adv_bus_trans_fk = pad.business_trans_pk
    where
        bt.business_trans_status_fk IN (420, 423)
        and (
                gbt.application_update_timestamp > timestamp('{last_process_ts}')
                or
                gbt.application_update_timestamp is null
            )
),

cte_trans_status as (
    select
        case
            when tst.bo_bus_trans_status_skey is null
            or tst.bo_bus_trans_status_skey = 0
            then -1
            else tst.bo_bus_trans_status_skey end               as bo_bus_trans_status_skey,
        cd_tbl.code_pk                                          as business_trans_status_fk
    from  curated_db.tbl_bo_bus_trans_status_dim tst
    join  raw_db.corporate_code_table cd_tbl on tst.bus_trans_status_bid = cd_tbl.code_constant_id
),

cte_trans_type as (
    select
        case
            when ttyp.bo_gov_bank_trans_type_skey is null
            or ttyp.bo_gov_bank_trans_type_skey = 0
            then -1
            else ttyp.bo_gov_bank_trans_type_skey end           as bo_gov_bank_trans_type_skey,
        cd_tbl.code_pk                                          as gov_banking_trans_type_fk
    from   curated_db.tbl_bo_gov_bank_trans_type_dim ttyp
    join   raw_db.corporate_code_table cd_tbl on ttyp.gov_bank_trans_typ_bid = cd_tbl.code_constant_id
),

cte_gov_bank_category as (
    select
        bo_gov_bank_category_skey,
        gov_bank_category_bid
    from
        curated_db.tbl_bo_gov_bank_category_dim
    where
        bo_gov_bank_category_skey > 0
        and gov_bank_category_bid is not null
),

cte_trans_service as (
    select
        bus_trans_service_nm,
        bo_bus_trans_service_skey
    from
        curated_db.tbl_bo_bus_trans_service_dim
    where
        bo_bus_trans_service_skey <> -1
),

cte_region as (
    select
        case
            when reg.bo_region_skey is null
            or
            reg.bo_region_skey = 0
            then -1
            else reg.bo_region_skey end     as bo_region_skey,
        region_bid                          as region_bid
    from
       curated_db.tbl_bo_region_dim reg
),

cte_shipment_bundle as (
    select
        bo_shipment_bundle_skey,
        rk_shipment_bundle_pk
    from
       curated_db.tbl_bo_shipment_bundle_fact
    where
        rk_shipment_bundle_pk is not null
),

cte_reconciliation_unit as (
    select
        case
            when recon.bo_reconciliation_unit_skey is null
            or recon.bo_reconciliation_unit_skey = 0
            then -1
            else recon.bo_reconciliation_unit_skey end          as bo_reconciliation_unit_skey,
        reconciliation_unit_bid                                 as reconciliation_unit_bid
    from
        curated_db.tbl_bo_reconciliation_unit_dim recon
),

cte_instruction_source as (
    select
        case
            when isrc.BO_INSTRUCTION_SOURCE_SKEY is null
            or isrc.BO_INSTRUCTION_SOURCE_SKEY = 0
            then -1
            else isrc.BO_INSTRUCTION_SOURCE_SKEY end        as bo_instruction_source_skey,
        instruction_source_bid                              as instruction_source_bid
    from
        curated_db.tbl_bo_instruction_source_dim isrc
    where
        instruction_source_bid is not null
        and bo_instruction_source_skey > 0
),

cte_instruction_service as (
    select
        case
            when isvc.bo_instruction_service_skey is null
            or isvc.bo_instruction_service_skey = 0
            then -1
            else isvc.bo_instruction_service_skey end         as instruction_service_skey,
        instruction_srvc_bid                                  as instruction_srvc_bid
    from
        curated_db.tbl_bo_instruction_service_dim isvc
    where
        instruction_srvc_bid is not null
        and bo_instruction_service_skey > 0
),

cte_payment_type as (
    select
        cd_tbl.code_pk as payment_type_fk,
        case
            when pt.bo_payment_type_skey is null
            or
            pt.bo_payment_type_skey = 0
            then -1
            else pt.bo_payment_type_skey end                  as bo_payment_type_skey
    from
       curated_db.tbl_bo_payment_type_dim pt join raw_db.corporate_code_table cd_tbl
            on cd_tbl.code_constant_id = pt.payment_type_bid
    where
        pt.bo_payment_type_skey > 0
),

cte_pcss_type as (
    select
        pcss_type_bid,
        case
            when pc.bo_pcss_type_skey is null or pc.bo_pcss_type_skey = 0
            then -1
            else pc.bo_pcss_type_skey end         as bo_pcss_type_skey
    from
       curated_db.tbl_bo_pcss_type_dim pc
    where
        bo_pcss_type_skey > 0
        and pcss_type_bid is not null
),

cte_bus_trans_ind as (
    select
        case
            when ind.bo_gov_bus_trans_ind_skey is null
            or ind.bo_gov_bus_trans_ind_skey = 0
            then -1
            else ind.bo_gov_bus_trans_ind_skey end            as bo_gov_bus_trans_ind_skey,
           concat(CAST(ind.confirmation_ind as string), CAST(ind.override_ind as string),
                  CAST(ind.status_override_ind as string), CAST(ind.was_in_repair_ind as string),
                  CAST(ind.shipment_ind as string), CAST(ind.manual_intervention_ind as string)) as lkp_ind
    from   curated_db.tbl_bo_gov_bus_trans_ind_dim ind
    where  bo_gov_bus_trans_ind_skey > 0
),

cte_gle as(
    select
        case when legal.global_legal_entity_skey is null
            or legal.global_legal_entity_skey = 0
         then -1
         else legal.global_legal_entity_skey end as client_gle_skey,
        rk_habs_client_pk
    from view_db.vwu_global_legal_entity_dim legal
)

INSERT INTO curated_db.tbl_bo_gov_bus_trans_fact
  (
    business_value_dt,
    client_gle_skey,
    bo_bus_trans_status_skey,
    bo_gov_bank_trans_type_skey,
    bo_gov_bank_category_skey,
    original_bo_gov_bank_category_skey,
    bo_reconciliation_unit_skey,
    bo_region_skey,
    bo_gov_bus_trans_ind_skey,
    revenue_account_dt,
    rk_habs_business_trans_pk,
    rk_shipment_bundle_pk,
    rk_habs_payment_advice_pk,
    rk_habs_associated_payment_pk,
    par_value_amt,
    business_value_amt,
    application_update_ts,
    instruction_source_skey,
    instruction_service_skey,
    md_create_ts,
    md_last_update_ts,
    md_workflow_execution_skey,
    md_data_load_method_skey,
    md_system_skey,
    instruction_end_time,
    bo_payment_type_skey,
    bo_pcss_type_skey,
    narrative_desc,
    revenue_account_desc,
    src_reference_num,
    volume_of_items_num,
    bo_payment_direction,
    authorizing_user_nm,
    application_user_nm,
    audit_creation_user_nm,
    audit_creation_date_ts,
    audit_last_update_user_nm,
    audit_last_update_date_ts,
    md_chksum,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
    )

select
    s.business_value_dt                 as business_value_dt,
    gle.client_gle_skey                 as client_gle_skey,
    tst.bo_bus_trans_status_skey        as bo_bus_trans_status_skey,
    ttyp.bo_gov_bank_trans_type_skey    as bo_gov_bank_trans_type_skey,
    case
        when s.gov_banking_cat is not null
        then cat.bo_gov_bank_category_skey
        else -1 end                     as bo_gov_bank_category_skey,
    case
        when s.org_gov_banking_cat is not null
        then cat.bo_gov_bank_category_skey
        else -1 end                     as original_bo_gov_bank_category_skey,
    recon.bo_reconciliation_unit_skey   as bo_reconciliation_unit_skey,
    reg.bo_region_skey                  as bo_region_skey,
    ind.bo_gov_bus_trans_ind_skey       as bo_gov_bus_trans_ind_skey,
    s.revenue_account_date              as revenue_account_dt,
    s.rk_business_trans_pk              as rk_habs_business_trans_pk,
    s.shipment_bundle_fk                as rk_shipment_bundle_pk,
    s.payment_adv_bus_trans_fk          as rk_habs_payment_advice_pk,
    S.rk_habs_associated_payment_pk     as rk_habs_associated_payment_pk,
    s.par_value_amt                     as par_value_amt,
    s.business_value_amt                as business_value_amt,
    s.application_update_ts             as application_update_ts,
    isrc.BO_INSTRUCTION_SOURCE_SKEY     as instruction_source_skey,
    isvc.instruction_service_skey       as instruction_service_skey,
    null                                as md_create_ts,
    null                                as md_last_update_ts,
    NULL                                as md_workflow_execution_skey,
    null                                as md_data_load_method_skey,
    null                                as md_system_skey,           -- hardcoded to 1 in this job
    s.instruction_end_time              as instruction_end_time,
    pt.bo_payment_type_skey             as bo_payment_type_skey,
    pc.bo_pcss_type_skey                as bo_pcss_type_skey,
    s.narrative_desc                    as narrative_desc,
    s.revenue_account_desc              as revenue_account_desc,
    s.src_reference_num                 as src_reference_num,
    s.volume_of_items_num               as volume_of_items_num,
    CAST(NULL as string)                                            as bo_payment_direction,      -- no derivation found in source job
    s.authorizing_user_name                                        as authorizing_user_nm,
    s.application_user_name                                        as application_user_nm,
    s.audit_creation_user                                          as audit_creation_user_nm,
    s.audit_creation_date                                          as audit_creation_date_ts,
    s.audit_last_update_user                                       as audit_last_update_user_nm,
    s.audit_last_update_date                                       as audit_last_update_date_ts,
    -- ChkSum: row hash over the natural/business columns, for downstream CDC
    md5(
        concat_ws('|',
            CAST(s.rk_business_trans_pk as string), CAST(s.client_fk as string), s.src_reference_num,
            date_format(s.business_value_dt,'yyyyMMdd'), CAST(s.business_value_amt as string),
            s.bus_trans_service_name, CAST(s.gov_banking_trans_type_fk as string),
            CAST(s.payment_type_fk as string), CAST(s.pcss_type_fk as string),
            CAST(s.shipment_bundle_fk as string), CAST(s.reconciliation_unit_fk as string),
            date_format(s.p_timestamp,'yyyyMMddHHmmss'), date_format(s.c_timestamp,'yyyyMMddHHmmss')
        )
    )                                                                 as md_chksum,
    {job_run_id}                             as audit_load_id,
    current_timestamp()                      as audit_create_ts,
    current_timestamp()                      as audit_last_update_ts
from src_data s
left join cte_gle gle on gle.rk_habs_client_pk = s.client_fk
left join cte_trans_status     tst   on tst.business_trans_status_fk   = s.business_trans_status_fk
left join cte_trans_type      ttyp  on ttyp.gov_banking_trans_type_fk = s.gov_banking_trans_type_fk
left join cte_gov_bank_category       cat   on cat.gov_bank_category_bid      = s.gov_banking_cat_fk
left join cte_trans_service   trs   on trs.bus_trans_service_nm       = s.bus_trans_service_name
left join cte_region           reg   on reg.region_bid                 = s.region_fk
left join cte_reconciliation_unit         recon on recon.reconciliation_unit_bid  = s.reconciliation_unit_fk
left join cte_instruction_source     isrc  on isrc.INSTRUCTION_SOURCE_BID    = s.instruction_source_fk
left join cte_instruction_service    isvc  on isvc.instruction_srvc_bid      = s.instruction_service_fk
left join cte_payment_type      pt    on pt.payment_type_fk             = s.payment_type_fk
left join cte_pcss_type          pc    on pc.pcss_type_bid               = s.pcss_type_fk
left join cte_bus_trans_ind           ind
       on ind.lkp_ind = concat(
              s.confirmation_ind, s.override_ind, s.status_override_ind,
              s.was_in_repair_ind, s.shipment_ind, s.manual_interventation_ind
          )
"""

logger.info("Executing INSERT for curated_db.tbl_bo_gov_bus_trans_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_gov_bus_trans_fact build")