{# 入札公告 1 件 1 行。取ったファイルのうち、まだ無い公告だけを追記する。
   公告の中身は登録後に変わらない前提で、前回の行は書き換えない。 #}
{{ config(materialized='incremental', incremental_strategy='append') }}

with notices as (
    select *
    from {{ ref('stg_notices') }}
    -- 同じ公告が隣の日のファイルにも出たときは 1 行にする
    qualify row_number() over (partition by notice_key order by cft_issue_datetime desc) = 1
)

select * exclude (cft_issue_datetime)
from notices
{% if is_incremental() %}
where notice_key not in (select notice_key from {{ this }})
{% endif %}
order by cft_issue_date, notice_key
