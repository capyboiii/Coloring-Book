"""Tiện ích dùng chung."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


def slugify(text: str) -> str:
    """
    'Đại dương kỳ thú' -> 'dai-duong-ky-thu'

    Bỏ dấu tiếng Việt để slug an toàn khi làm tên thư mục và URL.
    """
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "khong-ten"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def image_files(directory: Path) -> list[Path]:
    """Ảnh trong thư mục, sắp xếp theo tên. Bỏ qua file ẩn."""
    if not directory.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = [
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in exts and not p.name.startswith(".")
    ]
    return sorted(files, key=lambda p: p.name)


def info(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"  ! {msg}", file=sys.stderr, flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"LỖI: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def human_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}ph {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}ph"
