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
    # Ảnh bìa giả — thật ra do `generate` sinh ra ở bước ①
    Image.new("RGB", (896, 1152), (200, 120, 60)).save(
        tmp / slug / "cover-art.png")
    rc = build_cmd.run(Args(
        slug=slug, pages=None, no_title_page=False,
        autocontrast=False,
        black_point=config.LEVELS_BLACK,
        white_point=config.LEVELS_WHITE,
        no_cover=False, subtitle="Kiểm thử", bg=None,
    ))
    check("build trả về 0", rc == 0)
    check("build tự dựng luôn bìa, không cần lệnh riêng",
          (tmp / slug / "out" / "cover.pdf").exists())

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

    print("\n[6] Bìa")
    # Công thức Lulu: gáy = (số trang / 444) + 0.06
    check("Gáy sách 80 trang = 0.240 in",
          abs(config.spine_width_in(80) - 0.2402) < 0.001,
          f"{config.spine_width_in(80):.4f} in")
    check("Gáy sách 200 trang = 0.510 in",
          abs(config.spine_width_in(200) - 0.5104) < 0.001,
          f"{config.spine_width_in(200):.4f} in")

    cw, ch = config.cover_size_in(80)
    # 8.5 + 8.5 + 0.2402 gáy + 0.25 bleed = 17.4902
    check("Khổ bìa 80 trang = 17.490 x 11.250 in",
          abs(cw - 17.4902) < 0.001 and abs(ch - 11.25) < 0.001,
          f"{cw:.3f} x {ch:.3f} in")

    from studio.commands import cover as cover_cmd
    art = tmp / "fake-cover.png"
    Image.new("RGB", (896, 1152), (200, 120, 60)).save(art)
    rc = cover_cmd.run(Args(
        slug=slug, scene=None, image=str(art), bg="#1B7A8C",
        subtitle="Kiểm thử", seed=1, steps=None,
    ))
    check("cover trả về 0", rc == 0)
    check("cover.pdf tồn tại", (out / "cover.pdf").exists())
    check("web/cover.webp tồn tại", (out / "web" / "cover.webp").exists())

    try:
        from pypdf import PdfReader
    except ImportError:
        pass
    else:
        cr = PdfReader(str(out / "cover.pdf"))
        check("cover.pdf có đúng 1 trang", len(cr.pages) == 1)
        cbox = cr.pages[0].mediabox
        pages_built = 2 + n_pages * 2
        exp_w, exp_h = config.cover_size_in(pages_built)
        check("Khổ cover.pdf khớp số trang thật của interior",
              abs(float(cbox.width) / 72 - exp_w) < 0.02
              and abs(float(cbox.height) / 72 - exp_h) < 0.02,
              f"{float(cbox.width) / 72:.3f} x {float(cbox.height) / 72:.3f} in "
              f"cho {pages_built} trang")
        size_mb = (out / "cover.pdf").stat().st_size / 1e6
        check("cover.pdf dưới 5 MB (dùng JPEG chứ không phải PNG)",
              size_mb < 5, f"{size_mb:.1f} MB")

    print("\n[7] Lọc kết quả model local (lệnh subjects)")
    from studio.llm import clean_lines, strip_thinking

    check("Cắt khối <think> của Qwen",
          strip_thinking("<think>để xem nào...</think>\nabc") == "abc")
    check("Cắt được cả <think> không có thẻ đóng (bị cụt token)",
          strip_thinking("abc\n<think>đang nghĩ dở") == "abc")

    # Đúng kiểu bừa bộn mà model 9B hay trả về: khối suy nghĩ, câu dẫn,
    # hàng rào ```, đánh số dù đã dặn đừng, lẫn tiếng Việt, trùng dòng, cụt lủn
    messy = """<think>
The user wants ocean scenes. Let me think about what to include.
</think>
Thinking Process:
Here are the scenes:
```
1. a smiling sea turtle swimming through a coral reef, small fish above it, seaweed below
2. a cluster of jellyfish drifting upward, bubbles around them, coral reef below
- a smiling sea turtle swimming through a coral reef, small fish above it, seaweed below
* con cá heo nhảy trên sóng, chim biển bay phía trên
jellyfish
a manta ray gliding over a busy coral reef, tropical fish everywhere, rocks below
```"""
    got, warns = clean_lines(messy, 24)

    check("Bỏ khối suy nghĩ, câu dẫn, ``` và số thứ tự",
          got and got[0].startswith("a smiling sea turtle"),
          repr(got[0][:40]) if got else "rỗng")
    check("Không sót chữ nào từ khối <think>",
          not any("user wants" in g.lower() for g in got))
    check("Bỏ mọi dòng kết thúc bằng ':' (tiêu đề, câu dẫn)",
          not any(g.endswith(":") for g in got)
          and not any("Thinking Process" in g for g in got))
    check("Bỏ hẳn dòng dưới 6 từ, không chỉ cảnh báo",
          not any(g == "jellyfish" for g in got))
    check("Bỏ dòng trùng", len(got) == 3, f"{len(got)} dòng")
    check("Bỏ dòng tiếng Việt", not any("cá heo" in g for g in got))

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
