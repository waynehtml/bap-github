create or replace view view_db.vwu_bo_business_day_dim
as


    select 
        occurrence                                          as date_id,
    case when 
        banking_operation_holiday = true then 'No'
        else 'Yes'  end                                     as business_day_en_ic
    from 
        {ref_catalog}.curated_db.tbl_itm_holiday_calendar
    where 
        year_nb >= year(getdate())
        and Holiday_country='CA' 
        and weekday = true
        and banking_operation_holiday = true