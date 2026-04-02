#!/usr/bin/env python3
"""
Googleスプレッドシート「確認用」シートに翌日22:00投稿の予告を書くスクリプト
毎日17:00にcronで実行する。

使い方:
    python scripts/run_preview_sheet.py            # 翌日22:00の投稿を書く
    python scripts/run_preview_sheet.py --no <No.> # 指定番号を書く（テスト用）
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.logger import get_logger
from teams.posting.x_poster import XPoster

logger = get_logger("preview_sheet")

CSV_FILE = ROOT_DIR / "content" / "drafts" / "posts_80.csv"
YEAR = 2026


def parse_schedule(date_str: str, time_str: str) -> datetime:
    date_part = date_str.split("(")[0]
    month, day = date_part.split("/")
    hour, minute = time_str.split(":")
    return datetime(YEAR, int(month), int(day), int(hour), int(minute))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no", type=str, default=None, help="強制指定するNo.（テスト用）")
    args = parser.parse_args()

    load_env()

    with open(CSV_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # 翌日22:00の投稿を探す
    tomorrow = datetime.now() + timedelta(days=1)
    target_date = f"{tomorrow.month}/{tomorrow.day}"

    target_row = None
    if args.no:
        target_row = next((r for r in rows if r["No."] == args.no), None)
        if not target_row:
            logger.error(f"No.{args.no} が見つかりません")
            sys.exit(1)
    else:
        for row in rows:
            date_part = row["日付"].split("(")[0]
            if date_part == target_date and row["時間"] == "22:00":
                target_row = row
                break

    if not target_row:
        logger.info(f"翌日({target_date}) 22:00 の投稿が見つかりません（スキップ）")
        return

    no = target_row["No."]
    logger.info(f"確認用シートに書き込み: No.{no} {target_row['日付']} {target_row['時間']}")

    # 画像生成（プロンプトがある場合）
    image_path = None
    image_prompt = target_row.get("画像プロンプト(英語)", "").strip()
    if image_prompt:
        try:
            from teams.posting.image_generator import ImageGenerator
            image_gen = ImageGenerator(api_key=require_env("GOOGLE_API_KEY"))
            label = f"post_{no.zfill(3)}_preview"
            image_path = image_gen.generate_and_censor(image_prompt, label=label)
            if image_path:
                logger.info(f"画像生成完了: {image_path.name}")
            else:
                # 検閲失敗時は生成済み画像を使用（確認用なので可）
                import glob
                pattern = str(ROOT_DIR / "assets" / "generated" / f"post_{no.zfill(3)}_preview_*.png")
                matches = sorted(glob.glob(pattern))
                if matches:
                    image_path = Path(matches[-1])
                    logger.info(f"検閲失敗 → 生成画像を使用: {image_path.name}")
        except Exception as e:
            logger.warning(f"画像生成失敗: {e}")

    # シートに書き込み
    from shared.sheets_writer import write_preview_to_sheet
    write_preview_to_sheet(
        no=no,
        date_str=target_row["日付"],
        time_str=target_row["時間"],
        text=target_row["投稿文"],
        image_path=image_path,
        image_prompt=image_prompt,
    )
    logger.info("完了")


if __name__ == "__main__":
    main()
