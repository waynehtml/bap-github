catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_security_trade_bt_fact build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(business_value_dt), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_security_trade_bt_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""
with cte_instruction_history as (
    select
        instruction_fk                  as instruction_fk,
        max(instruction_activity_date)  as instruction_end_time_ts
    from
        raw_db.habs_instruction_history
    group by instruction_fk
),

cte_isin as
(
select
    trim(isin_cd) as isin,
    financial_instrument_skey as financial_instrument_skey
from
    view_db.vwu_financial_instrument_dim
where
    md_current_ind = 1
    and financial_instrument_skey > 0
    and trim(isin_cd) is not null
),

cte_safekeeping_acc_key as
(
    select
        rk_account_pk   as rk_account_pk,
        bo_account_skey as bo_safekeeping_account_skey
    from
        curated_db.tbl_bo_account_dim
    where
        md_current_ind = 1 and bo_account_skey > 0
),

cte_cash_account as
(
    select
        rk_account_pk   as rk_account_pk,
        bo_account_skey as bo_cash_account_skey
    from
        curated_db.tbl_bo_account_dim
    where
        md_current_ind = 1 and bo_account_skey > 0
),

cte_sec_trade_type as
(
    select
        sec_trade_type_bid              as sec_trade_type_bid,
        bo_security_trade_type_skey     as bo_security_trade_type_skey
    from
        curated_db.tbl_bo_security_trade_type_dim
    where
        md_current_ind =1 and
        bo_security_trade_type_skey > 0
),

cte_market_operation_type as
(
    select
        mkt_operation_type_bid          as mkt_operation_type_bid,
        bo_market_operation_type_skey   as bo_market_operation_type_skey
    from
         curated_db.tbl_bo_market_operation_type_dim
    where
        md_current_ind = 1 and bo_market_operation_type_skey > 0
),

cte_instruction_source as
(
    select
        instruction_source_bid          as instruction_source_bid,
        bo_instruction_source_skey      as bo_instruction_source_skey
    from
        curated_db.tbl_bo_instruction_source_dim
    where
        md_current_ind = 1 and bo_instruction_source_skey > 0
),

cte_instruction_service as
(
    select
        instruction_srvc_bid            as instruction_srvc_bid,
        bo_instruction_service_skey     as bo_instruction_service_skey
    from
        curated_db.tbl_bo_instruction_service_dim
    where
        md_current_ind = 1 and bo_instruction_service_skey > 0
),

cte_participant_profile as
(
    select
        participant_profile_bid         as participant_profile_bid,
        bo_participant_profile_skey     as bo_participant_profile_skey
    from
        curated_db.tbl_bo_participant_profile_dim
    where
        md_current_ind = 1 and bo_participant_profile_skey > 0
),

cte_pcss_type as
(
    select
        pcss_type_bid                   as pcss_type_bid,
        bo_pcss_type_skey               as bo_pcss_type_skey
    from
        curated_db.tbl_bo_pcss_type_dim
    where
        md_current_ind = 1 and bo_pcss_type_skey > 0
),

cte_bus_trans_status as
(
    select
        code_table.code_pk          as bo_bus_trans_status_bid,
        BO_BUS_TRANS_STATUS_SKEY    as bo_bus_trans_status_skey
    from
        raw_db.corporate_code_table code_table join curated_db.tbl_bo_bus_trans_status_dim trans_status
            on code_table.code_constant_id = trans_status.bus_trans_status_bid
    where
        code_table.code_constant_id = 'Settle' and
        code_table.code_pk = 423
),

cte_global_legal_entity as
(
    select
        global_legal_entity_skey    as global_legal_entity_skey,
        cast(client_id as int)      as client_id,
        rk_habs_client_pk           as rk_habs_client_pk
    from view_db.vwu_global_legal_entity_dim
    where global_legal_entity_skey > 0 and client_id is not null
),

cte_security_trade as
(
    select
        bo_security_trade_bt_ind_skey                                                                                           as bo_security_trade_bt_ind_skey,
        (boc_submission_ind||confirmation_ind||manual_intervention_ind||override_ind||status_override_ind||was_in_repair_ind)   as lkp_ind
    from
        curated_db.tbl_bo_security_trade_bt_ind_dim
    where  bo_security_trade_bt_ind_skey > 0
),

cte_settlement_agent as
(
    select
        bo_settlement_agent_skey                                                                         as bo_settlement_agent_skey,
        (trim(settlement_agent_desc)||trim(settlement_agent_cuid_code)||trim(settlement_agent_bic_code)) as agent_lkp
    from
        curated_db.tbl_bo_settlement_agent_dim
    where
        bo_settlement_agent_skey > 0 and
        (trim(settlement_agent_desc)||trim(settlement_agent_cuid_code)||trim(settlement_agent_bic_code)) is not null
),

cte_trade_group as
(
    select
        bo_trade_group_id_skey      as bo_trade_group_id_skey,
        trade_group_id              as trade_group_id
    from
        curated_db.tbl_bo_trade_group_id_dim
    where
        bo_trade_group_id_skey > 0 and trade_group_id is not null
),


cte_beneficiary as
(
    select
        bo_beneficiary_desc_skey    as bo_beneficiary_desc_skey,
        beneficiary_desc            as beneficiary_desc
    from
        curated_db.tbl_bo_beneficiary_desc_dim
    where
        beneficiary_desc is not null and bo_beneficiary_desc_skey > 0
),

source_sec_trade_fact as
(
    select
        bt.business_value_date                          as business_value_dt,
        cte_gle.global_legal_entity_skey                as client_gle_skey,
        cte_isin.financial_instrument_skey              as financial_instrument_skey,
        cte_trans_status.bo_bus_trans_status_skey       as bo_bus_trans_status_skey,
        cte_stt.bo_security_trade_type_skey             as bo_security_trade_type_skey,
        cte_sak.bo_safekeeping_account_skey             as bo_safekeeping_account_skey,
        cte_cash_acc.bo_cash_account_skey               as bo_cash_account_skey,
        cte_pcss_type.bo_pcss_type_skey                 as bo_pcss_type_skey,
        cte_partic_profile.bo_participant_profile_skey  as bo_participant_profile_skey,
        cte_mot.bo_market_operation_type_skey           as bo_market_operation_type_skey,
        cte_inst_source.bo_instruction_source_skey      as bo_instruction_source_skey,
        cte_inst_serv.bo_instruction_service_skey       as bo_instruction_service_skey,
        cte_sec_trade.bo_security_trade_bt_ind_skey     as bo_security_trade_bt_ind_skey,
        cte_benef.bo_beneficiary_desc_skey              as bo_beneficiary_desc_skey,
        cte_stlm_agent.bo_settlement_agent_skey         as bo_settlement_agent_skey,
        cte_trd_grp.bo_trade_group_id_skey              as bo_trade_group_id_skey,
        bt.business_trans_pk                            as rk_habs_business_trans_pk,
        bt.src_reference_num                            as src_reference_num,
        stbt.client_reference_desc                      as client_reference_desc,
        stbt.cdsx_traded_id                             as cdsx_traded_id,
        ih.instruction_end_time_ts                      as instruction_end_time_ts,
        stbt.settlement_amt                             as settlement_amt,
        stbt.securities_amt                             as securities_amt,
        bt.authorizing_user_name                        as authorizing_user_nm,
        bt.application_user_name                        as application_user_nm,
        case
            when bt.application_update_timestamp is null then stbt.application_update_timestamp
            when stbt.application_update_timestamp is null then bt.application_update_timestamp
            when bt.application_update_timestamp > stbt.application_update_timestamp then bt.application_update_timestamp
            else stbt.application_update_timestamp
          end                                           as application_update_ts,
        stbt.audit_creation_user                        as audit_creation_user_nm,
        bt.audit_creation_date                          as audit_creation_date_ts,
        bt.audit_last_update_user                       as audit_last_update_user_nm,
        bt.AUDIT_LAST_UPDATE_DATE                       as audit_last_update_date_ts,
        null                                            as md_create_ts,
        null                                            as md_last_update_ts,
        null                                            as md_workflow_execution_skey,
        null                                            as md_system_skey,
        null                                            as md_data_load_method_skey,
        null                                            as md_data_source_notes,
        null                                            as md_chksum
    from
        raw_db.habs_business_transaction bt join raw_db.habs_security_trade_bus_transaction stbt
            on bt.business_trans_pk = stbt.business_trans_pk
                inner join raw_db.habs_client c on c.client_pk = bt.client_fk
        left join raw_db.habs_instruction i on bt.business_trans_pk = i.business_trans_fk
        left join cte_instruction_history ih on ih.instruction_fk = I.instruction_pk
        inner join raw_db.corporate_code_table instruction_service_code on instruction_service_code.code_pk = i.instruction_service_fk
       /* isin */
    left join cte_isin cte_isin
        on cte_isin.isin = stbt.isin

    /* safekeeping account */
    left join cte_safekeeping_acc_key cte_sak
        on cte_sak.rk_account_pk = stbt.safekeeping_account_fk

    /* cash account */
    left join cte_cash_account cte_cash_acc
        on cte_cash_acc.rk_account_pk = stbt.cash_account_fk

    /* sec trade */
    left join cte_sec_trade_type cte_stt
        on cte_stt.sec_trade_type_bid = stbt.security_trade_type_fk

    /* market operation type */
    left join cte_market_operation_type cte_mot
        on cte_mot.mkt_operation_type_bid = stbt.market_operation_type_fk

    /* instruction */
    left join cte_instruction_source cte_inst_source
        on cte_inst_source.instruction_source_bid = i.instruction_source_fk

    /* instruction service */
    left join cte_instruction_service cte_inst_serv
        on cte_inst_serv.instruction_srvc_bid = i.instruction_service_fk

    /* participant profile */
    left join cte_participant_profile cte_partic_profile
        on cte_partic_profile.participant_profile_bid = stbt.participant_profile_fk

    /* pcss type */
    left join cte_pcss_type cte_pcss_type
        on cte_pcss_type.pcss_type_bid = stbt.pcss_type_fk

    /* trans status */
    left join cte_bus_trans_status cte_trans_status
        on cte_trans_status.bo_bus_trans_status_bid = bt.business_trans_status_fk

    /* gle */
    /* replace by view in uc */
    left join cte_global_legal_entity cte_gle
        on cte_gle.client_id = c.client_id

    /* security trade */
    left join cte_security_trade cte_sec_trade
        on cte_sec_trade.lkp_ind = (
            stbt.boc_submission_ind ||
            bt.confirmation_ind ||
            i.manual_interventation_ind ||
            bt.override_ind ||
            bt.status_override_ind ||
            bt.was_in_repair_ind
        )

    /* settlement agent */
    left join cte_settlement_agent cte_stlm_agent
        on cte_stlm_agent.agent_lkp = (
            trim(settlement_agent_desc) ||
            trim(settlement_agent_cuid_code) ||
            trim(settlement_agent_bic_code)
        )

    /* trade group */
    left join cte_trade_group cte_trd_grp
        on cte_trd_grp.trade_group_id = bt.src_reference_num

    /* beneficiary */
    left join cte_beneficiary cte_benef
        on cte_benef.beneficiary_desc = stbt.beneficiary_payee_desc

    where bt.business_trans_status_fk = 423
    and instruction_service_code.code_constant_id in (
        'SecurityTradeIn',
        'SecurityTradeOut',
        'SecurityTrade'
    )
    and bt.business_value_date > timestamp('{last_process_ts}')
    )

insert into curated_db.tbl_bo_security_trade_bt_fact
(
    business_value_dt,
    client_gle_skey,
    financial_instrument_skey,
    bo_bus_trans_status_skey,
    bo_security_trade_type_skey,
    bo_safekeeping_account_skey,
    bo_cash_account_skey,
    bo_pcss_type_skey,
    bo_participant_profile_skey,
    bo_market_operation_type_skey,
    bo_instruction_source_skey,
    bo_instruction_service_skey,
    bo_security_trade_bt_ind_skey,
    bo_beneficiary_desc_skey,
    bo_settlement_agent_skey,
    bo_trade_group_id_skey,
    rk_habs_business_trans_pk,
    src_reference_num,
    client_reference_desc,
    cdsx_traded_id,
    instruction_end_time_ts,
    settlement_amt,
    securities_amt,
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
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
)

select
    src.BUSINESS_VALUE_DT,
    src.CLIENT_GLE_SKEY,
    src.FINANCIAL_INSTRUMENT_SKEY,
    src.BO_BUS_TRANS_STATUS_SKEY,
    src.BO_SECURITY_TRADE_TYPE_SKEY,
    src.BO_SAFEKEEPING_ACCOUNT_SKEY,
    src.BO_CASH_ACCOUNT_SKEY,
    src.BO_PCSS_TYPE_SKEY,
    src.BO_PARTICIPANT_PROFILE_SKEY,
    src.BO_MARKET_OPERATION_TYPE_SKEY,
    src.BO_INSTRUCTION_SOURCE_SKEY,
    src.BO_INSTRUCTION_SERVICE_SKEY,
    src.BO_SECURITY_TRADE_BT_IND_SKEY,
    src.BO_BENEFICIARY_DESC_SKEY,
    src.BO_SETTLEMENT_AGENT_SKEY,
    src.BO_TRADE_GROUP_ID_SKEY,
    src.RK_HABS_BUSINESS_TRANS_PK,
    src.SRC_REFERENCE_NUM,
    src.CLIENT_REFERENCE_DESC,
    src.CDSX_TRADED_ID,
    src.INSTRUCTION_END_TIME_TS,
    src.SETTLEMENT_AMT,
    src.SECURITIES_AMT,
    src.AUTHORIZING_USER_NM,
    src.APPLICATION_USER_NM,
    src.APPLICATION_UPDATE_TS,
    src.AUDIT_CREATION_USER_NM,
    src.AUDIT_CREATION_DATE_TS,
    src.AUDIT_LAST_UPDATE_USER_NM,
    src.AUDIT_LAST_UPDATE_DATE_TS,
    src.MD_CREATE_TS,
    src.MD_LAST_UPDATE_TS,
    src.MD_WORKFLOW_EXECUTION_SKEY,
    src.MD_SYSTEM_SKEY,
    src.MD_DATA_LOAD_METHOD_SKEY,
    src.MD_DATA_SOURCE_NOTES,
    src.MD_CHKSUM,
    {job_run_id},
    current_timestamp(),
    current_timestamp()
from source_sec_trade_fact src
 left anti join curated_db.tbl_bo_security_trade_bt_fact tgt
    on src.RK_HABS_BUSINESS_TRANS_PK = tgt.rk_habs_business_trans_pk
"""

logger.info("Executing INSERT for curated_db.tbl_bo_security_trade_bt_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_security_trade_bt_fact build")