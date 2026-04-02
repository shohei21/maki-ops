#!/usr/bin/env python3
"""Team B: コンテンツチーム — 今日の投稿文3本を生成してNotionとファイルに保存"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.claude_client import ClaudeClient
from shared.notion_client import NotionWriter
from shared.file_utils import timestamped_path, ensure_dirs, latest_file
from shared.logger import get_logger
from teams.content.post_generator import PostGenerator

logger = get_logger("run_content")
CONTENT_DIR = ROOT_DIR / "content" / "drafts"
RESEARCH_DIR = ROOT_DIR / "research"


def main() -> None:
    load_env()
    claude = ClaudeClient(api_key=require_env("ANTHROPIC_API_KEY"))
    notion = NotionWriter(
        token=require_env("NOTION_TOKEN"),
        parent_page_id=require_env("NOTION_MAKI_PAGE_ID"),  # まきプロジェクトページID
    )
    ensure_dirs(CONTENT_DIR)

    logger.info("=" * 50)
    logger.info("Team B: コンテンツチーム 起動")
    logger.info("=" * 50)

    # 今日のトレンドヒントがあれば読み込む
    trend_context = ""
    hint_file = latest_file(RESEARCH_DIR, "trend_hints_*.txt")
    if hint_file:
        trend_context = hint_file.read_text(encoding="utf-8")
        logger.info(f"トレンドヒント使用: {hint_file.name}")

    generator = PostGenerator(claude=claude)
    posts = generator.generate_daily_posts(trend_context=trend_context, count=3)

    if not posts:
        logger.error("投稿文の生成に失敗しました")
        sys.exit(1)

    # ファイル保存
    from datetime import date
    md = generator.posts_to_markdown(posts)
    posts_path = timestamped_path(CONTENT_DIR, "posts", ".md")
    posts_path.write_text(md, encoding="utf-8")
    logger.info(f"投稿文保存: {posts_path}")

    # Notion保存
    today = date.today().strftime("%Y/%m/%d")
    notion.create_page(f"📅 {today} 投稿文", md)

    logger.info("=" * 50)
    logger.info(f"Team B 完了！{len(posts)}本の投稿文を生成しました。")
    logger.info("次: python scripts/run_post.py --dry-run  # 確認してから投稿")
    logger.info("=" * 50)

    # 投稿文をコンソールにも表示
    for i, p in enumerate(posts, 1):
        print(f"\n--- 投稿{i} ({p.get('post_time', '--:--')}) ---")
        print(p.get("text", ""))


if __name__ == "__main__":
    main()
