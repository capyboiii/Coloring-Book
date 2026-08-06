"""Bước ① TẠO — sinh ảnh line art từ một chủ đề."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .. import config
from ..prompts import load_subjects, make_prompts
from ..providers import GenRequest, ProviderError, get_provider
from ..util import human_duration, info, slugify, warn, write_json


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "generate",
        help="Sinh ảnh line art cho một chủ đề",
        description="Sinh N ảnh line art vào library/<slug>/raw/",
    )
    p.add_argument("topic", help='Chủ đề, ví dụ "đại dương kỳ thú"')
    p.add_argument("--count", type=int, default=40,
                   help="Số ảnh cần sinh (mặc định 40)")
    p.add_argument("--slug", default=None,
                   help="Tên thư mục. Mặc định suy ra từ chủ đề")
    p.add_argument("--title", default=None,
                   help="Tên sách hiển thị. Mặc định lấy chủ đề")
    p.add_argument("--complexity", default="medium",
                   choices=["simple", "medium", "detailed"],
                   help="simple cho trẻ nhỏ, detailed cho người lớn")
    p.add_argument("--subjects", default=None,
                   help="File .txt liệt kê chủ thể, mỗi dòng một cái")
    p.add_argument("--seed", type=int, default=None,
                   help="Seed khởi đầu. Đặt cố định để sinh lại y hệt mẻ cũ")
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--guidance", type=float, default=None)
    p.add_argument("--overwrite", action="store_true",
                   help="Sinh đè ảnh đã có (mặc định bỏ qua để chạy tiếp được)")
    p.set_defaults(func=run)


def run(args) -> int:
    settings = config.load_settings()
    slug = args.slug or slugify(args.topic)
    raw = config.raw_dir(settings, slug)
    raw.mkdir(parents=True, exist_ok=True)

    subjects = load_subjects(args.subjects) if args.subjects else None
    if subjects:
        info(f"Đọc được {len(subjects)} chủ thể từ {args.subjects}")

    plan = make_prompts(
        topic=args.topic,
        count=args.count,
        complexity=args.complexity,
        subjects=subjects,
        seed_start=args.seed,
    )

    steps = args.steps if args.steps is not None else settings.steps
    guidance = args.guidance if args.guidance is not None else settings.guidance

    try:
        provider = get_provider(settings, "comfyui")
        device = provider.healthcheck()
    except ProviderError as exc:
        print(f"LỖI: {exc}")
        return 1

    info(f"ComfyUI  : {settings.comfyui_url} · {device}")
    info(f"Sách     : {slug}")
    info(f"Kích thước: {config.GEN_W}x{config.GEN_H} px "
         f"(tỉ lệ vùng vẽ {config.ART_W_IN}x{config.ART_H_IN} in)")
    info(f"Sinh     : {len(plan)} ảnh · {steps} steps · guidance {guidance}")
    info("")

    # Ghi thông tin sách trước, để lỡ đứt giữa chừng vẫn còn dấu vết
    write_json(
        config.book_dir(settings, slug) / "book.json",
        {
            "slug": slug,
            "title": args.title or args.topic,
            "topic": args.topic,
            "complexity": args.complexity,
            "planned_count": args.count,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "gen": {
                "provider": "comfyui",
                "width": config.GEN_W,
                "height": config.GEN_H,
                "steps": steps,
                "guidance": guidance,
                "seed_start": plan[0].seed if plan else None,
            },
        },
    )

    started = time.time()
    made = skipped = failed = 0

    for item in plan:
        stem = f"{item.index:03d}"
        img_path = raw / f"{stem}.png"

        if img_path.exists() and not args.overwrite:
            skipped += 1
            continue

        req = GenRequest(
            prompt=item.prompt,
            negative=item.negative,
            seed=item.seed,
            width=config.GEN_W,
            height=config.GEN_H,
            steps=steps,
            guidance=guidance,
        )

        t0 = time.time()
        try:
            data = provider.generate(req)
        except ProviderError as exc:
            warn(f"{stem} hỏng: {exc}")
            failed += 1
            continue

        img_path.write_bytes(data)
        write_json(
            raw / f"{stem}.json",
            {
                **item.to_dict(),
                "file": img_path.name,
                "steps": steps,
                "guidance": guidance,
                "width": config.GEN_W,
                "height": config.GEN_H,
                "provider": "comfyui",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "seconds": round(time.time() - t0, 1),
            },
        )
        made += 1

        done = made + failed
        remaining = len(plan) - skipped - done
        eta = (time.time() - started) / done * remaining if done else 0
        info(f"  [{done + skipped:>3}/{len(plan)}] {stem}.png "
             f"· {time.time() - t0:.0f}s · còn ~{human_duration(eta)}")

    info("")
    info(f"Xong sau {human_duration(time.time() - started)} — "
         f"{made} ảnh mới, {skipped} bỏ qua, {failed} lỗi")
    info(f"Ảnh nằm ở: {raw}")
    info("")
    info("Bước tiếp theo — DUYỆT BẰNG TAY:")
    info(f"  1. Mở thư mục {raw}")
    info("  2. Xoá những ảnh xấu. BẤM GIỜ từ lúc mở tới lúc xong.")
    info(f"  3. Chạy: python studio.py approve {slug}")
    return 0 if failed == 0 else 2
