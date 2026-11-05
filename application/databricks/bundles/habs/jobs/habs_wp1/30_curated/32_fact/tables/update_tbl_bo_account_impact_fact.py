catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_ACCOUNT_IMPACT_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
select coalesce(max(account_operation_eff_dt), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_account_impact_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

sql = f"""
WITH cte_main_src_data AS (
    SELECT
        abh.account_bal_history_pk                  AS account_bal_history_pk,
        CAST(c.client_id AS STRING)                 AS client_id,
        abh.account_fk                              AS account_fk,
        CAST (abh.account_impact_fk AS STRING)      AS account_impact_fk,
        ROW_NUMBER() OVER (PARTITION BY c.client_id, abh.account_fk
                               ORDER BY abh.account_operation_effect_date,
                                        abh.application_update_timestamp)  AS order_no,
           abh.account_operation_effect_date,
           abh.account_operation_amt,
           abh.account_operation_balance_amt,
           abh.business_trans_fk,
           btt.attribute_en_name                             AS trans_type,
           abh.application_update_timestamp
    FROM   raw_db.habs_account_bal_history abh
    JOIN   raw_db.habs_account a ON a.account_pk = abh.account_fk
    JOIN   raw_db.habs_client c ON c.client_pk = a.client_fk
    JOIN   raw_db.habs_business_transaction bt ON bt.business_trans_pk = abh.business_trans_fk
    JOIN   raw_db.corporate_code_table btt ON btt.code_pk = bt.business_trans_type_fk
    WHERE  abh.account_bal_type_fk = 463
    AND    (abh.account_operation_effect_date > timestamp('{last_process_ts}'))
),

cte_account_impact AS (
    SELECT bo_account_impact_type_skey,
           account_impact_type_bid
    FROM   curated_db.tbl_bo_account_impact_type_dim
    WHERE  md_current_ind = 1
    AND    account_impact_type_bid IS NOT NULL
),

cte_account AS (
    SELECT bo_account_skey,
           rk_account_pk
    FROM   curated_db.tbl_bo_account_dim
    WHERE  md_current_ind = 1
    AND    bo_account_skey > 0
),

cte_bus_trans_type AS (
    SELECT bo_bus_trans_type_skey,
           bus_trans_type_bid
    FROM   curated_db.tbl_bo_bus_trans_type_dim
    WHERE  md_current_ind = 1
    AND    bus_trans_type_bid IS NOT NULL
)

INSERT INTO curated_db.tbl_bo_account_impact_fact
  (
    bo_account_skey,
    bo_account_impact_type_skey,
    account_operation_eff_dt,
    client_gle_skey,
    bo_bus_trans_type_skey,
    rk_habs_account_bal_history_pk,
    rk_habs_bus_trans_pk,
    order_nb,
    account_operation_amt,
    account_operation_balance_amt,
    application_update_ts,
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

SELECT
    cte_account.bo_account_skey                                        AS bo_account_skey,
    CASE WHEN cte_account_impact.bo_account_impact_type_skey IS NULL OR cte_account_impact.bo_account_impact_type_skey = 0
         THEN -1 ELSE cte_account_impact.bo_account_impact_type_skey END           AS bo_account_impact_type_skey,
    cte_main_src_data.account_operation_effect_date                                 AS account_operation_eff_dt,
    CASE WHEN gle.global_legal_entity_skey IS NULL OR gle.global_legal_entity_skey = 0
         THEN -1 ELSE gle.global_legal_entity_skey END              AS client_gle_skey,
    CASE WHEN cte_bus_trans_type.bo_bus_trans_type_skey IS NULL OR cte_bus_trans_type.bo_bus_trans_type_skey = 0
         THEN -1 ELSE cte_bus_trans_type.bo_bus_trans_type_skey END                AS bo_bus_trans_type_skey,
    CASE WHEN cte_main_src_data.account_bal_history_pk IS NULL OR cte_main_src_data.account_bal_history_pk = 0
         THEN -1 ELSE cte_main_src_data.account_bal_history_pk END                   AS rk_habs_account_bal_history_pk,
    cte_main_src_data.business_trans_fk                                              AS rk_habs_bus_trans_pk,   -- no default: passthrough
    cte_main_src_data.order_no                                                       AS order_nb,
    cte_main_src_data.account_operation_amt,
    cte_main_src_data.account_operation_balance_amt,
    cte_main_src_data.application_update_timestamp                                  AS application_update_ts,
    current_timestamp()                                              AS md_create_ts,
    current_timestamp()                                              AS md_last_update_ts,
    null                                                              AS md_workflow_execution_skey,
    1                                                                 AS md_system_skey,
    1                                                                 AS md_data_load_method_skey,
    'Daily ETL Load'                                                  AS md_data_source_notes,
    md5(
        concat_ws('|',
            cte_main_src_data.client_id, cte_main_src_data.account_fk, cte_main_src_data.account_impact_fk,
            CAST(cte_main_src_data.order_no AS STRING),
            date_format(cte_main_src_data.account_operation_effect_date,'yyyyMMddHHmmss'),
            CAST(cte_main_src_data.account_operation_amt AS STRING),
            CAST(cte_main_src_data.account_operation_balance_amt AS STRING),
            CAST(cte_main_src_data.business_trans_fk AS STRING),
            cte_main_src_data.trans_type,
            date_format(cte_main_src_data.application_update_timestamp,'yyyyMMddHHmmssSSS')
        )
    )                                                                  AS md_chksum,
    {job_run_id}                                                       AS audit_load_id,
    current_timestamp()                                                AS audit_create_ts,
    current_timestamp()                                                AS audit_last_update_ts
FROM
    cte_main_src_data cte_main_src_data
    LEFT JOIN cte_account cte_account  ON cte_account.rk_account_pk = cte_main_src_data.account_fk
    LEFT JOIN view_db.vwu_global_legal_entity_dim gle on gle.client_id=cte_main_src_data.client_id
    LEFT JOIN cte_account_impact cte_account_impact  ON cte_account_impact.account_impact_type_bid = cte_main_src_data.account_impact_fk
    LEFT JOIN cte_bus_trans_type   cte_bus_trans_type ON cte_bus_trans_type.bus_trans_type_bid = cte_main_src_data.trans_type
"""

logger.info("Executing INSERT for curated_db.TBL_BO_ACCOUNT_IMPACT_FACT")
logger.info(sql)
spark.sql(sql)

logger.info("Completed TBL_BO_ACCOUNT_IMPACT_FACT build")