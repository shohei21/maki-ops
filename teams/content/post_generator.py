"""
Team B: コンテンツチーム
まきのキャラクターを維持しながら今日のX投稿文を生成する
"""
import json
from pathlib import Path
from shared.claude_client import ClaudeClient
from shared.logger import get_logger

logger = get_logger("content")

BIBLE_PATH = Path(__file__).parent.parent.parent / "character" / "bible.md"

POST_TYPES = {
    "daily": "日常系（仕事終わり・ひとりご飯・部屋着・すっぴんなど）",
    "emotion": "感情系（孤独・歳上への憧れ・裏アカの本音など）",
    "gravure": "グラビア系（水着・オフィスカジュアル際どめ・部屋着など）",
    "fan": "ファン向けサービス系（感謝・note誘導・歳上さんへの質問など）",
}

SYSTEM_PROMPT = """あなたは「まき」というSNSキャラクターの投稿文ライターです。
キャラクターバイブルに完全に沿った投稿文を生成します。

ルール:
- 140字以内
- タメ口ベース（〜だよ / 〜じゃん / 〜かも / えへへ / ///）
- 過度に媚びない・あざとくなりすぎない
- 照れ表現・素直な感情を自然に入れる
- ハッシュタグは2〜3個（#裏アカ #OL #歳上さんが好き 等）
- note誘導はさりげなく（ガツガツ宣伝しない）
- 明示的なアダルト表現は禁止（Xガイドライン遵守）"""


class PostGenerator:
    def __init__(self, claude: ClaudeClient):
        self.claude = claude

    def _load_bible(self) -> str:
        return BIBLE_PATH.read_text(encoding="utf-8") if BIBLE_PATH.exists() else ""

    def generate_daily_posts(self, trend_context: str = "", count: int = 3) -> list[dict]:
        """今日の投稿文をcount本生成してlist[dict]で返す"""
        logger.info(f"投稿文{count}本を生成中...")
        bible = self._load_bible()

        trend_section = f"\n【今日のトレンドキーワード（参考）】\n{trend_context}\n" if trend_context else ""

        result = self.claude.complete_json(
            system=SYSTEM_PROMPT,
            user=f"""以下のキャラクター設定をもとに、今日のX投稿文を{count}本作ってください。

【キャラクターバイブル】
{bible}
{trend_section}
投稿タイプのバランス（{count}本中）:
- 日常系: {count // 3 + (1 if count % 3 > 0 else 0)}本
- 感情系 or ファン向け: {count // 3 + (1 if count % 3 > 1 else 0)}本
- グラビア系: {count // 3}本

以下のJSON配列形式で返してください:
[
  {{
    "type": "daily",
    "text": "投稿文（140字以内・ハッシュタグ含む）",
    "image_prompt": "撮影シチュエーションの説明（日本語）",
    "post_time": "07:30",
    "note": "この投稿のポイントや注意事項"
  }}
]""",
            max_tokens=4000,
        )

        if isinstance(result, list):
            logger.info(f"  → {len(result)}本生成完了")
            return result
        logger.warning("生成失敗。空リストを返します。")
        return []

    def generate_reply_texts(self, context: str, count: int = 5) -> list[str]:
        """リプ周り用の返信文をcount本生成"""
        logger.info(f"返信文{count}本を生成中...")
        bible = self._load_bible()

        result = self.claude.complete_json(
            system=SYSTEM_PROMPT,
            user=f"""以下のキャラクター設定をもとに、フォロワーへの返信文を{count}本作ってください。

【キャラクターバイブル】
{bible}

【返信する相手・状況】
{context}

短い返信文をJSON配列で返してください（各50字以内）:
["返信1", "返信2", ...]""",
            max_tokens=1000,
        )

        if isinstance(result, list):
            return result
        return []

    def posts_to_markdown(self, posts: list[dict]) -> str:
        """投稿リストをMarkdown形式に変換"""
        from datetime import date
        lines = [f"# まき 投稿文 {date.today().strftime('%Y年%m月%d日')}\n"]
        for i, p in enumerate(posts, 1):
            lines.append(f"## 投稿{i}（{p.get('post_time', '--:--')}）｜{POST_TYPES.get(p.get('type', ''), p.get('type', ''))}")
            lines.append(f"\n{p.get('text', '')}\n")
            lines.append(f"- **撮影シチュエーション**: {p.get('image_prompt', '')}")
            if p.get("note"):
                lines.append(f"- **メモ**: {p.get('note', '')}")
            lines.append("")
        return "\n".join(lines)
