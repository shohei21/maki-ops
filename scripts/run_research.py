#!/usr/bin/env python3
"""Team D: リサーチチーム — Xのバズ投稿を収集して今日のトレンドヒントを生成"""
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.claude_client import ClaudeClient
from shared.file_utils import timestamped_path, ensure_dirs
from shared.logger import get_logger
from teams.research.trend_analyzer import TrendAnalyzer

logger = get_logger("run_research")
RESEARCH_DIR = ROOT_DIR / "research"


def main() -> None:
    load_env()
    claude = ClaudeClient(api_key=require_env("ANTHROPIC_API_KEY"))
    api_key = require_env("SOCIALDATA_API_KEY")
    ensure_dirs(RESEARCH_DIR)

    logger.info("=" * 50)
    logger.info("Team D: リサーチチーム 起動")
    logger.info("=" * 50)

    analyzer = TrendAnalyzer(claude=claude, api_key=api_key)

    # バズ投稿収集
    tweets = analyzer.collect_trends()
    tweets_path = timestamped_path(RESEARCH_DIR, "trends", ".json")
    tweets_path.write_text(json.dumps(tweets, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"収集結果: {tweets_path} ({len(tweets)}件)")

    # トレンドヒント生成
    hints = analyzer.extract_post_hints(tweets)
    hints_path = timestamped_path(RESEARCH_DIR, "trend_hints", ".txt")
    hints_path.write_text(hints, encoding="utf-8")
    logger.info(f"トレンドヒント: {hints_path}")

    logger.info("=" * 50)
    logger.info("Team D 完了！")
    logger.info("次: python scripts/run_content.py  # ヒントを活かして投稿文生成")
    logger.info("=" * 50)

    print("\n今日のトレンドヒント:")
    print(hints)


if __name__ == "__main__":
    main()
