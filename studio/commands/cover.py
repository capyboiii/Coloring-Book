"""
Dựng bìa in — bìa sau | gáy | bìa trước trong MỘT trang PDF.

    ┌────────────┬──┬────────────┐
    │  bìa sau   │gáy│  bìa trước │
    └────────────┴──┴────────────┘

Độ dày gáy phụ thuộc SỐ TRANG THẬT của interior.pdf, nên phải chạy `build`
trước. Sai độ dày gáy là bìa lệch hẳn khi in — hình bìa trước tràn sang gáy,
chữ gáy tràn sang mặt bìa.

Ảnh bìa do Flux vẽ màu (workflow riêng, bỏ ràng buộc line art). Chữ tiêu đề
do Pillow ghép vào sau — KHÔNG để Flux viết chữ, nó sai chính tả.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .. import config
from ..imageops import (cover_outline_ratio, cover_vividness,
                        load_font)
from ..prompts import build_cover_prompt, has_non_ascii, load_subjects
from ..providers import GenRequest, ProviderError, get_provider
from ..util import image_files, info, read_json, warn, write_json

DEFAULT_BG = "#1B7A8C"  # xanh biển đậm


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "cover",
        help="Dựng cover.pdf (bìa sau + gáy + bìa trước)",
        description="Chạy SAU `build`, vì độ dày gáy phụ thuộc số trang thật",
    )
    p.add_argument("slug", help="Tên thư mục sách")
    p.add_argument("--scene", default=None,
                   help="Mô tả ảnh bìa bằng TIẾNG ANH. Không có thì lấy cảnh "
                        "đầu tiên trong bộ chủ thể của sách")
    p.add_argument("--image", default=None,
                   help="Dùng file ảnh có sẵn thay vì để Flux vẽ")
    p.add_argument("--bg", default=DEFAULT_BG,
                   help=f"Màu nền dạng #RRGGBB (mặc định {DEFAULT_BG})")
    p.add_argument("--subtitle", default=None,
                   help="Dòng chữ nhỏ dưới tiêu đề")
    p.add_argument("--colors", default=None, metavar="<màu chính>",
                   help='Màu chủ đạo cho chủ thể, tiếng Anh. '
                        'Ví dụ: "warm pink and cream"')
    p.add_argument("--colors2", default=None, metavar="<màu phụ>",
                   help='Màu phụ. Ví dụ: "soft yellow and mint green"')
    p.add_argument("--bg-colors", dest="bg_colors", default=None,
                   metavar="<màu nền>",
                   help='Màu nền. Ví dụ: "sky blue and sandy beige"')
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--steps", type=int, default=None)
    p.set_defaults(func=run)


# --------------------------------------------------------------------------
# Chữ
# --------------------------------------------------------------------------

def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (c / 255 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(draw, text: str, max_w: int, max_h: int,
              start: int, min_size: int = 24):
    """Thu nhỏ cỡ chữ tới khi tiêu đề lọt vào khung. Trả về (font, các dòng)."""
    size = start
    while size > min_size:
        font = load_font(size)
        lines = _wrap(draw, text, font, max_w)
        height = len(lines) * size * 1.25
        if height <= max_h:
            return font, lines
        size -= 6
    font = load_font(min_size)
    return font, _wrap(draw, text, font, max_w)


def _draw_block(draw, lines, font, cx: int, top: int, fill, spacing=1.25) -> int:
    y = top
    step = int(font.size * spacing) if hasattr(font, "size") else 40
    for line in lines:
        draw.text((cx, y), line, font=font, fill=fill, anchor="ma")
        y += step
    return y


# --------------------------------------------------------------------------

def _page_count(settings, slug: str) -> int | None:
    """Số trang thật của interior.pdf. Ưu tiên build.json, không có thì suy ra."""
    out = config.out_dir(settings, slug)
    manifest = read_json(out / "build.json")
    if manifest and manifest.get("pdf_pages"):
        return int(manifest["pdf_pages"])

    approved = image_files(config.approved_dir(settings, slug))
    if approved:
        return len(approved) * 2 + 2  # mỗi hình 2 trang, cộng bìa lót
    return None


def _make_art(settings, args, book: dict) -> Image.Image:
    """Ảnh bìa: lấy từ --image, hoặc để Flux vẽ."""
    if args.image:
        path = Path(args.image)
        if not path.exists():
            raise FileNotFoundError(f"Không thấy ảnh {path}")
        origin = ("Flux đã vẽ lúc generate" if path.name == "cover-art.png"
                  else "do ông cấp")
        info(f"Ảnh bìa   : {path.name} ({origin})")
        with Image.open(path) as im:
            return im.convert("RGB")

    scene = args.scene
    if not scene:
        theme = book.get("theme")
        if theme:
            try:
                scene = load_subjects(theme)[0]
                info(f"Cảnh bìa  : lấy từ bộ '{theme}'")
            except (FileNotFoundError, IndexError):
                scene = None
    if not scene:
        scene = book.get("topic") or book.get("title") or "a cheerful scene"
        if has_non_ascii(scene):
            warn(f"Cảnh bìa {scene!r} là tiếng Việt — Flux sẽ bỏ qua. "
                 f"Dùng --scene \"<mô tả tiếng Anh>\"")

    prompt = build_cover_prompt(
        scene,
        main_colors=getattr(args, "colors", None),
        secondary_colors=getattr(args, "colors2", None),
        background_colors=getattr(args, "bg_colors", None),
    )
    info(f"Prompt bìa: {prompt[:110]}...")

    provider = get_provider(settings, "comfyui", cover=True)
    info(f"ComfyUI   : {provider.healthcheck()}")

    import random
    req = GenRequest(
        prompt=prompt,
        negative="",
        seed=args.seed if args.seed is not None
        else random.randint(1, 2**31 - 1),
        width=config.COVER_GEN_W,
        height=config.COVER_GEN_H,
        steps=args.steps if args.steps is not None else settings.steps,
        guidance=settings.guidance,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cover.png"
        path.write_bytes(provider.generate(req))
        with Image.open(path) as im:
            art = im.convert("RGB")

    # Bìa nhạt thì lên kệ là chìm nghỉm, mà nhìn từng ảnh một không thấy gì
    # lạ — phải có số mới so được. Xem cover_vividness().
    sat, pale = cover_vividness(art)
    outline = cover_outline_ratio(art)
    info(f"Độ rực    : bão hoà {sat:.0f}/255, {pale:.0%} nhạt, "
         f"nét đen {outline:.1%}")
    if sat < config.COVER_SAT_MIN or pale > config.COVER_PALE_MAX:
        warn(f"BÌA NHẠT. Cần bão hoà >= {config.COVER_SAT_MIN:.0f} và "
             f"dưới {config.COVER_PALE_MAX:.0%} diện tích nhạt.")
        warn("Sinh lại với seed khác, hoặc tả cảnh có sẵn màu mạnh — "
             '"a penguin on white snow" thì kiểu gì cũng ra trắng.')
    if outline < config.COVER_OUTLINE_MIN:
        warn(f"BÌA KHÔNG CÓ NÉT ĐEN ({outline:.1%}, cần "
             f">= {config.COVER_OUTLINE_MIN:.0%}). Bìa phải trông như trang "
             f"tô màu ĐÃ TÔ, để khách nhìn là biết bên trong ra sao.")
        warn("Sinh lại với seed khác.")
    return art


def _cover_fit(img: Image.Image, w: int, h: int) -> Image.Image:
    """Phóng rồi CẮT để lấp đầy khung — bìa phải tràn lề, không được chừa trắng."""
    scale = max(w / img.width, h / img.height)
    resized = img.resize(
        (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
        Image.LANCZOS,
    )
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


# --------------------------------------------------------------------------

def run(args) -> int:
    return make_cover(
        config.load_settings(), args.slug,
        image=args.image, scene=args.scene, bg=args.bg,
        subtitle=args.subtitle, seed=args.seed, steps=args.steps,
        colors=getattr(args, "colors", None),
        colors2=getattr(args, "colors2", None),
        bg_colors=getattr(args, "bg_colors", None),
    )


def make_cover(settings, slug: str, *, image: str | None = None,
               scene: str | None = None, bg: str = DEFAULT_BG,
               subtitle: str | None = None, seed: int | None = None,
               steps: int | None = None, colors: str | None = None,
               colors2: str | None = None,
               bg_colors: str | None = None) -> int:
    """
    Dựng bìa. Tách khỏi `run` để `build` gọi lại được — người dùng không phải
    nhớ chạy thêm một lệnh nữa.
    """
    args = SimpleNamespace(image=image, scene=scene, bg=bg,
                           subtitle=subtitle, seed=seed, steps=steps,
                           colors=colors, colors2=colors2,
                           bg_colors=bg_colors)
    out = config.out_dir(settings, slug)

    pages = _page_count(settings, slug)
    if not pages:
        print(f"LỖI: chưa biết số trang. Chạy `build {slug}` trước đã.")
        return 1

    book = read_json(config.book_dir(settings, slug) / "book.json", {}) or {}
    title = book.get("title") or slug

    spine_in = config.spine_width_in(pages)
    cover_w_in, cover_h_in = config.cover_size_in(pages)

    info(f"Sách      : {title}  ({slug})")
    info(f"Số trang  : {pages}")
    info(f"Gáy       : {spine_in:.3f} in  "
         f"= {pages}/{config.SPINE_PAGES_PER_INCH:.0f} + "
         f"{config.SPINE_GLUE_IN}")
    info(f"Khổ bìa   : {cover_w_in:.3f} x {cover_h_in:.3f} in")
    info("")

    try:
        art = _make_art(settings, args, book)
    except (ProviderError, FileNotFoundError) as exc:
        print(f"LỖI: {exc}")
        return 1

    # ---------------------------------------------------------- toạ độ (px)
    W = config.inch_to_px(cover_w_in)
    H = config.inch_to_px(cover_h_in)
    bleed = config.inch_to_px(config.BLEED_IN)
    safety = config.inch_to_px(config.SAFETY_IN)
    spine_px = config.inch_to_px(spine_in)
    panel = config.inch_to_px(config.TRIM_W_IN)

    back_left = bleed                    # mép trim bìa sau
    spine_left = bleed + panel
    front_left = spine_left + spine_px   # mép trim bìa trước

    bg = tuple(int(args.bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    on_dark = _luminance(bg) < 0.55
    fg = (255, 255, 255) if on_dark else (20, 20, 20)

    cover = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(cover)

    # ------------------------------------------------- bìa trước: ảnh tràn lề
    front_w = W - front_left            # gồm cả bleed phải
    cover.paste(_cover_fit(art, front_w, H), (front_left, 0))

    # ------------------------------------------------ bìa trước: dải chữ trên
    band_h = int(H * 0.24)
    band = Image.new("RGBA", (front_w, band_h), (*bg, 225))
    cover.paste(Image.alpha_composite(
        cover.crop((front_left, 0, W, band_h)).convert("RGBA"), band
    ).convert("RGB"), (front_left, 0))

    text_w = W - bleed - safety - (front_left + safety)
    text_cx = front_left + safety + text_w // 2

    font_title, lines = _fit_text(
        draw, title, text_w, int(band_h * 0.55), start=int(H * 0.075))
    y = _draw_block(draw, lines, font_title,
                    text_cx, int(H * 0.045), (255, 255, 255) if on_dark else fg)

    if args.subtitle:
        font_sub = load_font(int(H * 0.026))
        _draw_block(draw, _wrap(draw, args.subtitle, font_sub, text_w),
                    font_sub, text_cx, y + 20,
                    (255, 255, 255) if on_dark else fg)

    # ------------------------------------------------------------- bìa sau
    back_cx = back_left + panel // 2
    back_w = panel - 2 * safety
    font_back, back_lines = _fit_text(
        draw, title, back_w, int(H * 0.2), start=int(H * 0.045))
    _draw_block(draw, back_lines, font_back, back_cx, int(H * 0.40), fg)

    font_note = load_font(int(H * 0.022))
    draw.text((back_cx, int(H * 0.62)),
              f"{(pages - 2) // 2} trang tô màu", font=font_note,
              fill=fg, anchor="ma")

    # ---------------------------------------------------------------- gáy
    if spine_in >= config.SPINE_TEXT_MIN_IN:
        strip = Image.new("RGB", (H, spine_px), bg)
        sdraw = ImageDraw.Draw(strip)
        font_spine, _ = _fit_text(
            draw, title, int(H * 0.7), spine_px, start=int(spine_px * 0.55))
        sdraw.text((H // 2, spine_px // 2), title,
                   font=font_spine, fill=fg, anchor="mm")
        cover.paste(strip.rotate(90, expand=True), (spine_left, 0))
    else:
        warn(f"Gáy {spine_in:.3f} in mỏng hơn {config.SPINE_TEXT_MIN_IN} in "
             f"— bỏ chữ gáy, in lên sẽ tràn sang mặt bìa")

    # --------------------------------------------------------------- xuất
    out.mkdir(parents=True, exist_ok=True)
    pdf = out / "cover.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        # JPEG chứ không phải PNG. Bìa là ảnh màu dày đặc chi tiết — PNG
        # không nén được, ra file 13 MB. JPEG chất lượng 92 ở 300 DPI mắt
        # thường không phân biệt được, mà file nhỏ hơn khoảng 10 lần.
        # (Ruột vẫn dùng PNG vì line art đen trắng nén rất tốt và JPEG sẽ
        # tạo nhiễu quanh nét.)
        png = Path(tmp) / "cover.jpg"
        cover.save(png, format="JPEG", quality=92, subsampling=0, dpi=(300, 300))
        c = canvas.Canvas(
            str(pdf),
            pagesize=(config.inch_to_pt(cover_w_in),
                      config.inch_to_pt(cover_h_in)),
        )
        c.setPageCompression(1)
        c.drawImage(ImageReader(str(png)), 0, 0,
                    width=config.inch_to_pt(cover_w_in),
                    height=config.inch_to_pt(cover_h_in),
                    preserveAspectRatio=False)
        c.showPage()
        c.save()

    # Ảnh bìa trước cho web (không có gáy, không có bìa sau)
    front_only = cover.crop((front_left + bleed // 2, bleed,
                             W - bleed, H - bleed))
    web = out / "web"
    web.mkdir(parents=True, exist_ok=True)
    ratio = config.PREVIEW_WEB_WIDTH / front_only.width
    front_only.resize(
        (config.PREVIEW_WEB_WIDTH, round(front_only.height * ratio)),
        Image.LANCZOS,
    ).save(web / "cover.webp", format="WEBP", quality=86, method=6)

    write_json(out / "cover.json", {
        "slug": slug,
        "title": title,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "page_count": pages,
        "spine_in": round(spine_in, 4),
        "cover_in": [round(cover_w_in, 4), round(cover_h_in, 4)],
        "cover_px": [W, H],
        "background": args.bg,
        "spine_text": spine_in >= config.SPINE_TEXT_MIN_IN,
        "files": {"cover": "cover.pdf", "web": "web/cover.webp"},
    })

    info("")
    info(f"✓ cover.pdf     — {cover_w_in:.3f} x {cover_h_in:.3f} in, "
         f"{pdf.stat().st_size / 1e6:.1f} MB")
    info(f"✓ web/cover.webp")
    info("")
    info("⚠ Số trang đổi thì ĐỘ DÀY GÁY ĐỔI THEO. Sửa ruột xong phải chạy")
    info("  lại `build` — nó dựng lại bìa luôn. Đừng dùng lại bìa cũ.")
    return 0
