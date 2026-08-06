"""Bước ① TẠO — sinh ảnh line art từ một chủ đề."""

from __future__ import annotations

import random
import time
from datetime import datetime, timezone

from .. import config
from ..prompts import (build_cover_prompt, has_non_ascii, list_themes,
                       load_subjects, make_prompts)
from ..providers import GenRequest, ProviderError, get_provider
from ..util import human_duration, info, slugify, warn, write_json


def _check_language(args, subjects: list[str] | None) -> bool:
    """
    Chặn lỗi đắt nhất: chủ thể viết bằng tiếng Việt.

    Flux không hiểu tiếng Việt. Nó không báo lỗi, chỉ lặng lẽ bỏ qua và vẽ
    thứ gì đó ngẫu nhiên. Mẻ đầu tiên gõ "đại dương" ra toàn hoa lá đúng vì
    lý do này. Chặn ở đây rẻ hơn nhiều so với để chạy hết 40 lượt GPU.
    """
    if subjects:
        bad = [s for s in subjects if has_non_ascii(s)]
        if bad:
            warn(f"{len(bad)}/{len(subjects)} chủ thể có ký tự tiếng Việt. "
                 f"Flux sẽ bỏ qua chúng. Ví dụ: {bad[0]!r}")
        return True

    if has_non_ascii(args.topic) and not args.force:
        print(f"LỖI: chủ đề {args.topic!r} viết bằng tiếng Việt.\n")
        print("Flux chỉ hiểu tiếng Anh. Nó sẽ không báo lỗi mà lặng lẽ vẽ bừa —")
        print("đây đúng là lý do mẻ đầu ra toàn hoa lá thay vì cảnh biển.\n")
        print("Cách sửa, chọn một:")
        print("  1. Dùng bộ chủ thể dựng sẵn (nên làm):")
        print(f"     python studio.py generate \"{args.topic}\" --theme ocean")
        print(f"     Có sẵn: {', '.join(list_themes())}")
        print("  2. Tự viết file chủ thể tiếng Anh rồi --theme <file>.txt")
        print("  3. Đặt chủ đề bằng tiếng Anh")
        print("  4. --force nếu vẫn muốn chạy (không khuyến khích)")
        return False

    if not subjects:
        warn("Không có --theme: cả 40 ảnh dùng chung một chủ thể, chỉ khác "
             "bố cục. Tỷ lệ giữ lại sẽ rất thấp.")
        warn(f"Nên dùng: --theme {' | '.join(list_themes())}")
    return True


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
                   help="Độ tinh xảo của NÉT. simple cho trẻ nhỏ, "
                        "detailed cho người lớn")
    p.add_argument("--density", default="rich",
                   choices=["single", "normal", "rich"],
                   help="Bao nhiêu ĐỐI TƯỢNG trên một trang. "
                        "rich (mặc định) lấp đầy trang; "
                        "single chỉ một chủ thể trên nền trắng")
    p.add_argument("--theme", "--subjects", dest="theme", default=None,
                   metavar="<tên|file>",
                   help="Bộ chủ thể dựng sẵn (ocean, mandala, floral, "
                        "forest-animals) hoặc đường dẫn file .txt. "
                        "RẤT NÊN dùng — không có nó ảnh ra rất kém")
    p.add_argument("--list-themes", action="store_true",
                   help="Liệt kê các bộ chủ thể dựng sẵn rồi thoát")
    p.add_argument("--seed", type=int, default=None,
                   help="Seed khởi đầu. Đặt cố định để sinh lại y hệt mẻ cũ")
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--guidance", type=float, default=None)
    p.add_argument("--overwrite", action="store_true",
                   help="Sinh đè ảnh đã có (mặc định bỏ qua để chạy tiếp được)")
    p.add_argument("--force", action="store_true",
                   help="Bỏ qua cảnh báo chủ đề không phải tiếng Anh")
    p.add_argument("--no-cover", action="store_true",
                   help="Đừng sinh ảnh bìa màu (mặc định có sinh)")
    p.add_argument("--cover-scene", default=None,
                   help="Mô tả ảnh bìa bằng tiếng Anh. Mặc định lấy cảnh đầu "
                        "trong bộ chủ thể")
    p.set_defaults(func=run)


def run(args) -> int:
    settings = config.load_settings()

    if args.list_themes:
        themes = list_themes()
        info("Bộ chủ thể dựng sẵn:")
        for name in themes:
            count = len(load_subjects(name))
            info(f"  {name:<16} {count} chủ thể")
        info("")
        info('Dùng: python studio.py generate "ocean" --theme ocean --count 40')
        return 0

    slug = args.slug or slugify(args.topic)
    raw = config.raw_dir(settings, slug)
    raw.mkdir(parents=True, exist_ok=True)

    subjects = None
    if args.theme:
        try:
            subjects = load_subjects(args.theme)
        except FileNotFoundError as exc:
            print(f"LỖI: {exc}")
            return 1
        info(f"Đọc được {len(subjects)} chủ thể từ '{args.theme}'")

    if not _check_language(args, subjects):
        return 1

    if args.theme == "mandala" and args.density == "rich":
        warn("Mandala vốn đã đối xứng và lấp kín trang. --density rich sẽ "
             "phá đối xứng, ra một mớ hỗn độn. Nên dùng --density normal.")

    plan = make_prompts(
        topic=args.topic,
        count=args.count,
        complexity=args.complexity,
        subjects=subjects,
        seed_start=args.seed,
        density=args.density,
    )

    steps = args.steps if args.steps is not None else settings.steps
    guidance = args.guidance if args.guidance is not None else settings.guidance

    try:
        provider = get_provider(settings, "comfyui")
        device = provider.healthcheck()
    except ProviderError as exc:
        print(f"LỖI: {exc}")
        return 1

    uses_guidance = "guidance" in provider.supported_params

    info(f"ComfyUI  : {settings.comfyui_url} · {device}")
    info(f"Sách     : {slug}")
    info(f"Kích thước: {config.GEN_W}x{config.GEN_H} px "
         f"(tỉ lệ vùng vẽ {config.ART_W_IN}x{config.ART_H_IN} in)")
    info(f"Sinh     : {len(plan)} ảnh · {steps} steps"
         + (f" · guidance {guidance}" if uses_guidance
            else " · guidance: workflow không dùng"))
    if args.guidance is not None and not uses_guidance:
        warn("--guidance bị bỏ qua: workflow hiện tại không có node FluxGuidance "
             "(FLUX.1-schnell không dùng guidance)")
    info("")

    # Ghi thông tin sách trước, để lỡ đứt giữa chừng vẫn còn dấu vết
    write_json(
        config.book_dir(settings, slug) / "book.json",
        {
            "slug": slug,
            "title": args.title or args.topic,
            "topic": args.topic,
            "complexity": args.complexity,
            "density": args.density,
            "theme": args.theme,
            "subject_count": len(subjects) if subjects else 0,
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

    if not args.no_cover:
        info("")
        _make_cover_art(settings, args, slug, subjects, steps)

    info("")
    info("Bước tiếp theo — DUYỆT BẰNG TAY:")
    info(f"  1. Mở thư mục {raw}")
    info("  2. Xoá những ảnh xấu. BẤM GIỜ từ lúc mở tới lúc xong.")
    info(f"  3. Chạy: python studio.py approve {slug} --minutes <số phút>")
    info(f"  4. Chạy: python studio.py build {slug}")
    info("     (build dựng luôn cả bìa từ ảnh vừa sinh, không cần lệnh riêng)")
    return 0 if failed == 0 else 2


def _make_cover_art(settings, args, slug: str,
                    subjects: list[str] | None, steps: int) -> None:
    """
    Sinh ảnh bìa MÀU ngay trong lượt gen sách, cùng lúc với các trang ruột.

    Chỉ sinh phần ẢNH. Không dựng được cover.pdf ở đây vì độ dày gáy phụ
    thuộc số trang cuối cùng, mà số trang thì phải duyệt xong mới biết.
    `build` sẽ lấy ảnh này ghép thành bìa hoàn chỉnh.
    """
    art_path = config.book_dir(settings, slug) / "cover-art.png"
    if art_path.exists() and not args.overwrite:
        info(f"Bìa      : đã có {art_path.name}, bỏ qua (--overwrite để làm lại)")
        return

    scene = args.cover_scene
    if not scene and subjects:
        scene = subjects[0]
    if not scene:
        scene = args.topic
        if has_non_ascii(scene):
            warn(f"Cảnh bìa {scene!r} là tiếng Việt, Flux sẽ bỏ qua. "
                 f'Dùng --cover-scene "<mô tả tiếng Anh>"')

    prompt = build_cover_prompt(scene)
    info(f"Bìa      : đang vẽ ảnh màu — {scene[:60]}...")

    try:
        provider = get_provider(settings, "comfyui", cover=True)
        t0 = time.time()
        data = provider.generate(GenRequest(
            prompt=prompt,
            negative="",
            seed=(args.seed + 9999) if args.seed is not None
            else random.randint(1, 2**31 - 1),
            width=config.COVER_GEN_W,
            height=config.COVER_GEN_H,
            steps=steps,
            guidance=settings.guidance,
        ))
    except ProviderError as exc:
        warn(f"Không vẽ được bìa: {exc}")
        warn("Các trang ruột vẫn ổn. Chạy `cover` riêng sau, hoặc dùng --image.")
        return

    art_path.write_bytes(data)
    write_json(art_path.with_suffix(".json"), {
        "scene": scene,
        "prompt": prompt,
        "steps": steps,
        "width": config.COVER_GEN_W,
        "height": config.COVER_GEN_H,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seconds": round(time.time() - t0, 1),
    })
    info(f"Bìa      : xong sau {time.time() - t0:.0f}s → {art_path.name}")
