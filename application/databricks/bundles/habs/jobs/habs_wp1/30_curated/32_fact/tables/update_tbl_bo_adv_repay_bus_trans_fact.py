catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_ADV_REPAY_BUS_TRANS_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
select coalesce(max(adv_business_value_dt), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_adv_repay_bus_trans_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""
with src_raw as (
    select
        abt.business_trans_pk       as rk_habs_adv_business_trans_pk,
        arbt.business_trans_pk      as rk_habs_repay_business_trans_pk,
        bt.client_fk                as client_fk,
        bt.src_reference_num        as src_reference_num,
        bt.business_value_date      as adv_business_value_date,
        btrp.business_value_date    as repay_business_value_dt,
        bt.business_value_amt       as adv_business_value_amt,
        btrp.business_value_amt     as repay_business_value_amt,
        case
            when bt.confirmation_ind is null or trim(cast(bt.confirmation_ind as string)) = '' then '-1'
            else cast(bt.confirmation_ind as string)
        end as adv_confirmation_ind,
        case
            when btrp.confirmation_ind is null or trim(cast(btrp.confirmation_ind as string)) = '' then '-1'
            else cast(btrp.confirmation_ind as string)
        end as repay_confirmation_ind,
        case
            when bt.override_ind is null or trim(cast(bt.override_ind as string)) = '' then '-1'
            else cast(bt.override_ind as string)
        end as adv_override_ind,
        case
            when btrp.override_ind is null or trim(cast(btrp.override_ind as string)) = '' then '-1'
            else cast(btrp.override_ind as string)
        end as repay_override_ind,
        case
            when bt.status_override_ind is null or trim(cast(bt.status_override_ind as string)) = '' then '-1'
            else cast(bt.status_override_ind as string)
        end as adv_status_override_ind,
        case
            when btrp.status_override_ind is null or trim(cast(btrp.status_override_ind as string)) = '' then '-1'
            else cast(btrp.status_override_ind as string)
        end as repay_status_override_ind,
        case
            when bt.was_in_repair_ind is null or trim(cast(bt.was_in_repair_ind as string)) = '' then '-1'
            else cast(bt.was_in_repair_ind as string)
        end as adv_was_in_repair_ind,
        case
            when btrp.was_in_repair_ind is null or trim(cast(btrp.was_in_repair_ind as string)) = '' then '-1'
            else cast(btrp.was_in_repair_ind as string)
        end as repay_was_in_repair_ind,
        abt.interest_rate                               as interest_rate,
        abt.advance_type_fk                             as advance_type_fk,
        abt.repayment_date                              as repayment_date,
        abt.term_num                                    as term_num,
        abt.alloc_bus_trans_fk                          as alloc_bus_trans_fk,
        abt.pledge_bus_trans_fk                         as pledge_bus_trans_fk,
        abt.account_fk                                  as adv_account_fk,
        arbt.account_fk                                 as repay_account_fk,
        abt.advance_application_date                    as advance_application_date,
        abt.payment_adv_bus_trans_fk                    as payment_adv_bus_trans_fk,
        arbt.interest_amt                               as interest_amt,
        abt.application_user_name                       as application_user_name,
        arbt.application_user_name                      as repay_application_user_name,
        bt.application_update_timestamp                 as adv_p_timestamp,
        abt.application_update_timestamp                as adv_c_timestamp,
        abt.audit_creation_user                         as adv_audit_creation_user,
        abt.audit_creation_date                         as adv_audit_creation_date,
        abt.audit_last_update_user                      as adv_audit_last_update_user,
        abt.audit_last_update_date                      as adv_audit_last_update_date,
        btrp.application_update_timestamp               as repay_p_timestamp,
        arbt.application_update_timestamp               as repay_c_timestamp,
        arbt.audit_creation_user                        as repay_audit_creation_user,
        arbt.audit_creation_date                        as repay_audit_creation_date,
        arbt.audit_last_update_user                     as repay_audit_last_update_user,
        arbt.audit_last_update_date                     as repay_audit_last_update_date,
        i.instruction_source_fk                         as adv_instruction_source_fk,
        i.instruction_service_fk                        as adv_instruction_service_fk,
        irp.instruction_source_fk                       as repay_instruction_source_fk,
        irp.instruction_service_fk                      as repay_instruction_service_fk,
        case
            when i.manual_interventation_ind is null or trim(cast(i.manual_interventation_ind as string)) = '' then '-1'
            else cast(i.manual_interventation_ind as string)
        end as adv_manual_intervention_ind,
        case
            when irp.manual_interventation_ind is null or trim(cast(irp.manual_interventation_ind as string)) = '' then '-1'
            else cast(irp.manual_interventation_ind as string)
        end as repay_manual_intervention_ind,
        concat(
            case when bt.confirmation_ind is null or trim(cast(bt.confirmation_ind as string)) = '' then '-1' else cast(bt.confirmation_ind as string) end,
            case when i.manual_interventation_ind is null or trim(cast(i.manual_interventation_ind as string)) = '' then '-1' else cast(i.manual_interventation_ind as string) end,
            case when bt.override_ind is null or trim(cast(bt.override_ind as string)) = '' then '-1' else cast(bt.override_ind as string) end,
            case when bt.status_override_ind is null or trim(cast(bt.status_override_ind as string)) = '' then '-1' else cast(bt.status_override_ind as string) end,
            case when bt.was_in_repair_ind is null or trim(cast(bt.was_in_repair_ind as string)) = '' then '-1' else cast(bt.was_in_repair_ind as string) end,
            case when btrp.confirmation_ind is null or trim(cast(btrp.confirmation_ind as string)) = '' then '-1' else cast(btrp.confirmation_ind as string) end,
            case when irp.manual_interventation_ind is null or trim(cast(irp.manual_interventation_ind as string)) = '' then '-1' else cast(irp.manual_interventation_ind as string) end,
            case when btrp.override_ind is null or trim(cast(btrp.override_ind as string)) = '' then '-1' else cast(btrp.override_ind as string) end,
            case when btrp.status_override_ind is null or trim(cast(btrp.status_override_ind as string)) = '' then '-1' else cast(btrp.status_override_ind as string) end,
            case when btrp.was_in_repair_ind is null or trim(cast(btrp.was_in_repair_ind as string)) = '' then '-1' else cast(btrp.was_in_repair_ind as string) end
        ) as repay_ind_key,

        case
            when abt.application_update_timestamp is null and bt.application_update_timestamp is null then null
            when abt.application_update_timestamp is null then bt.application_update_timestamp
            when bt.application_update_timestamp is null then abt.application_update_timestamp
            else greatest(
                abt.application_update_timestamp,
                bt.application_update_timestamp
            ) end                                                           as adv_application_update_timestamp,
    case
        when arbt.application_update_timestamp is null and btrp.application_update_timestamp is null then null
        when arbt.application_update_timestamp is null then btrp.application_update_timestamp
        when btrp.application_update_timestamp is null then arbt.application_update_timestamp
        else greatest(arbt.application_update_timestamp, btrp.application_update_timestamp)
    end as repay_application_update_timestamp
    from
        raw_db.habs_advance_bus_transaction abt
    left join raw_db.habs_adv_repay_bus_transaction arbt
        on arbt.assoc_advance_bus_trans_fk = abt.business_trans_pk
    left join raw_db.habs_business_transaction bt
        on bt.business_trans_pk = abt.business_trans_pk
    left join raw_db.habs_business_transaction btrp
        on btrp.business_trans_pk = arbt.business_trans_pk
    left join raw_db.habs_instruction i
        on abt.business_trans_pk = i.business_trans_fk
    left join raw_db.habs_instruction irp
        on arbt.business_trans_pk = irp.business_trans_fk
    where
        i.instruction_service_fk in ('350', '10566')
    and btrp.business_value_date > timestamp('{last_process_ts}')
),

cte_global_legal_entity as (
    select
        case
            when global_legal_entity_skey is null
                or global_legal_entity_skey = 0 then -1
            else global_legal_entity_skey end   as client_gle_skey,
        cast(client_id as decimal(18,0))        as client_id
    from
        view_db.vwu_global_legal_entity_dim
    where
        client_id is not null
        and global_legal_entity_skey > 0
),

dim_advance_type AS (
    select
        case
            when advance_type.bo_advance_type_skey is null
             or advance_type.bo_advance_type_skey = 0
            then -1
            else advance_type.bo_advance_type_skey
        end as advance_type_fkey,
        advance_type_bid
    from curated_db.tbl_bo_advance_type_dim advance_type
    where bo_advance_type_skey > 0
),

dim_account AS (
    select
        case
            when adv_acct.bo_account_skey is null
                or adv_acct.bo_account_skey = 0
            then -1
            else adv_acct.bo_account_skey
        end                                 as adv_account_skey,
        adv_acct.rk_account_pk              as rk_habs_account_pk
    from curated_db.tbl_bo_account_dim adv_acct
    where bo_account_skey > 0
),

dim_instruction_source as (
    select
        case
            when adv_src.BO_INSTRUCTION_SOURCE_SKEY is null
                 or adv_src.BO_INSTRUCTION_SOURCE_SKEY = 0
            then -1
            else adv_src.BO_INSTRUCTION_SOURCE_SKEY
        end as instruction_source_skey,
        instruction_source_bid as instruction_source_bid
    from curated_db.tbl_bo_instruction_source_dim adv_src
    where bo_instruction_source_skey > 0
),

dim_instruction_service as (
    select
        case
            when adv_srv.bo_instruction_service_skey is null
                 or adv_srv.bo_instruction_service_skey = 0
            then -1
            else adv_srv.bo_instruction_service_skey
        end as adv_instruction_service_skey,
        adv_srv.instruction_srvc_bid as instruction_service_bid
    from curated_db.tbl_bo_instruction_service_dim adv_srv
    where bo_instruction_service_skey > 0
),

dim_repayment_indicator as (
    select
        case
            when ind.bo_adv_repay_bus_trans_ind_skey is null
                 or ind.bo_adv_repay_bus_trans_ind_skey = 0
            then -1
            else ind.bo_adv_repay_bus_trans_ind_skey
        end as bo_adv_repay_bus_trans_ind_skey,
        concat(
            cast(ind.adv_confirmation_ind as string),
            cast(ind.adv_manual_intervention_ind as string),
            cast(ind.adv_override_ind as string),
            cast(ind.adv_status_override_ind as string),
            cast(ind.adv_was_in_repair_ind as string),
            cast(ind.repay_confirmation_ind as string),
            cast(ind.repay_manual_intervention_ind as string),
            cast(ind.repay_override_ind as string),
            cast(ind.repay_status_override_ind as string),
            cast(ind.repay_was_in_repair_ind as string)
        ) as ref_lkp_key
    from curated_db.tbl_bo_adv_repay_bus_trans_ind_dim ind
    where ind.bo_adv_repay_bus_trans_ind_skey > 0
)

INSERT INTO curated_db.tbl_bo_adv_repay_bus_trans_fact (
    adv_application_date,
    rk_habs_adv_business_trans_pk,
    rk_habs_repay_business_trans_pk,
    client_gle_skey,
    src_reference_num,
    adv_business_value_dt,
    adv_business_value_amt,
    repay_business_value_dt,
    repay_business_value_amt,
    interest_rate,
    advance_type_fkey,
    repayment_date,
    term_num,
    rk_habs_alloc_bus_trans_pk,
    rk_habs_pledge_bus_trans_pk,
    adv_account_skey,
    repay_account_skey,
    rk_habs_repayment_advice_pk,
    interest_amount,
    adv_authorizing_user_name,
    repay_authorizing_user_name,
    adv_application_update_timestamp,
    adv_audit_creation_user,
    adv_audit_creation_date,
    adv_audit_last_update_user,
    adv_audit_last_update_date,
    repay_application_update_timestamp,
    repay_audit_creation_user,
    repay_audit_creation_date,
    repay_audit_last_update_user,
    repay_audit_last_update_date,
    adv_instruction_source_skey,
    adv_instruction_service_skey,
    repay_instruction_source_skey,
    repay_instruction_service_skey,
    bo_adv_repay_bus_trans_ind_skey,
    md_system_skey,
    md_data_load_method_skey,
    md_workflow_execution_skey,
    md_create_ts,
    md_last_update_ts,
    md_chksum,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
)

select
    src_data.advance_application_date           as adv_application_date,
    src_data.rk_habs_adv_business_trans_pk      as rk_habs_adv_business_trans_pk,
    src_data.rk_habs_repay_business_trans_pk    as rk_habs_repay_business_trans_pk,
    gle.client_gle_skey                         as client_gle_skey,
    src_data.src_reference_num                  as src_reference_num,
    src_data.adv_business_value_date            as adv_business_value_dt,
    src_data.adv_business_value_amt             as adv_business_value_amt,
    src_data.repay_business_value_dt            as repay_business_value_dt,
    src_data.repay_business_value_amt           as repay_business_value_amt,
    src_data.interest_rate                      as interest_rate,
    at.advance_type_fkey                        as advance_type_fkey,
    src_data.repayment_date                     as repayment_date,
    src_data.term_num                           as term_num,
    src_data.alloc_bus_trans_fk                 as rk_habs_alloc_bus_trans_pk,
    src_data.pledge_bus_trans_fk                as rk_habs_pledge_bus_trans_pk,
    adv_acct.adv_account_skey                   as adv_account_skey,
    repay_acct.adv_account_skey                 as repay_account_skey,
    src_data.adv_account_fk                     as rk_habs_repayment_advice_pk,
    src_data.interest_amt                       as interest_amount,
    src_data.adv_audit_creation_user            as adv_authorizing_user_name,
    src_data.repay_audit_creation_user          as repay_authorizing_user_name,
    src_data.adv_application_update_timestamp   as adv_application_update_timestamp,
    src_data.adv_audit_creation_user            as adv_audit_creation_user,
    src_data.adv_audit_creation_date            as adv_audit_creation_date,
    src_data.adv_audit_last_update_user         as adv_audit_last_update_user,
    src_data.adv_audit_last_update_date         as adv_audit_last_update_date,
    src_data.repay_application_update_timestamp as repay_application_update_timestamp,
    src_data.repay_audit_creation_user          as repay_audit_creation_user,
    src_data.repay_audit_creation_date          as repay_audit_creation_date,
    src_data.repay_audit_last_update_user       as repay_audit_last_update_user,
    src_data.repay_audit_last_update_date       as repay_audit_last_update_date,
    adv_src.INSTRUCTION_SOURCE_SKEY             as adv_instruction_source_skey,
    adv_srv.adv_instruction_service_skey        as adv_instruction_service_skey,
    repay_src.INSTRUCTION_SOURCE_SKEY           as repay_instruction_source_skey,
    repay_srv.adv_instruction_service_skey      as repay_instruction_service_skey,
    ind.bo_adv_repay_bus_trans_ind_skey         as bo_adv_repay_bus_trans_ind_skey,
    5                                           as md_system_skey,
    1                                           as md_data_load_method_skey,
    null                                        as md_workflow_execution_skey,
    null                                        as md_create_ts,
    null                                        as md_last_update_ts,
    null                                        as md_chksum,
    {job_run_id}                                as audit_load_id,
    current_timestamp()                         as audit_create_ts,
    current_timestamp()                         as audit_last_update_ts
from
    src_raw src_data inner join cte_global_legal_entity gle
        on src_data.client_fk = gle.client_id
    inner join dim_advance_type at
        on src_data.advance_type_fk = at.advance_type_bid
    inner join dim_account adv_acct
        on src_data.adv_account_fk = adv_acct.rk_habs_account_pk
    inner join dim_account repay_acct
        on src_data.repay_account_fk = repay_acct.rk_habs_account_pk
    inner join dim_instruction_source adv_src
        on src_data.adv_instruction_source_fk = adv_src.INSTRUCTION_SOURCE_BID
    inner join dim_instruction_source repay_src
        on src_data.repay_instruction_source_fk = repay_src.INSTRUCTION_SOURCE_BID
    inner join dim_instruction_service adv_srv
        on src_data.adv_instruction_service_fk = adv_srv.instruction_service_bid
    inner join dim_instruction_service repay_srv
        on src_data.repay_instruction_service_fk = repay_srv.instruction_service_bid
    inner join dim_repayment_indicator ind
        on src_data.repay_ind_key = ind.ref_lkp_key
"""