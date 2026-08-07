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
    from studio.prompts import load_subjects

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
**Task:** Write exactly 8 scene descriptions for a printed coloring book
*Idea 1:* Santa on a roof
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
    # Prompt bị nhại lại luôn có markdown đậm/nghiêng; cảnh thì không bao giờ
    check("Bỏ ghi chú của mô hình (**Task:**, *Idea 1:*)",
          not any("**" in g or g.startswith("*") for g in got))

    # Rác thật lấy từ log chạy hỏng của Bao — suy luận nằm lẫn trong content
    junk = """Formula: main subject + what it is doing + 2 or 3 other things filling the rest of the page
Content only (no "line art", "black and white", etc.)
One sentence per line, about twenty words (approximate)
All 8 scenes must be clearly different (no repeating animals/objects/layouts)
Only drawable things (no fog, light rays, reflections, shadows)
Draft: A jolly Santa Claus riding a red sleigh, holding a sack of gifts, snowy mountains in the background
Wait, re-reading the end of the prompt: I must avoid those specific Santa descriptions
a cheerful snowman wearing a striped scarf, two children rolling snowballs beside him, pine trees and falling snow filling the background"""
    kept, _ = clean_lines(junk, 24)
    check("Lọc sạch rác suy luận thật, chỉ giữ đúng cảnh thật",
          len(kept) == 1 and kept[0].startswith("a cheerful snowman"),
          f"{len(kept)} dòng: {kept}")

    # Bộ lọc phải giữ được chính themes/ viết tay. Bản đầu đặt ngưỡng >=12 từ
    # và >=2 dấu phẩy theo hình dạng của rác, kết quả là mandala rớt 24/24.
    # Lọc theo rác chứ không theo cảnh thật là sai.
    from studio.prompts import list_themes as _themes
    for name in _themes():
        subs = load_subjects(name)
        kept_t, _ = clean_lines("\n".join(subs), 999)
        check(f"themes/{name}.txt qua bộ lọc nguyên vẹn",
              len(kept_t) == len(subs), f"{len(kept_t)}/{len(subs)}")

    # Ba dòng bị loại OAN trong lần chạy thật với Qwen2.5-7B, chủ đề Giáng sinh.
    # Danh từ riêng viết hoa là đúng — chủ đề nào cũng có thể có.
    proper_nouns = """Santa Claus sitting at a table writing letters to children, a stack of envelopes beside him, a candle glowing on the desk
Mrs. Claus baking pies while singing Christmas songs, flour dusting her apron, cookies cooling on the windowsill
Rudolph leading the sleigh through falling snow, bells jingling on his harness, pine trees lining the path below"""
    kept_pn, _ = clean_lines(proper_nouns, 24)
    check("Không loại oan cảnh mở đầu bằng danh từ riêng (Santa, Mrs. Claus)",
          len(kept_pn) == 3, f"{len(kept_pn)}/3")

    # Nhưng ghi chú viết hoa VÀ ngắn thì vẫn phải loại
    still_junk = """One sentence per line, about twenty words (approximate)
All 8 scenes must be clearly different (no repeating animals)
a cheerful snowman wearing a striped scarf, two children rolling snowballs beside him, pine trees filling the background"""
    kept_sj, _ = clean_lines(still_junk, 24)
    check("Vẫn loại ghi chú viết hoa mà ngắn",
          len(kept_sj) == 1 and kept_sj[0].startswith("a cheerful"),
          f"{len(kept_sj)} dòng")

    from studio.llm import looks_like_reasoning
    check("Nhận ra suy luận nằm lẫn trong content",
          looks_like_reasoning("Thinking Process:\n\n1. **Analyze the Request:**"))
    check("Không báo nhầm khi content là cảnh thật",
          not looks_like_reasoning(
              "a smiling sea turtle swimming through a coral reef, "
              "schools of small fish above it, seaweed below"))
    check("Bỏ dòng trùng", len(got) == 3, f"{len(got)} dòng")
    check("Bỏ dòng tiếng Việt", not any("cá heo" in g for g in got))

    print("\n[8] Công thức sách (books/*.yaml)")
    import studio.recipe as recipe_mod
    from studio.recipe import Recipe, RecipeError, _validate

    recipe_mod.BOOKS_DIR = tmp / "books"

    path = recipe_mod.scaffold("sach-thu", "Sách Thử")
    check("scaffold tạo được file công thức", path.exists())
    r = recipe_mod.load("sach-thu")
    check("Đọc lại đúng tên sách", r.title == "Sách Thử", r.title)
    check("generate mặc định lớn hơn pages",
          r.generate > r.pages, f"{r.generate} > {r.pages}")

    def bad(**kw):
        base = dict(slug="x", title="X", pages=10, generate=20)
        base.update(kw)
        try:
            _validate(Recipe(**base))
            return False
        except RecipeError:
            return True

    check("Chặn complexity sai", bad(complexity="siêu-nét"))
    check("Chặn density sai", bad(density="đầy"))
    check("Chặn màu bìa sai định dạng",
          bad(cover=recipe_mod.Cover(bg="xanh")))
    check("Chặn generate ít hơn pages", bad(pages=40, generate=10))
    check("Chặn mandala + density rich (phá đối xứng)",
          bad(theme="mandala", density="rich"))
    check("Công thức hợp lệ thì không chặn", not bad())

    kid = Recipe(slug="x", title="X", audience="kids",
                 complexity="detailed", density="rich")
    check("Góp ý khi sách trẻ em mà nét tinh xảo + trang rối",
          len(kid.hints()) == 2, f"{len(kid.hints())} góp ý")
    ok_kid = Recipe(slug="x", title="X", audience="kids",
                    complexity="simple", density="normal")
    check("Không góp ý khi công thức trẻ em đã đúng",
          not ok_kid.hints())

    print("\n[9] Chống ảnh bị tô màu sẵn")
    from studio.imageops import colour_amount
    from studio.llm import scrub_colour_and_light

    check("Ảnh đen trắng -> 0% màu",
          colour_amount(Image.new("RGB", (64, 64), (255, 255, 255))) == 0.0)
    check("Ảnh có màu -> phát hiện được",
          colour_amount(Image.new("RGB", (64, 64), (230, 90, 60))) == 1.0)

    # Đúng câu đã làm ảnh 002 bị tô màu
    fixed, notes = scrub_colour_and_light(
        "an elf decorating a tree with colorful ornaments, "
        "fairy lights twinkling all around")
    check("Cắt được từ chỉ màu khỏi mô tả cảnh",
          "colorful" not in fixed, fixed[:50])
    check("Báo còn từ tả ánh sáng",
          any("ánh sáng" in n for n in notes))
    # Trạng từ phải cắt cùng, nếu không câu bị què
    fixed2, _ = scrub_colour_and_light("a flock of brightly colored penguins")
    check("Cắt cả trạng từ đi kèm, không để câu què",
          fixed2 == "a flock of penguins", repr(fixed2))

    for name in _themes():
        subs = load_subjects(name)
        dirty = [s for s in subs
                 if scrub_colour_and_light(s)[0] != s
                 or scrub_colour_and_light(s)[1]]
        check(f"themes/{name}.txt không còn từ chỉ màu / ánh sáng",
              not dirty, f"{len(dirty)} dòng: {dirty[:1]}")

    print("\n[10] Tiêu chuẩn sách trẻ em")
    from studio.llm import lint_for_kids

    cases = [
        ("a wolf howling on a rock at night", True, "con vật đáng sợ"),
        ("bats hanging from a branch", True, "con vật đáng sợ"),
        ("a fox framed by an ornate decorative border", True, "khung viền"),
        ("a cat with a swirling pattern border", True, "hoa văn"),
        ("a deer, a fawn, a sheep, a fox and a rabbit in a meadow", True,
         "quá nhiều nhân vật"),
        # Hai câu này TỪNG bị báo động giả
        ("overlapping monstera and palm leaves filling the page", False,
         "monstera không phải monster"),
        ("a group of dolphins leaping over waves, swirling water below", False,
         "swirling water là chuyển động thật"),
        ("a smiling fox sitting in tall grass, two mushrooms beside it", False,
         "cảnh hợp lệ"),
    ]
    for text, should_flag, why in cases:
        flagged = bool(lint_for_kids(text))
        check(f"{'Bắt' if should_flag else 'Tha'}: {why}",
              flagged == should_flag, text[:44])

    for name in _themes():
        bad = [s for s in load_subjects(name) if lint_for_kids(s)]
        check(f"themes/{name}.txt đạt tiêu chuẩn trẻ em",
              not bad, f"{len(bad)} dòng: {bad[:1]}")

    print("\n[11] Làm mịn nét")
    check("Có bật làm mịn trước khi khử xám",
          config.SMOOTH_RADIUS > 0, f"bán kính {config.SMOOTH_RADIUS}")
    check("Có bật nối khe hở trên nét",
          config.CLOSE_GAPS > 1, f"{config.CLOSE_GAPS}px")
    check("Sinh ảnh ở độ phân giải đủ cao (nét dày, ít phải phóng)",
          config.GEN_W >= 1200,
          f"{config.GEN_W}x{config.GEN_H}, phóng "
          f"{config.ART_W_PX / config.GEN_W:.2f} lần")
    # COMPOSITIONS phải nói về BỐ TRÍ, không nói mật độ — nếu không nó đánh
    # nhau với DENSITY. Đây từng là lỗi thật.
    from studio.prompts import COMPOSITIONS, build_prompt
    clash = [c for c in COMPOSITIONS
             if any(w in c.lower()
                    for w in ("filling", "densely", "packed", "edge to edge"))]
    check("COMPOSITIONS không nói về mật độ (tránh đánh nhau với DENSITY)",
          not clash, f"{len(clash)} mục: {clash[:1]}")

    print("\n[12] Prompt không tự lặp")
    pr = build_prompt("a smiling fox sitting in tall grass",
                      "simple", "centered composition", "normal", "kawaii")
    words = len(pr.split())
    check("Prompt dưới 180 từ (dài quá thì chủ thể bị chìm)",
          words < 180, f"{words} từ")
    # Bản trước độ dày nét được nhắc ở cả 4 khối, prompt phình lên 180 từ.
    # Mỗi ý phải nói đúng một lần.
    for phrase, limit in (("line weight", 1), ("no shading", 1),
                          ("texture", 1), ("uncolored", 1)):
        n = pr.lower().count(phrase)
        check(f"'{phrase}' chỉ xuất hiện {limit} lần", n <= limit, f"{n} lần")
    check("Chủ thể có mặt trong prompt", "smiling fox" in pr)

    from studio.prompts import STYLE
    check("Có phong cách kawaii làm mặc định cho sách trẻ em",
          "kawaii" in STYLE and "chibi" in STYLE["kawaii"])

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
