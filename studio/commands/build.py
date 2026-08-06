"""
Bước ③ DỰNG — từ approved/ ra file bán được.

Sinh ra ba thứ:
  interior.pdf   file gửi nhà in / bán cho khách. KHÔNG BAO GIỜ để public.
  preview.pdf    3 trang đầu, hạ DPI, đóng dấu. Phát tự do.
  web/*.webp     ảnh cho trang chi tiết sách.

Bố cục interior.pdf theo đúng spec Lulu:
  - Khổ file 8.75 x 11.25 in (đã gồm bleed 0.125 in mỗi cạnh)
  - Hình nằm trong vùng an toàn 7.25 x 10 in
  - Gutter 0.25 in ở mép trái
  - IN MỘT MẶT: sau mỗi trang hình là một trang trắng, nên bút không lem
    sang hình kế tiếp. Tổng số trang = 2 x số hình (+ 2 nếu có trang bìa lót).
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .. import config
from ..imageops import load_font, prepare_page, watermark, web_preview
from ..util import image_files, info, read_json, warn, write_json

PAGE_W_PT = config.inch_to_pt(config.PAGE_W_IN)
PAGE_H_PT = config.inch_to_pt(config.PAGE_H_IN)


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "build",
        help="Dựng interior.pdf + preview.pdf + ảnh web",
        description="Đọc approved/ và xuất file bán được ra out/",
    )
    p.add_argument("slug", help="Tên thư mục sách")
    p.add_argument("--pages", type=int, default=None,
                   help="Chỉ lấy N trang đầu (mặc định lấy hết)")
    p.add_argument("--no-title-page", action="store_true",
                   help="Bỏ trang bìa lót ở đầu sách")
    p.add_argument("--autocontrast", action="store_true",
                   help="Kéo giãn tương phản trước khi khử xám. "
                        "Bật nếu ảnh Flux ra nền xám nhiều")
    p.add_argument("--black-point", type=int, default=config.LEVELS_BLACK)
    p.add_argument("--white-point", type=int, default=config.LEVELS_WHITE)
    p.set_defaults(func=run)


# --------------------------------------------------------------------------

def _title_page(title: str, subtitle: str = "") -> Image.Image:
    """Trang bìa lót vẽ bằng PIL — DejaVu hiển thị được dấu tiếng Việt,
    font Type1 sẵn có của reportlab thì không."""
    page = Image.new("L", (config.PAGE_W_PX, config.PAGE_H_PX), 255)
    draw = ImageDraw.Draw(page)

    font_title = load_font(150)
    font_sub = load_font(60)

    cx = config.PAGE_W_PX // 2
    cy = int(config.PAGE_H_PX * 0.42)

    draw.text((cx, cy), title, font=font_title, fill=0, anchor="mm")
    if subtitle:
        draw.text((cx, cy + 220), subtitle, font=font_sub, fill=90, anchor="mm")
    return page


def _write_pdf(pages: list[Image.Image | None], out_path: Path,
               dpi_scale: float = 1.0) -> None:
    """
    pages: mỗi phần tử là một ảnh trang, hoặc None cho trang trắng.
    Trang trắng không nhúng ảnh — vừa đúng vừa giảm dung lượng file.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=(PAGE_W_PT, PAGE_H_PT))
    c.setPageCompression(1)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for i, page in enumerate(pages):
            if page is not None:
                if dpi_scale != 1.0:
                    page = page.resize(
                        (round(page.width * dpi_scale),
                         round(page.height * dpi_scale)),
                        Image.LANCZOS,
                    )
                png = tmpdir / f"p{i:04d}.png"
                page.save(png, format="PNG", optimize=True)
                c.drawImage(
                    ImageReader(str(png)),
                    0, 0, width=PAGE_W_PT, height=PAGE_H_PT,
                    preserveAspectRatio=False,
                )
            c.showPage()
        c.save()


# --------------------------------------------------------------------------

def run(args) -> int:
    settings = config.load_settings()
    slug = args.slug
    approved = config.approved_dir(settings, slug)
    out = config.out_dir(settings, slug)

    sources = image_files(approved)
    if not sources:
        print(f"LỖI: {approved} trống. Chạy `approve {slug}` trước đã.")
        return 1

    if args.pages:
        sources = sources[: args.pages]

    book = read_json(config.book_dir(settings, slug) / "book.json", {}) or {}
    title = book.get("title") or slug

    info(f"Sách  : {title}  ({slug})")
    info(f"Nguồn : {len(sources)} ảnh từ approved/")
    info(f"Khổ   : {config.PAGE_W_IN}x{config.PAGE_H_IN} in "
         f"({config.PAGE_W_PX}x{config.PAGE_H_PX} px @ {config.DPI} DPI)")
    info("")

    # ---------------------------------------------------------- xử lý ảnh
    art_pages: list[Image.Image] = []
    problems: list[dict] = []

    for i, path in enumerate(sources, start=1):
        page, metrics = prepare_page(
            path,
            autocontrast=args.autocontrast,
            black_point=args.black_point,
            white_point=args.white_point,
        )
        art_pages.append(page)

        found = metrics.problems()
        if found:
            problems.append({"file": path.name, "problems": found})
            warn(f"{path.name}: {'; '.join(found)}")
        info(f"  [{i:>3}/{len(sources)}] {path.name}")

    info("")

    # ----------------------------------------------------- dựng interior
    seq: list[Image.Image | None] = []
    if not args.no_title_page:
        seq.append(_title_page(title))
        seq.append(None)  # mặt sau bìa lót

    for page in art_pages:
        seq.append(page)
        seq.append(None)  # mặt sau để trắng — chống lem bút

    interior = out / "interior.pdf"
    _write_pdf(seq, interior)
    info(f"✓ interior.pdf  — {len(seq)} trang, "
         f"{interior.stat().st_size / 1e6:.1f} MB")

    # ------------------------------------------------------ dựng preview
    n_prev = min(config.PREVIEW_PAGES, len(art_pages))
    preview_pages = [watermark(p.convert("RGB")) for p in art_pages[:n_prev]]
    preview = out / "preview.pdf"
    # 150 DPI: đủ xem, không đủ để in thay hàng thật
    _write_pdf(list(preview_pages), preview, dpi_scale=0.5)
    info(f"✓ preview.pdf   — {n_prev} trang có đóng dấu, "
         f"{preview.stat().st_size / 1e6:.1f} MB")

    # ---------------------------------------------------------- ảnh web
    web = out / "web"
    web.mkdir(parents=True, exist_ok=True)
    for old in web.glob("*.webp"):
        old.unlink()

    web_files = []
    for i, page in enumerate(art_pages[:n_prev], start=1):
        img = web_preview(page)
        name = f"page-{i:02d}.webp"
        img.save(web / name, format="WEBP", quality=82, method=6)
        web_files.append(f"web/{name}")
    info(f"✓ web/          — {len(web_files)} ảnh .webp")

    # ---------------------------------------------------------- manifest
    manifest = {
        "slug": slug,
        "title": title,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "art_pages": len(art_pages),
        "pdf_pages": len(seq),
        "print_spec": {
            "trim_in": [config.TRIM_W_IN, config.TRIM_H_IN],
            "page_in": [config.PAGE_W_IN, config.PAGE_H_IN],
            "bleed_in": config.BLEED_IN,
            "safety_in": config.SAFETY_IN,
            "gutter_in": config.GUTTER_IN,
            "dpi": config.DPI,
            "single_sided": True,
        },
        "files": {
            "interior": "interior.pdf",
            "preview": "preview.pdf",
            "web": web_files,
        },
        "warnings": problems,
    }
    write_json(out / "build.json", manifest)

    info("")
    info(f"Tất cả nằm ở: {out}")
    if problems:
        info(f"⚠ {len(problems)} trang có cảnh báo, xem build.json")
    info("")
    info("⚠ interior.pdf là sản phẩm bán. Không đẩy lên hosting công khai,")
    info("  không commit vào git. Thư mục library/ đã nằm trong .gitignore.")
    return 0
