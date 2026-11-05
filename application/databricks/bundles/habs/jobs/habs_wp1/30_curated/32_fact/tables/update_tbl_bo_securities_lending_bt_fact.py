catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_securities_lending_bt_fact build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(application_update_ts), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_securities_lending_bt_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""
    with source_data as (
        select
            bt.business_trans_pk                        as rk_habs_business_trans_pk,
            bt.business_trans_status_fk                 as business_trans_status_fk,
            c.client_id                                 as client_id,
            bt.src_reference_num                        as src_reference_num,
            bt.business_value_date                      as business_value_date,
            sli.sec_lending_item_pk                     as rk_habs_coll_sec_lending_item_pk,
            loan.sec_lending_item_pk                    as rk_habs_loan_sec_lending_item_pk,
            sli.cdsx_pledge_trans_id                    as cdsx_pledge_trans_id,
            sli.cdsx_pledge_mod_trans_id                as cdsx_pledge_mod_trans_id,
            sli.isin                                    as coll_isin,
            loan.isin                                   as loan_isin,
            sli.par_value_amt                           as coll_par_value_amt,
            loan.par_value_amt                          as loan_par_value_amt,
            stbt.settlement_agent_cuid_code             as settlement_agent_cuid_code,
            stbt.client_reference_desc                  as client_reference_desc,
            stbt.securities_desc                        as securities_desc,
            bt.bus_trans_service_name                   as bus_trans_service_name,
            bt.authorizing_user_name                    as authorizing_user_name,
            sli.application_user_name                   as application_user_name,
            bt.application_update_timestamp             as p_timestamp,
            sli.application_update_timestamp            as c_timestamp,
            sli.audit_creation_user                     as audit_creation_user,
            sli.audit_creation_date                     as audit_creation_date,
            sli.audit_last_update_user                  as audit_last_update_user,
            sli.audit_last_update_date                  as audit_last_update_date,
            i.instruction_source_fk                     as instruction_source_fk,
            i.instruction_service_fk                    as instruction_service_fk,
            coalesce(bt.confirmation_ind, -1)           as confirmation_ind,
            coalesce(bt.override_ind, -1)               as override_ind,
            coalesce(bt.status_override_ind, -1)        as status_override_ind,
            coalesce(bt.was_in_repair_ind, -1)          as was_in_repair_ind,
            coalesce(i.manual_interventation_ind, -1)   as manual_intervention_ind,
            i.application_update_timestamp              as instruction_end_time,
            case
                when sli.application_update_timestamp is null then bt.application_update_timestamp
                when bt.application_update_timestamp is null then sli.application_update_timestamp
                when sli.application_update_timestamp > bt.application_update_timestamp then sli.application_update_timestamp
                else bt.application_update_timestamp
            end                                         as application_update_ts
        from 
            raw_db.habs_business_transaction bt join raw_db.habs_securities_lending_item sli
                on bt.business_trans_pk = sli.business_trans_fk
            join raw_db.habs_client c 
                on c.client_pk = bt.client_fk
            left join raw_db.habs_instruction i 
                on bt.business_trans_pk = i.business_trans_fk
            left join raw_db.habs_security_trade_bus_transaction stbt
            on stbt.business_trans_pk = sli.business_trans_fk
            join(
                select business_trans_fk, isin, par_value_amt, sec_lending_item_pk
                from  raw_db.habs_securities_lending_item
                where loan_ind = 1
            ) loan
            on sli.business_trans_fk = loan.business_trans_fk
        where 
            sli.loan_ind = 0
            and bt.business_trans_status_fk = 423
            and sli.application_update_timestamp > timestamp('{last_process_ts}')
    ),

    dim_business_trans_status as (
        select 
            code_table.code_pk                                          as code_pk,
            coalesce(trans_status_dim.bo_bus_trans_status_skey, -1)     as bo_bus_trans_status_skey 
        from 
            raw_db.corporate_code_table code_table
        join curated_db.tbl_bo_bus_trans_status_dim trans_status_dim
        on code_table.code_constant_id = trans_status_dim.bus_trans_status_bid
    ),
 
    dim_global_legal_entity as (
        select 
            gle.client_id                               as client_id,
            coalesce(gle.global_legal_entity_skey, -1)  as global_legal_entity_skey
        from 
            view_db.vwu_global_legal_entity_dim gle
        where 
            client_id is not null
    ),

    dim_bus_trans_service as (
        select 
            coalesce(svcnm.bo_bus_trans_service_skey, -1)   as bo_bus_trans_service_skey,
            svcnm.bus_trans_service_nm                      as bus_trans_service_nm
        from 
            curated_db.tbl_bo_bus_trans_service_dim svcnm
        where 
            bus_trans_service_nm is not null
    ),   

    dim_financial_instrument as (
        select
            coalesce(loanfi.financial_instrument_skey, -1)      as financial_instrument_skey,
            loanfi.isin_cd                                      as isin
        from 
            view_db.vwu_financial_instrument_dim loanfi
        where 
            loanfi.isin_cd is not null
    ),	

    dim_instruction_source as (
        select
            instruction_source_bid      as instruction_source_bid,
            bo_instruction_source_skey  as bo_instruction_source_skey
        from
            curated_db.tbl_bo_instruction_source_dim
        where 
            bo_instruction_source_skey > -1
            and instruction_source_bid is not null
    ),

    dim_instruction_service as (
        select 
            instruction_srvc_bid            as instruction_srvc_bid,
            bo_instruction_service_skey     as bo_instruction_service_skey
        from 
        curated_db.tbl_bo_instruction_service_dim
        where 
            bo_instruction_service_skey > -1
            and instruction_srvc_bid is not null
    ),

    dim_securities_lending_ind as (
        select
            -- NOTE: 243, not -1 (distinct "unknown" member)
            coalesce(ind.bo_securities_lending_ind_skey, 243)   as bo_securities_lending_ind_skey,
            ind.confirmation_ind                                as confirmation_ind, 
            ind.override_ind                                    as override_ind,          
            ind.status_override_ind                             as status_override_ind, 
            ind.was_in_repair_ind                               as was_in_repair_ind,
            ind.manual_intervention_ind                         as manual_intervention_ind
        from 
        curated_db.tbl_bo_securities_lending_ind_dim ind
    ),

    dim_settlement_agent as (
        select distinct
            concat(agent.settlement_agent_cuid_code, agent.settlement_agent_bic_code, agent.settlement_agent_desc)  as agent_id,
            coalesce(agent.bo_settlement_agent_skey, -1)                                                            as bo_settlement_agent_skey,
            settlement_agent_cuid_code                                                                              as settlement_agent_cuid_code
        from 
            curated_db.tbl_bo_settlement_agent_dim agent
        where 
            concat(settlement_agent_cuid_code, settlement_agent_bic_code, settlement_agent_desc) is not null
    )

    INSERT INTO curated_db.tbl_bo_securities_lending_bt_fact
    (  
        business_value_dt,					client_gle_skey,						bo_bus_trans_status_skey,
        bo_bus_trans_service_skey,			bo_settlement_agent_skey,				bo_securities_lending_ind_skey,
        loan_financial_instrument_skey,		collateral_financial_instrument_skey,	rk_habs_business_trans_pk,
        rk_habs_loan_sec_lending_item_pk,	rk_habs_coll_sec_lending_item_pk,		src_reference_num,
        authorizing_user_nm,				client_reference_desc,					securities_desc,
        cdsx_pledge_trans_id,				cdsx_pledge_mod_trans_id,				loan_par_value_amt,
        collateral_par_value_amt,			instruction_end_time,					application_user_nm,
        application_update_ts,				bo_instruction_source_skey,				bo_instruction_service_skey,
        audit_creation_user_nm,				audit_creation_date_ts,					audit_last_update_user_nm,
        audit_last_update_date_ts,			md_create_ts,							md_last_update_ts,
        md_workflow_execution_skey,			md_system_skey,							md_data_load_method_skey,
        md_chksum,							audit_load_id,							audit_create_ts,
        audit_last_update_ts
    )
    select
        s.business_value_date                                       as business_value_dt,
        gle.global_legal_entity_skey                                as client_gle_skey,
        btstat.bo_bus_trans_status_skey                             as bo_bus_trans_status_skey,
        svcnm.bo_bus_trans_service_skey                             as bo_bus_trans_service_skey,
        agent.bo_settlement_agent_skey                              as bo_settlement_agent_skey,
        ind.bo_securities_lending_ind_skey                          as bo_securities_lending_ind_skey, 
        loanfi.financial_instrument_skey                            as loan_financial_instrument_skey,
        collfi.financial_instrument_skey                            as collateral_financial_instrument_skey,
        s.rk_habs_business_trans_pk                                 as rk_habs_business_trans_pk,
        s.rk_habs_loan_sec_lending_item_pk                          as rk_habs_loan_sec_lending_item_pk,
        s.rk_habs_coll_sec_lending_item_pk                          as rk_habs_coll_sec_lending_item_pk,
        s.src_reference_num                                         as src_reference_num,
        s.authorizing_user_name                                     as authorizing_user_nm,
        s.client_reference_desc                                     as client_reference_desc,
        s.securities_desc                                           as securities_desc,
        s.cdsx_pledge_trans_id                                      as cdsx_pledge_trans_id,
        s.cdsx_pledge_mod_trans_id                                  as cdsx_pledge_mod_trans_id,
        s.loan_par_value_amt                                        as loan_par_value_amt,
        s.coll_par_value_amt                                        as collateral_par_value_amt,
        s.instruction_end_time                                      as instruction_end_time,
        s.application_user_name                                     as application_user_nm,
        s.application_update_ts                                     as application_update_ts,
        instsrc.BO_INSTRUCTION_SOURCE_SKEY                          as bo_instruction_source_skey,
        instsvc.bo_instruction_service_skey                         as bo_instruction_service_skey,
        s.audit_creation_user                                       as audit_creation_user_nm,
        date_trunc('DAY', s.audit_creation_date)                    as audit_creation_date_ts,
        s.audit_last_update_user                                    as audit_last_update_user_nm,
        date_trunc('DAY', s.audit_last_update_date)                 as audit_last_update_date_ts,
        null                                                        as md_create_ts,
        null                                                        as md_last_update_ts,
        null                                                        as md_workflow_execution_skey,
        1                                                           as md_system_skey,
        1                                                           as md_data_load_method_skey,
        null                                                        as md_chksum,
        {job_run_id}                                                as audit_load_id,
        current_timestamp()                                         as audit_create_ts,
        current_timestamp()                                         as audit_last_update_ts
    from source_data s
        left join dim_business_trans_status  btstat 
            on s.business_trans_status_fk = btstat.code_pk
        left join dim_global_legal_entity gle 
            on s.client_id = gle.client_id
        left join dim_bus_trans_service svcnm  
            on s.bus_trans_service_name = svcnm.bus_trans_service_nm
        left join dim_financial_instrument collfi 
            on s.coll_isin = collfi.isin
        left join dim_financial_instrument loanfi 
            on s.loan_isin = loanfi.isin
        left join dim_instruction_source  instsrc 
            on s.instruction_source_fk = instsrc.INSTRUCTION_SOURCE_BID
        left join dim_instruction_service instsvc 
            on s.instruction_service_fk = instsvc.instruction_srvc_bid
        left join dim_securities_lending_ind ind
            on  s.confirmation_ind        <=> ind.confirmation_ind
            and s.override_ind            <=> ind.override_ind
            and s.status_override_ind     <=> ind.status_override_ind
            and s.was_in_repair_ind       <=> ind.was_in_repair_ind
            and s.manual_intervention_ind <=> ind.manual_intervention_ind
        left join dim_settlement_agent agent
            on s.settlement_agent_cuid_code = agent.settlement_agent_cuid_code
"""

logger.info("Executing INSERT for curated_db.tbl_bo_securities_lending_bt_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_securities_lending_bt_fact build")