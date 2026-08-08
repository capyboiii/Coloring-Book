"""
Công thức một cuốn sách.

Một file YAML trong `books/` ghi hết mọi thứ cần để ra một cuốn: chủ đề, số
trang, phong cách, bìa, và phần thông tin bán hàng cho web.

Vì sao cần: trước đây mọi tham số nằm rải trong lệnh gõ tay. Ba tuần sau muốn
in lại đúng cuốn cũ thì không nhớ đã chạy `--complexity` gì, `--density` gì.
Ghi vào file thì tái tạo được, sửa được, và commit vào git được.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import ROOT
from .util import slugify

BOOKS_DIR = ROOT / "books"

# Chủ đề KHÔNG có nhân vật sống. Gắn mặt vào những thứ này là ra ảnh kỳ quặc.
PLANT_THEMES = {"floral", "hoa-trong-chau", "mandala"}

TEMPLATE = """\
# Công thức sách — {slug}
#
# Sửa file này rồi chạy:  python studio.py make {slug}
# Mọi tham số đều ghi ở đây để ba tuần sau còn tái tạo lại được đúng cuốn này.

title: "{title}"
subtitle: ""

# ---- Nội dung ----
theme: ocean          # tên bộ trong themes/ (studio.py generate x --list-themes)
pages: 40             # số hình trong sách. In một mặt nên số trang gấp đôi
generate: 60          # sinh dư để còn chỗ loại. Tỷ lệ giữ lại thường 50-70%
complexity: medium    # simple=3-5t | medium=5-8t | detailed=8-12t | intricate=NL
density: rich         # single | normal | rich      — số ĐỐI TƯỢNG mỗi trang
style: kawaii         # kawaii | cartoon | decorative — PHONG CÁCH vẽ
lora:                 # tên file LoRA trong ComfyUI/models/loras/. Trống = không dùng
lora_strength: 0.9    # 0.6-1.0. Cao quá thì LoRA nuốt mất chủ thể
seed:                 # để trống là ngẫu nhiên. Điền số để sinh lại y hệt

# ---- Bìa ----
cover:
  scene:              # để trống là lấy cảnh đầu trong theme
  bg: "#1B7A8C"

# ---- Thông tin bán hàng (web đọc từ đây) ----
collection: relaxation
audience: all         # kids | adults | all
price_usd: 14.99
tags: []
description: |
  Viết mô tả bán hàng ở đây.
"""


@dataclass
class Cover:
    scene: str | None = None
    bg: str = "#1B7A8C"


@dataclass
class Recipe:
    slug: str
    title: str
    subtitle: str = ""
    theme: str = "ocean"
    pages: int = 40
    generate: int = 60
    complexity: str = "medium"
    density: str = "rich"
    style: str = "kawaii"
    lora: str | None = None
    lora_strength: float = 0.9
    seed: int | None = None
    cover: Cover = field(default_factory=Cover)
    collection: str = ""
    audience: str = "all"
    price_usd: float | None = None
    tags: list[str] = field(default_factory=list)
    description: str = ""
    path: Path | None = None

    def hints(self) -> list[str]:
        """Góp ý, không chặn — chỉ là kinh nghiệm hay sai."""
        out = []
        # Chủ đề hoa lá đồ vật + style kawaii = HOA CÓ MẶT NGƯỜI.
        # Chuỗi kawaii có "dot eyes and a small smile", nên khi chủ thể là bó
        # hoa hồng thì Flux vẫn gắn mặt vào cho bằng được. Soi ảnh trong
        # library/floral/ thấy đúng thế: một khuôn mặt mọc giữa bông hồng.
        # Đây là một trong mấy trang Bao thấy "logic chưa hợp lý".
        if self.style == "kawaii" and self.theme in PLANT_THEMES:
            out.append(
                f"theme '{self.theme}' là hoa lá/hoạ tiết nhưng style=kawaii. "
                f"Kawaii gắn mắt và miệng vào chủ thể, nên sẽ ra hoa có mặt "
                f"người — dùng style=decorative")
        if self.audience == "kids" and self.complexity in ("detailed", "intricate"):
            out.append(
                f"audience=kids nhưng complexity={self.complexity}. "
                f"Trẻ nhỏ cần hình to, ít chi tiết — dùng simple (3-5 tuổi) "
                f"hoặc medium (5-8 tuổi)")
        if self.audience == "kids" and self.density == "rich":
            out.append(
                "audience=kids nhưng density=rich. Trang quá rối, trẻ nhỏ khó "
                "tô — dùng density=normal")
        if self.audience == "adults" and self.complexity in ("simple", "medium"):
            out.append(
                f"audience=adults với complexity={self.complexity} sẽ ra sách "
                f"quá đơn giản so với kỳ vọng — cân nhắc intricate")
        return out

    def sale_info(self) -> dict[str, Any]:
        """Phần web cần. Tách riêng để `book.json` không lẫn tham số kỹ thuật."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "collection": self.collection,
            "audience": self.audience,
            "price_usd": self.price_usd,
            "tags": list(self.tags),
            "description": self.description.strip(),
        }


class RecipeError(RuntimeError):
    pass


def recipe_path(slug: str) -> Path:
    return BOOKS_DIR / f"{slug}.yaml"


def list_recipes() -> list[str]:
    if not BOOKS_DIR.exists():
        return []
    return sorted(p.stem for p in BOOKS_DIR.glob("*.yaml"))


def scaffold(slug: str, title: str | None = None) -> Path:
    path = recipe_path(slug)
    if path.exists():
        raise RecipeError(f"Đã có công thức {path}")
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        TEMPLATE.format(slug=slug, title=title or slug), encoding="utf-8")
    return path


def load(slug: str) -> Recipe:
    path = recipe_path(slug)
    if not path.exists():
        have = ", ".join(list_recipes()) or "(chưa có công thức nào)"
        raise RecipeError(
            f"Không thấy {path}\n"
            f"Công thức hiện có: {have}\n"
            f"Tạo mới: python studio.py make {slug} --init"
        )

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RecipeError(f"{path} sai cú pháp YAML:\n{exc}") from exc

    if not isinstance(data, dict):
        raise RecipeError(f"{path} phải là một map YAML")

    cover_raw = data.get("cover") or {}
    if not isinstance(cover_raw, dict):
        raise RecipeError("mục 'cover' phải là một map")

    r = Recipe(
        slug=data.get("slug") or slug,
        title=str(data.get("title") or slug),
        subtitle=str(data.get("subtitle") or ""),
        theme=str(data.get("theme") or "ocean"),
        pages=int(data.get("pages") or 40),
        generate=int(data.get("generate") or 0),
        complexity=str(data.get("complexity") or "medium"),
        density=str(data.get("density") or "rich"),
        style=str(data.get("style") or "kawaii"),
        lora=(str(data["lora"]) if data.get("lora") else None),
        lora_strength=float(data.get("lora_strength") or 0.9),
        seed=data.get("seed") if data.get("seed") not in ("", None) else None,
        cover=Cover(
            scene=cover_raw.get("scene") or None,
            bg=str(cover_raw.get("bg") or "#1B7A8C"),
        ),
        collection=str(data.get("collection") or ""),
        audience=str(data.get("audience") or "all"),
        price_usd=data.get("price_usd"),
        tags=list(data.get("tags") or []),
        description=str(data.get("description") or ""),
        path=path,
    )

    if r.generate <= 0:
        # Sinh dư 50%: tỷ lệ giữ lại thực tế thường 50-70%
        r.generate = int(r.pages * 1.5)

    _validate(r)
    return r


def _validate(r: Recipe) -> None:
    problems = []

    if r.complexity not in ("simple", "medium", "detailed", "intricate"):
        problems.append(
            f"complexity '{r.complexity}' không hợp lệ "
            f"(simple | medium | detailed | intricate)")
    if r.density not in ("single", "normal", "rich"):
        problems.append(
            f"density '{r.density}' không hợp lệ (single | normal | rich)")
    if r.style not in ("kawaii", "cartoon", "decorative"):
        problems.append(
            f"style '{r.style}' không hợp lệ (kawaii | cartoon | decorative)")
    if r.audience not in ("kids", "adults", "all"):
        problems.append(
            f"audience '{r.audience}' không hợp lệ (kids | adults | all)")
    if r.pages < 1:
        problems.append("pages phải >= 1")
    if r.generate < r.pages:
        problems.append(
            f"generate ({r.generate}) nhỏ hơn pages ({r.pages}) — "
            f"duyệt xong sẽ không đủ trang")
    if r.slug != slugify(r.slug):
        problems.append(f"slug '{r.slug}' phải ở dạng slug: {slugify(r.slug)}")
    if not 0.0 <= r.lora_strength <= 1.5:
        problems.append(
            f"lora_strength {r.lora_strength} ngoài khoảng hợp lý 0.0-1.5")
    bg = r.cover.bg.lstrip("#")
    if len(bg) != 6 or any(c not in "0123456789abcdefABCDEF" for c in bg):
        problems.append(f"cover.bg '{r.cover.bg}' phải dạng #RRGGBB")

    # Cảnh báo chứ không chặn: mandala vốn đã lấp kín trang, thêm rich vào
    # sẽ phá đối xứng
    if r.theme == "mandala" and r.density == "rich":
        problems.append(
            "theme mandala với density rich sẽ phá đối xứng — dùng normal")

    if problems:
        raise RecipeError(
            f"Công thức {r.path} có lỗi:\n  · " + "\n  · ".join(problems))
