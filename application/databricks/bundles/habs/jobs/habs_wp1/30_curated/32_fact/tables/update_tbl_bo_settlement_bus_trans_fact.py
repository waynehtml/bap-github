catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_SETTLEMENT_BUS_TRANS_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(business_value_dt), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_settlement_bus_trans_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""

with cte_settlement_bus_trans_data as (
    SELECT DISTINCT
           bt.business_trans_pk                                         as rk_business_trans_pk,
           bt.business_trans_status_fk                                  as business_trans_status_fk,
           c.client_id                                                  as client_id,
           bt.src_reference_num                                         as src_reference_num,
           bt.business_value_date                                       as business_value_date,
           bt.business_value_amt                                        as business_value_amt,
           bt.bus_trans_service_name                                    as bus_trans_service_name,
           bt.authorizing_user_name                                     as authorizing_user_name,
           sbt.settlement_impact_fk                                     as settlement_impact_fk,
           sbt.pcss_type_fk                                             as pcss_type_fk,
           sbt.participant_profile_fk                                   as participant_profile_fk,
           sbt.client_account_fk                                        as client_account_fk,
           sbt.payment_adv_bus_trans_fk                                 as payment_adv_bus_trans_fk,
           sbt.payment_bus_trans_fk                                     as payment_bus_trans_fk,
           sbt.application_user_name                                    as application_user_name,
           bt.application_update_timestamp                              as p_timestamp,
           sbt.application_update_timestamp                             as c_timestamp,
           sbt.audit_creation_user                                      as audit_creation_user,
           sbt.audit_creation_date                                      as audit_creation_date,
           sbt.audit_last_update_user                                   as audit_last_update_user,
           sbt.audit_last_update_date                                   as audit_last_update_date,
           i.instruction_source_fk                                      as instruction_source_fk,
           i.instruction_service_fk                                     as instruction_service_fk,
           coalesce(cast(bt.confirmation_ind as string), '0')           as confirmation_ind,
           coalesce(cast(bt.override_ind as string), '0')               as override_ind,
           coalesce(cast(bt.status_override_ind as string), '0')        as status_override_ind,
           coalesce(cast(bt.was_in_repair_ind as string), '0')          as was_in_repair_ind,
           coalesce(cast(pbt.reserve_ind as string), '0')               as reserve_ind,
           coalesce(cast(pbt.sys_generated_payment_ind as string), '0') as sys_generated_payment_ind,
           coalesce(cast(i.manual_interventation_ind as string), '0')   as manual_interventation_ind
    from   
        raw_db.habs_business_transaction bt join raw_db.habs_settlement_bus_transaction sbt 
            on bt.business_trans_pk = sbt.business_trans_pk
        left join raw_db.habs_payment_bus_transaction pbt 
            on sbt.payment_bus_trans_fk = pbt.business_trans_pk
        left join raw_db.habs_payment_advice_bus_transaction pabt 
            on sbt.payment_adv_bus_trans_fk = pabt.business_trans_pk
        join raw_db.habs_client c 
            on c.client_pk = bt.client_fk
        left join raw_db.habs_instruction i 
            on bt.business_trans_pk = i.business_trans_fk
        join raw_db.corporate_code_table instructionsource
            on instructionsource.code_pk = i.instruction_source_fk
        join raw_db.corporate_code_table instructionservice 
            on instructionservice.code_pk = i.instruction_service_fk
    where
        bt.business_trans_status_fk in (420, 423)
        and bt.business_value_date > timestamp('{last_process_ts}')
),

cte_instr_service as (
    select 
        case when bo_instruction_service_skey is null or bo_instruction_service_skey = 0
        then -1 else bo_instruction_service_skey end    as bo_instruction_service_skey, 
        cast(instruction_srvc_bid as decimal(18,0))     as instruction_srvc_bid
    from  
        curated_db.tbl_bo_instruction_service_dim
    where
        instruction_srvc_bid is not null 
        and bo_instruction_service_skey > 0
),

cte_pcss as (
    select 
        case when bo_pcss_type_skey is null or 
            bo_pcss_type_skey = 0 
        then -1 else bo_pcss_type_skey  end     as bo_pcss_type_skey, 
        cast(pcss_type_bid as decimal(18,0))    as pcss_type_bid
    from 
        curated_db.tbl_bo_pcss_type_dim
    where
        pcss_type_bid is not null
        and bo_pcss_type_skey > 0
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

cte_trans_service as (
    select 
        case 
            when bo_bus_trans_service_skey is null or bo_bus_trans_service_skey = 0
            then -1 else bo_bus_trans_service_skey end  as bo_bus_trans_service_skey,
            bus_trans_service_nm                        as bus_trans_service_nm
    from
        curated_db.tbl_bo_bus_trans_service_dim
    where  bus_trans_service_nm is not null    
),

cte_partic_profile as (
    select 
        case 
            when bo_participant_profile_skey is null 
                or bo_participant_profile_skey = 0
            then -1 else bo_participant_profile_skey end    as bo_participant_profile_skey,
        cast(participant_profile_bid as decimal(18,0))      as participant_profile_bid
    from   
        curated_db.tbl_bo_participant_profile_dim
    where
        participant_profile_bid is not null
        and bo_participant_profile_skey > 0
),

cte_settlement_impact as (
    select 
        case when bo_settlement_impact_skey is null or bo_settlement_impact_skey = 0
         then -1 else bo_settlement_impact_skey end             as bo_settlement_impact_skey,
        cast(settlement_impact_bid as decimal(18,0))            as settlement_impact_bid
    from   
       curated_db.tbl_bo_settlement_impact_dim
    where 
       bo_settlement_impact_skey > 0
       and settlement_impact_bid is not null       
),

cte_instruction_source as (
    select 
        case when bo_instruction_source_skey is null 
            or bo_instruction_source_skey = 0
        then -1 else bo_instruction_source_skey end     as bo_instruction_source_skey,
        cast(instruction_source_bid as decimal(18,0))   as instruction_source_bid
    from   
        curated_db.tbl_bo_instruction_source_dim
    where  instruction_source_bid is not null
    and    bo_instruction_source_skey > 0
),

cte_account as (
    select 
        case 
            when bo_account_skey is null 
            or bo_account_skey = 0 
            then -1 else bo_account_skey end as bo_client_account_skey, 
            rk_account_pk
    from   
        curated_db.tbl_bo_account_dim
    where  
        bo_account_skey > 0
        and rk_account_pk is not null
),

cte_settlement_bus_trans_ind as (
    select 
        case 
            when bo_settlement_bus_trans_ind_skey is null or 
                 bo_settlement_bus_trans_ind_skey = 0
            then -1 else bo_settlement_bus_trans_ind_skey end as bo_settlement_bus_trans_ind_skey,           
        concat(cast(confirmation_ind as string), cast(override_ind as string),
            cast(status_override_ind as string), cast(was_in_repair_ind as string),
            cast(reserve_ind as string), cast(sys_generated_payment_ind as string),
            cast(manual_intervention_ind as string))    as lkp_set_ind
    from  
        curated_db.tbl_bo_settlement_bus_trans_ind_dim
    where
        bo_settlement_bus_trans_ind_skey > 0
)

INSERT INTO curated_db.tbl_bo_settlement_bus_trans_fact
  ( 
        business_value_dt,
        client_gle_skey,
        bo_bus_trans_service_skey,
        bo_settlement_impact_skey,
        bo_settlement_bus_trans_ind_skey,
        bo_pcss_type_skey,
        bo_participant_profile_skey,
        bo_client_account_skey,
        bo_instruction_source_skey,
        bo_instruction_service_skey,
        rk_habs_business_trans_pk,
        rk_habs_payment_adv_fk,
        rk_habs_payment_fk,
        src_reference_num,
        instruction_end_time_ts,
        authorizing_user_nm,
        business_value_amt,
        application_user_nm,
        application_update_ts,
        audit_creation_user_nm,
        audit_creation_date_ts,
        audit_last_update_user_nm,
        audit_last_update_date_ts,
        md_create_ts,
        md_last_update_ts,
        md_workflow_execution_skey,
        md_data_load_method_skey,
        md_system_skey,
        md_chksum,
        audit_load_id,
        audit_create_ts,
        audit_last_update_ts
    )

SELECT   
    s.business_value_date                   as business_value_dt,
    gle.client_gle_skey                     as client_gle_skey,
    trn.bo_bus_trans_service_skey           as bo_bus_trans_service_skey,
    si.bo_settlement_impact_skey            as bo_settlement_impact_skey,
    sind.bo_settlement_bus_trans_ind_skey   as bo_settlement_bus_trans_ind_skey,
    pcss.bo_pcss_type_skey                  as bo_pcss_type_skey,
    pp.bo_participant_profile_skey          as bo_participant_profile_skey,
    acc.bo_client_account_skey              as bo_client_account_skey,
    isrc.BO_INSTRUCTION_SOURCE_SKEY         as bo_instruction_source_skey,
    isvc.bo_instruction_service_skey        as bo_instruction_service_skey,
    s.rk_business_trans_pk                  as rk_habs_business_trans_pk,
    s.payment_adv_bus_trans_fk              as rk_habs_payment_adv_fk,
    s.payment_bus_trans_fk                  as rk_habs_payment_fk,
    s.src_reference_num                     as src_reference_num,
    s.c_timestamp                           as instruction_end_time_ts,
    s.authorizing_user_name                 as authorizing_user_nm,
    s.business_value_amt                    as business_value_amt,
    s.application_user_name                 as application_user_nm,
    coalesce(s.c_timestamp, s.p_timestamp)  as application_update_ts,
    s.audit_creation_user                   as audit_creation_user_nm,
    s.audit_creation_date                   as audit_creation_date_ts,
    s.audit_last_update_user                as audit_last_update_user_nm,
    s.audit_last_update_date                as audit_last_update_date_ts,
    null                                    as md_create_ts,
    null                                    as md_last_update_ts,
    null                                    as md_workflow_execution_skey,
    1                                       as md_data_load_method_skey,
    5                                       as md_system_skey,    
    md5(
        concat_ws('|',
            cast(s.rk_business_trans_pk as string), s.client_id, s.src_reference_num,
            date_format(s.business_value_date,'yyyyMMdd'), cast(s.business_value_amt as string),
            s.bus_trans_service_name, cast(s.settlement_impact_fk as string),
            cast(s.pcss_type_fk as string), cast(s.participant_profile_fk as string),
            cast(s.client_account_fk as string), cast(s.payment_adv_bus_trans_fk as string),
            cast(s.payment_bus_trans_fk as string),
            date_format(s.p_timestamp,'yyyyMMddHHmmss'), date_format(s.c_timestamp,'yyyyMMddHHmmss')
        )
    )                                        as md_chksum,
    {job_run_id}                             as audit_load_id,
    current_timestamp()                      as audit_create_ts,
    current_timestamp()                      as audit_last_update_ts
from 
    cte_settlement_bus_trans_data s left join cte_global_legal_entity gle
        on gle.client_id = s.client_id
    left join cte_trans_service trn 
        on trn.bus_trans_service_nm = s.bus_trans_service_name
    left join cte_settlement_impact si  
        on si.settlement_impact_bid = s.settlement_impact_fk
    left join cte_pcss pcss 
        on pcss.pcss_type_bid = s.pcss_type_fk
    left join cte_partic_profile pp 
        on pp.participant_profile_bid  = s.participant_profile_fk
    left join cte_account acc 
        on acc.rk_account_pk = s.client_account_fk
    left join cte_instruction_source isrc 
        on isrc.INSTRUCTION_SOURCE_BID = s.instruction_source_fk
    left join cte_instr_service isvc 
        on isvc.instruction_srvc_bid = s.instruction_service_fk
    left join cte_settlement_bus_trans_ind sind
       on sind.lkp_set_ind = concat(
              s.confirmation_ind, s.override_ind, s.status_override_ind, s.was_in_repair_ind,
              s.reserve_ind, s.sys_generated_payment_ind, s.manual_interventation_ind)

"""