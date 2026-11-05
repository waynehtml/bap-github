catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_gov_bank_category_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_gov_bank_category_dim as tgt
using (
    with gov_bank_category_code as (
        select
            a.code_pk,
            a.code_constant_id,
            a.attribute_en_name,
            a.attribute_fr_name,
            a.attribute_en_desc,
            a.attribute_fr_desc
        from raw_db.corporate_code_table as a
        inner join raw_db.corporate_code_category_table as b
            on a.code_category_fk = b.code_category_pk
        where b.attribute_en_name = 'GOVBANKCAT'
    ),
    reporting_category_code as (
        select
            a.code_pk,
            a.code_constant_id,
            a.attribute_en_name,
            a.attribute_fr_name,
            a.attribute_en_desc,
            a.attribute_fr_desc
        from raw_db.corporate_code_table as a
        inner join raw_db.corporate_code_category_table as b
            on a.code_category_fk = b.code_category_pk
        where b.attribute_en_name = 'REPORTINGCATEGORY'
    ),
    ship_content_type_code as (
        select
            a.code_pk,
            a.code_constant_id,
            a.attribute_en_name,
            a.attribute_fr_name,
            a.attribute_en_desc,
            a.attribute_fr_desc
        from raw_db.corporate_code_table as a
        inner join raw_db.corporate_code_category_table as b
            on a.code_category_fk = b.code_category_pk
        where b.attribute_en_name = 'SHIPCONTTYPE'
    ),
    reconciliation_unit_code as (
        select
            a.code_pk,
            a.code_constant_id,
            a.attribute_en_name,
            a.attribute_fr_name,
            a.attribute_en_desc,
            a.attribute_fr_desc
        from raw_db.corporate_code_table as a
        inner join raw_db.corporate_code_category_table as b
            on a.code_category_fk = b.code_category_pk
        where b.attribute_en_name = 'RECONUNIT'
    )
    select
        gov.code_constant_id as gov_bank_category_bid,
        gov.attribute_en_name as gov_bank_category_short_en_nm,
        gov.attribute_fr_name as gov_bank_category_short_fr_nm,
        gov.attribute_en_desc as gov_bank_category_long_en_nm,
        gov.attribute_fr_desc as gov_bank_category_long_fr_nm,
        gov.attribute_en_desc as gov_bank_category_en_desc,
        gov.attribute_fr_desc as gov_bank_category_fr_desc,
        reporting.code_constant_id as reporting_category_bid,
        reporting.attribute_en_name as reporting_category_short_en_nm,
        reporting.attribute_fr_name as reporting_category_short_fr_nm,
        reporting.attribute_en_desc as reporting_category_long_en_nm,
        reporting.attribute_fr_desc as reporting_category_long_fr_nm,
        reporting.attribute_en_desc as reporting_category_en_desc,
        reporting.attribute_fr_desc as reporting_category_fr_desc,
        ship_content.code_constant_id as ship_content_type_bid,
        ship_content.attribute_en_name as ship_content_type_short_en_nm,
        ship_content.attribute_fr_name as ship_content_type_short_fr_nm,
        ship_content.attribute_en_desc as ship_content_type_long_en_nm,
        ship_content.attribute_fr_desc as ship_content_type_long_fr_nm,
        ship_content.attribute_en_desc as ship_content_type_en_desc,
        ship_content.attribute_fr_desc as ship_content_type_fr_desc,
        recon.code_constant_id as recon_unit_bid,
        recon.attribute_en_name as recon_unit_short_en_nm,
        recon.attribute_fr_name as recon_unit_short_fr_nm,
        recon.attribute_en_desc as recon_unit_long_en_nm,
        recon.attribute_fr_desc as recon_unit_long_fr_nm,
        recon.attribute_en_desc as recon_unit_en_desc,
        recon.attribute_fr_desc as recon_unit_fr_desc
    from raw_db.habs_government_banking_category as gbc
    left join gov_bank_category_code as gov
        on gbc.gov_banking_cat_pk = gov.code_pk
    left join reporting_category_code as reporting
        on gbc.reporting_category_fk = reporting.code_pk
    left join ship_content_type_code as ship_content
        on gbc.shipment_content_type_fk = ship_content.code_pk
    left join reconciliation_unit_code as recon
        on gbc.reconciliation_unit_fk = recon.code_pk
) as src
on tgt.gov_bank_category_bid = src.gov_bank_category_bid

when matched and (
    not (tgt.gov_bank_category_short_en_nm <=> src.gov_bank_category_short_en_nm)
    or not (tgt.gov_bank_category_short_fr_nm <=> src.gov_bank_category_short_fr_nm)
    or not (tgt.gov_bank_category_long_en_nm <=> src.gov_bank_category_long_en_nm)
    or not (tgt.gov_bank_category_long_fr_nm <=> src.gov_bank_category_long_fr_nm)
    or not (tgt.gov_bank_category_en_desc <=> src.gov_bank_category_en_desc)
    or not (tgt.gov_bank_category_fr_desc <=> src.gov_bank_category_fr_desc)
    or not (tgt.reporting_category_bid <=> src.reporting_category_bid)
    or not (tgt.reporting_category_short_en_nm <=> src.reporting_category_short_en_nm)
    or not (tgt.reporting_category_short_fr_nm <=> src.reporting_category_short_fr_nm)
    or not (tgt.reporting_category_long_en_nm <=> src.reporting_category_long_en_nm)
    or not (tgt.reporting_category_long_fr_nm <=> src.reporting_category_long_fr_nm)
    or not (tgt.reporting_category_en_desc <=> src.reporting_category_en_desc)
    or not (tgt.reporting_category_fr_desc <=> src.reporting_category_fr_desc)
    or not (tgt.ship_content_type_bid <=> src.ship_content_type_bid)
    or not (tgt.ship_content_type_short_en_nm <=> src.ship_content_type_short_en_nm)
    or not (tgt.ship_content_type_short_fr_nm <=> src.ship_content_type_short_fr_nm)
    or not (tgt.ship_content_type_long_en_nm <=> src.ship_content_type_long_en_nm)
    or not (tgt.ship_content_type_long_fr_nm <=> src.ship_content_type_long_fr_nm)
    or not (tgt.ship_content_type_en_desc <=> src.ship_content_type_en_desc)
    or not (tgt.ship_content_type_fr_desc <=> src.ship_content_type_fr_desc)
    or not (tgt.recon_unit_bid <=> src.recon_unit_bid)
    or not (tgt.recon_unit_short_en_nm <=> src.recon_unit_short_en_nm)
    or not (tgt.recon_unit_short_fr_nm <=> src.recon_unit_short_fr_nm)
    or not (tgt.recon_unit_long_en_nm <=> src.recon_unit_long_en_nm)
    or not (tgt.recon_unit_long_fr_nm <=> src.recon_unit_long_fr_nm)
    or not (tgt.recon_unit_en_desc <=> src.recon_unit_en_desc)
    or not (tgt.recon_unit_fr_desc <=> src.recon_unit_fr_desc)
) then update set
    gov_bank_category_short_en_nm = src.gov_bank_category_short_en_nm,
    gov_bank_category_short_fr_nm = src.gov_bank_category_short_fr_nm,
    gov_bank_category_long_en_nm = src.gov_bank_category_long_en_nm,
    gov_bank_category_long_fr_nm = src.gov_bank_category_long_fr_nm,
    gov_bank_category_en_desc = src.gov_bank_category_en_desc,
    gov_bank_category_fr_desc = src.gov_bank_category_fr_desc,
    reporting_category_bid = src.reporting_category_bid,
    reporting_category_short_en_nm = src.reporting_category_short_en_nm,
    reporting_category_short_fr_nm = src.reporting_category_short_fr_nm,
    reporting_category_long_en_nm = src.reporting_category_long_en_nm,
    reporting_category_long_fr_nm = src.reporting_category_long_fr_nm,
    reporting_category_en_desc = src.reporting_category_en_desc,
    reporting_category_fr_desc = src.reporting_category_fr_desc,
    ship_content_type_bid = src.ship_content_type_bid,
    ship_content_type_short_en_nm = src.ship_content_type_short_en_nm,
    ship_content_type_short_fr_nm = src.ship_content_type_short_fr_nm,
    ship_content_type_long_en_nm = src.ship_content_type_long_en_nm,
    ship_content_type_long_fr_nm = src.ship_content_type_long_fr_nm,
    ship_content_type_en_desc = src.ship_content_type_en_desc,
    ship_content_type_fr_desc = src.ship_content_type_fr_desc,
    recon_unit_bid = src.recon_unit_bid,
    recon_unit_short_en_nm = src.recon_unit_short_en_nm,
    recon_unit_short_fr_nm = src.recon_unit_short_fr_nm,
    recon_unit_long_en_nm = src.recon_unit_long_en_nm,
    recon_unit_long_fr_nm = src.recon_unit_long_fr_nm,
    recon_unit_en_desc = src.recon_unit_en_desc,
    recon_unit_fr_desc = src.recon_unit_fr_desc,
    audit_load_id = {job_run_id},
    audit_last_update_ts = current_timestamp()

when not matched then insert (
    gov_bank_category_bid,
    gov_bank_category_short_en_nm,
    gov_bank_category_short_fr_nm,
    gov_bank_category_long_en_nm,
    gov_bank_category_long_fr_nm,
    gov_bank_category_en_desc,
    gov_bank_category_fr_desc,
    reporting_category_bid,
    reporting_category_short_en_nm,
    reporting_category_short_fr_nm,
    reporting_category_long_en_nm,
    reporting_category_long_fr_nm,
    reporting_category_en_desc,
    reporting_category_fr_desc,
    ship_content_type_bid,
    ship_content_type_short_en_nm,
    ship_content_type_short_fr_nm,
    ship_content_type_long_en_nm,
    ship_content_type_long_fr_nm,
    ship_content_type_en_desc,
    ship_content_type_fr_desc,
    recon_unit_bid,
    recon_unit_short_en_nm,
    recon_unit_short_fr_nm,
    recon_unit_long_en_nm,
    recon_unit_long_fr_nm,
    recon_unit_en_desc,
    recon_unit_fr_desc,
    md_current_ind,
    md_eff_ts,
    md_exp_ts,
    md_workflow_execution_skey,
    md_exp_workflow_execution_skey,
    md_create_ts,
    md_last_update_ts,
    audit_load_id,
    audit_create_ts,
    audit_last_update_ts
) values (
    src.gov_bank_category_bid,
    src.gov_bank_category_short_en_nm,
    src.gov_bank_category_short_fr_nm,
    src.gov_bank_category_long_en_nm,
    src.gov_bank_category_long_fr_nm,
    src.gov_bank_category_en_desc,
    src.gov_bank_category_fr_desc,
    src.reporting_category_bid,
    src.reporting_category_short_en_nm,
    src.reporting_category_short_fr_nm,
    src.reporting_category_long_en_nm,
    src.reporting_category_long_fr_nm,
    src.reporting_category_en_desc,
    src.reporting_category_fr_desc,
    src.ship_content_type_bid,
    src.ship_content_type_short_en_nm,
    src.ship_content_type_short_fr_nm,
    src.ship_content_type_long_en_nm,
    src.ship_content_type_long_fr_nm,
    src.ship_content_type_en_desc,
    src.ship_content_type_fr_desc,
    src.recon_unit_bid,
    src.recon_unit_short_en_nm,
    src.recon_unit_short_fr_nm,
    src.recon_unit_long_en_nm,
    src.recon_unit_long_fr_nm,
    src.recon_unit_en_desc,
    src.recon_unit_fr_desc,
    1,
    current_timestamp(),
    timestamp('9999-12-31 00:00:00'),
    0,
    0,
    current_timestamp(),
    current_timestamp(),
    {job_run_id},
    current_timestamp(),
    current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_gov_bank_category_dim")
logger.info(sql)
spark.sql(sql)

spark.sql("""
update curated_db.tbl_bo_gov_bank_category_dim
set bo_gov_bank_category_dkey = bo_gov_bank_category_skey
where bo_gov_bank_category_dkey is null
""")

logger.info("Completed tbl_bo_gov_bank_category_dim build")
