"""官公需情報ポータルサイト（中小企業庁）の検索 API から入札公告を取り出す。

API は検索語（Query）・件名・機関名・都道府県のどれかが必須で、全件を返す呼び方が無い。
Query に「NOT 存在しない語」を指定すると、ほかの条件に合う全件が返る。これを公告日
（CFT_Issue_Date）1 日ずつに絞って取る。1 回で返るのは 1,000 件までなので、1 日で
1,000 件を超えたら Query を「q AND 語」と「q ANDNOT 語」に分けて取り直す。2 つは
重ならず、合わせると元の件数になる。

公告は公開から 1 日ほどたって登録され、公告日より後に登録されるもの（予告）もある。
毎回、前回取った最後の公告日の REFETCH_DAYS 日前から取り直す。初回と過去分は
MAX_DAYS 日ずつ進め、今日まで来たら公告日が先の予告も取る。

出力: data/kkj/notices/<公告日>.ndjson.gz（1 行 = 1 公告）

データソース: 官公需情報ポータルサイト（中小企業庁） https://www.kkj.go.jp/s/
"""

import gzip
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from shared.fetch import fetch, replacing

logger = logging.getLogger("pipelines")

API = "https://www.kkj.go.jp/api/"
USER_AGENT = "dataset-kkj (+https://github.com/queria-io/dataset-kkj)"
OUTPUT = Path("data/kkj/notices")
# 2021-01-07 に 1 件あり、2021-04 から毎日入っている（2026-11-10 確認）
FIRST_DAY = date(2021, 1, 1)
REFETCH_DAYS = 30
AHEAD_DAYS = 90
MAX_DAYS = int(os.environ.get("KKJ_MAX_DAYS", "180"))
PAGE_LIMIT = 1000
# 利用規約は特定のサーバーからの継続した大量アクセスを禁じている。1 回ずつ間を空ける
INTERVAL_SECONDS = 2.0
EVERYTHING = "NOT zzqqxxnone"
# 1 日の件数が 1,000 を超えたときに Query を分ける語。前から順に使う
SPLIT_TERMS = ["工事", "業務", "委託", "購入", "賃貸借", "保守", "令和", "一般競争入札"]


def decode(body: bytes) -> str:
    """API の本文。BMP の外の文字がサロゲートペアの 3 バイトずつ (CESU-8) で届くことがあるので、組み直す"""
    text = body.decode("utf-8", "surrogatepass")
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def search(query: str, day: date) -> ET.Element:
    time.sleep(INTERVAL_SECONDS)
    params = {"Query": query, "CFT_Issue_Date": day.isoformat(), "Count": PAGE_LIMIT}
    root = ET.fromstring(decode(fetch(f"{API}?{urlencode(params)}", user_agent=USER_AGENT, timeout=180)))
    if (error := root.findtext("Error")) is not None:
        raise RuntimeError(f"{day} {query}: {error}")
    return root


def to_row(result: ET.Element) -> dict:
    """SearchResult 1 件。添付は [{name, uri}]、ほかのタグは文字のまま。"""
    row = {child.tag: child.text for child in result if child.tag not in ("ResultId", "Attachments")}
    row["Attachments"] = [
        {"name": a.findtext("Name"), "uri": a.findtext("Uri")} for a in result.iterfind("Attachments/Attachment")
    ]
    return row


def day_rows(day: date, query: str = EVERYTHING, terms: tuple[str, ...] = tuple(SPLIT_TERMS)) -> Iterator[dict]:
    root = search(query, day)
    hits = int(root.findtext("SearchResults/SearchHits"))
    results = root.findall("SearchResults/SearchResult")
    if hits <= len(results) or not terms:
        if hits > len(results):
            logger.warning("  %s: %d 件中 %d 件しか取れない（分ける語が尽きた）: %s", day, hits, len(results), query)
        yield from map(to_row, results)
        return
    term, rest = terms[0], terms[1:]
    yield from day_rows(day, f"({query}) AND {term}", rest)
    yield from day_rows(day, f"({query}) ANDNOT {term}", rest)


def fetch_day(day: date, fetched_at: str, output: Path) -> int:
    rows = {row["Key"]: row for row in day_rows(day)}
    path = output / f"{day.isoformat()}.ndjson.gz"
    with replacing(path) as partial, gzip.open(partial, "wt", encoding="utf-8") as f:
        f.writelines(json.dumps({**row, "fetched_at": fetched_at}, ensure_ascii=False) + "\n" for row in rows.values())
    return len(rows)


def published_cursor() -> date | None:
    """公開中の tender.notices で、取った日までに公告日が来ていた最後の公告日。

    FDL_WORKING が無い（PR のビルド確認）か、表がまだ無ければ None。
    """
    working = os.environ.get("FDL_WORKING")
    if not working:
        return None
    import duckdb

    con = duckdb.connect(config={"custom_user_agent": os.environ.get("QUERIA_USER_AGENT", "")})
    con.execute("INSTALL ducklake; LOAD ducklake; INSTALL httpfs; LOAD httpfs;")
    con.execute(f"ATTACH 'ducklake:{working.replace(chr(39), chr(39) * 2)}' AS previous (READ_ONLY, META_TYPE 'sqlite')")
    try:
        return con.sql(
            "select max(cft_issue_date) from previous.tender.notices where cft_issue_date <= fetched_at::date"
        ).fetchone()[0]
    except duckdb.CatalogException as error:
        logger.info("  公開中の表が無い: %s", error)
        return None
    finally:
        con.close()


def days_to_fetch(cursor: date | None, today: date, has_catalog: bool) -> list[date]:
    if not has_catalog:
        # PR のビルド確認は直近の数日だけ
        start, end = today - timedelta(days=3), today
    else:
        start = max(FIRST_DAY, cursor - timedelta(days=REFETCH_DAYS)) if cursor else FIRST_DAY
        end = min(start + timedelta(days=MAX_DAYS - 1), today)
        if end == today:
            end = today + timedelta(days=AHEAD_DAYS)
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def download_kkj(output: Path = OUTPUT) -> int:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    cursor = published_cursor()
    days = days_to_fetch(cursor, today, bool(os.environ.get("FDL_WORKING")))
    logger.info("  前回の最後の公告日 %s、%s から %s まで %d 日", cursor, days[0], days[-1], len(days))
    output.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(UTC).isoformat()
    total = 0
    for day in days:
        count = fetch_day(day, fetched_at, output)
        total += count
        logger.info("  %s: %d 件", day, count)
    if total == 0:
        raise SystemExit("1 件も取れない（API の形が変わった？）")
    return total
