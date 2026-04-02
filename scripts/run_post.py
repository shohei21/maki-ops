#!/usr/bin/env python3
"""Team C: 投稿チーム — 生成済みの投稿文をXに自動投稿する

使い方:
    python scripts/run_post.py --dry-run     # 確認のみ（実際には投稿しない）
    python scripts/run_post.py               # 実際に投稿
    python scripts/run_post.py --file content/drafts/posts_20260402_120000.md
"""
import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.file_utils import latest_file
from shared.logger import get_logger
from teams.posting.x_poster import XPoster

logger = get_logger("run_post")
DRAFTS_DIR = ROOT_DIR / "content" / "drafts"


def parse_posts_from_md(md: str) -> list[dict]:
    """Markdownの投稿文ファイルから投稿リストを抽出"""
    posts = []
    # "投稿N（HH:MM）｜タイプ" ブロックを抽出
    blocks = re.split(r"## 投稿\d+", md)[1:]  # 最初の空要素を除く
    for block in blocks:
        lines = block.strip().split("\n")
        # 投稿文本文（ハッシュタグを含む行）を取得
        text_lines = [l for l in lines if l and not l.startswith("-") and not l.startswith("#")]
        if text_lines:
            text = "\n".join(text_lines).strip()
            # タイプを判定
            post_type = "daily"
            if "グラビア" in block:
                post_type = "gravure"
            elif "感情" in block:
                post_type = "emotion"
            elif "ファン" in block:
                post_type = "fan"
            posts.append({"text": text, "type": post_type})
    return posts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="実際には投稿しない（確認用）")
    parser.add_argument("--file", type=str, default=None, help="投稿文MDファイルのパス")
    args = parser.parse_args()

    load_env()

    logger.info("=" * 50)
    logger.info(f"Team C: 投稿チーム 起動{'（DRY-RUN）' if args.dry_run else ''}")
    logger.info("=" * 50)

    # 投稿文ファイルを特定
    if args.file:
        posts_file = Path(args.file)
    else:
        posts_file = latest_file(DRAFTS_DIR, "posts_*.md")

    if not posts_file or not posts_file.exists():
        logger.error("投稿文ファイルが見つかりません。先に run_content.py を実行してください。")
        sys.exit(1)

    logger.info(f"投稿ファイル: {posts_file.name}")
    md = posts_file.read_text(encoding="utf-8")
    posts = parse_posts_from_md(md)

    if not posts:
        logger.error("投稿文を解析できませんでした")
        sys.exit(1)

    logger.info(f"{len(posts)}件の投稿を処理します")

    poster = XPoster(
        api_key=require_env("X_API_KEY"),
        api_secret=require_env("X_API_SECRET"),
        access_token=require_env("X_ACCESS_TOKEN"),
        access_token_secret=require_env("X_ACCESS_TOKEN_SECRET"),
    )

    for i, p in enumerate(posts, 1):
        print(f"\n--- 投稿{i} ({p['type']}) ---")
        print(p["text"])
        if not args.dry_run:
            confirm = input("\nこの内容で投稿しますか？ [y/N]: ").strip().lower()
            if confirm != "y":
                logger.info(f"投稿{i} スキップ")
                continue
        result = poster.post(p["text"], p["type"], dry_run=args.dry_run)
        if "url" in result and result["url"]:
            logger.info(f"投稿{i} 完了: {result['url']}")
        elif "error" in result:
            logger.error(f"投稿{i} 失敗: {result['error']}")

    logger.info("=" * 50)
    logger.info("Team C 完了！")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
