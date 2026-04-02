"""
Team A: ビジョンチーム
まきアカウントの月10万円ロードマップ・note設計・KPIを生成してNotionに保存する
"""
from pathlib import Path
from shared.claude_client import ClaudeClient
from shared.logger import get_logger

logger = get_logger("vision")

BIBLE_PATH = Path(__file__).parent.parent.parent / "character" / "bible.md"
STRATEGY_PATH = Path(__file__).parent.parent.parent / "character" / "fan-strategy.md"


def _load_character() -> str:
    bible = BIBLE_PATH.read_text(encoding="utf-8") if BIBLE_PATH.exists() else ""
    strategy = STRATEGY_PATH.read_text(encoding="utf-8") if STRATEGY_PATH.exists() else ""
    return f"{bible}\n\n---\n\n{strategy}"


SYSTEM_PROMPT = """あなたはSNS×コンテンツ販売の収益化専門家です。
キャラクターを活かしたSNS運用でファンを獲得し、noteで月10万円を達成するための
具体的・実行可能なビジネス設計を行います。

重要な前提:
- XでOLキャラ「まき」としてSNS運用
- 顔出しなし（アーム・後ろ姿・口元のみ）
- noteで写真集・限定コンテンツ販売
- 非アダルト（Xガイドライン遵守）"""


class VisionPlanner:
    def __init__(self, claude: ClaudeClient):
        self.claude = claude

    def create_vision_doc(self) -> str:
        """まきアカウントのビジョン・月10万ロードマップを生成"""
        logger.info("ビジョン設計書を作成中...")
        character = _load_character()

        return self.claude.complete(
            system=SYSTEM_PROMPT,
            user=f"""以下のキャラクター設計をもとに、「まき」アカウントで月10万円を達成するための
ビジョン設計書を作成してください。

【キャラクター設定】
{character}

以下の構成でMarkdown形式で作成してください:

# まき SNS運用ビジョン設計書

## 1. ミッション・ビジョン
- このアカウントが何を目指すか（1〜2文で端的に）
- 理想の状態（6ヶ月後のゴール）

## 2. 収益モデル全体像
- 収益の柱（メイン・サブ）
- 月10万円の内訳シミュレーション（具体的な数字）

## 3. フォロワー → 収益化 パスの設計
- フォロワー数ごとのフェーズ定義（0→500→2000→5000）
- 各フェーズで何をするか

## 4. noteコンテンツ設計
- 無料記事の設計（集客用）
- 有料コンテンツのラインナップ（価格・内容）
- 月10万達成に必要な販売本数

## 5. SNS運用KPI（毎週見直す指標）
- フォロワー増加数・目標値
- エンゲージメント率目標
- note売上目標

## 6. 月次マイルストーン（6ヶ月分）
- 月ごとの具体的な目標と行動

## 7. 差別化戦略
- 他の裏アカOLと「まき」が違う点
- 長期的なファンを作るための仕掛け

## 8. 毎日のルーティン（最小工数で最大成果）
- 朝・昼・夜それぞれの投稿・作業内容
- 1日の合計作業時間目安
""",
            max_tokens=8000,
        )

    def create_note_content_plan(self) -> str:
        """note販売コンテンツの具体的なラインナップと台本を生成"""
        logger.info("noteコンテンツ計画を作成中...")
        character = _load_character()

        return self.claude.complete(
            system=SYSTEM_PROMPT,
            user=f"""以下のキャラクター設定をもとに、「まき」のnoteで販売するコンテンツの
具体的なラインナップと、最初の1本の販売ページ文章を作成してください。

【キャラクター設定】
{character}

以下の構成でMarkdown形式で作成してください:

# まき note販売コンテンツ計画

## 無料記事（3本）
各記事のタイトル・概要・CTAを設計してください

## 有料コンテンツ ラインナップ
価格帯別（500円・1000円・3000円）に各2〜3本

## 最初の有料note 販売ページ（完全版）
- タイトル
- キャッチコピー
- リード文（まきらしいトーンで）
- 内容紹介
- 購入者の声（想定）
- CTA
""",
            max_tokens=6000,
        )
