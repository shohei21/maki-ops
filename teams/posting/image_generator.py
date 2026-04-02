"""
画像生成モジュール
CSVの英語プロンプトからGemini（gemini-3.1-flash-image-preview）で画像を生成する
ai-account-opsのgenerate.pyと同じ仕組みをmaki-ops向けに統合
"""
import time
from datetime import datetime
from pathlib import Path

from PIL import Image
from google import genai
from google.genai import types

from shared.logger import get_logger

logger = get_logger("image_gen")

REFERENCE_IMAGE = Path(__file__).parent.parent.parent / "assets" / "references" / "maki_ref.jpeg"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "assets" / "generated"
MODEL = "gemini-3.1-flash-image-preview"

# まきキャラクターの固定プロンプト（顔を映さない・一貫性を保つ）
CHARACTER_BASE = (
    "same Japanese woman, consistent features, no face visible, "
    "arm only or back view or silhouette, "
    "natural beauty, photorealistic photography, "
    "hyperdetailed, ultra realistic"
)


class ImageGenerator:
    def __init__(self, api_key: str, use_reference: bool = True):
        self.client = genai.Client(api_key=api_key)
        self.ref_image: Image.Image | None = None
        if use_reference and REFERENCE_IMAGE.exists():
            self.ref_image = Image.open(REFERENCE_IMAGE).convert("RGB")
            logger.info(f"参照画像ロード: {REFERENCE_IMAGE.name}")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def generate(self, prompt: str, label: str = "post") -> Path | None:
        """プロンプトから画像を生成してPathを返す。失敗時はNone。"""
        full_prompt = f"{CHARACTER_BASE}, {prompt}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"{label}_{timestamp}.png"

        contents: list = [full_prompt]
        if self.ref_image is not None:
            contents.append(self.ref_image)

        try:
            response = self.client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )
            for part in response.parts:
                if part.inline_data is not None:
                    img = part.as_image()
                    img.save(output_path)
                    logger.info(f"画像生成完了: {output_path.name}")
                    return output_path

            text = " ".join(p.text for p in response.parts if hasattr(p, "text") and p.text)
            logger.warning(f"画像が返されませんでした: {text[:100]}")
            return None

        except Exception as e:
            logger.error(f"画像生成エラー: {e}")
            return None
