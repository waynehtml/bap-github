catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_ACCOUNT_BALANCE_DAILY_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_securities_lending_sumry_fact as tgt
using (

    with agg as (

        select
            rk_habs_business_trans_pk								as rk_habs_business_trans_pk,
            max(business_value_dt) 									as business_value_dt,
            max(client_gle_skey) 									as client_gle_skey,
            max(loan_financial_instrument_skey) 					as loan_financial_instrument_skey,
            count(distinct collateral_financial_instrument_skey)	as count_of_collateral_isin,
            max(bo_settlement_agent_skey)			                as settlement_agent_cuid_code,
            max(src_reference_num)									as src_reference_num,
            max(client_reference_desc)								as client_reference_desc,
            max(securities_desc)									as securities_desc,
            max(cdsx_pledge_trans_id)								as cdsx_pledge_trans_id,
            max(cdsx_pledge_mod_trans_id)							as cdsx_pledge_mod_trans_id,
            max(loan_par_value_amt)									as loan_par_value_amt,
            sum(coalesce(collateral_par_value_amt, 0))				as collateral_par_value_amt
        from
			curated_db.tbl_bo_securities_lending_bt_fact
        group by
            rk_habs_business_trans_pk
    ),

    src as (

        select
            rk_habs_business_trans_pk						as rk_habs_business_trans_pk,
            business_value_dt								as business_value_dt,
            client_gle_skey									as client_gle_skey,
            loan_financial_instrument_skey					as loan_financial_instrument_skey,
            count_of_collateral_isin						as count_of_collateral_isin,
            try_cast(
                collateral_par_value_amt
                / nullif(loan_par_value_amt, 0)
                as decimal(24,9)
            ) 												as collateral_to_loan_ratio,

            settlement_agent_cuid_code						as settlement_agent_cuid_code,
            src_reference_num								as src_reference_num,
            client_reference_desc							as client_reference_desc,
            securities_desc									as securities_desc,
            cdsx_pledge_trans_id							as cdsx_pledge_trans_id,
            cdsx_pledge_mod_trans_id						as cdsx_pledge_mod_trans_id,
            cast(loan_par_value_amt as decimal(24,9))		as loan_par_value_amt,
            cast(collateral_par_value_amt as decimal(24,9))	as collateral_par_value_amt,
            {job_run_id} 									as audit_load_id,
            current_timestamp() 							as audit_create_ts,
            current_timestamp() 							as audit_last_update_ts
        from agg
    )

    select *
    from src

) src

on tgt.rk_habs_business_trans_pk = src.RK_HABS_BUSINESS_TRANS_PK

when matched and (

       tgt.business_value_dt
            is distinct from src.BUSINESS_VALUE_DT

    or tgt.client_gle_skey
            is distinct from src.CLIENT_GLE_SKEY

    or tgt.loan_financial_instrument_skey
            is distinct from src.LOAN_FINANCIAL_INSTRUMENT_SKEY

    or tgt.count_of_collateral_isin
            is distinct from src.COUNT_OF_COLLATERAL_ISIN

    or tgt.collateral_to_loan_ratio
            is distinct from src.COLLATERAL_TO_LOAN_RATIO

    or tgt.settlement_agent_cuid_code
            is distinct from src.SETTLEMENT_AGENT_CUID_CODE

    or tgt.src_reference_num
            is distinct from src.SRC_REFERENCE_NUM

    or tgt.client_reference_desc
            is distinct from src.CLIENT_REFERENCE_DESC

    or tgt.securities_desc
            is distinct from src.SECURITIES_DESC

    or tgt.cdsx_pledge_trans_id
            is distinct from src.CDSX_PLEDGE_TRANS_ID

    or tgt.cdsx_pledge_mod_trans_id
            is distinct from src.CDSX_PLEDGE_MOD_TRANS_ID

    or tgt.loan_par_value_amt
            is distinct from src.LOAN_PAR_VALUE_AMT

    or tgt.collateral_par_value_amt
            is distinct from src.COLLATERAL_PAR_VALUE_AMT

)

then update set

    business_value_dt              = src.BUSINESS_VALUE_DT,
    client_gle_skey                = src.CLIENT_GLE_SKEY,
    loan_financial_instrument_skey = src.LOAN_FINANCIAL_INSTRUMENT_SKEY,
    count_of_collateral_isin       = src.COUNT_OF_COLLATERAL_ISIN,
    collateral_to_loan_ratio       = src.COLLATERAL_TO_LOAN_RATIO,
    settlement_agent_cuid_code     = src.SETTLEMENT_AGENT_CUID_CODE,
    src_reference_num              = src.SRC_REFERENCE_NUM,
    client_reference_desc          = src.CLIENT_REFERENCE_DESC,
    securities_desc                = src.SECURITIES_DESC,
    cdsx_pledge_trans_id           = src.CDSX_PLEDGE_TRANS_ID,
    cdsx_pledge_mod_trans_id       = src.CDSX_PLEDGE_MOD_TRANS_ID,
    loan_par_value_amt             = src.LOAN_PAR_VALUE_AMT,
    collateral_par_value_amt       = src.COLLATERAL_PAR_VALUE_AMT,
    audit_load_id                  = src.AUDIT_LOAD_ID,
    audit_last_update_ts           = src.AUDIT_LAST_UPDATE_TS

when not matched then insert (
    business_value_dt,
    client_gle_skey,
    loan_financial_instrument_skey,
    rk_habs_business_trans_pk,
    count_of_collateral_isin,
    collateral_to_loan_ratio,
    settlement_agent_cuid_code,
    src_reference_num,
    client_reference_desc,
    securities_desc,
    cdsx_pledge_trans_id,
    cdsx_pledge_mod_trans_id,
    loan_par_value_amt,
    collateral_par_value_amt,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
)
values (
    src.BUSINESS_VALUE_DT,
    src.CLIENT_GLE_SKEY,
    src.LOAN_FINANCIAL_INSTRUMENT_SKEY,
    src.RK_HABS_BUSINESS_TRANS_PK,
    src.COUNT_OF_COLLATERAL_ISIN,
    src.COLLATERAL_TO_LOAN_RATIO,
    src.SETTLEMENT_AGENT_CUID_CODE,
    src.SRC_REFERENCE_NUM,
    src.CLIENT_REFERENCE_DESC,
    src.SECURITIES_DESC,
    src.CDSX_PLEDGE_TRANS_ID,
    src.CDSX_PLEDGE_MOD_TRANS_ID,
    src.LOAN_PAR_VALUE_AMT,
    src.COLLATERAL_PAR_VALUE_AMT,
    src.AUDIT_LOAD_ID,
    src.AUDIT_CREATE_TS,
    src.AUDIT_LAST_UPDATE_TS
)
"""

logger.info("Executing INSERT for curated_db.tbl_bo_securities_lending_sumry_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_securities_lending_sumry_fact build")