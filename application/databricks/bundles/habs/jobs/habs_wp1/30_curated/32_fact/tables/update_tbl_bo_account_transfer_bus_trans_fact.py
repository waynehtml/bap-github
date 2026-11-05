catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_ACCOUNT_TRANSFER_BUS_TRANS_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
select coalesce(max(application_update_ts), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_account_transfer_bus_trans_fact
"""

row = spark.sql(sql).first()
last_process_ts = row["max_date"]

sql = f"""

with source_account_transfer as (
    select
        bt.business_trans_pk                        as rk_habs_business_trans_pk,
        atb.account_transfer_bus_trans_fk           as rk_habs_contra_business_trans_pk,
        bt.business_trans_type_fk                   as business_trans_type_fk,
        bt.business_trans_status_fk                 as business_trans_status_fk,
        coalesce(bt.client_fk, -1)                  as client_fk,
        coalesce(bta.client_fk, -1)                 as contra_client_fk,
        bt.src_reference_num                        as src_reference_num,
        bt.business_value_date                      as business_value_dt,
        bt.business_value_amt                       as business_value_amt,
        coalesce(bt.was_in_repair_ind, '-1')        as was_in_repair_ind,
        coalesce(bta.was_in_repair_ind, '-1')       as contra_was_in_repair_ind,
        bt.authorizing_user_name                    as authorizing_user_name,
        atb.application_user_name                   as application_user_name,
        bt.application_update_timestamp             as p_timestamp,
        atb.application_update_timestamp            as c_timestamp,
        coalesce(atb.application_update_timestamp, bt.application_update_timestamp) as application_update_ts,
        atb.audit_creation_user                     as audit_creation_user,
        atb.audit_creation_date                     as audit_creation_date,
        atb.audit_last_update_user                  as audit_last_update_user,
        atb.audit_last_update_date                  as audit_last_update_date,
        i.instruction_source_fk                     as instruction_source_fk,
        i.instruction_service_fk                    as instruction_service_fk,
        atb.narrative_desc                          as narrative_desc,
        atb.account_impact_fk                       as account_impact_fk,
        atb.account_transfer_type_fk                as account_transfer_type_fk,
        atb.account_transfer_context_fk             as account_transfer_context_fk,
        atb.client_account_fk                       as client_account_fk,
        catb.client_account_fk                      as contra_client_account_fk,
        coalesce(i.manual_interventation_ind, '-1') as manual_intervention_ind,
        bta_attr.key_value                          as related_reference
    from
        raw_db.habs_account_transfer_bus_trans atb inner join raw_db.habs_business_transaction bt
            on atb.business_trans_pk = bt.business_trans_pk
        left join raw_db.habs_business_transaction bta
            on atb.account_transfer_bus_trans_fk = bta.business_trans_pk
        left join raw_db.habs_account_transfer_bus_trans catb
            on catb.business_trans_pk = atb.account_transfer_bus_trans_fk
        left join raw_db.habs_instruction i
            on i.business_trans_fk = atb.business_trans_pk
        left join raw_db.habs_business_trans_attr bta_attr
            on bta_attr.business_trans_fk = atb.business_trans_pk
            and bta_attr.key_name = 'RelatedReferenceNumber'
    where bt.business_trans_status_fk in (420, 423)
      and i.instruction_service_fk in (358, 359)
      and atb.account_transfer_bus_trans_fk is not null
    and atb.application_update_timestamp > timestamp '{last_process_ts}'
),

dim_business_transaction_type as (
    select
        ct.code_pk                  as business_trans_type_bid,
        case
        when btt.bo_bus_trans_type_skey is null
          or btt.bo_bus_trans_type_skey = 0
            then -1
        else btt.bo_bus_trans_type_skey
        end                         as bo_bus_trans_type_skey
    from
        raw_db.corporate_code_table ct inner join curated_db.tbl_bo_bus_trans_type_dim btt
        on trim(ct.code_constant_id) = trim(btt.bus_trans_type_bid)
),

dim_business_transaction_status as (
    select
        ct.code_pk                      as business_trans_status_bid,
        case when bts.bo_bus_trans_status_skey is null or bts.bo_bus_trans_status_skey = 0
          then -1
          else bts.bo_bus_trans_status_skey
          end                           as bo_bus_trans_status_skey
    from
        raw_db.corporate_code_table ct inner join curated_db.tbl_bo_bus_trans_status_dim bts
        on trim(ct.code_constant_id) = trim(bts.bus_trans_status_bid)
),

dim_global_legal_entity as (
    select
        gle.rk_habs_client_pk           as rk_habs_client_pk,
        case
    when gle.global_legal_entity_skey is null or gle.global_legal_entity_skey = 0
    then -1
    else gle.global_legal_entity_skey end as global_legal_entity_skey
    from view_db.vwu_global_legal_entity_dim gle
    where gle.global_legal_entity_skey > -1
      and gle.rk_habs_client_pk is not null
),

dim_account_impact_type as (
    select
        account_impact_type_bid         as account_impact_type_bid,
        case
            when impact.bo_account_impact_type_skey is null or impact.bo_account_impact_type_skey = 0
            then -1
            else impact.bo_account_impact_type_skey
            end                         as bo_account_impact_type_skey
    from
        curated_db.tbl_bo_account_impact_type_dim impact
    where
        bo_account_impact_type_skey > -1
        and account_impact_type_bid is not null
),

dim_account_transfer_context as (
    select
        transfer_context.account_transfer_context_bid           as account_transfer_context_bid,
         case
            when transfer_context.bo_account_transfer_context_skey is null or transfer_context.bo_account_transfer_context_skey = 0
            then -1
            else transfer_context.bo_account_transfer_context_skey
            end                                                 as bo_account_transfer_context_skey
    from
        curated_db.tbl_bo_account_transfer_context_dim transfer_context
    where
        transfer_context.bo_account_transfer_context_skey > -1
        and transfer_context.account_transfer_context_bid is not null
),

dim_account_transfer_type as (
    select
        account_transfer_type_bid           as account_transfer_type_bid,
        case
    when transfer_type.bo_account_transfer_type_skey is null or transfer_type.bo_account_transfer_type_skey = 0
    then -1
    else transfer_type.bo_account_transfer_type_skey
    end                                     as bo_account_transfer_type_skey
    from
        curated_db.tbl_bo_account_transfer_type_dim transfer_type
    where
        transfer_type.bo_account_transfer_type_skey > -1
        and transfer_type.account_transfer_type_bid is not null
),

dim_account as (
    select
        account.rk_account_pk       as rk_account_pk,
        case
            when account.bo_account_skey is null or account.bo_account_skey = 0
            then -1
            else account.bo_account_skey
            end                     as bo_account_skey
    from
        curated_db.tbl_bo_account_dim account
    where
        account.bo_account_skey > -1
        and account.rk_account_pk is not null
),

dim_instruction_source as (
    select
        instruction_source.instruction_source_bid       as instruction_source_bid,
        case
            when instruction_source.bo_instruction_source_skey is null or instruction_source.bo_instruction_source_skey = 0
            then -1
            else instruction_source.bo_instruction_source_skey
            end                                         as bo_instruction_source_skey
    from
        curated_db.tbl_bo_instruction_source_dim instruction_source
    where
        instruction_source.bo_instruction_source_skey > -1
        and instruction_source.instruction_source_bid is not null
),

dim_instruction_service as (
    select
        instruction_srvc_bid            as instruction_srvc_bid,
        case
        when instruction_service.bo_instruction_service_skey is null or instruction_service.bo_instruction_service_skey = 0
        then -1
        else instruction_service.bo_instruction_service_skey
        end                             as bo_instruction_service_skey
    from
        curated_db.tbl_bo_instruction_service_dim instruction_service
    where
        bo_instruction_service_skey > -1
        and instruction_srvc_bid is not null
),

dim_account_transfer_indicator as (
    select
        cast(ind.contra_was_in_repair_ind as string)        as contra_was_in_repair_ind,
        cast(ind.manual_intervention_ind as string)         as manual_intervention_ind,
        cast(ind.was_in_repair_ind as string)               as was_in_repair_ind,
        case
            when ind.bo_account_bus_trans_ind_skey is null or ind.bo_account_bus_trans_ind_skey = 0
            then -1
            else ind.bo_account_bus_trans_ind_skey
            end                                             as bo_account_bus_trans_ind_skey
    from
        curated_db.tbl_bo_account_transfer_bus_trans_ind_dim ind
    )

insert into curated_db.tbl_bo_account_transfer_bus_trans_fact (
    business_value_dt,
    client_gle_skey,
    contra_client_gle_skey,
    bo_bus_trans_type_skey,
    bo_bus_trans_status_skey,
    bo_account_bus_trans_ind_skey,
    bo_account_transfer_type_skey,
    bo_account_transfer_context_skey,
    bo_account_skey,
    bo_contra_account_skey,
    bo_account_impact_type_skey,
    bo_instruction_service_skey,
    bo_instruction_source_skey,
    instruction_end_time,
    rk_habs_business_trans_pk,
    rk_habs_contra_business_trans_pk,
    src_reference_num,
    business_value_amt,
    narrative_desc,
    related_reference,
    authorizing_user_nm,
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
select
    src.BUSINESS_VALUE_DT                               as business_value_dt,
    gle.global_legal_entity_skey                        as client_gle_skey,
    contra_gle.global_legal_entity_skey                 as contra_client_gle_skey,
    btt.bo_bus_trans_type_skey                          as bo_bus_trans_type_skey,
    bts.bo_bus_trans_status_skey                        as bo_bus_trans_status_skey,
    ind.bo_account_bus_trans_ind_skey                   as bo_account_bus_trans_ind_skey,
    transfer_type.bo_account_transfer_type_skey         as bo_account_transfer_type_skey,
    transfer_context.bo_account_transfer_context_skey   as bo_account_transfer_context_skey,
    account.bo_account_skey                             as bo_account_skey,
    contra_account.bo_account_skey                      as bo_contra_account_skey,
    impact.bo_account_impact_type_skey                  as bo_account_impact_type_skey,
    instruction_service.bo_instruction_service_skey     as bo_instruction_service_skey,
    instruction_source.bo_instruction_source_skey       as bo_instruction_source_skey,
    src.C_TIMESTAMP                                     as instruction_end_time,
    src.RK_HABS_BUSINESS_TRANS_PK                       as rk_habs_business_trans_pk,
    src.RK_HABS_CONTRA_BUSINESS_TRANS_PK                as rk_habs_contra_business_trans_pk,
    src.SRC_REFERENCE_NUM                               as src_reference_num,
    src.BUSINESS_VALUE_AMT                              as business_value_amt,
    src.NARRATIVE_DESC                                  as narrative_desc,
    src.RELATED_REFERENCE                               as related_reference,
    src.AUTHORIZING_USER_NAME                           as authorizing_user_nm,
    src.APPLICATION_USER_NAME                           as application_user_nm,
    src.APPLICATION_UPDATE_TS                           as application_update_ts,
    src.AUDIT_CREATION_USER                             as audit_creation_user_nm,
    src.AUDIT_CREATION_DATE                             as audit_creation_date_ts,
    src.AUDIT_LAST_UPDATE_USER                          as audit_last_update_user_nm,
    src.AUDIT_LAST_UPDATE_DATE                          as audit_last_update_date_ts,
    null                                                as md_create_ts,
    null                                                as md_last_update_ts,
    null                                                as md_workflow_execution_skey,
    null                                                as md_data_load_method_skey,
    null                                                as md_system_skey,
    null                                                as md_chksum,
    {job_run_id}                                        as audit_load_id,
    current_timestamp()                                 as audit_create_ts,
    current_timestamp()                                 as audit_last_update_ts
from
    source_account_transfer src
    left join dim_business_transaction_type btt
        on src.BUSINESS_TRANS_TYPE_FK = btt.business_trans_type_bid
    left join dim_business_transaction_status bts
        on src.BUSINESS_TRANS_STATUS_FK = bts.business_trans_status_bid
    left join dim_global_legal_entity gle
        on src.CLIENT_FK = gle.rk_habs_client_pk
    left join dim_global_legal_entity contra_gle
        on src.CONTRA_CLIENT_FK = contra_gle.rk_habs_client_pk
    left join dim_account_impact_type impact
        on src.ACCOUNT_IMPACT_FK = impact.account_impact_type_bid
    left join dim_account_transfer_context transfer_context
        on src.ACCOUNT_TRANSFER_CONTEXT_FK = transfer_context.account_transfer_context_bid
    left join dim_account_transfer_type transfer_type
        on src.ACCOUNT_TRANSFER_TYPE_FK = transfer_type.account_transfer_type_bid
    left join dim_account account
        on src.CLIENT_ACCOUNT_FK = account.rk_account_pk
    left join dim_account contra_account
        on src.CONTRA_CLIENT_ACCOUNT_FK = contra_account.rk_account_pk
    left join dim_instruction_source instruction_source
        on src.INSTRUCTION_SOURCE_FK = instruction_source.instruction_source_bid
    left join dim_instruction_service instruction_service
        on src.INSTRUCTION_SERVICE_FK = instruction_service.instruction_srvc_bid
    left join dim_account_transfer_indicator ind
        on src.CONTRA_WAS_IN_REPAIR_IND = ind.contra_was_in_repair_ind
        and src.MANUAL_INTERVENTION_IND = ind.manual_intervention_ind
        and src.WAS_IN_REPAIR_IND = ind.was_in_repair_ind

"""

logger.info("Executing INSERT for curated_db.tbl_bo_account_transfer_bus_trans_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_account_transfer_bus_trans_fact build")
