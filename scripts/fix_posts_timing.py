#!/usr/bin/env python3
"""
posts_80.csv の時間帯ミスマッチ修正スクリプト

修正内容:
1. 平日/休日・朝/昼/夜のコンテキストに合わない投稿文をClaude APIで書き直し
2. 朝(07:30)・昼(12:30)の画像プロンプトを空欄に
"""
import csv
import sys
import shutil
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from shared.config_loader import load_env, require_env
import anthropic

load_env()

CSV_FILE = ROOT_DIR / "content" / "drafts" / "posts_80.csv"
WEEKDAYS = {"月", "火", "水", "木", "金"}

# 時間帯ごとのコンテキスト定義
CONTEXT = {
    ("平日", "朝"): "平日の朝07:30。まきは出勤前。起き抜け・朝の準備・通勤・最寄り駅ホームでの電車待ちなど。仕事のことが頭にある。「今日も行くか」感。",
    ("平日", "昼"): "平日の昼12:30。まきはランチ休憩中。オフィス近くのコンビニ・定食屋・カフェ・デスクで食べるなど。午後の仕事が控えている。",
    ("平日", "夜"): "平日の夜22:00。まきは仕事終わり〜帰宅後。残業明け・帰り道・ひとり飲み・帰宅後の部屋でのんびりなど。一日の終わりのゆるい感じ。",
    ("休日", "朝"): "休日の朝07:30。まきはゆっくり起きた。寝起き・布団でごろごろ・パンとコーヒー・朝のテレビなど。のんびりした休日の始まり。",
    ("休日", "昼"): "休日の昼12:30。まきはお出かけ・ひとりご飯・のんびり外出など。平日と違ってリラックスした昼。",
    ("休日", "夜"): "休日の夜22:00。まきは家でのんびり。お風呂上がり・部屋着・明日からまた仕事という感覚が少しある。",
}

# 画像プロンプトを残すのは夜(22:00)のみ
KEEP_IMAGE_SLOTS = {"夜"}

# 内容NGキーワード（時間帯別）
NG_KEYWORDS = {
    ("平日", "朝"): ["仕事終わり", "部屋着", "お風呂済ませ", "寝るだけ", "水曜の夜", "金曜の夜", "日曜夜", "土曜日の朝", "仕事終わりに1枚"],
    ("平日", "昼"): ["月曜日の朝", "残業終わったら", "月曜の夜", "日曜の夜", "GW初日", "帰り道に", "帰り道ひとり"],
    ("平日", "夜"): ["ランチひとりで", "今日のランチ", "土曜の昼間", "お昼休みに"],
    ("休日", "朝"): ["仕事帰りに", "お風呂上がり", "今日1日お疲れ", "水曜日って"],
    ("休日", "夜"): ["早く帰れた", "夕方の電車", "有給とって"],
}


def get_slot(time_str: str) -> str:
    hour = int(time_str.split(":")[0])
    if hour < 12:
        return "朝"
    elif hour < 18:
        return "昼"
    return "夜"


def get_day_type(date_str: str) -> str:
    dow = date_str[date_str.find("(") + 1: date_str.find(")")]
    return "平日" if dow in WEEKDAYS else "休日"


def needs_rewrite(text: str, day_type: str, slot: str) -> bool:
    ngs = NG_KEYWORDS.get((day_type, slot), [])
    return any(ng in text for ng in ngs)


def rewrite_post(client: anthropic.Anthropic, row: dict, day_type: str, slot: str, context_desc: str) -> tuple[str, str, str]:
    """Claude APIで投稿文・ハッシュタグ・備考を書き直す。(投稿文, ハッシュタグ, 備考) を返す"""
    post_type = row.get("投稿タイプ", "日常系")
    old_text = row["投稿文"]
    date = row["日付"]

    system = """あなたはSNSキャラクター「まき」（23歳OL・裏アカ）の投稿文を書くライターです。

キャラクター概要:
- 23歳 都内OL（営業か事務）。仕事はできると思われているが本人は淡々とこなしている感覚
- 表では「しっかりしてる子」、裏では甘えたい・見せたい気持ちがある
- 言葉遣い: タメ口ベース＋照れ表現（えへへ、///、ちょっとー笑）。重すぎず軽すぎず
- 歳上の人に惹かれがち。孤独感・等身大の日常・ちょっとした色気が武器

投稿タイプ:
- 日常系: OLあるある・食事・通勤・部屋でごろごろなど等身大の日常
- 感情系: 孤独感・歳上への憧れ・ふとした夜の気持ち（重すぎず照れで締める）
- グラビア系: 水着・部屋着・際どいショットの照れ混じりキャプション
- ファン向け: noteへの誘導・フォロワーへの感謝"""

    prompt = f"""以下の投稿を書き直してください。

投稿タイプ: {post_type}
投稿日: {date}
時間帯コンテキスト: {context_desc}

【現在の投稿文（時間帯が合っていないためNG）】
{old_text}

【修正ルール】
- 上記コンテキスト（時間帯・曜日）に自然に合う内容にする
- キャラの口調・雰囲気は維持（タメ口・えへへ・/// など）
- 投稿タイプの方向性を維持
- 文字数は元の投稿文と同程度（50〜120文字程度）
- ハッシュタグは本文に含めず別で出力

以下のJSON形式で出力してください（コードブロック不要）:
{{
  "投稿文": "（ハッシュタグ抜きの本文のみ）",
  "ハッシュタグ": "#タグ1 #タグ2",
  "備考": "（ひと言で内容の補足）"
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    import json
    raw = response.content[0].text.strip()
    # コードブロックを除去
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    result = json.loads(raw)
    text = result["投稿文"].strip()
    hashtags = result.get("ハッシュタグ", "").strip()
    note = result.get("備考", "").strip()
    # ハッシュタグを本文末尾に結合
    full_text = f"{text}\n\n{hashtags}" if hashtags else text
    return full_text, hashtags, note


def main():
    client = anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))

    with open(CSV_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys())
    fixed_rows = []
    rewrite_count = 0
    image_clear_count = 0

    for row in rows:
        row = dict(row)
        no = row["No."]
        date = row["日付"]
        time = row["時間"]
        day_type = get_day_type(date)
        slot = get_slot(time)
        context_desc = CONTEXT.get((day_type, slot), "")

        # 1. 画像プロンプトのクリア（朝・昼）
        if slot not in KEEP_IMAGE_SLOTS and row.get("画像プロンプト(英語)", "").strip():
            row["画像プロンプト(英語)"] = ""
            image_clear_count += 1

        # 2. 内容NG → 書き直し
        if needs_rewrite(row["投稿文"], day_type, slot):
            print(f"[No.{no:>2}] {date} {time} [{day_type}/{slot}] 書き直し中...")
            print(f"  旧: {row['投稿文'][:60]}")
            try:
                new_text, new_hashtags, new_note = rewrite_post(client, row, day_type, slot, context_desc)
                row["投稿文"] = new_text
                row["ハッシュタグ"] = new_hashtags
                row["備考"] = new_note
                rewrite_count += 1
                print(f"  新: {new_text[:60]}")
            except Exception as e:
                print(f"  エラー: {e}（スキップ）")

        fixed_rows.append(row)

    # バックアップ
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = CSV_FILE.parent / f"posts_80_backup_{ts}.csv"
    shutil.copy(CSV_FILE, backup)
    print(f"\nバックアップ: {backup.name}")

    # 書き出し
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(fixed_rows)

    print(f"\n完了: 内容書き直し {rewrite_count}件 / 画像プロンプト削除 {image_clear_count}件")


if __name__ == "__main__":
    main()
