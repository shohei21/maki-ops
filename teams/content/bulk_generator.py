"""
Team B: 80本一括生成
まきのX投稿文80本をタイプ別に生成し、CSVとMarkdownで出力する
"""
import csv
import io
from datetime import date, timedelta
from pathlib import Path

from shared.claude_client import ClaudeClient
from shared.logger import get_logger

logger = get_logger("bulk")

BIBLE_PATH = Path(__file__).parent.parent.parent / "character" / "bible.md"

# 80本の内訳
BATCHES = [
    {
        "type": "daily",
        "label": "日常系",
        "count": 25,
        "description": "仕事終わり・通勤・ひとりご飯・コンビニ・部屋着・すっぴんなど。等身大の日常を切り取る。",
    },
    {
        "type": "emotion",
        "label": "感情系",
        "count": 20,
        "description": "孤独感・歳上への憧れ・裏アカの本音・夜の気持ち・甘えたい瞬間など。共感を生む投稿。",
    },
    {
        "type": "gravure",
        "label": "グラビア系",
        "count": 20,
        "description": "水着・部屋着・オフィスカジュアル際どめ・バスルームなど。非アダルト・照れ混じりのキャプション。",
    },
    {
        "type": "fan",
        "label": "ファン向け",
        "count": 15,
        "description": "感謝・歳上さんへの質問・note誘導・フォロワーへのサービス投稿。さりげなくCTA。",
    },
]

# 1日3投稿のスロット
DAILY_SLOTS = ["07:30", "12:30", "22:00"]

SYSTEM_PROMPT = """あなたは「まき」というSNSキャラクターの投稿文ライターです。
キャラクターバイブルに完全に沿った投稿文と、Higgsfield画像生成用の英語プロンプトを生成します。

投稿文ルール:
- 140字以内（ハッシュタグ含む）
- タメ口（〜だよ / 〜じゃん / えへへ / ///）
- あざとくなりすぎない・自然な素直さ
- ハッシュタグ2〜3個
- note誘導はさりげなく（ファン向け投稿のみ積極的に）
- 明示的なアダルト表現禁止

画像プロンプトルール:
- Higgsfield/Stable Diffusion向け英語プロンプト
- 顔は映さない（arm, back, side profile, mouth only）
- 現実的な日常シーン・シチュエーション
- 50語以内"""


class BulkGenerator:
    def __init__(self, claude: ClaudeClient):
        self.claude = claude

    def _load_bible(self) -> str:
        return BIBLE_PATH.read_text(encoding="utf-8") if BIBLE_PATH.exists() else ""

    def generate_batch(self, batch: dict) -> list[dict]:
        """1タイプ分の投稿をまとめて生成"""
        count = batch["count"]
        label = batch["label"]
        desc = batch["description"]
        logger.info(f"  {label} {count}本を生成中...")

        bible = self._load_bible()

        result = self.claude.complete_json(
            system=SYSTEM_PROMPT,
            user=f"""以下のキャラクター設定をもとに、「{label}」タイプのX投稿文を{count}本生成してください。

【キャラクターバイブル】
{bible}

【このタイプの定義】
{desc}

{count}本すべてバリエーション豊富に、季節・曜日・時間帯を意識して生成してください。
（2026年4月〜5月を想定）

以下のJSON配列形式で返してください（{count}要素）:
[
  {{
    "text": "投稿文（140字以内・ハッシュタグ含む）",
    "hashtags": "#裏アカ #OL",
    "image_prompt": "English image prompt for Higgsfield (no face, realistic, 50 words max)",
    "slot": "22:00",
    "note": "撮影・投稿のメモ（日本語）"
  }}
]""",
            max_tokens=16000,
        )

        if isinstance(result, list):
            logger.info(f"    → {len(result)}本生成完了")
            # typeラベルを付与
            for item in result:
                item["type"] = batch["type"]
                item["type_label"] = label
            return result

        logger.warning(f"    → {label} 生成失敗")
        return []

    def generate_all(self) -> list[dict]:
        """80本全て生成"""
        logger.info("80本一括生成 開始...")
        all_posts = []
        for batch in BATCHES:
            posts = self.generate_batch(batch)
            all_posts.extend(posts)
        logger.info(f"合計 {len(all_posts)} 本生成完了")
        return all_posts

    def assign_schedule(self, posts: list[dict], start_date: date | None = None) -> list[dict]:
        """投稿スケジュールを割り当てる（1日3本、start_date翌日から）"""
        if start_date is None:
            start_date = date.today()

        scheduled = []
        day_offset = 0
        slot_idx = 0

        for i, post in enumerate(posts):
            current_date = start_date + timedelta(days=day_offset)
            weekday = ["月", "火", "水", "木", "金", "土", "日"][current_date.weekday()]
            date_str = f"{current_date.month}/{current_date.day}({weekday})"
            time_str = DAILY_SLOTS[slot_idx]

            scheduled.append({
                "no": i + 1,
                "date": date_str,
                "time": time_str,
                **post,
            })

            slot_idx += 1
            if slot_idx >= len(DAILY_SLOTS):
                slot_idx = 0
                day_offset += 1

        return scheduled

    def to_csv(self, posts: list[dict]) -> str:
        """CSVテキストに変換（ai-account-opsと互換フォーマット）"""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["No.", "日付", "時間", "投稿文", "ハッシュタグ", "画像プロンプト(英語)", "投稿タイプ", "備考"])
        for p in posts:
            writer.writerow([
                p.get("no", ""),
                p.get("date", ""),
                p.get("time", ""),
                p.get("text", ""),
                p.get("hashtags", ""),
                p.get("image_prompt", ""),
                p.get("type_label", p.get("type", "")),
                p.get("note", ""),
            ])
        return output.getvalue()

    def to_markdown(self, posts: list[dict]) -> str:
        """Notion用のMarkdownに変換"""
        from collections import defaultdict
        by_type: dict[str, list] = defaultdict(list)
        for p in posts:
            by_type[p.get("type_label", "その他")].append(p)

        lines = [f"# まき X投稿文 80本\n\n> 生成日: {date.today().strftime('%Y年%m月%d日')}  \n> 1日3本（07:30 / 12:30 / 22:00）× 約27日分\n"]
        for type_label, type_posts in by_type.items():
            lines.append(f"\n## {type_label}（{len(type_posts)}本）\n")
            for p in type_posts:
                lines.append(f"### No.{p['no']} | {p['date']} {p['time']}")
                lines.append(f"\n{p.get('text', '')}\n")
                lines.append(f"- **ハッシュタグ**: {p.get('hashtags', '')}")
                lines.append(f"- **画像プロンプト**: `{p.get('image_prompt', '')}`")
                if p.get("note"):
                    lines.append(f"- **メモ**: {p.get('note', '')}")
                lines.append("")

        return "\n".join(lines)
