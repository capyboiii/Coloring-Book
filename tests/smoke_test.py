#!/usr/bin/env python3
"""
Kiểm thử đường ống KHÔNG CẦN GPU.

Sinh ảnh line art giả bằng Pillow rồi chạy approve + build, kiểm tra
PDF ra đúng khổ và đúng số trang.

    python tests/smoke_test.py

Chạy cái này mỗi lần sửa imageops hoặc build. Nó bắt được lỗi khổ giấy
và lỗi bố cục trước khi ông đốt 40 lượt GPU.
"""

from __future__ import annotations

import math
import random
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from studio import config  # noqa: E402
from studio.commands import approve as approve_cmd  # noqa: E402
from studio.commands import build as build_cmd  # noqa: E402
from studio.util import write_json  # noqa: E402

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "✓" if condition else "✗"
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILURES.append(label)


def fake_lineart(path: Path, seed: int) -> None:
    """Ảnh giả: nét đen trên nền hơi xám, giống thứ Flux hay trả về."""
    rnd = random.Random(seed)
    img = Image.new("L", (config.GEN_W, config.GEN_H), 244)  # nền XÁM cố ý
    draw = ImageDraw.Draw(img)
    cx, cy = config.GEN_W // 2, config.GEN_H // 2

    # Giữ mọi nét cách mép >5% để không dính cảnh báo "chạm mép"
    for i in range(6):
        r = 60 + i * 45
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=20, width=7)

    for i in range(12):
        angle = i * math.pi / 6 + rnd.random()
        draw.line(
            (cx, cy,
             cx + int(300 * math.cos(angle)),
             cy + int(300 * math.sin(angle))),
            fill=20, width=6,
        )
    img.save(path)


class Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="studio-smoke-"))
    slug = "kiem-thu"
    n_pages = 4

    # Trỏ thư viện sách vào thư mục tạm
    import os
    os.environ["STUDIO_LIBRARY"] = str(tmp)

    raw = tmp / slug / "raw"
    raw.mkdir(parents=True)

    print(f"Thư mục tạm: {tmp}")
    print(f"Sinh {n_pages} ảnh giả...")
    for i in range(1, n_pages + 1):
        fake_lineart(raw / f"{i:03d}.png", seed=i)

    write_json(tmp / slug / "book.json", {
        "slug": slug,
        "title": "Sách Kiểm Thử",
        "topic": "kiem thu",
        "planned_count": n_pages,
    })

    print("\n[1] Cấu hình khổ giấy")
    check("Khổ file PDF 8.75 x 11.25 in",
          (config.PAGE_W_IN, config.PAGE_H_IN) == (8.75, 11.25),
          f"{config.PAGE_W_IN} x {config.PAGE_H_IN}")
    check("Pixel/trang 2625 x 3375",
          (config.PAGE_W_PX, config.PAGE_H_PX) == (2625, 3375),
          f"{config.PAGE_W_PX} x {config.PAGE_H_PX}")
    check("Vùng vẽ 7.25 x 10 in",
          (round(config.ART_W_IN, 3), round(config.ART_H_IN, 3)) == (7.25, 10.0),
          f"{config.ART_W_IN} x {config.ART_H_IN}")
    check("Lề trái = bleed + safety + gutter",
          abs(config.ART_LEFT_IN - 0.875) < 1e-9,
          f"{config.ART_LEFT_IN} in")

    print("\n[2] Khử xám")
    from studio.imageops import apply_levels, prepare_page
    grey = Image.new("L", (10, 10), 244)
    cleaned = apply_levels(grey)
    check("Nền xám 244 bị ép về trắng tinh 255",
          cleaned.getextrema() == (255, 255),
          f"extrema {cleaned.getextrema()}")

    page, metrics = prepare_page(raw / "001.png")
    check("Trang ra đúng khổ đầy đủ",
          page.size == (config.PAGE_W_PX, config.PAGE_H_PX),
          f"{page.size}")
    check("Nền trang là trắng tinh", page.getextrema()[1] == 255)
    check("ink_ratio trong khoảng hợp lệ",
          config.INK_RATIO_MIN < metrics.ink_ratio < config.INK_RATIO_MAX,
          f"{metrics.ink_ratio:.3%}")

    print("\n[3] Lệnh approve")
    rc = approve_cmd.run(Args(slug=slug, minutes=12.0, check_only=False))
    check("approve trả về 0", rc == 0)
    approved = list((tmp / slug / "approved").glob("*.png"))
    check(f"Chép đủ {n_pages} ảnh sang approved/",
          len(approved) == n_pages, f"{len(approved)} ảnh")

    print("\n[4] Lệnh build")
    rc = build_cmd.run(Args(
        slug=slug, pages=None, no_title_page=False,
        autocontrast=False,
        black_point=config.LEVELS_BLACK,
        white_point=config.LEVELS_WHITE,
    ))
    check("build trả về 0", rc == 0)

    out = tmp / slug / "out"
    interior = out / "interior.pdf"
    preview = out / "preview.pdf"
    check("interior.pdf tồn tại", interior.exists())
    check("preview.pdf tồn tại", preview.exists())
    check("Có ảnh .webp cho web",
          len(list((out / "web").glob("*.webp"))) > 0)

    print("\n[5] Nội dung PDF")
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  ! Chưa cài pypdf, bỏ qua phần kiểm tra PDF")
        print("    pip install -r requirements-dev.txt")
    else:
        reader = PdfReader(str(interior))
        expected = 2 + n_pages * 2  # bìa lót + mặt sau, rồi mỗi hình 2 trang
        check(f"interior.pdf có đúng {expected} trang",
              len(reader.pages) == expected, f"{len(reader.pages)} trang")
        check("Số trang chẵn (yêu cầu đóng gáy keo)",
              len(reader.pages) % 2 == 0)

        box = reader.pages[0].mediabox
        w_in = float(box.width) / 72
        h_in = float(box.height) / 72
        check("MediaBox = 8.75 x 11.25 in",
              abs(w_in - 8.75) < 0.01 and abs(h_in - 11.25) < 0.01,
              f"{w_in:.3f} x {h_in:.3f} in")

        prev_reader = PdfReader(str(preview))
        check(f"preview.pdf có {config.PREVIEW_PAGES} trang",
              len(prev_reader.pages) == min(config.PREVIEW_PAGES, n_pages),
              f"{len(prev_reader.pages)} trang")

    print("\n" + "─" * 50)
    if FAILURES:
        print(f"HỎNG: {len(FAILURES)} mục không đạt")
        for f in FAILURES:
            print(f"  · {f}")
    else:
        print("Toàn bộ kiểm thử ĐẠT")

    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
