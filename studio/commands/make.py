"""
Chạy trọn một cuốn sách từ công thức trong `books/<slug>.yaml`.

    python studio.py make dai-duong-ky-thu --init   # tạo công thức mẫu
    python studio.py make dai-duong-ky-thu          # lần 1: sinh ảnh
    #   ... mở raw/ xoá ảnh xấu bằng tay ...
    python studio.py make dai-duong-ky-thu          # lần 2: dựng sách + bìa

Lệnh này **chạy tiếp được**: nó nhìn thư mục sách đang ở bước nào rồi làm
bước kế tiếp. Không có cách nào gộp thành đúng một lần chạy, vì ở giữa có
bước duyệt bằng mắt người — và đó là bước cố tình giữ lại.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from .. import config
from ..recipe import RecipeError, list_recipes, load, recipe_path, scaffold
from ..util import image_files, info, read_json, warn, write_json
from . import approve as approve_cmd
from . import build as build_cmd
from . import generate as generate_cmd


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "make",
        help="Chạy trọn một cuốn sách từ công thức books/<slug>.yaml",
        description="Sinh ảnh → (ông duyệt tay) → dựng ruột + bìa + gói bán",
    )
    p.add_argument("slug", nargs="?", default=None, help="Tên công thức")
    p.add_argument("--init", action="store_true",
                   help="Tạo file công thức mẫu rồi thoát")
    p.add_argument("--title", default=None, help="Tên sách, dùng với --init")
    p.add_argument("--list", action="store_true",
                   help="Liệt kê công thức đang có")
    p.add_argument("--yes", action="store_true",
                   help="Không dừng chờ duyệt — giữ hết ảnh vừa sinh. "
                        "Chỉ nên dùng để chạy thử")
    p.add_argument("--minutes", type=float, default=None,
                   help="Thời gian ông vừa bỏ ra để duyệt (phút)")
    p.add_argument("--force", action="store_true",
                   help="Dựng lại dù sách đã hoàn chỉnh")
    p.set_defaults(func=run)


# --------------------------------------------------------------------------

def _state(settings, slug: str) -> str:
    raw = image_files(config.raw_dir(settings, slug))
    approved = image_files(config.approved_dir(settings, slug))
    interior = config.out_dir(settings, slug) / "interior.pdf"

    if not raw:
        return "cần sinh ảnh"
    if not approved:
        return "cần duyệt"
    if not interior.exists():
        return "cần dựng"
    return "xong"


def _write_package(settings, r, slug: str) -> None:
    """
    Gói bàn giao cho web.

    Web chỉ đọc file này. Nó không cần biết Flux, ComfyUI hay prompt là gì —
    đúng ranh giới giữa studio và cửa hàng.
    """
    out = config.out_dir(settings, slug)
    build = read_json(out / "build.json", {}) or {}
    cover = read_json(out / "cover.json", {}) or {}
    stats = read_json(config.book_dir(settings, slug) / "approved.json", {}) or {}

    package = {
        "slug": slug,
        **r.sale_info(),
        "art_pages": build.get("art_pages"),
        "pdf_pages": build.get("pdf_pages"),
        "print": {
            **(build.get("print_spec") or {}),
            "spine_in": cover.get("spine_in"),
            "cover_in": cover.get("cover_in"),
        },
        "files": {
            # Hai file này KHÔNG được để public
            "interior": "interior.pdf",
            "cover": "cover.pdf",
            # Ba thứ này phát tự do
            "preview": "preview.pdf",
            "cover_image": "web/cover.webp",
            "preview_images": (build.get("files") or {}).get("web", []),
        },
        "source": {
            "recipe": str(r.path.name) if r.path else None,
            "theme": r.theme,
            "complexity": r.complexity,
            "density": r.density,
            "style": r.style,
            "seed": r.seed,
            "retention_rate": stats.get("retention_rate"),
            "review_minutes": stats.get("review_minutes"),
        },
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
    }
    write_json(out / "book.json", package)


def _do_generate(settings, r, args) -> int:
    return generate_cmd.run(SimpleNamespace(
        list_themes=False,
        topic=r.title,
        theme=r.theme,
        slug=r.slug,
        title=r.title,
        count=r.generate,
        complexity=r.complexity,
        density=r.density,
        style=r.style,
        seed=r.seed,
        steps=None,
        guidance=None,
        overwrite=False,
        force=False,
        no_cover=False,
        cover_scene=r.cover.scene,
    ))


def _do_finish(settings, r, args) -> int:
    rc = approve_cmd.run(SimpleNamespace(
        slug=r.slug, minutes=args.minutes, check_only=False))
    if rc != 0:
        return rc

    info("")
    return build_cmd.run(SimpleNamespace(
        slug=r.slug,
        pages=r.pages,
        no_title_page=False,
        autocontrast=False,
        black_point=config.LEVELS_BLACK,
        white_point=config.LEVELS_WHITE,
        no_cover=False,
        subtitle=r.subtitle or None,
        bg=r.cover.bg,
    ))


# --------------------------------------------------------------------------

def run(args) -> int:
    if args.list:
        names = list_recipes()
        if not names:
            info("Chưa có công thức nào trong books/")
            info('Tạo mới: python studio.py make <ten-sach> --init')
            return 0
        info("Công thức trong books/:")
        for n in names:
            info(f"  {n}")
        return 0

    if not args.slug:
        print("LỖI: thiếu tên công thức.")
        print('Ví dụ: python studio.py make dai-duong-ky-thu')
        print('       python studio.py make --list')
        return 1

    if args.init:
        try:
            path = scaffold(args.slug, args.title)
        except RecipeError as exc:
            print(f"LỖI: {exc}")
            return 1
        info(f"✓ Tạo {path}")
        info("")
        info("Mở file đó ra sửa chủ đề, số trang, giá... rồi chạy:")
        info(f"  python studio.py make {args.slug}")
        return 0

    try:
        r = load(args.slug)
    except RecipeError as exc:
        print(f"LỖI: {exc}")
        return 1

    settings = config.load_settings()
    state = _state(settings, r.slug)

    info(f"Công thức : {recipe_path(r.slug).name}")
    info(f"Sách      : {r.title}")
    info(f"Chủ đề    : {r.theme} · {r.style} · {r.complexity} · density {r.density}")
    info(f"Trang      : {r.pages} hình (sinh {r.generate} để còn chỗ loại)")
    info(f"Đối tượng  : {r.audience}")
    info(f"Trạng thái : {state}")
    for h in r.hints():
        warn(h)
    info("")

    if state == "xong" and not args.force:
        out = config.out_dir(settings, r.slug)
        info(f"Sách đã hoàn chỉnh ở {out}")
        info("Dựng lại thì thêm --force")
        return 0

    if state == "cần sinh ảnh":
        rc = _do_generate(settings, r, args)
        if rc != 0:
            return rc

        if not args.yes:
            raw = config.raw_dir(settings, r.slug)
            info("")
            info("─" * 60)
            info("DỪNG LẠI ĐỂ ÔNG DUYỆT — đây là bước cố tình giữ bằng tay")
            info("")
            info(f"  1. Mở {raw}")
            info("  2. Xoá ảnh xấu. BẤM GIỜ từ lúc mở tới lúc xong.")
            info(f"  3. Chạy lại:  python studio.py make {r.slug} "
                 f"--minutes <số phút>")
            info("─" * 60)
            return 0

        warn("--yes: giữ hết ảnh vừa sinh, bỏ qua bước duyệt. "
             "Chỉ nên dùng để chạy thử.")
        info("")

    elif state == "cần duyệt":
        info("Đã có ảnh trong raw/, coi như ông duyệt xong. Dựng sách...")
        info("")

    rc = _do_finish(settings, r, args)
    if rc != 0:
        return rc

    _write_package(settings, r, r.slug)

    out = config.out_dir(settings, r.slug)
    info("")
    info("─" * 60)
    info(f"XONG — gói sách ở {out}")
    info("")
    info("  book.json        thông tin cho web đọc")
    info("  interior.pdf     ⚠ sản phẩm bán, KHÔNG để public")
    info("  cover.pdf        ⚠ gửi nhà in")
    info("  preview.pdf      phát tự do")
    info("  web/*.webp       ảnh cho trang chi tiết")
    info("─" * 60)
    return 0
