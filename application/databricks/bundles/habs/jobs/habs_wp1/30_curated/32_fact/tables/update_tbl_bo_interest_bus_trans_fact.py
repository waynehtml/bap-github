catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_INTEREST_BUS_TRANS_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(application_update_timestamp), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_interest_bus_trans_fact
"""

last_process_ts = spark.sql(sql).first()["max_date"]

validation_sql = f"""

-- -------------------------------------------------------------------------------------
-- 1. Guard rail — abort if any candidate row's client has no match in the Global
--    Legal Entity dimension (mirrors the DataStage job's mandatory/force_error lookup
--    on lnk_GlobalLegalEntity). Runs as its own statement so it is always evaluated,
--    not optimized away.
-- -------------------------------------------------------------------------------------
select
    CASE
        WHEN COUNT(*) > 0
        THEN raise_error(
                concat('Job aborting due to lookup failure on: global_legal_entity_dim. Unmatched clients: ',
                       CAST(COUNT(*) as string))
             )
        ELSE 'GLE guard passed'
    END as gle_guard_result
from (
    select DISTINCT
        trim(trailing 'L' from
            trim(leading '0' from
                trim(trailing 'A' from
                    trim(trailing '.' from CAST(c.client_id as string))
                )
            )
        ) as client_id
    from raw_db.habs_business_transaction bt join raw_db.habs_client c
      on c.client_pk = bt.client_fk
    where bt.business_trans_status_fk IN (420, 423)
      and bt.application_update_timestamp > timestamp('{last_process_ts}')
) candidates
left join (
    select distinct
        trim(leading '0' from trim(trailing '.' from CAST(client_id as string))) as client_id
    from  view_db.vwu_global_legal_entity_dim
) gle
  on candidates.client_id = gle.client_id
where gle.client_id IS null

"""

spark.sql(validation_sql)

sql = f"""

-- =======================================================================================
-- 2. CTEs + final load
-- =======================================================================================
with src as (
    select
        bt.business_trans_pk                                                as rk_habs_business_trans_pk,
        bt.business_trans_type_fk,
        bt.business_trans_status_fk,
        trim(trailing 'L' from
            trim(leading '0' from
                trim(trailing 'A' from
                    trim(trailing '.' from CAST(c.client_id as string))
                )
            )
        )                                                                   as client_id,
        bt.src_reference_num                                                as src_reference_num,
        bt.business_value_date                                              as business_value_dt,
        bt.business_value_amt                                               as business_value_amt,
        bt.confirmation_ind                                                 as confirmation_ind,
        bt.override_ind                                                     as override_ind,
        bt.bus_trans_service_name                                           as payment_direction,
        bt.status_override_ind                                              as status_override_ind,
        bt.was_in_repair_ind                                                as was_in_repair_ind,
        bt.authorizing_user_name                                            as authorizing_user_name,
        ibt.narrative_desc                                                  as narrative_desc,
        ibt.compensation_account_fk                                         as compensation_account_fk,
        ibt.client_account_fk                                               as client_account_fk,
        ibt.interest_facility_fk                                            as interest_facility_fk,
        bt.application_user_name                                            as application_user_name,
        bt.application_update_timestamp                                     as application_update_timestamp,
        ibt.audit_creation_user                                             as audit_creation_user,
        coalesce(ibt.audit_creation_date, TIMESTAMP'1900-01-01 00:00:00')   as audit_creation_date,
        ibt.audit_last_update_user                                          as audit_last_update_user,
        ibt.audit_last_update_date                                          as audit_last_update_date,
        i.instruction_source_fk                                             as instruction_source_fk,
        i.instruction_service_fk                                            as instruction_service_fk,
        i.manual_interventation_ind                                         as manual_intervention_ind,
        max(ih.instruction_activity_date)                                   as instruction_end_time
    from
         raw_db.habs_business_transaction bt left join raw_db.habs_interest_bus_transaction ibt
           on bt.business_trans_pk = ibt.business_trans_pk
        left join raw_db.habs_client c on c.client_pk = bt.client_fk
        left join raw_db.habs_instruction i on bt.business_trans_pk = i.business_trans_fk
        left join raw_db.corporate_code_table instructionsource on instructionsource.code_pk = i.instruction_source_fk
        left join raw_db.corporate_code_table instructionservice on instructionservice.code_pk = i.instruction_service_fk
        left join raw_db.habs_instruction_history ih on ih.instruction_fk = i.instruction_pk
    where
        bt.business_trans_status_fk IN (420, 423)
        and c.client_id IN (select client_id from view_db.vwu_global_legal_entity_dim)
        and bt.application_update_timestamp > timestamp('{last_process_ts}')
    group by
        bt.business_trans_pk, bt.business_trans_type_fk, bt.business_trans_status_fk,
        c.client_id, bt.src_reference_num, bt.business_value_date, bt.business_value_amt,
        bt.confirmation_ind, bt.override_ind, bt.bus_trans_service_name, bt.status_override_ind,
        bt.was_in_repair_ind, bt.authorizing_user_name, ibt.narrative_desc, ibt.compensation_account_fk,
        ibt.client_account_fk, ibt.interest_facility_fk, bt.application_user_name, bt.application_update_timestamp,
        ibt.audit_creation_user, ibt.audit_creation_date, ibt.audit_last_update_user,
        ibt.audit_last_update_date, i.instruction_source_fk, i.instruction_service_fk,
        i.manual_interventation_ind
),

dim_compensation_account as (
    select
        comp_acct.rk_account_pk                     as rk_account_pk,
        coalesce(comp_acct.bo_account_skey, -1)     as compensation_account_skey
    from
       curated_db.tbl_bo_account_dim comp_acct
),

dim_client_account as (
    select
        cli_acct.rk_account_pk                      as rk_account_pk,
        coalesce(cli_acct.bo_account_skey, -1)     as client_account_skey
    from
        curated_db.tbl_bo_account_dim cli_acct
),

dim_interest_facility as (
    select
        intfac.interest_facility_bid                        as interest_facility_bid,
        coalesce(intfac.bo_interest_facility_skey, -1)      as bo_interest_facility_skey
    from
       curated_db.tbl_bo_interest_facility_dim intfac
),

dim_instruction_source as (
    select
        instsrc.INSTRUCTION_SOURCE_BID                      AS instruction_source_bid,
        coalesce(instsrc.BO_INSTRUCTION_SOURCE_SKEY, -1)    as bo_instruction_source_skey
    from
       curated_db.tbl_bo_instruction_source_dim instsrc
),

dim_instruction_service as (
    select
        instsvc.instruction_srvc_bid                        as instruction_srvc_bid,
        coalesce(instsvc.bo_instruction_service_skey, -1)   as bo_instruction_service_skey
    from
       curated_db.tbl_bo_instruction_service_dim instsvc
),

dim_business_trans_status as (
    select
        code_table.code_pk                                      as code_pk,
        coalesce(trans_status.bo_bus_trans_status_skey, -1)     as bo_bus_trans_status_skey
    from
        raw_db.corporate_code_table code_table join raw_db.corporate_code_category_table code_cat_table
            on code_table.code_category_fk = code_cat_table.code_category_pk
        join curated_db.tbl_bo_bus_trans_status_dim trans_status
            on code_table.code_constant_id = trans_status.bus_trans_status_bid
    where
        upper(code_cat_table.attribute_en_name) = 'BUSTRANSSTAT'
),

dim_business_trans_type as (
    select
        code_table.code_pk                                  as code_pk,
        coalesce(trans_type.bo_bus_trans_type_skey, -1)     as bo_bus_trans_type_skey
    from
       raw_db.corporate_code_table code_table join raw_db.corporate_code_category_table code_cat_table
            on code_table.code_category_fk = code_cat_table.code_category_pk
        join curated_db.tbl_bo_bus_trans_type_dim  trans_type
            on code_table.code_constant_id = trans_type.bus_trans_type_bid
    where
        UPPER(code_cat_table.attribute_en_name) = 'BUSTRANSTYPE'
),

dim_interest_bus_trans_ind as (
    select
        ind.confirmation_ind                                as confirmation_ind,
        ind.override_ind                                    as override_ind,
        ind.status_override_ind                             as status_override_ind,
        ind.was_in_repair_ind                               as was_in_repair_ind,
        ind.manual_intervention_ind                         as manual_intervention_ind,
        coalesce(ind.bo_interest_bus_trans_ind_skey, -1)    as bo_interest_bus_trans_ind_skey
    from
       curated_db.tbl_bo_interest_bus_trans_ind_dim ind
),

dim_global_legal_entity as (
    select
        trim(leading '0' from trim(trailing '.' from CAST(gle.client_id as string)))    as client_id,
        coalesce(gle.global_legal_entity_skey, -1)                                      as global_legal_entity_skey
    from
        view_db.vwu_global_legal_entity_dim gle
)

INSERT INTO curated_db.tbl_bo_interest_bus_trans_fact
(
    client_gle_skey,				business_value_dt,			client_account_skey,            compensation_account_skey,  instruction_source_skey,	instruction_service_skey,       bo_bus_trans_type_skey, 	bo_bus_trans_status_skey,	    bo_interest_facility_skey,  bo_interest_bus_trans_ind_skey,
    rk_habs_business_trans_pk,	    src_reference_num,          payment_direction,			    instruction_end_time,		narrative_desc,
    authorizing_user_name,			application_user_name,		application_update_timestamp,   audit_creation_user,		audit_creation_date,
    audit_last_update_user,         audit_last_update_date,     md_create_ts,   				md_last_update_ts,          md_chksum,
    md_workflow_execution_skey,	    md_system_skey,             md_data_load_method_skey,		business_value_amt,			audit_load_id,
    audit_create_ts,				audit_last_update_ts
)

select
    gle.global_legal_entity_skey                        as client_gle_skey,
    s.business_value_dt                                 as business_value_dt,
    cli_acct.client_account_skey                        as client_account_skey,
    comp_acct.compensation_account_skey                 as compensation_account_skey,
    instsrc.BO_INSTRUCTION_SOURCE_SKEY                  as instruction_source_skey,
    instsvc.bo_instruction_service_skey                 as instruction_service_skey,
    bttype.bo_bus_trans_type_skey                       as bo_bus_trans_type_skey,
    btstat.bo_bus_trans_status_skey                     as bo_bus_trans_status_skey,
    intfac.bo_interest_facility_skey                    as bo_interest_facility_skey,
    ind.bo_interest_bus_trans_ind_skey                  as bo_interest_bus_trans_ind_skey,
    s.rk_habs_business_trans_pk                         as rk_habs_business_trans_pk,
    s.src_reference_num                                 as src_reference_num,
    s.payment_direction                                 as payment_direction,
    s.instruction_end_time                              as instruction_end_time,
    s.narrative_desc                                    as narrative_desc,
    s.authorizing_user_name                             as authorizing_user_name,
    s.application_user_name                             as application_user_name,
    s.application_update_timestamp                      as application_update_timestamp,
    s.audit_creation_user                               as audit_creation_user,
    s.audit_creation_date                               as audit_creation_date,
    s.audit_last_update_user                            as audit_last_update_user,
    s.audit_last_update_date                            as audit_last_update_date,
    null                                                as md_create_ts,
    null                                                as md_last_update_ts,
    null                                                as md_chksum,
    null                                                as md_workflow_execution_skey,
    null                                                as md_system_skey,
    null                                                as md_data_load_method_skey,
    s.business_value_amt                                as business_value_amt,
    {job_run_id}                                        as audit_load_id,
    current_timestamp()                                 as audit_create_ts,
    current_timestamp()                                 as audit_last_update_ts
from
    src s left join dim_compensation_account comp_acct
        on s.compensation_account_fk = comp_acct.rk_account_pk
    left join dim_client_account cli_acct
        on s.client_account_fk      = cli_acct.rk_account_pk
    left join dim_interest_facility intfac
        on s.interest_facility_fk   = intfac.interest_facility_bid
    left join dim_instruction_source instsrc
        on s.instruction_source_fk  = instsrc.INSTRUCTION_SOURCE_BID
    left join dim_instruction_service instsvc
        on s.instruction_service_fk = instsvc.instruction_srvc_bid
    left join dim_business_trans_status btstat
        on s.business_trans_status_fk = btstat.code_pk
    left join dim_business_trans_type bttype
        on s.business_trans_type_fk   = bttype.code_pk
    left join dim_interest_bus_trans_ind ind
       on  s.confirmation_ind        <=> ind.confirmation_ind
       and s.override_ind            <=> ind.override_ind
       and s.status_override_ind     <=> ind.status_override_ind
       and s.was_in_repair_ind       <=> ind.was_in_repair_ind
       and s.manual_intervention_ind <=> ind.manual_intervention_ind
    left join dim_global_legal_entity gle
        on s.client_id = gle.client_id
"""

logger.info("Executing INSERT for curated_db.TBL_BO_INTEREST_BUS_TRANS_FACT")
logger.info(sql)
spark.sql(sql)

logger.info("Completed TBL_BO_INTEREST_BUS_TRANS_FACT build")