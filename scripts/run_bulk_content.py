#!/usr/bin/env python3
"""
SNS投稿文 80本 一括生成スクリプト
まきキャラクターで80本のX投稿文+画像プロンプトを生成し、
CSV（自動投稿用）とNotionに保存する

使い方:
    python scripts/run_bulk_content.py
    python scripts/run_bulk_content.py --start-date 2026-04-10  # 開始日を指定
"""
import argparse
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.claude_client import ClaudeClient
from shared.notion_client import NotionWriter
from shared.file_utils import timestamped_path, ensure_dirs
from shared.logger import get_logger
from teams.content.bulk_generator import BulkGenerator

logger = get_logger("run_bulk")
CONTENT_DIR = ROOT_DIR / "content"
DRAFTS_DIR = ROOT_DIR / "content" / "drafts"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=str, default=None, help="投稿開始日 (例: 2026-04-10)")
    args = parser.parse_args()

    start_date = date.today()
    if args.start_date:
        start_date = date.fromisoformat(args.start_date)

    load_env()
    claude = ClaudeClient(api_key=require_env("ANTHROPIC_API_KEY"))
    notion = NotionWriter(
        token=require_env("NOTION_TOKEN"),
        parent_page_id=require_env("NOTION_MAKI_PAGE_ID"),
    )
    ensure_dirs(DRAFTS_DIR)

    logger.info("=" * 60)
    logger.info("まき SNS投稿文 80本 一括生成")
    logger.info(f"投稿開始日: {start_date} ～ 約27日間（1日3本）")
    logger.info("=" * 60)

    generator = BulkGenerator(claude=claude)

    # 80本生成
    posts = generator.generate_all()
    if not posts:
        logger.error("生成失敗")
        sys.exit(1)

    # スケジュール割り当て
    scheduled = generator.assign_schedule(posts, start_date=start_date)

    # CSV保存（自動投稿スクリプトが読み込む）
    csv_text = generator.to_csv(scheduled)
    csv_path = DRAFTS_DIR / "posts_80.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    logger.info(f"CSV保存: {csv_path} ({len(scheduled)}件)")

    # バックアップCSV（タイムスタンプ付き）
    backup_path = timestamped_path(DRAFTS_DIR, "posts_80_backup", ".csv")
    backup_path.write_text(csv_text, encoding="utf-8")

    # Markdown保存
    md = generator.to_markdown(scheduled)
    md_path = timestamped_path(CONTENT_DIR, "posts_80", ".md")
    md_path.write_text(md, encoding="utf-8")

    # Notion保存
    notion.create_page("📱 X投稿文 80本（スケジュール付き）", md)
    logger.info("Notion保存完了")

    logger.info("=" * 60)
    logger.info(f"完了！{len(scheduled)}本の投稿文を生成しました")
    logger.info(f"CSV: {csv_path}")
    logger.info("自動投稿: python scripts/run_auto_post.py --dry-run")
    logger.info("=" * 60)

    # 最初の3件をプレビュー表示
    print("\n▼ 最初の3件プレビュー")
    for p in scheduled[:3]:
        print(f"\n[No.{p['no']}] {p['date']} {p['time']} ({p.get('type_label', '')})")
        print(p["text"])
        print(f"📸 {p['image_prompt']}")


if __name__ == "__main__":
    main()
