#!/usr/bin/env python3
"""
Opusモデルで全80ポストをインプ1000を狙えるレベルに書き直し。
句読点（。！？）で改行、共感・バズ狙いの文体に。
"""
import csv
import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
from shared.logger import get_logger
import anthropic

logger = get_logger("rewrite")

CSV_FILE = ROOT_DIR / "content" / "drafts" / "posts_80.csv"
MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """あなたはSNSバズ専門のコピーライターです。
「まき」（23歳都内OL、裏アカ）のXポストを書き直してください。

## キャラクター
- 23歳、都内OL（営業/事務）、裏アカ始めたばかりの初々しさがある
- 表ではしっかりした子、裏では甘えたい・見せたい気持ちがある
- タメ口ベース、照れ表現（///、ちょっとー笑）、重すぎず媚びすぎず
- 孤独感・仕事の疲れ・ひとり飲み・部屋着でごろごろが日常

## 書き直しルール
1. **句読点（。！？）のあとで必ず改行**する
2. 読点（、）で区切られる場合も、リズムを考えて適宜改行してOK
3. **1投稿=最大140字**（ハッシュタグ含む）
4. **共感ファースト**：1行目で「わかる！」と思わせるフックを置く
5. **バズる要素**：OLあるある、孤独感、ちょっとした本音、照れ混じりの素直さ
6. 「えへへ」は使わない
7. ハッシュタグはそのまま維持（変更不要）。本文と1行空けて最後に置く
8. 出力は投稿文のみ（説明・注釈不要）

## 時間帯別トーン
- 朝7:30：寝ぼけ感・今日も頑張る系・出勤前のリアル
- 昼12:30：ランチ・仕事中のぼやき・午後への憂鬱と小さな幸せ
- 夜22:00：仕事終わり・ひとりの時間・素の感情・ちょっと大人な雰囲気"""


def format_with_linebreaks(text: str) -> str:
    """句読点（。！？）で改行する"""
    result = []
    i = 0
    while i < len(text):
        c = text[i]
        result.append(c)
        if c in "。！？" and i + 1 < len(text) and text[i + 1] not in "\n":
            result.append("\n")
        i += 1
    return "".join(result).strip()


def rewrite_post(client: anthropic.Anthropic, row: dict) -> str:
    """1投稿をOpusで書き直す"""
    no = row["No."]
    date = row["日付"]
    time_str = row["時間"]
    current_text = row["投稿文"]
    hashtags = row["ハッシュタグ"]
    post_type = row["投稿タイプ"]
    memo = row.get("備考", "")

    # 曜日判定
    weekday_chars = ["月", "火", "水", "木", "金"]
    is_weekday = any(f"({d})" in date for d in weekday_chars)
    day_label = "平日" if is_weekday else "休日"

    prompt = f"""以下のXポストを書き直してください。

## 条件
- No.{no} / {date} {time_str}（{day_label}）
- 投稿タイプ: {post_type}
- メモ: {memo}

## 現在の投稿文
{current_text}

## ハッシュタグ（変更不要）
{hashtags}

## 出力形式
本文（句読点で改行）を書き、1行空けてハッシュタグを最後に置く。
説明や注釈は不要。投稿文のみ出力。"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def main():
    load_env()
    api_key = require_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    with open(CSV_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys())
    updated_rows = []
    errors = []

    print(f"処理開始: {len(rows)}件 (モデル: {MODEL})")

    for i, row in enumerate(rows, 1):
        no = row["No."]
        print(f"  No.{no} ({i}/{len(rows)}) ...", end=" ", flush=True)
        try:
            new_text = rewrite_post(client, row)
            row = dict(row)
            row["投稿文"] = new_text
            print("OK")
        except Exception as e:
            logger.error(f"No.{no}: {e}")
            errors.append(no)
            print(f"ERROR: {e}")
        updated_rows.append(row)
        # レート制限対策
        if i % 10 == 0:
            time.sleep(2)
        else:
            time.sleep(0.3)

    # CSV保存
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"\n完了: {len(updated_rows) - len(errors)}件更新, {len(errors)}件エラー")
    if errors:
        print(f"エラーNo.: {errors}")


if __name__ == "__main__":
    main()
