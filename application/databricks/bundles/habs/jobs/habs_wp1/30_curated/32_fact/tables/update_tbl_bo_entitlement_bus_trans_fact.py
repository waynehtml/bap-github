catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_ENTITLEMENT_BUS_TRANS_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
select coalesce(max(application_update_ts), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_entitlement_bus_trans_fact
"""

row = spark.sql(sql).first()
last_process_ts = row["max_date"]

sql = f"""

with source_entitlement as (
    select
        bt.business_trans_pk                    as rk_habs_business_trans_pk,
        bt.business_trans_type_fk               as business_trans_type_fk,
        bt.business_trans_status_fk             as business_trans_status_fk,
        bt.client_fk                            as client_fk,
        bt.src_reference_num                    as src_reference_num,
        bt.business_value_date                  as business_value_dt,
        bt.business_value_amt                   as business_value_amt,
        bt.authorizing_user_name                as authorizing_user_name,
        cast(bt.confirmation_ind as string)     as confirmation_ind,
        cast(bt.override_ind as string)         as override_ind,
        bt.bus_trans_service_name               as payment_direction,
        cast(bt.status_override_ind as string)  as status_override_ind,
        cast(bt.was_in_repair_ind as string)    as was_in_repair_ind,
        bt.application_user_name                as application_user_name,
        trim(ebt.isin)                          as isin,
        ebt.security_desc                       as security_desc,
        ebt.out_payment_bus_trans_fk            as out_payment_bus_trans_fk,
        ebt.in_payment_bus_trans_fk             as in_payment_bus_trans_fk,
        ebt.cuid                                as cuid,
        cast(ebt.entitlement_type_fk as string) as entitlement_type_fk,
        ebt.entitlement_paymenttype_fk          as entitlement_paymenttype_fk,
        ebt.application_update_timestamp        as application_update_timestamp,
        ebt.audit_creation_user                 as audit_creation_user,
        ebt.audit_creation_date                 as audit_creation_date,
        ebt.audit_last_update_user              as audit_last_update_user,
        ebt.audit_last_update_date              as audit_last_update_date,
        i.instruction_source_fk                 as instruction_source_fk,
        i.instruction_service_fk                as instruction_service_fk,
        cast(i.manual_interventation_ind as string)
                                                as manual_intervention_ind,
        ebt.safekeeping_account_fk              as safekeeping_account_fk,
        ebt.cash_account_fk                     as cash_account_fk,
        max(ih.instruction_activity_date)       as instruction_end_time
    from
        raw_db.habs_business_transaction bt join raw_db.habs_entitlement_bus_transaction ebt
            on bt.business_trans_pk = ebt.business_trans_pk
        join raw_db.habs_client c on c.client_pk = bt.client_fk
          left join raw_db.habs_instruction i on bt.business_trans_pk = i.business_trans_fk
        left join raw_db.corporate_code_table instructionsource on instructionsource.code_pk = i.instruction_source_fk
        join raw_db.corporate_code_table instructionservice on instructionservice.code_pk = i.instruction_service_fk
        left join raw_db.habs_instruction_history ih on ih.instruction_fk = i.instruction_pk
        left join raw_db.corporate_code_table btt on btt.code_pk = bt.business_trans_type_fk
        left join raw_db.corporate_code_table ett on ett.code_pk = ebt.entitlement_type_fk
        left join raw_db.corporate_code_table bst on bst.code_pk = bt.business_trans_status_fk
        left join raw_db.corporate_code_table ept on ept.code_pk = ebt.entitlement_paymenttype_fk
    where
        bst.code_constant_id = 'Process'
        and ebt.application_update_timestamp > timestamp('{last_process_ts}')
    group by
        bt.business_trans_pk,
        bt.business_trans_type_fk,
        bt.business_trans_status_fk,
        bt.client_fk,
        bt.src_reference_num,
        bt.business_value_date,
        bt.business_value_amt,
        bt.authorizing_user_name,
        bt.confirmation_ind,
        bt.override_ind,
        bt.bus_trans_service_name,
        bt.status_override_ind,
        bt.was_in_repair_ind,
        bt.application_user_name,
        ebt.isin,
        ebt.security_desc,
        ebt.out_payment_bus_trans_fk,
        ebt.in_payment_bus_trans_fk,
        ebt.cuid,
        ebt.entitlement_type_fk,
        ebt.entitlement_paymenttype_fk,
        ebt.application_update_timestamp,
        ebt.audit_creation_user,
        ebt.audit_creation_date,
        ebt.audit_last_update_user,
        ebt.audit_last_update_date,
        i.instruction_source_fk,
        i.instruction_service_fk,
        i.manual_interventation_ind,
        ebt.safekeeping_account_fk,
        ebt.cash_account_fk
),


dim_global_legal_entity as (
    select
        global_legal_entity_skey,
        rk_habs_client_pk,
        client_id
    from
        view_db.vwu_global_legal_entity_dim
    where
        global_legal_entity_skey > 0
),

dim_financial_instrument as (
    select
        trim(isin_cd)               as isin,
        financial_instrument_skey   as financial_instrument_skey
    from
        view_db.vwu_financial_instrument_dim
    where
        financial_instrument_skey > 0
        and trim(isin_cd) <> ''
),

dim_entitlement_type as (
    select
        entitlement_type.bo_entitlement_type_skey    as bo_entitlement_type_skey,
        entitlement_type.entitlement_type_bid        as entitlement_type_bid
    from
        curated_db.tbl_bo_entitlement_type_dim entitlement_type
    where
        entitlement_type.bo_entitlement_type_skey > 0
),

dim_entitlement_payment_type as (
    select
        bo_entitlement_payment_type_skey,
        entitlement_payment_type_bid
    from
        curated_db.tbl_bo_entitlement_payment_type_dim
    where
        bo_entitlement_payment_type_skey > 0
),

dim_account as (
    select
        bo_account_skey,
        rk_account_pk
    from
        curated_db.tbl_bo_account_dim
    where
        bo_account_skey > 0
),

dim_instruction_service as (
    select
        bo_instruction_service_skey,
        cast(instruction_srvc_bid as decimal(21, 0))
            as instruction_service_bid
    from
        curated_db.tbl_bo_instruction_service_dim
    where
        bo_instruction_service_skey > 0
),

dim_instruction_source as (
    select
        instruction_source_bid,
        bo_instruction_source_skey
    from
        curated_db.tbl_bo_instruction_source_dim
    where
        md_current_ind = 1
        and bo_instruction_source_skey > 0
),

dim_entitlement_indicator as (
    select
        bo_entitlement_ind_skey,
        concat(
            cast(confirmation_ind as string),
            cast(override_ind as string),
            cast(status_override_ind as string),
            cast(was_in_repair_ind as string),
            cast(manual_intervention_ind as string)
        ) as entitlement_indicator
    from
        curated_db.tbl_bo_entitlement_ind_dim
    where
        bo_entitlement_ind_skey > 0
),

final_entitlement as (
    select
        src.BUSINESS_VALUE_DT,
        case
            when gle.global_legal_entity_skey is null
                or gle.global_legal_entity_skey = 0
            then -1
            else gle.global_legal_entity_skey
        end                                 as client_gle_skey,
        case
            when entitlement_type.bo_entitlement_type_skey is null
                or entitlement_type.bo_entitlement_type_skey = 0
            then -1
            else entitlement_type.bo_entitlement_type_skey
        end                                 as bo_entitlement_type_skey,
        case
            when instrument.financial_instrument_skey is null
                or instrument.financial_instrument_skey = 0
            then -1
            else instrument.financial_instrument_skey
        end                                 as financial_instrument_skey,
        case
            when safekeeping_account.bo_account_skey is null
                or safekeeping_account.bo_account_skey = 0
            then -1
            else safekeeping_account.bo_account_skey
        end                                 as safekeeping_account_skey,
        case
            when cash_account.bo_account_skey is null
                or cash_account.bo_account_skey = 0
            then -1
            else cash_account.bo_account_skey
        end                                 as cash_account_skey,
        case
            when payment_type.bo_entitlement_payment_type_skey is null
                or payment_type.bo_entitlement_payment_type_skey = 0
            then -1
            else payment_type.bo_entitlement_payment_type_skey
        end                                 as bo_entitlement_payment_type_skey,
        case
            when entitlement_ind.bo_entitlement_ind_skey is null
                or entitlement_ind.bo_entitlement_ind_skey = 0
            then -1
            else entitlement_ind.bo_entitlement_ind_skey
        end                                 as bo_entitlement_ind_skey,
        case
            when instruction_service.bo_instruction_service_skey is null
                or instruction_service.bo_instruction_service_skey = 0
            then -1
            else instruction_service.bo_instruction_service_skey
        end                                 as bo_instruction_service_skey,
        case
            when instruction_source.bo_instruction_source_skey is null
                or instruction_source.bo_instruction_source_skey = 0
            then -1
            else instruction_source.bo_instruction_source_skey
        end                                 as bo_instruction_source_skey,
        src.RK_HABS_BUSINESS_TRANS_PK       as rk_habs_business_trans_pk,
        src.OUT_PAYMENT_BUS_TRANS_FK        as rk_habs_out_payment_fk,
        src.IN_PAYMENT_BUS_TRANS_FK         as rk_habs_in_payment_fk,
        src.CUID                            as cuid,
        src.SRC_REFERENCE_NUM               as src_reference_num,
        src.BUSINESS_VALUE_AMT              as business_value_amt,
        src.INSTRUCTION_END_TIME            as instruction_end_time,
        src.APPLICATION_USER_NAME           as application_user_nm,
        src.APPLICATION_UPDATE_TIMESTAMP    as application_update_ts,
        src.AUDIT_CREATION_USER             as audit_creation_user_nm,
        src.AUDIT_CREATION_DATE             as audit_creation_date_ts,
        src.AUDIT_LAST_UPDATE_USER          as audit_last_update_user_nm,
        src.AUDIT_LAST_UPDATE_DATE          as audit_last_update_date_ts,
        null                                as md_create_ts,
        null                                as md_last_update_ts,
        null                                as workflow_execution_skey,
        null                                as md_chksum,
        {job_run_id}                        as audit_load_id,
        current_timestamp()                 as audit_create_ts,
        current_timestamp()                 as audit_last_update_ts
    from
        source_entitlement src left join dim_global_legal_entity gle
            on src.CLIENT_FK = gle.rk_habs_client_pk
        left join dim_financial_instrument instrument
            on src.ISIN = instrument.isin
        left join dim_entitlement_type entitlement_type
            on cast(src.ENTITLEMENT_TYPE_FK as bigint) = cast(entitlement_type.entitlement_type_bid as bigint)
        left join dim_entitlement_payment_type payment_type
            on cast(src.ENTITLEMENT_PAYMENTTYPE_FK as bigint) = cast(payment_type.entitlement_payment_type_bid as bigint)
        left join dim_account safekeeping_account
            on src.SAFEKEEPING_ACCOUNT_FK = safekeeping_account.rk_account_pk
        left join dim_account cash_account
            on src.CASH_ACCOUNT_FK = cash_account.rk_account_pk
        left join dim_instruction_service instruction_service
            on src.INSTRUCTION_SERVICE_FK = instruction_service.instruction_service_bid
        left join dim_instruction_source instruction_source
            on cast(src.INSTRUCTION_SOURCE_FK as string) = cast(instruction_source.instruction_source_bid as string)
        left join dim_entitlement_indicator entitlement_ind
            on concat(
                coalesce(src.CONFIRMATION_IND, ''),
                coalesce(src.OVERRIDE_IND, ''),
                coalesce(src.STATUS_OVERRIDE_IND, ''),
                coalesce(src.WAS_IN_REPAIR_IND, ''),
                coalesce(src.MANUAL_INTERVENTION_IND, '')
            ) = entitlement_ind.entitlement_indicator
)

insert into curated_db.tbl_bo_entitlement_bus_trans_fact
(
    business_value_dt,                client_gle_skey,            bo_entitlement_type_skey,
    financial_instrument_skey,        safekeeping_account_skey,   cash_account_skey,
    bo_entitlement_payment_type_skey, bo_entitlement_ind_skey,    bo_instruction_service_skey,
    bo_instruction_source_skey,       rk_habs_business_trans_pk,  rk_habs_out_payment_fk,
    rk_habs_in_payment_fk,            cuid,                       src_reference_num,
    business_value_amt,               instruction_end_time,       application_user_nm,
    application_update_ts,            audit_creation_user_nm,     audit_creation_date_ts,
    audit_last_update_user_nm,        audit_last_update_date_ts,  workflow_execution_skey,
    md_create_ts,                     md_last_update_ts,          md_chksum,
    audit_load_id,                    audit_create_ts,            audit_last_update_ts
)
select
    business_value_dt,                client_gle_skey,            bo_entitlement_type_skey,
    financial_instrument_skey,        safekeeping_account_skey,   cash_account_skey,
    bo_entitlement_payment_type_skey, bo_entitlement_ind_skey,    bo_instruction_service_skey,
    bo_instruction_source_skey,       rk_habs_business_trans_pk,  rk_habs_out_payment_fk,
    rk_habs_in_payment_fk,            cuid,                       src_reference_num,
    business_value_amt,               instruction_end_time,       application_user_nm,
    application_update_ts,            audit_creation_user_nm,     audit_creation_date_ts,
    audit_last_update_user_nm,        audit_last_update_date_ts,  workflow_execution_skey,
    md_create_ts,                     md_last_update_ts,          md_chksum,
    audit_load_id,                    audit_create_ts,            audit_last_update_ts
from
    final_entitlement
"""

logger.info("Executing INSERT for curated_db.tbl_bo_entitlement_bus_trans_fact")
logger.info(sql)
spark.sql(sql)
logger.info("Completed tbl_bo_entitlement_bus_trans_fact build")