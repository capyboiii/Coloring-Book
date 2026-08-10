"""Bước ① TẠO — sinh ảnh line art từ một chủ đề."""

from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timezone

from .. import config
from ..prompts import (AUDIENCES, COMPLEXITY, build_cover_prompt,
                       has_non_ascii, list_themes, load_subjects,
                       load_template, make_prompts, resolve_params,
                       theme_audience,
                       summarise_scenes)
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
    # MỘT lựa chọn thay cho ba. Xem prompts.resolve_params().
    p.add_argument("--for", dest="audience", default=None,
                   choices=list(AUDIENCES),
                   help="Sách này cho ai (kids | adults). Quyết định luôn độ "
                        "chi tiết, mật độ và phong cách vẽ. Bỏ trống thì lấy "
                        "theo chủ đề, không có thì mặc định kids")
    # Ba cờ dưới đây giữ lại làm lối thoát cho trường hợp cá biệt, mặc định
    # None nghĩa là "để studio suy ra". Không đưa vào --help chính để chúng
    # không trông như thứ phải điền.
    p.add_argument("--complexity", default=None, choices=list(COMPLEXITY),
                   help=argparse.SUPPRESS)
    p.add_argument("--density", default=None,
                   choices=["single", "normal", "rich"],
                   help=argparse.SUPPRESS)
    p.add_argument("--style", default=None,
                   choices=["kawaii", "cartoon", "decorative"],
                   help=argparse.SUPPRESS)
    p.add_argument("--theme", "--subjects", dest="theme", default=None,
                   metavar="<tên|file>",
                   help="Bộ chủ thể dựng sẵn (ocean, mandala, floral, "
                        "forest-animals) hoặc đường dẫn file .txt. "
                        "RẤT NÊN dùng — không có nó ảnh ra rất kém")
    p.add_argument("--list-themes", action="store_true",
                   help="Liệt kê các bộ chủ thể dựng sẵn rồi thoát")
    p.add_argument("--lora", default=None,
                   help="Tên file LoRA trong ComfyUI/models/loras/. "
                        "Chỉ có tác dụng nếu workflow có node LoraLoader")
    p.add_argument("--lora-strength", type=float, default=0.9,
                   help="0.6-1.0. Cao quá thì LoRA nuốt mất chủ thể")
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
    template = None
    if args.theme:
        try:
            subjects = load_subjects(args.theme)
        except FileNotFoundError as exc:
            print(f"LỖI: {exc}")
            return 1
        info(f"Đọc được {len(subjects)} chủ thể từ '{args.theme}'")
        try:
            template = load_template(args.theme)
        except ValueError as exc:
            print(f"LỖI: {exc}")
            return 1
        if template:
            info(f"Khuôn bố cục: {template}")

    # BA THAM SỐ SUY RA TỪ MỘT LỰA CHỌN.
    #
    # Trước đây người dùng phải gõ --complexity, --density, --style và tự nhớ
    # tổ hợp nào hợp với chủ đề nào. Gõ sai thì không ai báo, phải nhìn hết
    # 40 ảnh mới biết. Giờ chỉ cần --for kids|adults; chủ đề nào có nhu cầu
    # riêng thì tự khai trong file theme của nó.
    audience = args.audience or theme_audience(args.theme) or "kids"
    try:
        params = resolve_params(
            args.theme, audience,
            complexity=args.complexity, density=args.density,
            style=args.style)
    except ValueError as exc:
        print(f"LỖI: {exc}")
        return 1

    manual = [k for k in ("complexity", "density", "style")
              if getattr(args, k) is not None]
    info(f"Sách cho  : {audience}"
         + ("" if args.audience else "  (theo chủ đề)"))
    info(f"Kiểu vẽ   : {params['complexity']} · density {params['density']} "
         f"· {params['style']}"
         + (f"  (gõ tay: {', '.join(manual)})" if manual else "  (tự suy ra)"))

    if not _check_language(args, subjects):
        return 1

    plan = make_prompts(
        topic=args.topic,
        count=args.count,
        complexity=params["complexity"],
        subjects=subjects,
        seed_start=args.seed,
        density=params["density"],
        style=params["style"],
        template=template,
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
            "audience": audience,
            "complexity": params["complexity"],
            "density": params["density"],
            "style": params["style"],
            "lora": args.lora,
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
            lora=args.lora,
            lora_strength=args.lora_strength,
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

    # GỘP nhiều chủ thể chứ không lấy subjects[0].
    #
    # Đây là chỗ tôi sửa sót lần trước: tôi vá `cover.py` nhưng quên rằng
    # `generate` có đường sinh bìa RIÊNG, và đó mới là đường Bao thực sự chạy.
    # Nên bìa vẫn ra đúng một con báo. Cùng một lỗi, hai chỗ, sửa một chỗ.
    #
    # Ở đây chưa có approved/ (chưa duyệt), nên gộp từ chính mẻ vừa sinh —
    # đó cũng chính là những trang sắp vào sách.
    scene = args.cover_scene
    if not scene and subjects:
        scene = summarise_scenes(subjects, count=3) or subjects[0]
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

    # ẢNH BÌA SAU — cũng sinh ngay ở đây.
    #
    # Trước đây chỉ sinh một ảnh, nên `build` chỉ có bìa trước; bìa sau phải
    # chạy `cover` riêng mới có. Mà Bao thì chạy generate → approve → build,
    # không ai nhớ chạy thêm lệnh.
    # Ít nhân vật hơn và cảnh tĩnh hơn: bìa sau còn phải chừa chỗ cho chữ và
    # ô mã vạch.
    back_path = config.book_dir(settings, slug) / "cover-back-art.png"
    if subjects:
        back_scene = summarise_scenes(
            subjects, count=2, offset=1,
            ending="in a calm simple scene with open space around them")
    else:
        back_scene = scene
    info(f"Bìa sau  : đang vẽ ảnh màu — {back_scene[:60]}...")
    try:
        t1 = time.time()
        back = provider.generate(GenRequest(
            prompt=build_cover_prompt(back_scene),
            negative="",
            seed=(args.seed + 10000) if args.seed is not None
            else random.randint(1, 2**31 - 1),
            width=config.COVER_GEN_W,
            height=config.COVER_GEN_H,
            steps=steps,
            guidance=settings.guidance,
        ))
    except ProviderError as exc:
        # Bìa sau hỏng KHÔNG được làm hỏng cả lượt chạy: bìa trước mới là thứ
        # bán hàng, còn bìa sau thiếu thì in trên nền màu vẫn được.
        warn(f"Không vẽ được bìa sau: {exc}. Bìa sau sẽ dùng nền màu trơn.")
        return
    back_path.write_bytes(back)
    info(f"Bìa sau  : xong sau {human_duration(time.time() - t1)} "
         f"→ {back_path.name}")
    info(f"Bìa      : xong sau {time.time() - t0:.0f}s → {art_path.name}")
