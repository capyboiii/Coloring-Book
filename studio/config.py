"""
Cấu hình trung tâm — mọi con số về in ấn nằm ở đây.

Nguồn spec: Lulu Book Creation Guide
  - Bleed 0.125 in mỗi cạnh, BẮT BUỘC kể cả khi hình không tràn lề
  - Safety margin 0.5 in tính từ mép trim
  - Gutter (lề gáy) 0.2-0.3 in, bắt buộc khi sách > 60 trang
  - Coloring book in 1 MẶT để bút không lem sang trang sau
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv là tuỳ chọn
    pass


# --------------------------------------------------------------------------
# Spec in ấn
# --------------------------------------------------------------------------

DPI = 300

TRIM_W_IN = 8.5   # khổ sách sau khi xén
TRIM_H_IN = 11.0

BLEED_IN = 0.125  # Lulu yêu cầu
SAFETY_IN = 0.5   # chi tiết quan trọng phải nằm trong vùng này
GUTTER_IN = 0.25  # lề gáy thêm vào mép trong

# Khổ file PDF = khổ trim + bleed hai bên
PAGE_W_IN = TRIM_W_IN + 2 * BLEED_IN   # 8.75
PAGE_H_IN = TRIM_H_IN + 2 * BLEED_IN   # 11.25

# Vùng vẽ an toàn thực tế (đã trừ safety + gutter)
ART_W_IN = TRIM_W_IN - 2 * SAFETY_IN - GUTTER_IN  # 7.25
ART_H_IN = TRIM_H_IN - 2 * SAFETY_IN              # 10.0

# Vị trí vùng vẽ tính từ mép file PDF (không phải mép trim).
# Sách in 1 mặt: mọi trang có hình đều là trang lẻ (recto, nằm bên phải),
# nên gutter LUÔN ở bên trái. Không cần lật gương theo trang chẵn/lẻ.
ART_LEFT_IN = BLEED_IN + SAFETY_IN + GUTTER_IN  # 0.875
ART_TOP_IN = BLEED_IN + SAFETY_IN               # 0.625


def inch_to_px(inches: float) -> int:
    return int(round(inches * DPI))


def inch_to_pt(inches: float) -> float:
    """ReportLab làm việc bằng point: 1 inch = 72 pt."""
    return inches * 72.0


PAGE_W_PX = inch_to_px(PAGE_W_IN)   # 2625
PAGE_H_PX = inch_to_px(PAGE_H_IN)   # 3375
ART_W_PX = inch_to_px(ART_W_IN)     # 2175
ART_H_PX = inch_to_px(ART_H_IN)     # 3000


# --------------------------------------------------------------------------
# Sinh ảnh
# --------------------------------------------------------------------------

# Tỉ lệ đúng bằng vùng vẽ an toàn (7.25:10 = 0.725) và chia hết cho 16
# để Flux không phải nội suy. Sinh ở đây rồi upscale lên 2175x3000 sau.
GEN_W = 928
GEN_H = 1280

assert abs(GEN_W / GEN_H - ART_W_IN / ART_H_IN) < 0.001, "Tỉ lệ sinh ảnh lệch vùng vẽ"


# --------------------------------------------------------------------------
# Bìa
# --------------------------------------------------------------------------
#
# Bìa là MỘT trang PDF duy nhất trải ngang: bìa sau | gáy | bìa trước.
#
#   ┌────────────┬──┬────────────┐
#   │  bìa sau   │gáy│  bìa trước │   cao = 11.25 in (đã gồm bleed)
#   └────────────┴──┴────────────┘
#    8.5 in      ↑   8.5 in
#                └ dày theo số trang
#
# Công thức gáy của Lulu cho bìa mềm đóng keo:
#     gáy = (số trang / 444) + 0.06 in
# 444 là số trang trên mỗi inch của giấy tiêu chuẩn.
# 0.06 in là phần keo gáy.
#
# Sách 80 trang -> gáy 0.24 in. Sai con số này là bìa lệch hẳn khi in.

SPINE_PAGES_PER_INCH = 444.0
SPINE_GLUE_IN = 0.06

# Dưới ngưỡng này thì gáy quá mỏng, chữ in lên sẽ tràn sang mặt bìa
SPINE_TEXT_MIN_IN = 0.25

# Kích thước Flux sinh ảnh bìa màu (tỉ lệ xấp xỉ bìa trước có bleed)
COVER_GEN_W = 896
COVER_GEN_H = 1152


def spine_width_in(page_count: int) -> float:
    """Độ dày gáy theo số trang, đơn vị inch."""
    return page_count / SPINE_PAGES_PER_INCH + SPINE_GLUE_IN


def cover_size_in(page_count: int) -> tuple[float, float]:
    """Khổ file bìa (rộng, cao) tính bằng inch, đã gồm bleed."""
    width = 2 * TRIM_W_IN + spine_width_in(page_count) + 2 * BLEED_IN
    height = TRIM_H_IN + 2 * BLEED_IN
    return width, height


# --------------------------------------------------------------------------
# Xử lý ảnh
# --------------------------------------------------------------------------

# Khử xám bằng levels thay vì threshold cứng: giữ được khử răng cưa ở viền nét
# nhưng vẫn ép nền về trắng tinh và nét về đen tuyền.
LEVELS_BLACK = 80    # <= giá trị này -> đen tuyền
LEVELS_WHITE = 200   # >= giá trị này -> trắng tinh

# Ngưỡng cảnh báo tự động (Phase 2 sẽ dùng để lọc trước khi mắt người nhìn)
INK_RATIO_MIN = 0.005  # dưới 0.5% -> trang gần như trắng
INK_RATIO_MAX = 0.40   # trên 40%  -> trang đen kịt
THIN_LINE_MAX = 0.55   # tỉ lệ nét biến mất sau khi bào mòn 1px


# --------------------------------------------------------------------------
# Ảnh xem trước cho web
# --------------------------------------------------------------------------

PREVIEW_PAGES = 3        # số trang mẫu phát công khai
PREVIEW_WEB_WIDTH = 1000  # px
WATERMARK_TEXT = "PREVIEW"


# --------------------------------------------------------------------------
# Đường dẫn và biến môi trường
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    comfyui_url: str
    workflow: Path
    workflow_map: Path
    cover_workflow: Path
    cover_workflow_map: Path
    library: Path
    steps: int
    guidance: float
    timeout: int


def load_settings() -> Settings:
    def _path(key: str, default: str) -> Path:
        p = Path(_env(key, default))
        return p if p.is_absolute() else ROOT / p

    return Settings(
        comfyui_url=_env("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/"),
        workflow=_path("STUDIO_WORKFLOW", "workflows/flux_lineart.api.json"),
        workflow_map=_path("STUDIO_WORKFLOW_MAP", "workflows/flux_lineart.map.json"),
        cover_workflow=_path(
            "STUDIO_COVER_WORKFLOW", "workflows/flux_cover.api.json"),
        cover_workflow_map=_path(
            "STUDIO_COVER_WORKFLOW_MAP", "workflows/flux_cover.map.json"),
        library=_path("STUDIO_LIBRARY", "library"),
        # 4 bước là đúng cho FLUX.1-schnell (mô hình chưng cất).
        # Đổi sang FLUX.1-dev thì phải nâng lên 20-25.
        steps=int(_env("STUDIO_STEPS", "4")),
        guidance=float(_env("STUDIO_GUIDANCE", "3.5")),
        timeout=int(_env("STUDIO_TIMEOUT", "600")),
    )


# --------------------------------------------------------------------------
# Bố cục thư mục một cuốn sách
# --------------------------------------------------------------------------
#   library/<slug>/
#       book.json          thông tin cuốn sách
#       raw/               ảnh vừa sinh, CHƯA duyệt
#           001.png
#           001.json       prompt, seed, tham số -> để sinh lại y hệt
#       approved/          ảnh đã qua mắt người
#       out/               interior.pdf, preview.pdf, web/*.webp


def book_dir(settings: Settings, slug: str) -> Path:
    return settings.library / slug


def raw_dir(settings: Settings, slug: str) -> Path:
    return book_dir(settings, slug) / "raw"


def approved_dir(settings: Settings, slug: str) -> Path:
    return book_dir(settings, slug) / "approved"


def out_dir(settings: Settings, slug: str) -> Path:
    return book_dir(settings, slug) / "out"
