#!/usr/bin/env python3
"""Team A: ビジョンチーム — まきのビジョン設計書・noteコンテンツ計画をNotionに保存"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.claude_client import ClaudeClient
from shared.notion_client import NotionWriter
from shared.file_utils import timestamped_path, ensure_dirs
from shared.logger import get_logger
from teams.vision.vision_planner import VisionPlanner

logger = get_logger("run_vision")
CONTENT_DIR = ROOT_DIR / "content"


def main() -> None:
    load_env()
    claude = ClaudeClient(api_key=require_env("ANTHROPIC_API_KEY"))
    notion_root = NotionWriter(
        token=require_env("NOTION_TOKEN"),
        parent_page_id=require_env("NOTION_PARENT_PAGE_ID"),
    )
    ensure_dirs(CONTENT_DIR)

    # まき専用プロジェクトページ配下に出力
    notion = notion_root.create_project_page("🌙【まきSNS運用】月10万円プロジェクト")

    logger.info("=" * 50)
    logger.info("Team A: ビジョンチーム 起動")
    logger.info("=" * 50)

    planner = VisionPlanner(claude=claude)

    # ビジョン設計書
    vision_md = planner.create_vision_doc()
    vision_path = timestamped_path(CONTENT_DIR, "vision_doc", ".md")
    vision_path.write_text(vision_md, encoding="utf-8")
    notion.create_page("🎯 ビジョン設計書（月10万ロードマップ）", vision_md)
    logger.info(f"ビジョン設計書: {vision_path}")

    # noteコンテンツ計画
    note_md = planner.create_note_content_plan()
    note_path = timestamped_path(CONTENT_DIR, "note_plan", ".md")
    note_path.write_text(note_md, encoding="utf-8")
    notion.create_page("📝 noteコンテンツ計画", note_md)
    logger.info(f"noteコンテンツ計画: {note_path}")

    logger.info("=" * 50)
    logger.info("Team A 完了！Notionを確認してください。")
    logger.info("次: python scripts/run_content.py")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
