{# 入札公告 1 件 1 行。取ったファイルのうち、まだ無い公告だけを追記する。
   公告の中身は登録後に変わらない前提で、前回の行は書き換えない。 #}
{{ config(materialized='incremental', incremental_strategy='append') }}

with raw as (
    select *
    from read_json(
        'data/kkj/notices/*.ndjson.gz',
        format = 'newline_delimited',
        columns = {
            Key: 'VARCHAR', ExternalDocumentURI: 'VARCHAR', ProjectName: 'VARCHAR', Date: 'VARCHAR',
            FileType: 'VARCHAR', FileSize: 'VARCHAR', LgCode: 'VARCHAR', PrefectureName: 'VARCHAR',
            CityCode: 'VARCHAR', CityName: 'VARCHAR', Certification: 'VARCHAR', OrganizationName: 'VARCHAR',
            CftIssueDate: 'VARCHAR', PeriodEndTime: 'VARCHAR', Category: 'VARCHAR', ProcedureType: 'VARCHAR',
            Location: 'VARCHAR', TenderSubmissionDeadline: 'VARCHAR', OpeningTendersEvent: 'VARCHAR',
            ItemCode: 'VARCHAR', ProjectDescription: 'VARCHAR',
            Attachments: 'STRUCT(name VARCHAR, uri VARCHAR)[]', fetched_at: 'VARCHAR'
        }
    )
    -- 同じ公告が隣の日のファイルにも出たときは 1 行にする
    qualify row_number() over (partition by Key order by CftIssueDate desc) = 1
)

select
    Key as notice_key,
    ProjectName as project_name,
    OrganizationName as organization_name,
    nullif(lpad(LgCode, 2, '0'), '00') as prefecture_code,
    PrefectureName as prefecture_name,
    CityCode as lg_code,
    left(CityCode, 5) as city_code,
    CityName as city_name,
    Category as category,
    ProcedureType as procedure_type,
    string_split(nullif(trim(Certification), ''), ' ') as certifications,
    Location as location,
    ItemCode as item_code,
    cast(left(CftIssueDate, 10) as date) as cft_issue_date,
    cast(left(TenderSubmissionDeadline, 10) as date) as tender_submission_date,
    cast(left(OpeningTendersEvent, 10) as date) as opening_tenders_date,
    cast(left(PeriodEndTime, 10) as date) as period_end_date,
    ProjectDescription as description,
    ExternalDocumentURI as document_url,
    FileType as file_type,
    try_cast(FileSize as bigint) as file_size,
    Attachments as attachments,
    cast(Date as timestamptz) as crawled_at,
    cast(fetched_at as timestamptz) as fetched_at
from raw
{% if is_incremental() %}
where Key not in (select notice_key from {{ this }})
{% endif %}
order by cft_issue_date, notice_key
