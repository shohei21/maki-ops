import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent


def load_env() -> None:
    load_dotenv(ROOT_DIR / ".env")


def require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        sys.exit(f"ERROR: 環境変数 {key} が設定されていません")
    return val
