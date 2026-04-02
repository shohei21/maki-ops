# maki-ops

「まき」（23歳OL裏アカ）のSNS運用を自動化し、月10万円を目指すプロジェクト。
monthly-100k-opsのビジネス設計 × ai-account-opsのSNS自動化 を統合。

## チーム構成

| チーム | 役割 | スクリプト |
|--------|------|-----------|
| Team A | ビジョン：月10万ロードマップ・note設計 → Notion | `run_vision.py` |
| Team B | コンテンツ：今日の投稿文3本生成（まきキャラ維持） | `run_content.py` |
| Team C | 投稿：X自動投稿・ログ記録 | `run_post.py` |
| Team D | リサーチ：Xバズ収集・トレンドヒント生成 | `run_research.py` |
| 全自動 | 毎日の運用を1コマンドで実行 | `run_pipeline.py` |

## セットアップ

```bash
cd /home/shomar/projects/maki-ops
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env を確認（APIキーは設定済み）
```

## 初回実行（ビジョン設計）

```bash
python scripts/run_vision.py
```
→ Notionに「🌙【まきSNS運用】月10万円プロジェクト」ページが作られます
→ そのページIDを `.env` の `NOTION_MAKI_PAGE_ID` に設定してください

## 毎日の運用（初回ビジョン設定後）

```bash
# 通常実行（投稿前に1件ずつ確認）
python scripts/run_pipeline.py

# 投稿せず内容だけ確認
python scripts/run_pipeline.py --dry-run

# トレンド収集スキップ（APIエラー時など）
python scripts/run_pipeline.py --no-research
```

## 個別実行

```bash
python scripts/run_research.py   # Step1: トレンド収集のみ
python scripts/run_content.py    # Step2: 投稿文生成のみ
python scripts/run_post.py --dry-run  # Step3: 投稿確認のみ
python scripts/run_post.py       # Step3: 実際に投稿
```

## Notion構成

```
親ページ（NOTION_PARENT_PAGE_ID）
├── 📈【株式投資入門教育コンテンツ販売（note）】月10万円プロジェクト  ← monthly-100k-ops
│   ├── 💡 提案
│   ├── 📋 事業設計書
│   └── ...
└── 🌙【まきSNS運用】月10万円プロジェクト  ← maki-ops（このプロジェクト）
    ├── 🎯 ビジョン設計書（月10万ロードマップ）
    ├── 📝 noteコンテンツ計画
    └── 📅 YYYY/MM/DD 運用ログ（毎日追加）
```

## キャラクター

- `character/bible.md` — まきのキャラクターバイブル（性格・口調・投稿方針）
- `character/fan-strategy.md` — ファン化戦略・フェーズ設計

## 必要な環境変数

| 変数名 | 説明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Claude API |
| `X_API_KEY / SECRET / ACCESS_TOKEN / ACCESS_TOKEN_SECRET` | X API |
| `NOTION_TOKEN` | Notion API |
| `NOTION_PARENT_PAGE_ID` | 出力先の親ページID |
| `NOTION_MAKI_PAGE_ID` | まき専用プロジェクトページID（初回実行後に設定）|
| `SOCIALDATA_API_KEY` | トレンド収集用 |
