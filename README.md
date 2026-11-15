# dataset-kkj

Queria のデータセット `kkj`（官公需情報ポータルサイト 入札公告）のリポジトリです。データセットの説明は [docs/index.md](docs/index.md) にあります。

## ビルド

```bash
uv sync
scripts/build.sh   # 取得して dbt build し、Queria に公開する
```
