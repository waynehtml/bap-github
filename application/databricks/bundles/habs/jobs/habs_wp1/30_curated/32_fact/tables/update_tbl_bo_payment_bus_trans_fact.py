catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_PAYMENT_BUS_TRANS_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(business_value_dt), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_payment_bus_trans_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""
with cte_source_data as
(
    select distinct
        bt.business_trans_pk                                            as rk_business_trans_pk,
        bt.business_trans_status_fk                                     as business_trans_status_fk,
        c.client_id                                                     as client_id,
        bt.src_reference_num                                            as src_reference_num,
        bt.business_value_date                                          as business_value_date,
        bt.business_value_amt                                           as business_value_amt,
        upper(trim(bt.bus_trans_service_name))                          as bus_trans_service_name,
        bt.authorizing_user_name                                        as authorizing_user_name,
        pbt.payment_type_fk                                             as payment_type_fk,
        pbt.tranche_fk                                                  as tranche_fk,
        pbt.pcss_type_fk                                                as pcss_type_fk,
        pbt.participant_profile_fk                                      as participant_profile_fk,
        upper(trim(pbt.pcss_participant_swiftbic_code))                 as pcss_participant_swiftbic_code,
        upper(trim(pbt.beneficiary_desc))                               as beneficiary_desc,
        pbt.client_account_fk                                           as client_account_fk,
        pbt.assoc_inpay_bus_trans_fk                                    as assoc_inpay_bus_trans_fk,
        pbt.application_user_name                                       as application_user_name,
        bt.application_update_timestamp                                 as p_timestamp,
        pbt.application_update_timestamp                                as c_timestamp,
        pbt.audit_creation_user                                         as audit_creation_user,
        pbt.audit_creation_date                                         as audit_creation_date,
        pbt.audit_last_update_user                                      as audit_last_update_user,
        pbt.audit_last_update_date                                      as audit_last_update_date,
        i.instruction_source_fk                                         as instruction_source_fk,
        i.instruction_service_fk                                        as instruction_service_fk,
        pbt.payment_adv_bus_trans_fk                                    as payment_adv_bus_trans_fk,
        upper(trim(pabtswift.swiftbic_code))                            as pay_adv_swiftbic_code,
        pabtswift.related_ref_num                                       as payment_adv_related_ref_num,
        pabt.business_value_amt                                         as payment_adv_amt,
        pabt.application_update_timestamp                               as payment_adv_creation_dt,
        coalesce(cast(bt.confirmation_ind as string), ' ')              as confirmation_ind,
        coalesce(cast(bt.override_ind as string), ' ')                  as override_ind,
        coalesce(cast(bt.status_override_ind as string), ' ')           as status_override_ind,
        coalesce(cast(bt.was_in_repair_ind as string), ' ')             as was_in_repair_ind,
        coalesce(cast(pbt.reserve_ind as string), ' ')                  as reserve_ind,
        coalesce(cast(pbt.sys_generated_payment_ind as string), ' ')    as sys_generated_payment_ind,
        coalesce(cast(i.manual_interventation_ind as string), ' ')      as manual_interventation_ind,
        pbt.settl_mechanism_fk
    from
        raw_db.habs_business_transaction bt
        inner join raw_db.habs_payment_bus_transaction pbt
            on bt.business_trans_pk = pbt.business_trans_pk
        inner join raw_db.habs_client c
            on c.client_pk = bt.client_fk
        left join raw_db.habs_instruction i
            on bt.business_trans_pk = i.business_trans_fk
        inner join raw_db.corporate_code_table instructionsource
            on instructionsource.code_pk = i.instruction_source_fk
        inner join raw_db.corporate_code_table instructionservice
            on instructionservice.code_pk = i.instruction_service_fk
        left join raw_db.habs_business_transaction pabt
            on pbt.payment_adv_bus_trans_fk = pabt.business_trans_pk
        left join raw_db.habs_payment_advice_bus_transaction pabtswift
            on pbt.payment_adv_bus_trans_fk = pabtswift.business_trans_pk
    where
        bt.business_trans_status_fk in (420, 423)
        and (
            instructionservice.code_constant_id like 'PaymentIn%'
            or instructionservice.code_constant_id like 'PaymentOut%'
        )
        and (
            pbt.application_update_timestamp > timestamp('{last_process_ts}')
        )
),

cte_fin_inst as
(
    select
        client_id                   as client_id, 
        global_legal_entity_skey    as financial_institution_skey  
    from 
        view_db.vwu_global_legal_entity_dim
),

cte_instr_src as
(
    select
        instruction_source_bid      as instruction_source_bid,
        bo_instruction_source_skey  as bo_instruction_source_skey
    from 
        curated_db.tbl_bo_instruction_source_dim
    where 
        bo_instruction_source_skey > 0
),

cte_instr_service as
(
    select
        instruction_srvc_bid,
        bo_instruction_service_skey
    from 
        curated_db.tbl_bo_instruction_service_dim
    where 
        bo_instruction_service_skey > 0
),

cte_part_profile as
(
    select
        participant_profile_bid         as participant_profile_bid,
        bo_participant_profile_skey     as bo_participant_profile_skey
    from 
        curated_db.tbl_bo_participant_profile_dim
    where 
       bo_participant_profile_skey > 0
),

cte_pcss_type as
(
    select
        pcss_type_bid       as pcss_type_bid,
        bo_pcss_type_skey   as bo_pcss_type_skey 
    from 
        curated_db.tbl_bo_pcss_type_dim
    where 
        bo_pcss_type_skey > 0
),

cte_trans_status as
(
    select
        a.code_pk                   as bo_bus_trans_status_bid,
        b.bo_bus_trans_status_skey  as bo_bus_trans_status_skey 
    from 
        raw_db.corporate_code_table a inner join curated_db.tbl_bo_bus_trans_status_dim b
            on a.code_constant_id = b.bus_trans_status_bid
),

cte_trans_service as
(
    select
        bo_bus_trans_service_skey                        as bo_bus_trans_service_skey,
        upper(trim(coalesce(bus_trans_service_nm, ' '))) as bus_trans_service_nm
    from 
        curated_db.tbl_bo_bus_trans_service_dim
),

cte_payment_type as
(
    select
        bo_payment_type_skey    as bo_payment_type_skey,
        b.code_pk               as payment_type_bid
    from 
        curated_db.tbl_bo_payment_type_dim a inner join raw_db.corporate_code_table b
        on b.code_constant_id = a.payment_type_bid
),

cte_tranche as
(
    select
        bo_tranche_type_skey    as bo_tranche_type_skey,
        b.code_pk               as bo_tranche_type_bid
    from 
        curated_db.tbl_bo_tranche_type_dim a inner join raw_db.corporate_code_table b
            on a.tranche_type_bid = b.code_constant_id
    where bo_tranche_type_skey > 0
),

cte_pcss_bic as
(
    select
        bo_swiftbic_code_skey      as bo_swiftbic_code_skey,
        upper(trim(swiftbic_code)) as swiftbic_code
    from 
        curated_db.tbl_bo_swiftbic_code_dim
    where 
        swiftbic_code is not null
),

cte_pay_bic as
(
    select
        upper(trim(swiftbic_code)) as swiftbic_code,
        bo_swiftbic_code_skey      as bo_swiftbic_code_skey
    from 
        curated_db.tbl_bo_swiftbic_code_dim
),

cte_beneficiary as
(
    select
        bo_beneficiary_desc_skey      as bo_beneficiary_desc_skey,
        upper(trim(beneficiary_desc)) as beneficiary_desc
    from 
        curated_db.tbl_bo_beneficiary_desc_dim
    where 
        beneficiary_desc is not null
),

cte_account as
(
    select
        bo_account_skey     as bo_account_skey,
        rk_account_pk       as rk_account_pk
    from 
        curated_db.tbl_bo_account_dim
    where 
        rk_account_pk is not null
),

cte_bus_attribute as
(
    select
        bo_bus_trans_attribute_skey     as bo_bus_trans_attribute_skey,        
        rk_business_trans_pk            as rk_business_trans_pk
    from 
        curated_db.tbl_bo_bus_trans_attribute_dim
    where 
        rk_business_trans_pk is not null
),

cte_settlement_mechanism as
(
    select
        bo_settlement_mechanism_skey        as bo_settlement_mechanism_skey,
        cast(settlement_mech_bid as bigint) as settlement_mech_bid
    from 
        curated_db.tbl_bo_settlement_mechanism_dim
    where 
        settlement_mech_bid is not null and bo_settlement_mechanism_skey > 0
),

cte_cover_ind as
(
    select
        business_trans_fk,
        1 as cover_ind
    from 
        raw_db.habs_business_trans_attr
    where 
        upper(key_name) = upper('CovInfo')
),

cte_gov_ind as
(
    select
        cast(concat(inc_payment_bus_trans_fk, out_payment_bus_trans_fk) as int) as business_trans_pk,
        1 as gov_ind
    from 
        raw_db.habs_government_bus_transaction
),

cte_ent_ind as
(
    select
        business_trans_pk as business_trans_fk,
        1 as ent_ind
    from 
        raw_db.habs_entitlement_bus_transaction
),

cte_set_ind as
(
    select
        business_trans_pk as business_trans_pk,
        1 as set_ind
    from 
        raw_db.habs_settlement_bus_transaction
),

cte_payment_ind AS
(
    SELECT
        BO_PAYMENT_BUS_TRANS_IND_SKEY   AS BO_PAYMENT_BUS_TRANS_IND_SKEY,
        CONCAT(
            CAST(CONFIRMATION_IND AS STRING),
            CAST(OVERRIDE_IND AS STRING),
            CAST(STATUS_OVERRIDE_IND AS STRING),
            CAST(WAS_IN_REPAIR_IND AS STRING),
            CAST(SYS_GENERATED_PAYMENT_IND AS STRING),
            CAST(MANUAL_INTERVENTION_IND AS STRING),
            CAST(RESERVE_IND AS STRING),
            CAST(COVER_IND AS STRING),
            CAST(ENTITLEMENT_PAYMENT_IND AS STRING),
            CAST(GOV_PAYMENT_IND AS STRING),
            CAST(SETTLEMENT_PAYMENT_IND AS STRING)
        ) AS PAYMENT_IND
    FROM curated_db.tbl_BO_PAYMENT_BUS_TRANS_IND_DIM
    WHERE BO_PAYMENT_BUS_TRANS_IND_SKEY > 0
)

insert into curated_db.tbl_bo_payment_bus_trans_fact
(
    business_value_dt,
    payment_adv_creation_dt,
    bo_bus_trans_status_skey,
    bo_payment_direction_skey,
    bo_payment_type_skey,
    bo_tranche_type_skey,
    bo_account_skey,
    bo_pcss_type_skey,
    bo_participant_profile_skey,
    bo_instruction_source_skey,
    bo_instruction_service_skey,
    bo_payment_bus_trans_ind_skey,
    bo_bus_trans_attribute_skey,
    bo_pcss_part_swiftbic_cd_skey,
    bo_pay_adv_swiftbic_cd_skey,
    bo_beneficiary_desc_skey,
    bo_settlement_mechanism_skey,
    rk_business_trans_pk,
    rk_message_pk,
    rk_payment_adv_bus_trans_fk,
    rk_assoc_inpay_bus_trans_fk,
    src_reference_num,
    payment_adv_related_ref_num,
    instruction_end_time_ts,
    payment_adv_amt,
    business_value_amt,
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
    md_system_skey,
    md_data_load_method_skey,
    md_data_source_notes,
    md_chksum,
    client_gle_skey,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
)

select
    s.business_value_date                               as business_value_dt,
    cast(date(s.payment_adv_creation_dt) as date)       as payment_adv_creation_dt,
    coalesce(ts.bo_bus_trans_status_skey, -1)           as bo_bus_trans_status_skey,
    coalesce(tservice.bo_bus_trans_service_skey, -1)    as bo_payment_direction_skey,
    coalesce(pt.bo_payment_type_skey, -1)               as bo_payment_type_skey,
    coalesce(tr.bo_tranche_type_skey, -1)               as bo_tranche_type_skey,
    coalesce(ac.bo_account_skey, -1)                    as bo_account_skey,
    coalesce(pcss.bo_pcss_type_skey, -1)                as bo_pcss_type_skey,
    coalesce(pp.bo_participant_profile_skey, -1)        as bo_participant_profile_skey,
    coalesce(ins.bo_instruction_source_skey, -1)        as bo_instruction_source_skey,
    coalesce(isvc.bo_instruction_service_skey, -1)      as bo_instruction_service_skey,
    coalesce(pi.bo_payment_bus_trans_ind_skey, -1)      as bo_payment_bus_trans_ind_skey,
    coalesce(ba.bo_bus_trans_attribute_skey, -1)        as bo_bus_trans_attribute_skey,
    coalesce(pbic.bo_swiftbic_code_skey, -1)            as bo_pcss_part_swiftbic_cd_skey,
    coalesce(paybic.bo_swiftbic_code_skey, -1)          as bo_pay_adv_swiftbic_cd_skey,
    coalesce(ben.bo_beneficiary_desc_skey, -1)          as bo_beneficiary_desc_skey,
    coalesce(sm.bo_settlement_mechanism_skey, -1)       as bo_settlement_mechanism_skey,
    s.rk_business_trans_pk                              as rk_business_trans_pk,
    cast(-1 as bigint)                                  as rk_message_pk,
    s.payment_adv_bus_trans_fk                          as rk_payment_adv_bus_trans_fk,
    s.assoc_inpay_bus_trans_fk                          as rk_assoc_inpay_bus_trans_fk,
    s.src_reference_num                                 as src_reference_num,
    s.payment_adv_related_ref_num                       as payment_adv_related_ref_num,
    case
        when s.c_timestamp is null and s.p_timestamp is null then null
        when s.c_timestamp is null then s.p_timestamp
        when s.p_timestamp is null then s.c_timestamp
        when s.c_timestamp > s.p_timestamp then s.c_timestamp
        else s.p_timestamp
    end                                                 as instruction_end_time_ts,

    s.payment_adv_amt                                   as payment_adv_amt,
    s.business_value_amt                                as business_value_amt,
    s.authorizing_user_name                             as authorizing_user_nm,
    s.application_user_name                             as application_user_nm,
    case
        when s.c_timestamp is null and s.p_timestamp is null then null
        when s.c_timestamp is null then s.p_timestamp
        when s.p_timestamp is null then s.c_timestamp
        when s.c_timestamp > s.p_timestamp then s.c_timestamp
        else s.p_timestamp
    end                                                 as application_update_ts,
    s.audit_creation_user                               as audit_creation_user_nm,

    cast(
        concat(
            cast(s.audit_creation_date as string),
            ' 11:11:11'
        ) as timestamp
    )                                                   as audit_creation_date_ts,
    s.audit_last_update_user                            as audit_last_update_user_nm,
    cast(
        concat(
            cast(s.audit_last_update_date as string),
            ' 11:11:11'
        ) as timestamp
    )                                                   as audit_last_update_date_ts,
    current_timestamp()                                 as md_create_ts,
    current_timestamp()                                 as md_last_update_ts,
    null                                                as md_workflow_execution_skey,
    5                                                   as md_system_skey,
    1                                                   as md_data_load_method_skey,
    'Daily ETL Load'                                    as md_data_source_notes,

    -- equivalent of the datastage pxchecksum stage
    sha2(
        concat_ws(
            '||',
            cast(s.rk_business_trans_pk as string),
            cast(s.business_value_date as string),
            cast(s.payment_adv_creation_dt as string),
            cast(coalesce(fi.financial_institution_skey, -1) as string),
            cast(coalesce(ts.bo_bus_trans_status_skey, -1) as string),
            cast(coalesce(tservice.bo_bus_trans_service_skey, -1) as string),
            cast(coalesce(pt.bo_payment_type_skey, -1) as string),
            cast(coalesce(tr.bo_tranche_type_skey, -1) as string),
            cast(coalesce(ac.bo_account_skey, -1) as string),
            cast(coalesce(pcss.bo_pcss_type_skey, -1) as string),
            cast(coalesce(pp.bo_participant_profile_skey, -1) as string),
            cast(coalesce(ins.bo_instruction_source_skey, -1) as string),
            cast(coalesce(isvc.bo_instruction_service_skey, -1) as string),
            cast(coalesce(pi.bo_payment_bus_trans_ind_skey, -1) as string),
            cast(coalesce(ba.bo_bus_trans_attribute_skey, -1) as string),
            cast(coalesce(pbic.bo_swiftbic_code_skey, -1) as string),
            cast(coalesce(paybic.bo_swiftbic_code_skey, -1) as string),
            cast(coalesce(ben.bo_beneficiary_desc_skey, -1) as string),
            cast(coalesce(sm.bo_settlement_mechanism_skey, -1) as string),
            s.src_reference_num,
            s.payment_adv_related_ref_num,
            cast(s.payment_adv_amt as string),
            cast(s.business_value_amt as string),
            s.authorizing_user_name,
            s.application_user_name
        ),
        256
    ) as md_chksum,
    coalesce(fi.financial_institution_skey, -1)         as client_gle_skey,
    {job_run_id}                                        as audit_load_id,
    current_timestamp()                                 as audit_create_ts,
    current_timestamp()                                 as audit_last_update_ts
from
    cte_source_data s
    left join cte_fin_inst fi
        on s.client_id = fi.client_id
    left join cte_instr_src ins
        on s.instruction_source_fk = ins.instruction_source_bid
    left join cte_instr_service isvc
        on s.instruction_service_fk = isvc.instruction_srvc_bid
    left join cte_part_profile pp
        on s.participant_profile_fk = pp.participant_profile_bid
    left join cte_pcss_type pcss
        on s.pcss_type_fk = pcss.pcss_type_bid
    left join cte_trans_status ts
        on s.business_trans_status_fk = ts.bo_bus_trans_status_bid
    left join cte_trans_service tservice
        on s.bus_trans_service_name = tservice.bus_trans_service_nm
    left join cte_payment_type pt
        on s.payment_type_fk = pt.payment_type_bid
    left join cte_tranche tr
        on s.tranche_fk = tr.bo_tranche_type_bid
    left join cte_pcss_bic pbic
        on s.pcss_participant_swiftbic_code = pbic.swiftbic_code
    left join cte_pay_bic paybic
        on s.pay_adv_swiftbic_code = paybic.swiftbic_code
    left join cte_beneficiary ben
        on s.beneficiary_desc = ben.beneficiary_desc
    left join cte_account ac
        on s.client_account_fk = ac.rk_account_pk
    left join cte_cover_ind cov
        on s.rk_business_trans_pk = cov.business_trans_fk
    left join cte_gov_ind gov
        on s.rk_business_trans_pk = gov.business_trans_pk
    left join cte_ent_ind ent
        on s.rk_business_trans_pk = ent.business_trans_fk
    left join cte_set_ind sett
        on s.rk_business_trans_pk = sett.business_trans_pk
    left join cte_bus_attribute ba
        on s.rk_business_trans_pk = ba.rk_business_trans_pk
    left join cte_settlement_mechanism sm
        on s.settl_mechanism_fk = sm.settlement_mech_bid
    left join cte_payment_ind pi
        on concat(
            case
                when trim(s.confirmation_ind) = '' then '-1'
                else s.confirmation_ind
            end,
            case
                when trim(s.override_ind) = '' then '-1'
                else s.override_ind
            end,
            case
                when trim(s.status_override_ind) = '' then '-1'
                else s.status_override_ind
            end,
            case
                when trim(s.was_in_repair_ind) = '' then '-1'
                else s.was_in_repair_ind
            end,
            case
                when trim(s.sys_generated_payment_ind) = '' then '-1'
                else s.sys_generated_payment_ind
            end,
            case
                when trim(s.manual_interventation_ind) = '' then '-1'
                else s.manual_interventation_ind
            end,
            case
                when trim(s.reserve_ind) = '' then '-1'
                else s.reserve_ind
            end,
            case
                when cov.cover_ind is null then '-1'
                else cast(cov.cover_ind as string)
            end,
            case
                when ent.ent_ind is null then '-1'
                else cast(ent.ent_ind as string)
            end,
            case
                when gov.gov_ind is null then '-1'
                else cast(gov.gov_ind as string)
            end,
            case
                when sett.set_ind is null then '-1'
                else cast(sett.set_ind as string)
            end
        ) = pi.payment_ind
        /* Filter based on PK */
        left anti join curated_db.tbl_bo_payment_bus_trans_fact pay_bus_trans_fact 
        on s.rk_business_trans_pk = pay_bus_trans_fact.rk_business_trans_pk
"""

logger.info("Executing INSERT for curated_db.TBL_BO_PAYMENT_BUS_TRANS_FACT")
logger.info(sql)
spark.sql(sql)

logger.info("Completed TBL_BO_PAYMENT_BUS_TRANS_FACT build")