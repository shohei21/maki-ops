#!/usr/bin/env python3
"""
X 自動投稿スクリプト（画像生成 → アップロード → 投稿）
posts_80.csv を読み込み、予定時刻になったら:
  1. 英語プロンプトからGeminiで画像を自動生成
  2. 生成した画像をXにアップロード
  3. 本文 + ハッシュタグ + 画像をセットでXに投稿

cronで定期実行することで完全自動化。

使い方:
    # 予定時刻になった投稿を実行（cronで定期実行）
    python scripts/run_auto_post.py

    # 内容確認のみ（投稿しない・画像生成もしない）
    python scripts/run_auto_post.py --dry-run

    # 指定番号を今すぐ強制投稿
    python scripts/run_auto_post.py --force 1

    # 未投稿の全件を確認
    python scripts/run_auto_post.py --list

    # 画像なしでテキストのみ投稿（画像生成をスキップ）
    python scripts/run_auto_post.py --no-image

cron設定例（毎時00分・30分に実行）:
    0,30 * * * * cd /home/shomar/projects/maki-ops && .venv/bin/python scripts/run_auto_post.py >> logs/auto_post.log 2>&1
"""
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.logger import get_logger
from teams.posting.x_poster import XPoster

logger = get_logger("auto_post")

CSV_FILE = ROOT_DIR / "content" / "drafts" / "posts_80.csv"
POSTED_LOG = ROOT_DIR / "content" / "posted" / "posted_log.csv"
YEAR = 2026
TIME_WINDOW_MINUTES = 30  # 予定時刻±この分以内なら投稿する


def load_posted_nos() -> set[str]:
    """投稿済みのNo.一覧"""
    if not POSTED_LOG.exists():
        return set()
    with open(POSTED_LOG, encoding="utf-8") as f:
        return {row[0] for row in csv.reader(f) if row}


def parse_schedule(date_str: str, time_str: str) -> datetime:
    """例: '4/3(木)', '07:30' → datetime"""
    date_part = date_str.split("(")[0]
    month, day = date_part.split("/")
    hour, minute = time_str.split(":")
    return datetime(YEAR, int(month), int(day), int(hour), int(minute))


def build_tweet(row: dict) -> str:
    """投稿文とハッシュタグを結合"""
    text = row["投稿文"].strip()
    hashtags = row.get("ハッシュタグ", "").strip()
    if hashtags and hashtags not in text:
        return f"{text}\n\n{hashtags}"
    return text


def load_posts() -> list[dict]:
    if not CSV_FILE.exists():
        logger.error(f"CSVが見つかりません: {CSV_FILE}")
        logger.error("先に run_bulk_content.py を実行してください")
        sys.exit(1)
    with open(CSV_FILE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="投稿せず確認のみ（画像生成もスキップ）")
    parser.add_argument("--force", type=str, default=None, help="指定番号を今すぐ投稿")
    parser.add_argument("--list", action="store_true", help="未投稿一覧を表示")
    parser.add_argument("--no-image", action="store_true", help="画像生成をスキップしてテキストのみ投稿")
    args = parser.parse_args()

    load_env()
    rows = load_posts()
    posted_nos = load_posted_nos()
    now = datetime.now()

    # ─── --list: 未投稿一覧表示 ──────────────────────────────────
    if args.list:
        print(f"\n未投稿一覧（全{len(rows)}件中）:\n")
        for row in rows:
            no = row["No."]
            if no in posted_nos:
                continue
            try:
                scheduled = parse_schedule(row["日付"], row["時間"])
                status = "⏳ 予定" if scheduled > now else "⚠️ 期限切れ"
            except Exception:
                status = "❓"
            print(f"  [{no:>3}] {row['日付']} {row['時間']} {status} | {row['投稿タイプ']} | {row['投稿文'][:30]}...")
        return

    # ─── 投稿実行 ─────────────────────────────────────────────────
    poster = XPoster(
        api_key=require_env("X_API_KEY"),
        api_secret=require_env("X_API_SECRET"),
        access_token=require_env("X_ACCESS_TOKEN"),
        access_token_secret=require_env("X_ACCESS_TOKEN_SECRET"),
    )

    # 画像生成器（--no-imageでなければ初期化）
    image_gen = None
    if not args.no_image and not args.dry_run:
        try:
            from teams.posting.image_generator import ImageGenerator
            image_gen = ImageGenerator(api_key=require_env("GOOGLE_API_KEY"))
        except Exception as e:
            logger.warning(f"画像生成器の初期化失敗（テキストのみで投稿します）: {e}")

    posted_count = 0
    for row in rows:
        no = row["No."]

        if no in posted_nos:
            continue

        # --force 指定時は対象番号のみ
        if args.force and no != args.force:
            continue

        # 予定時刻チェック（--force時はスキップ）
        if not args.force:
            try:
                scheduled = parse_schedule(row["日付"], row["時間"])
            except Exception:
                continue
            diff_minutes = (now - scheduled).total_seconds() / 60
            if not (0 <= diff_minutes <= TIME_WINDOW_MINUTES):
                continue

        tweet_text = build_tweet(row)
        image_prompt = row.get("画像プロンプト(英語)", "").strip()

        print(f"\n[No.{no}] {row['日付']} {row['時間']} ({row.get('投稿タイプ', '')})")
        print(f"投稿文:\n{tweet_text}")
        if image_prompt:
            print(f"📸 画像プロンプト: {image_prompt[:70]}...")

        if args.dry_run:
            print("→ [DRY-RUN] 投稿しません")
            continue

        # 画像生成 → スタンプ → 口元確認
        image_path = None
        if image_gen and image_prompt:
            label = f"post_{no.zfill(3)}"
            image_path = image_gen.generate_and_censor(image_prompt, label=label)
            if image_path:
                print(f"→ 画像生成・加工完了(censored): {image_path.name}")
            else:
                print("→ 口元隠し確認失敗。この投稿はスキップします")
                continue

        # 投稿
        result = poster.post(tweet_text, row.get("投稿タイプ", "daily"), image_path=image_path, no=no)
        if "tweet_id" in result and not result.get("error"):
            img_note = " (画像付き)" if image_path else ""
            print(f"→ 投稿完了{img_note}: {result.get('url', '')}")
            posted_count += 1
        elif "error" in result:
            print(f"→ エラー: {result['error']}")

    if posted_count == 0 and not args.dry_run and not args.force and not args.list:
        logger.info("投稿予定時刻の投稿はありませんでした")

    if posted_count > 0:
        logger.info(f"{posted_count}件投稿完了")


if __name__ == "__main__":
    main()
