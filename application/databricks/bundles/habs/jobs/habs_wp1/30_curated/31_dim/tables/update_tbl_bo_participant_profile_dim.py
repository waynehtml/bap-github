catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_participant_profile_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_participant_profile_dim as tgt
using (
    select
        cast(pp.participant_profile_pk as string) as participant_profile_bid
        , pp.alias_name as alias_name
        , cast(pg.participation_group_pk as string) as prtcpnt_group_bid
        , pg.participation_group_en_name as prtcpnt_group_short_en_nm
        , pg.participation_group_fr_name as prtcpnt_group_short_fr_nm
        , pg.participation_group_en_desc as prtcpnt_group_long_en_nm
        , pg.participation_group_fr_desc as prtcpnt_group_long_fr_nm
        , pg.participation_group_en_desc as prtcpnt_group_en_desc
        , pg.participation_group_fr_desc as prtcpnt_group_fr_desc
        , ppct.code_constant_id as prtcpnt_prof_type_bid
        , ppct.attribute_en_name as prtcpnt_prof_type_short_en_nm
        , ppct.attribute_fr_name as prtcpnt_prof_type_short_fr_nm
        , ppct.attribute_en_desc as prtcpnt_prof_type_long_en_nm
        , ppct.attribute_fr_desc as prtcpnt_prof_type_long_fr_nm
        , ppct.attribute_en_desc as prtcpnt_prof_type_en_desc
        , ppct.attribute_fr_desc as prtcpnt_prof_type_fr_desc
        , ppst.code_constant_id as prtcpnt_prof_stat_bid
        , ppst.attribute_en_name as prtcpnt_prof_stat_short_en_nm
        , ppst.attribute_fr_name as prtcpnt_prof_stat_short_fr_nm
        , ppst.attribute_en_desc as prtcpnt_prof_stat_long_en_nm
        , ppst.attribute_fr_desc as prtcpnt_prof_stat_long_fr_nm
        , ppst.attribute_en_desc as prtcpnt_prof_stat_en_desc
        , ppst.attribute_fr_desc as prtcpnt_prof_stat_fr_desc
        , pp.inactive_date as inactive_date
        , pp.effective_date as effective_date
    from raw_db.habs_participant_profile pp
    join raw_db.habs_participation_group pg
        on pp.participation_group_fk = pg.participation_group_pk
    join raw_db.corporate_code_table ppct
        on ppct.code_pk = pp.participant_profile_type_fk
    join raw_db.corporate_code_table ppst
        on ppst.code_pk = pp.participant_profile_status_fk
) as src
on tgt.participant_profile_bid = src.PARTICIPANT_PROFILE_BID

when matched and (
    not (tgt.alias_name <=> src.ALIAS_NAME)
    or not (tgt.prtcpnt_group_bid <=> src.PRTCPNT_GROUP_BID)
    or not (tgt.prtcpnt_group_short_en_nm <=> src.PRTCPNT_GROUP_SHORT_EN_NM)
    or not (tgt.prtcpnt_group_short_fr_nm <=> src.PRTCPNT_GROUP_SHORT_FR_NM)
    or not (tgt.prtcpnt_group_long_en_nm <=> src.PRTCPNT_GROUP_LONG_EN_NM)
    or not (tgt.prtcpnt_group_long_fr_nm <=> src.PRTCPNT_GROUP_LONG_FR_NM)
    or not (tgt.prtcpnt_group_en_desc <=> src.PRTCPNT_GROUP_EN_DESC)
    or not (tgt.prtcpnt_group_fr_desc <=> src.PRTCPNT_GROUP_FR_DESC)
    or not (tgt.prtcpnt_prof_type_bid <=> src.PRTCPNT_PROF_TYPE_BID)
    or not (tgt.prtcpnt_prof_type_short_en_nm <=> src.PRTCPNT_PROF_TYPE_SHORT_EN_NM)
    or not (tgt.prtcpnt_prof_type_short_fr_nm <=> src.PRTCPNT_PROF_TYPE_SHORT_FR_NM)
    or not (tgt.prtcpnt_prof_type_long_en_nm <=> src.PRTCPNT_PROF_TYPE_LONG_EN_NM)
    or not (tgt.prtcpnt_prof_type_long_fr_nm <=> src.PRTCPNT_PROF_TYPE_LONG_FR_NM)
    or not (tgt.prtcpnt_prof_type_en_desc <=> src.PRTCPNT_PROF_TYPE_EN_DESC)
    or not (tgt.prtcpnt_prof_type_fr_desc <=> src.PRTCPNT_PROF_TYPE_FR_DESC)
    or not (tgt.prtcpnt_prof_stat_bid <=> src.PRTCPNT_PROF_STAT_BID)
    or not (tgt.prtcpnt_prof_stat_short_en_nm <=> src.PRTCPNT_PROF_STAT_SHORT_EN_NM)
    or not (tgt.prtcpnt_prof_stat_short_fr_nm <=> src.PRTCPNT_PROF_STAT_SHORT_FR_NM)
    or not (tgt.prtcpnt_prof_stat_long_en_nm <=> src.PRTCPNT_PROF_STAT_LONG_EN_NM)
    or not (tgt.prtcpnt_prof_stat_long_fr_nm <=> src.PRTCPNT_PROF_STAT_LONG_FR_NM)
    or not (tgt.prtcpnt_prof_stat_en_desc <=> src.PRTCPNT_PROF_STAT_EN_DESC)
    or not (tgt.prtcpnt_prof_stat_fr_desc <=> src.PRTCPNT_PROF_STAT_FR_DESC)
    or not (tgt.inactive_date <=> src.INACTIVE_DATE)
    or not (tgt.effective_date <=> src.EFFECTIVE_DATE)
)
then update set
    alias_name = src.ALIAS_NAME
    , prtcpnt_group_bid = src.PRTCPNT_GROUP_BID
    , prtcpnt_group_short_en_nm = src.PRTCPNT_GROUP_SHORT_EN_NM
    , prtcpnt_group_short_fr_nm = src.PRTCPNT_GROUP_SHORT_FR_NM
    , prtcpnt_group_long_en_nm = src.PRTCPNT_GROUP_LONG_EN_NM
    , prtcpnt_group_long_fr_nm = src.PRTCPNT_GROUP_LONG_FR_NM
    , prtcpnt_group_en_desc = src.PRTCPNT_GROUP_EN_DESC
    , prtcpnt_group_fr_desc = src.PRTCPNT_GROUP_FR_DESC
    , prtcpnt_prof_type_bid = src.PRTCPNT_PROF_TYPE_BID
    , prtcpnt_prof_type_short_en_nm = src.PRTCPNT_PROF_TYPE_SHORT_EN_NM
    , prtcpnt_prof_type_short_fr_nm = src.PRTCPNT_PROF_TYPE_SHORT_FR_NM
    , prtcpnt_prof_type_long_en_nm = src.PRTCPNT_PROF_TYPE_LONG_EN_NM
    , prtcpnt_prof_type_long_fr_nm = src.PRTCPNT_PROF_TYPE_LONG_FR_NM
    , prtcpnt_prof_type_en_desc = src.PRTCPNT_PROF_TYPE_EN_DESC
    , prtcpnt_prof_type_fr_desc = src.PRTCPNT_PROF_TYPE_FR_DESC
    , prtcpnt_prof_stat_bid = src.PRTCPNT_PROF_STAT_BID
    , prtcpnt_prof_stat_short_en_nm = src.PRTCPNT_PROF_STAT_SHORT_EN_NM
    , prtcpnt_prof_stat_short_fr_nm = src.PRTCPNT_PROF_STAT_SHORT_FR_NM
    , prtcpnt_prof_stat_long_en_nm = src.PRTCPNT_PROF_STAT_LONG_EN_NM
    , prtcpnt_prof_stat_long_fr_nm = src.PRTCPNT_PROF_STAT_LONG_FR_NM
    , prtcpnt_prof_stat_en_desc = src.PRTCPNT_PROF_STAT_EN_DESC
    , prtcpnt_prof_stat_fr_desc = src.PRTCPNT_PROF_STAT_FR_DESC
    , inactive_date = src.INACTIVE_DATE
    , effective_date = src.EFFECTIVE_DATE
    , audit_load_id = {job_run_id}
    , audit_last_update_ts = current_timestamp()

when not matched then
insert (
    participant_profile_bid
    , alias_name
    , prtcpnt_group_bid
    , prtcpnt_group_short_en_nm
    , prtcpnt_group_short_fr_nm
    , prtcpnt_group_long_en_nm
    , prtcpnt_group_long_fr_nm
    , prtcpnt_group_en_desc
    , prtcpnt_group_fr_desc
    , prtcpnt_prof_type_bid
    , prtcpnt_prof_type_short_en_nm
    , prtcpnt_prof_type_short_fr_nm
    , prtcpnt_prof_type_long_en_nm
    , prtcpnt_prof_type_long_fr_nm
    , prtcpnt_prof_type_en_desc
    , prtcpnt_prof_type_fr_desc
    , prtcpnt_prof_stat_bid
    , prtcpnt_prof_stat_short_en_nm
    , prtcpnt_prof_stat_short_fr_nm
    , prtcpnt_prof_stat_long_en_nm
    , prtcpnt_prof_stat_long_fr_nm
    , prtcpnt_prof_stat_en_desc
    , prtcpnt_prof_stat_fr_desc
    , inactive_date
    , effective_date
    , audit_load_id
    , audit_last_update_ts
)
values (
    src.PARTICIPANT_PROFILE_BID
    , src.ALIAS_NAME
    , src.PRTCPNT_GROUP_BID
    , src.PRTCPNT_GROUP_SHORT_EN_NM
    , src.PRTCPNT_GROUP_SHORT_FR_NM
    , src.PRTCPNT_GROUP_LONG_EN_NM
    , src.PRTCPNT_GROUP_LONG_FR_NM
    , src.PRTCPNT_GROUP_EN_DESC
    , src.PRTCPNT_GROUP_FR_DESC
    , src.PRTCPNT_PROF_TYPE_BID
    , src.PRTCPNT_PROF_TYPE_SHORT_EN_NM
    , src.PRTCPNT_PROF_TYPE_SHORT_FR_NM
    , src.PRTCPNT_PROF_TYPE_LONG_EN_NM
    , src.PRTCPNT_PROF_TYPE_LONG_FR_NM
    , src.PRTCPNT_PROF_TYPE_EN_DESC
    , src.PRTCPNT_PROF_TYPE_FR_DESC
    , src.PRTCPNT_PROF_STAT_BID
    , src.PRTCPNT_PROF_STAT_SHORT_EN_NM
    , src.PRTCPNT_PROF_STAT_SHORT_FR_NM
    , src.PRTCPNT_PROF_STAT_LONG_EN_NM
    , src.PRTCPNT_PROF_STAT_LONG_FR_NM
    , src.PRTCPNT_PROF_STAT_EN_DESC
    , src.PRTCPNT_PROF_STAT_FR_DESC
    , src.INACTIVE_DATE
    , src.EFFECTIVE_DATE
    , {job_run_id}
    , current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_participant_profile_dim")
logger.info(sql)
spark.sql(sql)

sql = """
update curated_db.tbl_bo_participant_profile_dim
set bo_participant_profile_dkey = bo_participant_profile_skey
where bo_participant_profile_dkey is null
"""
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_participant_profile_dim build")
