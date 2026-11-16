{# 今回のビルドで検索 API から取った入札公告 (data/kkj/notices/*.ndjson.gz) を、取得したままの形で読む。
   同じ公告が隣の日のファイルにも出ることがある #}

select *
from read_json(
    'data/kkj/notices/*.ndjson.gz',
    format = 'newline_delimited',
    -- 添付文書の本文を丸ごと ProjectDescription に持つ公告があり、1 行が 40MB を超える
    maximum_object_size = 268435456,
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
