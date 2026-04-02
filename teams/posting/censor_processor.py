"""
口元スタンプ処理 + 隠れ具合をGeminiで検証するモジュール
ai-account-opsのcensor.pyをmaki-ops向けに統合。
生成画像（assets/generated/）にスタンプを貼り、censored版（assets/censored/）を出力。
Geminiで口元が正しく隠れているか確認し、NGなら呼び出し元に知らせる。
"""
import math
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from google import genai
from google.genai import types

from shared.logger import get_logger

logger = get_logger("censor")

CENSORED_DIR = Path(__file__).parent.parent.parent / "assets" / "censored"
STAMP_TYPES = ["heart", "sakura", "star", "paw", "rainbow", "text_heart"]

_FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


# ── スタンプ描画（ai-account-ops censor.pyと同一ロジック）─────────────────

def _draw_heart(draw, cx, cy, r):
    points = []
    for deg in range(0, 360, 2):
        t = math.radians(deg)
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
        points.append((cx + x * r / 17, cy + y * r / 17))
    big = [(cx + (p[0]-cx)*1.08, cy + (p[1]-cy)*1.08) for p in points]
    draw.polygon(big, fill=(255, 255, 255, 255))
    draw.polygon(points, fill=(255, 160, 200, 255))
    draw.polygon(points, outline=(220, 100, 160, 255), width=max(2, r//20))

def _draw_star(draw, cx, cy, r):
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        radius = r if i % 2 == 0 else r * 0.42
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=(255, 230, 80, 255))
    draw.polygon(points, outline=(200, 160, 0, 255), width=max(2, r//20))

def _draw_paw(draw, cx, cy, r):
    color = (255, 182, 200, 255)
    outline = (210, 120, 155, 255)
    pw, ph = int(r*0.62), int(r*0.72)
    draw.ellipse([(cx-pw, cy-int(ph*0.5)), (cx+pw, cy+ph)], fill=color, outline=outline, width=max(2, r//20))
    toe_r = int(r*0.24)
    for tx, ty in [(cx-int(r*0.52), cy-int(r*0.62)), (cx-int(r*0.18), cy-int(r*0.82)),
                   (cx+int(r*0.18), cy-int(r*0.82)), (cx+int(r*0.52), cy-int(r*0.62))]:
        draw.ellipse([(tx-toe_r, ty-toe_r), (tx+toe_r, ty+toe_r)], fill=color, outline=outline, width=max(2, r//20))

def _draw_sakura(overlay, cx, cy, r):
    petal_w, petal_h = int(r*0.52), int(r*0.82)
    for i in range(5):
        angle_deg = i * 72 - 90
        petal = Image.new("RGBA", (petal_w*4, petal_h*4), (0,0,0,0))
        pd = ImageDraw.Draw(petal)
        pd.ellipse([petal_w, petal_h//2, petal_w*3, petal_h*2+petal_h//2],
                   fill=(255,192,210,255), outline=(230,140,170,255), width=2)
        petal = petal.rotate(-angle_deg, expand=True)
        offset = int(r*0.42)
        px = cx + int(offset*math.cos(math.radians(angle_deg))) - petal.width//2
        py = cy + int(offset*math.sin(math.radians(angle_deg))) - petal.height//2
        overlay.paste(petal, (px, py), petal)
    d = ImageDraw.Draw(overlay)
    cr = max(6, int(r*0.18))
    d.ellipse([(cx-cr, cy-cr), (cx+cr, cy+cr)], fill=(255,230,100,255), outline=(200,160,0,255), width=2)

def _draw_rainbow(draw, cx, cy, r):
    colors = [(255,80,80,220),(255,160,60,220),(255,230,60,220),(80,200,80,220),(60,140,255,220),(160,60,255,220)]
    band = max(4, r//7)
    for i, color in enumerate(colors):
        ar = int(r*(1.0 - i*0.13))
        draw.arc([(cx-ar, cy-ar),(cx+ar, cy+ar)], 190, 350, fill=color, width=band)
    for sign in (-1, 1):
        cloud_cx = cx + sign * int(r*0.98)
        for dx, dy, cr in [(0,0,int(r*0.22)),(-int(r*0.14),int(r*0.08),int(r*0.16)),(int(r*0.14),int(r*0.08),int(r*0.16))]:
            draw.ellipse([(cloud_cx+dx-cr, cy+dy-cr),(cloud_cx+dx+cr, cy+dy+cr)], fill=(255,255,255,240))

def _draw_text_heart(draw, cx, cy, r):
    from PIL import ImageFont
    font_size = max(24, r)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    heart = "\u2665"
    w_i = draw.textbbox((0,0), "I ", font=font)[2]
    w_h = draw.textbbox((0,0), heart, font=font)[2]
    h_h = draw.textbbox((0,0), heart, font=font)[3] - draw.textbbox((0,0), heart, font=font)[1]
    hx, hy = cx - w_h//2, cy - h_h//2
    for text, x, y in [("I ", hx-w_i, hy),(heart, hx, hy),(" YOU", hx+w_h, hy)]:
        for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-2,-2),(2,2)]:
            draw.text((x+dx, y+dy), text, font=font, fill=(255,100,180,255))
        draw.text((x, y), text, font=font, fill=(255,255,255,255))


STAMP_SCALE = {"heart":0.78,"sakura":0.62,"star":0.80,"text_heart":1.05,"paw":0.90,"rainbow":1.10}


def _apply_stamp(overlay: Image.Image, stamp_type: str, cx: int, cy: int, r: int):
    r = max(20, int(r * STAMP_SCALE.get(stamp_type, 1.0)))
    draw = ImageDraw.Draw(overlay)
    if stamp_type == "sakura":
        _draw_sakura(overlay, cx, cy, r)
    elif stamp_type == "heart":
        _draw_heart(draw, cx, cy, r)
    elif stamp_type == "star":
        _draw_star(draw, cx, cy, r)
    elif stamp_type == "paw":
        _draw_paw(draw, cx, cy, r)
    elif stamp_type == "rainbow":
        _draw_rainbow(draw, cx, cy, r)
    elif stamp_type == "text_heart":
        _draw_text_heart(draw, cx, cy, r)


def _detect_mouth(img_rgb: np.ndarray) -> tuple[int, int, int] | None:
    """顔検出して口元座標を返す。顔が見つからない場合はNoneを返す。"""
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    faces = _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    fx, fy, fw, fh = max(faces, key=lambda r: r[2]*r[3])
    cx = fx + fw//2
    cy = fy + int(fh * 0.81)
    radius = max(28, min(int(fw*0.24), w//5))
    return cx, cy, radius


# ── メインクラス ──────────────────────────────────────────────────────────

class CensorProcessor:
    def __init__(self, gemini_api_key: str):
        self.gemini = genai.Client(api_key=gemini_api_key)
        CENSORED_DIR.mkdir(parents=True, exist_ok=True)

    def apply_stamp(self, src_path: Path, stamp_type: str | None = None) -> tuple[Path, bool]:
        """
        生成画像にスタンプを貼ってcensored版を返す。
        顔が検出されなかった場合はスタンプなしで (censored_path, False) を返す。
        """
        img = Image.open(src_path).convert("RGBA")
        img_rgb = np.array(img.convert("RGB"))
        mouth = _detect_mouth(img_rgb)

        out_path = CENSORED_DIR / src_path.name

        if mouth is None:
            # 顔が見つからない = シルエット・後ろ姿など → 口元なし、スタンプ不要
            img.convert("RGB").save(out_path, quality=95)
            logger.info(f"顔検出なし（スタンプ不要）: {out_path.name}")
            return out_path, False

        cx, cy, radius = mouth
        chosen = stamp_type or random.choice(STAMP_TYPES)
        overlay = Image.new("RGBA", img.size, (0,0,0,0))
        _apply_stamp(overlay, chosen, cx, cy, radius)
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.8))

        out = Image.alpha_composite(img, overlay).convert("RGB")
        out.save(out_path, quality=95)
        logger.info(f"スタンプ適用({chosen}): {out_path.name}")
        return out_path, True

    def verify_mouth_hidden(self, censored_path: Path) -> tuple[bool, str]:
        """
        Gemini Visionで口元が隠れているか確認。
        シルエット・後ろ姿など口元が写っていない場合もOK。
        戻り値: (ok: bool, reason: str)
        """
        try:
            img = Image.open(censored_path).convert("RGB")
            response = self.gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    img,
                    "この画像を確認してください。\n"
                    "以下のいずれかを判定してください:\n"
                    "1. 口元（唇・歯・口）がスタンプや装飾で完全に隠れている → OK\n"
                    "2. 画像にそもそも口元が写っていない（シルエット・後ろ姿・腕のみ・遠景など） → OK\n"
                    "3. 口元が写っていて、かつ隠れていない → NG\n"
                    "以下の形式でのみ回答してください:\n"
                    "OK: （理由を1文で）\n"
                    "NG: （理由を1文で）"
                ],
            )
            text = response.text.strip()
            ok = text.startswith("OK")
            logger.info(f"口元検証: {'OK' if ok else 'NG'} — {censored_path.name}")
            return ok, text
        except Exception as e:
            logger.warning(f"検証エラー（スキップ）: {e}")
            return True, f"検証スキップ: {e}"

    def process(self, generated_path: Path, stamp_type: str | None = None, max_retries: int = 3) -> Path | None:
        """
        スタンプ適用 → Gemini検証 → NGなら別スタンプで最大max_retries回リトライ。
        成功したcensored_pathを返す。全試行失敗時はNone。
        """
        tried_stamps: list[str] = []
        for attempt in range(1, max_retries + 1):
            remaining = [s for s in STAMP_TYPES if s not in tried_stamps]
            chosen = stamp_type if (attempt == 1 and stamp_type) else (random.choice(remaining) if remaining else random.choice(STAMP_TYPES))
            tried_stamps.append(chosen)

            logger.info(f"スタンプ処理 試行{attempt}/{max_retries} ({chosen})")
            censored_path, stamp_applied = self.apply_stamp(generated_path, stamp_type=chosen)

            # 顔が検出されなかった場合はそのままOK（シルエット・後ろ姿など）
            if not stamp_applied:
                logger.info(f"顔なし画像のためスタンプ不要、そのまま使用: {censored_path.name}")
                return censored_path

            ok, reason = self.verify_mouth_hidden(censored_path)
            if ok:
                logger.info(f"口元隠し確認OK: {censored_path.name}")
                return censored_path
            else:
                logger.warning(f"口元隠し不十分({attempt}回目): {reason}")
                if attempt == max_retries:
                    logger.error(f"全{max_retries}回試行失敗。投稿をスキップします: {generated_path.name}")
                    return None
