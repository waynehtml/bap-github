catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_REPO_FAIL_DAILY_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
select coalesce(max(original_repo_date), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_repo_fail_daily_fact
"""

row = spark.sql(sql).first()
last_process_ts = row["max_date"]

sql = f"""

with cte_sells as (
    select
        substr(stbt.client_reference_desc, 1, 6)   as sells_ref_code,
        bt.business_value_date                     as sell_date,
        stbt.client_reference_desc                 as sell_ref
    from
        raw_db.habs_business_transaction bt
        join raw_db.habs_security_trade_bus_transaction stbt
            on bt.business_trans_pk = stbt.business_trans_pk
        join raw_db.corporate_code_table sectradetype
            on sectradetype.code_pk = stbt.security_trade_type_fk
        join raw_db.corporate_code_table marketoperationtype
            on marketoperationtype.code_pk = stbt.market_operation_type_fk
    where
        bt.business_trans_status_fk = 423
        and sectradetype.attribute_en_name = 'deliver against payment (sell)'
        and marketoperationtype.attribute_en_name in ('securities repo', 'overnight reverse repo')
        and bt.business_value_date < timestamp '{last_process_ts}'
),

cte_buys as (
    select
        substr(stbt.client_reference_desc, 1, 6)   as buys_ref_code,
        bt.business_value_date                     as buy_date,
        stbt.client_reference_desc                 as buy_ref
    from
        raw_db.habs_business_transaction bt
        join raw_db.habs_security_trade_bus_transaction stbt
            on bt.business_trans_pk = stbt.business_trans_pk
        join raw_db.corporate_code_table sectradetype
            on sectradetype.code_pk = stbt.security_trade_type_fk
        join raw_db.corporate_code_table marketoperationtype
            on marketoperationtype.code_pk = stbt.market_operation_type_fk
    where
        bt.business_trans_status_fk = 423
        and lower(sectradetype.attribute_en_name) = 'receive against payment (buy)'
        and lower(marketoperationtype.attribute_en_name) in ('securities repo', 'overnight reverse repo')
        and bt.business_value_date < timestamp '{last_process_ts}'
),

failed_refs as
(
  select
      s.sell_ref as sell_ref
  from
      cte_sells s left join cte_buys b
          on s.sells_ref_code = b.buys_ref_code
          and s.sell_ref = b.buy_ref
  where
      b.buys_ref_code is null
      and s.sell_date > date '2022-03-01'
),

cte_all_settled as (
    select
      stbt.settlement_agent_cuid_code   as settlement_agent_cuid_code,
      bt.business_value_date            as business_value_date,
      stbt.isin                         as isin,
      stbt.client_reference_desc        as client_reference_desc,
      stbt.securities_amt               as securities_amt,
      stbt.settlement_amt               as settlement_amt
  from
      raw_db.habs_business_transaction bt join raw_db.habs_security_trade_bus_transaction stbt
          on bt.business_trans_pk = stbt.business_trans_pk
      join raw_db.corporate_code_table sectradetype
          on sectradetype.code_pk = stbt.security_trade_type_fk
  where
      bt.business_value_date <= timestamp('{last_process_ts}')
),

cte_all_unsettled as (
    select
      stbt.settlement_agent_cuid_code   as settlement_agent_cuid_code,
      stbt.isin                         as isin,
      stbt.client_reference_desc        as client_reference_desc,
      stbt.securities_amt               as securities_amt,
      stbt.settlement_amt               as settlement_amt,
      stbt.market_operation_type_fk     as market_operation_type_fk,
      bt.src_reference_num              as src_reference_num,
      stbt.cdsx_traded_id               as cdsx_traded_id
  from
      raw_db.habs_business_transaction bt join raw_db.habs_security_trade_bus_transaction stbt
          on bt.business_trans_pk = stbt.business_trans_pk
      join raw_db.corporate_code_table sectradetype
          on sectradetype.code_pk = stbt.security_trade_type_fk
  where
      bt.business_value_date > timestamp('{last_process_ts}')
),

cte_source_data as (
    select
      u.settlement_agent_cuid_code      as cuid,
      u.isin                            as isin,
      u.client_reference_desc           as client_reference,
      u.securities_amt                  as par_value,
      u.settlement_amt                  as cash_value,
      u.market_operation_type_fk        as market_operation_type_fk,
      s.business_value_date             as original_repo_date,
      timestamp('{last_process_ts}')    as fail_report_date,
      u.src_reference_num               as src_reference_num,
      u.cdsx_traded_id                  as cdsx_traded_id
  from
      cte_all_settled s join cte_all_unsettled u
          on s.client_reference_desc = u.client_reference_desc
      join failed_refs f
          on f.sell_ref = s.client_reference_desc
),

cte_settlement_agent as (
    select
      settlement_agent_cuid_code  as settlement_agent_cuid_code,
      bo_settlement_agent_skey    as bo_settlement_agent_skey
    from (
        select
            settlement_agent_cuid_code,
            bo_settlement_agent_skey,
            row_number() over (
                partition by settlement_agent_cuid_code
                order by md_create_ts desc
            ) as rn
        from curated_db.tbl_bo_settlement_agent_dim
    ) t
    where
        rn = 1
        and settlement_agent_cuid_code is not null
        and bo_settlement_agent_skey > 0
),

cte_financial_instrument as (
    select
        isin_cd                     as isin_cd,
        financial_instrument_skey   as financial_instrument_skey
    from
        view_db.vwu_financial_instrument_dim
    where
        isin_cd is not null
),

cte_market_operation_type as (
    select
        mkt_operation_type_bid          as mkt_operation_type_bid,
        bo_market_operation_type_skey   as bo_market_operation_type_skey
    from
        curated_db.tbl_bo_market_operation_type_dim
    where
      mkt_operation_type_bid is not null
      and bo_market_operation_type_skey > 0
),

dim_holiday_date as (
        select
            cast(null as date) as holiday_date,
            cast(null as string) as holiday_flag
        where false
)

insert into curated_db.tbl_bo_repo_fail_daily_fact (
    bo_settlement_agent_skey,
    financial_instrument_skey,
    market_operation_type_skey,
    original_repo_date,
    fail_report_date,
    client_reference_desc,
    cdsx_traded_id,
    src_reference_num,
    securities_amt,
    settlement_amt,
    md_workflow_execution_skey,
    md_create_ts,
    md_last_update_ts,
    md_chksum,
    holiday_flag,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
)

SELECT
    coalesce(agent.bo_settlement_agent_skey, -1)          as bo_settlement_agent_skey,
    coalesce(fininstr.financial_instrument_skey, -1)      as financial_instrument_skey,
    coalesce(mkttype.bo_market_operation_type_skey, -1)   as market_operation_type_skey,
    s.original_repo_date                                  as original_repo_date,
    s.fail_report_date                                    as fail_report_date,
    s.client_reference                                    as client_reference_desc,
    s.cdsx_traded_id                                      as cdsx_traded_id,
    s.src_reference_num                                   as src_reference_num,
    s.par_value                                           as securities_amt,
    s.cash_value                                          as settlement_amt,
    null                                                  as md_workflow_execution_skey,
    null                                                  as md_create_ts,
    null                                                  as md_last_update_ts,
    null                                                  as md_chksum,
    hol.holiday_flag                                      as holiday_flag,
    {job_run_id}                                          as audit_load_id,
    current_timestamp()                                   as audit_create_ts,
    current_timestamp()                                   as audit_last_update_ts
FROM
  cte_source_data s left join cte_settlement_agent agent
    on s.cuid = agent.settlement_agent_cuid_code
  left join cte_financial_instrument  fininstr
    on s.isin = fininstr.isin_cd
  left join cte_market_operation_type mkttype
    on s.market_operation_type_fk = mkttype.mkt_operation_type_bid
  left join dim_holiday_date hol
    on s.fail_report_date = hol.holiday_date
"""

logger.info("Executing INSERT for curated_db.tbl_bo_repo_fail_daily_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_repo_fail_daily_fact build")