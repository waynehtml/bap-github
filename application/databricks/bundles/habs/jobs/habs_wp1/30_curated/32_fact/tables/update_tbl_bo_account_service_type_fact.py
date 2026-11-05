catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting TBL_BO_ACCOUNT_SERVICE_TYPE_FACT build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = """
select coalesce(max(creation_date), timestamp '1900-01-01 00:00:00') as max_date
from curated_db.tbl_bo_account_service_type_fact
"""

row = spark.sql(sql).first()
last_process_ts= row["max_date"]

sql = f"""

with source_account_service as (
    select
        ac.account_pk                                       as account_pk,
        ac.account_id                                       as account_id,
        cast(cl.client_id as string)                        as client_id,
        cl.client_pk                                        as client_pk,
        cl.swiftbic_code                                    as swiftbic_code,
        wg.swiftbic_code                                    as swiftbic_code_11,
        upper(replace(sertype.code_constant_id, ' ', ''))   as service_type,
        upper(replace(serfreq.attribute_en_desc, ' ', ''))  as service_frequency,
        upper(replace(sermeth.attribute_en_desc, ' ', ''))  as service_method,
        upper(replace(intfac.attribute_en_desc, ' ', ''))   as interest_facility,
        case
            when trim(cast(ac.balance_maint_ind as string)) = '' then '-1'
            else cast(ac.balance_maint_ind as string)
        end                                                 as balance_maint_ind,
        case
            when trim(cast(ac.stand_trans_proc_ind as string)) = '' then '-1'
            else cast(ac.stand_trans_proc_ind as string)
            end                                            as stand_trans_proc_ind,
        case
            when trim(cast(ac.respect_payment_ind as string)) = '' then '-1'
            else cast(ac.respect_payment_ind as string)
        end                                                 as respect_payment_ind,
        case
            when trim(cast(ac.balance_override_ind as string)) = '' then '-1'
            else cast(ac.balance_override_ind as string)
        end                                                 as balance_override_ind,
        case
            when trim(cast(ac.credit_line_fac_ind as string)) = '' then '-1'
            else cast(ac.credit_line_fac_ind as string)
        end                                                 as credit_line_fac_ind,
        case
            when trim(cast(ac.has_ever_been_activated_ind as string)) = '' then '-1'
            else cast(ac.has_ever_been_activated_ind as string)
        end                                                 as has_ever_been_activated_ind,
        ac.creation_date                                    as creation_date,
        asr.comp_account_fk                                 as comp_account_fk
    from
        raw_db.habs_account ac left join raw_db.habs_org org on org.org_pk = ac.client_fk
        left join raw_db.habs_client cl on cl.client_pk = ac.client_fk
        left join raw_db.corporate_code_table actype on actype.code_pk = ac.account_type_fk
        left join raw_db.corporate_code_table acform on acform.code_pk = ac.account_format_fk
        left join raw_db.corporate_code_table gl on gl.code_pk = ac.gl_category_fk
        left join raw_db.corporate_code_table acstatus on acstatus.code_pk = ac.account_status_fk
        left join raw_db.corporate_code_table class on class.code_pk = cl.client_class_fk
        left join raw_db.corporate_code_table clstat on clstat.code_pk = cl.client_status_fk
        left join raw_db.habs_account_service asr on asr.account_fk = ac.account_pk
        left join raw_db.corporate_code_table sertype on sertype.code_pk = asr.service_type_fk
        left join raw_db.corporate_code_table serfreq on serfreq.code_pk = asr.service_frequency_fk
        left join raw_db.corporate_code_table sermeth on sermeth.code_pk = asr.service_method_fk
        left join raw_db.corporate_code_table intfac on intfac.code_pk = asr.interest_facility_fk
        left join raw_db.habs_workgroup wg on wg.client_fk = ac.client_fk
    where
        wg.workgroup_id = 1
        and ac.creation_date > timestamp('{last_process_ts}')
),

dim_global_legal_entity as (
    select
        global_legal_entity_skey      as global_legal_entity_skey,
        cast(client_id as string)     as client_id,
        rk_habs_client_pk             as rk_habs_client_pk
    from
        view_db.vwu_global_legal_entity_dim
    where
        global_legal_entity_skey > 0
),

dim_account as (
    select
        rk_account_pk     as rk_account_pk,
        bo_account_skey   as bo_account_skey
    from
        curated_db.tbl_bo_account_dim
    where
        bo_account_skey > 0
),

dim_account_service_type as (
    select
        bo_account_service_type_skey                                as bo_account_service_type_skey,
        upper(replace(account_service_type_long_en_nm, ' ', ''))    as account_service_type_long_en_nm
    from
        curated_db.tbl_bo_account_service_type_dim
    where
        bo_account_service_type_skey > 0
),

dim_account_service_frequency as (
    select
        bo_account_service_frequency_skey                             as bo_account_service_frequency_skey,
        upper(replace(account_service_frequency_long_en_nm, ' ', '')) as account_service_frequency_long_en_nm
    from
        curated_db.tbl_bo_account_service_frequency_dim
    where
        bo_account_service_frequency_skey > 0
),

dim_account_service_method as (
    select
        bo_account_service_method_skey                              as bo_account_service_method_skey,
        upper(replace(account_service_method_long_en_nm, ' ', ''))  as account_service_method_long_en_nm
    from
        curated_db.tbl_bo_account_service_method_dim
    where
        bo_account_service_method_skey > 0
),

dim_account_interest_facility as (
    select
        bo_account_interest_facility_skey                             as bo_account_interest_facility_skey,
        upper(replace(account_interest_facility_long_en_nm, ' ', '')) as account_interest_facility_long_en_nm
    from
        curated_db.tbl_bo_account_interest_facility_dim
    where
        bo_account_interest_facility_skey > 0
),

dim_account_service_type_indicator as (
    select
        bo_account_service_type_ind_skey          as bo_account_service_type_ind_skey,
        concat(
            cast(balance_maint_ind as string),
            cast(balance_override_ind as string),
            cast(credit_line_fac_ind as string),
            cast(has_ever_been_activated_ind as string),
            cast(respect_payment_ind as string),
            cast(stand_trans_proc_ind as string)
        )                                       as service_indicator
    from
        curated_db.tbl_bo_account_service_type_ind_dim
)

insert into curated_db.tbl_bo_account_service_type_fact
(
  bo_account_skey,
  client_gle_skey,
  bo_account_service_type_skey,
  bo_account_service_frequency_skey,
  bo_account_service_method_skey,
  bo_account_interest_facility_skey,
  bo_account_service_type_ind_skey,
  bic6,
  bic8,
  bic11,
  creation_date,
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
        case
            when acct.bo_account_skey is null
                or acct.bo_account_skey = 0
            then -1
            else acct.bo_account_skey
        end                               as bo_account_skey,

        case
            when gle.global_legal_entity_skey is null
                or gle.global_legal_entity_skey = 0
            then -1
            else gle.global_legal_entity_skey
        end                                 as client_gle_skey,

        case
            when service_type.bo_account_service_type_skey is null
                or service_type.bo_account_service_type_skey = 0
            then -1
            else service_type.bo_account_service_type_skey
        end                                 as bo_account_service_type_skey,

        case
            when service_frequency.bo_account_service_frequency_skey is null
                or service_frequency.bo_account_service_frequency_skey = 0
            then -1
            else service_frequency.bo_account_service_frequency_skey
        end                                 as bo_account_service_frequency_skey,

        case
            when service_method.bo_account_service_method_skey is null
                or service_method.bo_account_service_method_skey = 0
            then -1
            else service_method.bo_account_service_method_skey
        end                                 as bo_account_service_method_skey,

        case
            when interest_facility.bo_account_interest_facility_skey is null
                or interest_facility.bo_account_interest_facility_skey = 0
            then -1
            else interest_facility.bo_account_interest_facility_skey
        end                                 as bo_account_interest_facility_skey,

        case
            when service_indicator.bo_account_service_type_ind_skey is null
                or service_indicator.bo_account_service_type_ind_skey = 0
            then -1
            else service_indicator.bo_account_service_type_ind_skey
        end                                 as bo_account_service_type_ind_skey,

        src.SWIFTBIC_CODE                   as bic6,
        substr(src.SWIFTBIC_CODE_11, 1, 8)  as bic8,
        src.SWIFTBIC_CODE_11                as bic11,
        src.CREATION_DATE                   as creation_date,
        null                                as md_create_ts,
        null                                as md_last_update_ts,
        null                                as md_workflow_execution_skey,
        null                                as md_system_skey,
        null                                as md_data_load_method_skey,
        'Daily ETL Load'                    as md_data_source_notes,
        null                                as md_chksum,
        {job_run_id}                        as audit_load_id,
        current_timestamp()                 as audit_create_ts,
        current_timestamp()                 as audit_last_update_ts
    from
        source_account_service src
        left join dim_global_legal_entity gle
            on src.CLIENT_ID = gle.client_id
        left join dim_account acct
            on src.ACCOUNT_PK = acct.rk_account_pk
        left join dim_account_service_type service_type
            on src.SERVICE_TYPE =
               service_type.account_service_type_long_en_nm
        left join dim_account_service_frequency service_frequency
            on src.SERVICE_FREQUENCY =
               service_frequency.account_service_frequency_long_en_nm
        left join dim_account_service_method service_method
            on src.SERVICE_METHOD =
               service_method.account_service_method_long_en_nm
        left join dim_account_interest_facility interest_facility
            on src.INTEREST_FACILITY =
               interest_facility.account_interest_facility_long_en_nm
        left join dim_account_service_type_indicator service_indicator
            on concat(
                src.BALANCE_MAINT_IND,
                src.BALANCE_OVERRIDE_IND,
                src.CREDIT_LINE_FAC_IND,
                src.HAS_EVER_BEEN_ACTIVATED_IND,
                src.RESPECT_PAYMENT_IND,
                src.STAND_TRANS_PROC_IND
            ) = service_indicator.service_indicator

"""

logger.info("Executing INSERT for curated_db.tbl_bo_account_service_type_fact")
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_account_service_type_fact build")
