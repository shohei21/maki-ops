"""
Googleスプレッドシート「確認用」シートへの書き込み
- 投稿予定をセルに記入
- 画像をGoogle Driveにアップロードして IMAGE() 数式で埋め込む
"""
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from shared.logger import get_logger

logger = get_logger("sheets")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_ID = "1v9NhLWNxljpztsmlOacLVYlFKlOiRIFxHQB_hPVIUQA"
SHEET_NAME = "確認用"
DRIVE_FOLDER_ID = "1_mIpQe3kFb6Sd4ElyWlG-_njUPh3YShP"

CREDS_FILE = Path(__file__).parent.parent / "credentials.json"


def _get_creds() -> Credentials:
    return Credentials.from_service_account_file(str(CREDS_FILE), scopes=SCOPES)


GITHUB_RAW_BASE = "https://raw.githubusercontent.com/shohei21/maki-ops/maki-main"


def get_github_image_url(image_path: Path) -> str:
    """ローカルパスからGitHub rawコンテンツURLを生成してpushする"""
    import subprocess
    repo_root = Path(__file__).parent.parent

    # gitにadd & commit & push
    rel = image_path.resolve().relative_to(repo_root.resolve())
    subprocess.run(["git", "add", str(rel)], cwd=repo_root, check=True)
    result = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        cwd=repo_root
    )
    if result.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", f"chore: add preview image {image_path.name}"],
            cwd=repo_root, check=True
        )
        subprocess.run(["git", "push"], cwd=repo_root, check=True)
        logger.info(f"GitHub push完了: {image_path.name}")

    url = f"{GITHUB_RAW_BASE}/{rel}"
    return url


def write_preview_to_sheet(
    no: str,
    date_str: str,
    time_str: str,
    text: str,
    image_path: Path | None = None,
    image_prompt: str = "",
) -> None:
    """確認用シートに投稿予定を1行書き込む"""
    creds = _get_creds()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=200, cols=10)

    # ヘッダーがなければ追加
    existing = ws.get_all_values()
    if not existing or existing[0] != ["No.", "日付", "時間", "投稿文", "画像", "画像プロンプト", "ステータス"]:
        ws.update("A1:G1", [["No.", "日付", "時間", "投稿文", "画像", "画像プロンプト", "ステータス"]])

    # 画像URL取得
    image_formula = ""
    if image_path and image_path.exists():
        try:
            url = get_github_image_url(image_path)
            image_formula = f'=IMAGE("{url}")'
        except Exception as e:
            logger.warning(f"GitHub push失敗: {e}")
            image_formula = "（画像生成済み・URL取得失敗）"
    elif image_prompt:
        image_formula = f"（画像プロンプト）{image_prompt[:50]}"

    # 次の空行に追記
    next_row = len(ws.get_all_values()) + 1
    ws.update(
        f"A{next_row}:G{next_row}",
        [[no, date_str, time_str, text, image_formula, image_prompt, "投稿予定"]],
        value_input_option="USER_ENTERED",
    )

    # 行の高さを画像が見えるサイズに設定
    if image_formula.startswith("=IMAGE"):
        try:
            sh.batch_update({
                "requests": [{
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": ws.id,
                            "dimension": "ROWS",
                            "startIndex": next_row - 1,
                            "endIndex": next_row,
                        },
                        "properties": {"pixelSize": 150},
                        "fields": "pixelSize",
                    }
                }]
            })
        except Exception:
            pass

    logger.info(f"スプレッドシート書き込み完了: No.{no} {date_str} {time_str}")
