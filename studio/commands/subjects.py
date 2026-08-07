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

from ..llm import (LLMError, base_url, generate_subjects, lint_for_kids,
                   list_models)
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
    p.add_argument("--batch", type=int, default=8,
                   help="Hỏi bao nhiêu cảnh mỗi lần (mặc định 8). "
                        "Model hay trả rỗng thì hạ xuống 4")
    p.add_argument("--max-tokens", type=int, default=None,
                   help="Trần token mỗi lần gọi. Mặc định tính theo --batch")
    p.add_argument("--think", action="store_true",
                   help="Bật chế độ suy luận. Mặc định TẮT — Qwen3 hay đốt "
                        "sạch token vào phần suy nghĩ rồi trả về rỗng")
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
    info(f"Mỗi mẻ   : {args.batch} cảnh")
    info(f"Suy luận : {'bật' if args.think else 'tắt'}")
    info("")
    info(f"Đang hỏi model local ở {base_url()}...")

    def progress(rnd, have, total, ask):
        info(f"  mẻ {rnd}: đã có {have}/{total}, xin thêm {ask}...")

    def result(rnd, ask, added, dupes, dropped):
        detail = []
        if dupes:
            detail.append(f"{dupes} trùng")
        if dropped:
            detail.append(f"{dropped} bị loại")
        suffix = f"  ({', '.join(detail)})" if detail else ""
        info(f"         xin {ask}, dùng được {added}{suffix}")

    try:
        lines, warnings, model = generate_subjects(
            topic=args.topic,
            count=args.count,
            audience=args.audience,
            model=args.model,
            temperature=args.temperature,
            batch=args.batch,
            max_tokens=args.max_tokens,
            think=args.think,
            on_progress=progress,
            on_result=result,
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

    # Soi thêm theo tiêu chuẩn sách trẻ em. Cảnh báo chứ không loại —
    # ông đọc rồi tự sửa, file .txt sửa tay dễ hơn gen lại nhiều.
    if args.audience == "kids":
        flagged = [(i, ln, lint_for_kids(ln))
                   for i, ln in enumerate(lines, start=1)]
        flagged = [f for f in flagged if f[2]]
        if flagged:
            info("")
            info(f"── {len(flagged)}/{len(lines)} cảnh nên sửa cho hợp trẻ nhỏ ──")
            for i, ln, notes in flagged:
                warn(f"{i:>2}. {ln[:58]}...")
                warn(f"    {'; '.join(notes)}")

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
