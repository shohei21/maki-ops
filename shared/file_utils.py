from datetime import datetime
from pathlib import Path


def timestamped_path(directory: Path, prefix: str, suffix: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return directory / f"{prefix}_{ts}{suffix}"


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
