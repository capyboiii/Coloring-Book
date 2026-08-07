"""
Sinh bộ chủ thể cho một chủ đề bất kỳ.

    python studio.py subjects "Giáng sinh" --count 24
    → themes/giang-sinh.txt

Sau đó dùng như bộ dựng sẵn:

    python studio.py generate "Giáng sinh ấm áp" --theme giang-sinh --count 40

Chạy bằng model local trong LM Studio. Không cần API key, không tốn tiền,
không gửi gì ra ngoài.
"""

from __future__ import annotations

from datetime import date

from ..llm import LLMError, base_url, generate_subjects, list_models
from ..prompts import THEMES_DIR, list_themes
from ..util import info, slugify, warn


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "subjects",
        help="Sinh bộ chủ thể cho một chủ đề bất kỳ (cần LM Studio)",
        description="Biến một chủ đề tiếng Việt thành N cảnh tiếng Anh",
    )
    p.add_argument("topic", nargs="?", default=None,
                   help='Chủ đề, ví dụ "Giáng sinh"')
    p.add_argument("--count", type=int, default=24,
                   help="Số cảnh cần sinh (mặc định 24)")
    p.add_argument("--list-models", action="store_true",
                   help="Liệt kê model LM Studio đang nạp rồi thoát")
    p.add_argument("--name", default=None,
                   help="Tên bộ. Mặc định suy ra từ chủ đề")
    p.add_argument("--audience", default="all",
                   choices=["kids", "adults", "all"],
                   help="Nhắm tới ai — ảnh hưởng cách viết cảnh")
    p.add_argument("--model", default=None,
                   help="Tên model trong LM Studio. Mặc định lấy model "
                        "đang nạp")
    p.add_argument("--temperature", type=float, default=0.85,
                   help="Cao thì đa dạng hơn nhưng dễ lạc đề (mặc định 0.85)")
    p.add_argument("--overwrite", action="store_true",
                   help="Ghi đè bộ đã có")
    p.add_argument("--dry-run", action="store_true",
                   help="In ra màn hình, không ghi file")
    p.set_defaults(func=run)


HEADER = """\
# {topic} — {n} cảnh
#
# Sinh tự động bằng `studio.py subjects` ngày {today}
# Model local: {model}
# Sửa tay thoải mái — đây là file văn bản thuần, mỗi dòng một trang.
#
# Công thức mỗi dòng: nhân vật chính + hành động + 2-3 thứ lấp phần còn lại.
# Viết bằng tiếng Anh, vì Flux không hiểu tiếng Việt.
#
# Dùng: python studio.py generate "{topic}" --theme {name} --count 40
"""


def run(args) -> int:
    if args.list_models:
        try:
            models = list_models()
        except LLMError as exc:
            print(f"LỖI: {exc}")
            return 1
        info(f"LM Studio tại {base_url()}:")
        for m in models:
            info(f"  {m}")
        info("")
        info("Model đầu danh sách là mặc định. Đổi bằng --model hoặc "
             "STUDIO_LLM_MODEL trong .env")
        return 0

    if not args.topic:
        print("LỖI: thiếu chủ đề.")
        print('Ví dụ: python studio.py subjects "Giáng sinh" --count 24')
        return 1

    name = args.name or slugify(args.topic)
    path = THEMES_DIR / f"{name}.txt"

    if path.exists() and not args.overwrite and not args.dry_run:
        print(f"LỖI: đã có bộ '{name}' ({path}).")
        print("Dùng --overwrite để ghi đè, hoặc --name <tên khác>.")
        return 1

    info(f"Chủ đề    : {args.topic}")
    info(f"Bộ        : {name}")
    info(f"Đối tượng : {args.audience}")
    info(f"Số cảnh   : {args.count}")
    info("")
    info(f"Đang hỏi model local ở {base_url()}...")
    info("(mô hình 9B chạy CPU/GPU nhà có thể mất vài phút)")

    try:
        lines, warnings, model = generate_subjects(
            topic=args.topic,
            count=args.count,
            audience=args.audience,
            model=args.model,
            temperature=args.temperature,
        )
    except LLMError as exc:
        print(f"\nLỖI: {exc}")
        return 1

    info("")
    for i, line in enumerate(lines, start=1):
        info(f"  {i:>2}. {line}")

    if warnings:
        info("")
        for w in warnings:
            warn(w)

    if len(lines) < args.count:
        info("")
        warn(f"Chỉ được {len(lines)}/{args.count} cảnh. Chạy lại hoặc "
             f"tự thêm vào file cho đủ.")

    if args.dry_run:
        info("")
        info("--dry-run, không ghi file.")
        return 0

    THEMES_DIR.mkdir(parents=True, exist_ok=True)
    header = HEADER.format(topic=args.topic, n=len(lines), name=name,
                           today=date.today().isoformat(), model=model)
    path.write_text(header + "\n" + "\n".join(lines) + "\n", encoding="utf-8")

    info("")
    info(f"✓ Ghi {len(lines)} cảnh vào {path}")
    info(f"  Các bộ hiện có: {', '.join(list_themes())}")
    info("")
    info("Đọc lướt qua một lượt trước khi chạy 40 ảnh — sửa dòng nào không ưng.")
    info("Sau đó:")
    info(f'  python studio.py generate "{args.topic}" --theme {name} --count 40')
    return 0
