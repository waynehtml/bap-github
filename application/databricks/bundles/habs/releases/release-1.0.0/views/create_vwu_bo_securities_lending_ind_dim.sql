create or replace view view_db.vwu_bo_securities_lending_ind_dim
as
select * from curated_db.tbl_bo_securities_lending_ind_dim
;