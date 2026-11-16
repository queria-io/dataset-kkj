{# 入札公告 1 件 1 行。今回取り直した公告日の行は、前回の行を消して今回の行で置き換える。
   ポータルは登録後に公告のキーを振り直すことがある（2023-11 の国土地理院など）ので、
   キーではなく公告日で置き換える。取り直していない公告日の行はそのまま残す。 #}
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='cft_issue_date') }}

with notices as (
    select *
    from {{ ref('stg_notices') }}
    -- 同じ公告が隣の日のファイルにも出たときは 1 行にする
    qualify row_number() over (partition by notice_key order by cft_issue_datetime desc) = 1
)

select * exclude (cft_issue_datetime, file_date)
from notices
-- 取り直した最初の日より前の公告日は、その日の公告を全部は取っていない。置き換えると残りが消えるので入れない
where cft_issue_date >= (select min(file_date) from notices)
{% if is_incremental() %}
    -- 公告日が変わって置き換える範囲の外に前の行が残る公告は、前の行を残す（notice_key を重ねない）
    and notice_key not in (
        select notice_key from {{ this }} where cft_issue_date < (select min(file_date) from notices)
    )
{% endif %}
order by cft_issue_date, notice_key
