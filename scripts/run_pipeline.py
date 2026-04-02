#!/usr/bin/env python3
"""
まき SNS運用 全自動パイプライン
毎日1コマンドで: トレンド収集 → 投稿文生成 → 確認 → X投稿 → Notion記録

使い方:
    python scripts/run_pipeline.py              # 通常実行（投稿前に確認あり）
    python scripts/run_pipeline.py --dry-run    # 投稿せずに内容確認のみ
    python scripts/run_pipeline.py --no-research  # トレンド収集スキップ
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.claude_client import ClaudeClient
from shared.notion_client import NotionWriter
from shared.file_utils import timestamped_path, ensure_dirs, latest_file
from shared.logger import get_logger

logger = get_logger("run_pipeline")
CONTENT_DIR = ROOT_DIR / "content" / "drafts"
RESEARCH_DIR = ROOT_DIR / "research"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="X投稿をスキップ（確認のみ）")
    parser.add_argument("--no-research", action="store_true", help="トレンド収集をスキップ")
    args = parser.parse_args()

    load_env()
    claude = ClaudeClient(api_key=require_env("ANTHROPIC_API_KEY"))
    notion = NotionWriter(
        token=require_env("NOTION_TOKEN"),
        parent_page_id=require_env("NOTION_MAKI_PAGE_ID"),
    )
    ensure_dirs(CONTENT_DIR, RESEARCH_DIR)

    today = date.today().strftime("%Y/%m/%d")
    logger.info("=" * 60)
    logger.info(f"まき SNS運用パイプライン 起動 — {today}")
    logger.info("=" * 60)

    # ─── Step 1: トレンド収集 ──────────────────────────────────────
    trend_context = ""
    if not args.no_research:
        logger.info("Step 1: トレンド収集...")
        from teams.research.trend_analyzer import TrendAnalyzer
        analyzer = TrendAnalyzer(claude=claude, api_key=require_env("SOCIALDATA_API_KEY"))
        tweets = analyzer.collect_trends()
        if tweets:
            tweets_path = timestamped_path(RESEARCH_DIR, "trends", ".json")
            tweets_path.write_text(json.dumps(tweets, ensure_ascii=False, indent=2), encoding="utf-8")
            trend_context = analyzer.extract_post_hints(tweets)
            hints_path = timestamped_path(RESEARCH_DIR, "trend_hints", ".txt")
            hints_path.write_text(trend_context, encoding="utf-8")
            logger.info(f"  → {len(tweets)}件収集、ヒント生成完了")
    else:
        logger.info("Step 1: トレンド収集スキップ")
        hint_file = latest_file(RESEARCH_DIR, "trend_hints_*.txt")
        if hint_file:
            trend_context = hint_file.read_text(encoding="utf-8")

    # ─── Step 2: 投稿文生成 ────────────────────────────────────────
    logger.info("Step 2: 投稿文生成...")
    from teams.content.post_generator import PostGenerator
    generator = PostGenerator(claude=claude)
    posts = generator.generate_daily_posts(trend_context=trend_context, count=3)

    if not posts:
        logger.error("投稿文生成失敗")
        sys.exit(1)

    md = generator.posts_to_markdown(posts)
    posts_path = timestamped_path(CONTENT_DIR, "posts", ".md")
    posts_path.write_text(md, encoding="utf-8")
    logger.info(f"  → {len(posts)}本生成: {posts_path.name}")

    # ─── Step 3: 内容確認 & X投稿 ────────────────────────────────
    logger.info("Step 3: 投稿内容確認...")
    from teams.posting.x_poster import XPoster
    poster = XPoster(
        api_key=require_env("X_API_KEY"),
        api_secret=require_env("X_API_SECRET"),
        access_token=require_env("X_ACCESS_TOKEN"),
        access_token_secret=require_env("X_ACCESS_TOKEN_SECRET"),
    )

    posted_results = []
    for i, p in enumerate(posts, 1):
        print(f"\n{'='*50}")
        print(f"投稿{i}（{p.get('post_time', '--:--')}）")
        print(f"{'='*50}")
        print(p.get("text", ""))
        print(f"\n📸 シチュエーション: {p.get('image_prompt', '')}")

        if args.dry_run:
            logger.info(f"[DRY-RUN] 投稿{i} スキップ")
            posted_results.append({"skipped": True, **p})
        else:
            confirm = input("\nこの内容で投稿しますか？ [y/N/q(終了)]: ").strip().lower()
            if confirm == "q":
                logger.info("パイプライン中断")
                break
            elif confirm == "y":
                result = poster.post(p["text"], p.get("type", "daily"))
                posted_results.append(result)
            else:
                logger.info(f"投稿{i} スキップ")
                posted_results.append({"skipped": True, **p})

    # ─── Step 4: Notion記録 ────────────────────────────────────────
    logger.info("Step 4: Notion記録...")
    summary_lines = [f"# {today} 運用ログ\n"]
    if trend_context:
        summary_lines.append(f"## 今日のトレンドヒント\n{trend_context}\n")
    summary_lines.append("## 生成・投稿した内容")
    summary_lines.append(md)
    notion.create_page(f"📅 {today} 運用ログ", "\n".join(summary_lines))

    # ─── 完了 ─────────────────────────────────────────────────────
    posted_count = sum(1 for r in posted_results if not r.get("skipped"))
    logger.info("=" * 60)
    logger.info(f"パイプライン完了！投稿: {posted_count}/{len(posts)}本")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
