"""
Bước ② DUYỆT — chốt lại những ảnh còn sót trong raw/ sau khi ông xoá tay.

Phase 1 cố tình KHÔNG xây màn hình duyệt. Ông mở File Explorer, xoá ảnh xấu,
rồi chạy lệnh này. Nó chép phần còn lại sang approved/ và ghi lại hai con số
mà roadmap cần: tỷ lệ giữ lại và thời gian duyệt.

Hai con số đó quyết định Phase 2 nên làm gì. Đừng bỏ qua.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone

from .. import config
from ..imageops import prepare_page
from ..util import image_files, info, read_json, warn, write_json


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "approve",
        help="Chép ảnh còn lại trong raw/ sang approved/",
        description="Chạy sau khi đã xoá tay ảnh xấu trong raw/",
    )
    p.add_argument("slug", help="Tên thư mục sách")
    p.add_argument("--minutes", type=float, default=None,
                   help="Thời gian ông vừa bỏ ra để duyệt (phút). "
                        "Ghi lại để so sánh với Phase 2")
    p.add_argument("--check-only", action="store_true",
                   help="Chỉ soi chất lượng, không chép gì")
    p.set_defaults(func=run)


def run(args) -> int:
    settings = config.load_settings()
    slug = args.slug
    raw = config.raw_dir(settings, slug)
    approved = config.approved_dir(settings, slug)

    if not raw.exists():
        print(f"LỖI: không có {raw}. Chạy `generate` trước đã.")
        return 1

    kept = image_files(raw)
    if not kept:
        print(f"LỖI: {raw} không còn ảnh nào.")
        return 1

    book = read_json(config.book_dir(settings, slug) / "book.json", {}) or {}
    planned = book.get("planned_count") or len(kept)

    # Chạy `generate` nhiều lần với --count khác nhau thì planned_count trong
    # book.json là của lần CUỐI, không phải tổng. Giữ nguyên sẽ ra tỷ lệ giữ
    # lại kiểu 250% — vô nghĩa. Lấy con số lớn hơn làm mẫu số.
    if len(kept) > planned:
        warn(f"raw/ có {len(kept)} ảnh nhưng book.json ghi chỉ sinh {planned}. "
             f"Chắc ông chạy generate nhiều lần. Lấy {len(kept)} làm mẫu số, "
             f"nên tỷ lệ giữ lại dưới đây là chặn dưới, không phải số thật.")
        planned = len(kept)

    info(f"Sách    : {slug}")
    info(f"Đã sinh : {planned} ảnh")
    info(f"Giữ lại : {len(kept)} ảnh")
    info("")

    # Soi chất lượng từng ảnh giữ lại.
    #
    # Phải đo trên TRANG IN đã phóng to, không phải ảnh gốc. Ảnh gốc 928px có
    # nét dày ~3px; bào mòn 1px là mất 2/3, ra điểm rất thấp và báo động giả.
    # Cũng chính trang đó ở 2175px thì nét dày ~8px, bào mòn 1px chẳng hề gì.
    # Dùng chung prepare_page với `build` để hai lệnh nói cùng một ngôn ngữ.
    flagged = 0
    report = []
    for path in kept:
        _, m = prepare_page(path)
        problems = m.problems()
        report.append({"file": path.name, **m.to_dict()})
        if problems:
            flagged += 1
            warn(f"{path.name}: {'; '.join(problems)}")

    if flagged:
        info("")
        info(f"{flagged}/{len(kept)} ảnh bị đánh dấu ở trên. "
             f"Đây là cảnh báo, không chặn — ông tự quyết.")
        info("")

    if args.check_only:
        info("Chế độ --check-only, không chép gì.")
        return 0

    # Chép sang approved/
    approved.mkdir(parents=True, exist_ok=True)
    for old in image_files(approved):
        old.unlink()

    for path in kept:
        shutil.copy2(path, approved / path.name)
        meta = path.with_suffix(".json")
        if meta.exists():
            shutil.copy2(meta, approved / meta.name)

    retention = len(kept) / planned if planned else 0.0
    stats = {
        "slug": slug,
        "generated": planned,
        "kept": len(kept),
        "retention_rate": round(retention, 3),
        "review_minutes": args.minutes,
        "minutes_per_100_images": (
            round(args.minutes / planned * 100, 1)
            if args.minutes and planned else None
        ),
        "flagged": flagged,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "pages": report,
    }
    write_json(config.book_dir(settings, slug) / "approved.json", stats)

    info(f"Đã chép {len(kept)} ảnh sang {approved}")
    info("")
    info("── SỐ LIỆU PHASE 1 ──")
    info(f"Tỷ lệ giữ lại : {retention:.0%}  (roadmap dự đoán 40–60%)")
    if args.minutes:
        info(f"Thời gian duyệt: {args.minutes:.0f} phút cho {planned} ảnh")
        info(f"Quy đổi        : {stats['minutes_per_100_images']} phút / 100 ảnh")
    else:
        info("Thời gian duyệt: CHƯA GHI — chạy lại kèm --minutes <số phút>")
    info("")
    info(f"Bước tiếp theo: python studio.py build {slug}")
    return 0
