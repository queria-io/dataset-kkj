"""官公需情報ポータルサイト（中小企業庁）の入札公告のデータパイプライン。

1. kkj: 検索 API から公告日ごとに入札公告を取り出す
2. dbt: まだ無い公告を追記する
"""

import logging

from dbt.cli.main import dbtRunner

from pipelines.kkj import download_kkj

# dbt を読み込むとルートロガーが先に設定されるので、force で上書きする
logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
logger = logging.getLogger("pipelines")


def dbt_build():
    dbt = dbtRunner()
    for command in (["deps"], ["build"], ["docs", "generate"]):
        result = dbt.invoke(command)
        if not result.success:
            raise SystemExit(f"dbt {' '.join(command)} failed")


def main():
    logger.info("1/2: kkj (入札公告)")
    download_kkj()

    logger.info("2/2: dbt build")
    dbt_build()


if __name__ == "__main__":
    main()
