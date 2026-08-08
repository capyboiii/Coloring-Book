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


def _erode(mask):
    """Bào mòn 1 pixel, thuần numpy để khỏi thêm phụ thuộc scipy."""
    import numpy as np
    out = mask.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out &= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


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

    print("\n[0] Mọi module đều nạp được")
    # Bo kiem thu nay TUNG BO SOT generate.py hoan toan: no chi nap approve va
    # build. Ket qua la mot loi cu phap (truyen `lora` hai lan trong
    # GenRequest) nam yen trong generate.py qua ca mot commit, va chi lo ra
    # khi Bao chay `studio.py doctor` - tuc la luc dinh chay that.
    # Nap het moi module la phep thu re nhat co the co: no khong kiem tra logic
    # gi ca, chi bat dung loai loi ngu ngoc ma le ra phai chet ngay lap tuc.
    import importlib
    mods = sorted(p.stem for p in (ROOT / "studio" / "commands").glob("*.py")
                  if not p.stem.startswith("_"))
    for m in mods:
        try:
            importlib.import_module(f"studio.commands.{m}")
            bad = None
        except Exception as exc:
            bad = f"{type(exc).__name__}: {exc}"
        check(f"studio/commands/{m}.py", bad is None, bad or "")
    check("Nạp được studio.py (điểm vào)",
          importlib.util.find_spec("studio") is not None)

    print("\n[0b] Bắt ảnh dính màu")
    # Bo do CU chay tren 20 anh that cua Bao thi bo lot CA HAI kieu hong ma
    # mat thuong nhin ra ngay. Dung so do that lam kiem thu, khong bia so.
    from studio.imageops import colour_report, prepare_page
    import numpy as _np2

    def _fake(spread_px, spread_val, tint_val=0):
        """Anh trang co `spread_px` pixel lech mau `spread_val`."""
        a = _np2.full((256, 256, 3), 255, dtype=_np2.uint8)
        a[200:, :] = 255 - 60          # mot dai co muc de tint co cho ma do
        a[200:, :, 2] = 255 - 60 - tint_val
        n = int(spread_px * 256)
        a[:n, :, 0] = 200
        a[:n, :, 1] = _np2.clip(200 - spread_val, 0, 255)
        a[:n, :, 2] = _np2.clip(200 - spread_val, 0, 255)
        return Image.fromarray(a)

    patch, tint = colour_report(_fake(0, 0))
    check("Ảnh đen trắng thật: cả hai chỉ số bằng 0",
          patch == 0 and tint == 0, f"mảng {patch:.2%}, ám {tint:.1f}")

    # Kieu hong 1: DAM ma HEP - ma hong nhan vat, ~0.4% dien tich
    patch, _ = colour_report(_fake(0.004, 120))
    check("Bắt được mảng màu hẹp (má hồng ~0.4% diện tích)",
          patch > config.COLOUR_RATIO_MAX, f"{patch:.2%}")

    # Kieu hong 2: NHAT ma RONG - ca trang phu mot lop sac
    _, tint = colour_report(_fake(0, 0, tint_val=25))
    check("Bắt được ám màu nhạt phủ rộng (lệch kênh chỉ 25)",
          tint > config.COLOUR_TINT_MAX, f"{tint:.1f}")

    # Nguong phai TACH BACH duoc anh sach khoi anh ban, khong chi bat anh ban
    patch, tint = colour_report(_fake(0.001, 40))
    check("Không báo động giả với nhiễu nén quanh nét",
          patch <= config.COLOUR_RATIO_MAX and tint <= config.COLOUR_TINT_MAX,
          f"mảng {patch:.2%}, ám {tint:.1f}")

    # Neu library/ con anh that thi do luon tren do. library/ nam trong
    # .gitignore nen may khac se khong co - bo qua, khong bao hong.
    real = ROOT / "library"
    known_bad = {"floral/001", "floral/002", "thu-net-deu/001", "bienca/001"}
    if real.exists():
        seen = missed = false_alarm = 0
        for p in sorted(real.glob("*/raw/*.png")):
            key = f"{p.parent.parent.name}/{p.stem}"
            with Image.open(p) as im:
                pa, ti = colour_report(im.convert("RGB"))
            dirty = (pa > config.COLOUR_RATIO_MAX
                     or ti > config.COLOUR_TINT_MAX)
            seen += 1
            if key in known_bad and not dirty:
                missed += 1
                print(f"      bỏ lọt {key}: mảng {pa:.2%}, ám {ti:.1f}")
            if key not in known_bad and dirty:
                false_alarm += 1
                print(f"      báo nhầm {key}: mảng {pa:.2%}, ám {ti:.1f}")
        check(f"Bắt hết ảnh dính màu Bao chỉ ra ({len(known_bad)} ảnh)",
              missed == 0, f"bỏ lọt {missed}")
        check(f"Không báo nhầm ảnh sạch (trên {seen} ảnh thật)",
              false_alarm == 0, f"báo nhầm {false_alarm}")

    print("\n[0c] Xử lý ảnh không được làm vỡ nét")
    # Bao bao: anh raw dat yeu cau nhung anh out vo net, chi tiet nho bit lai.
    # Dung. Va KHONG chi so nao cua toi bat duoc - toi chi do manh roi va do
    # xam, ca hai deu noi TOT LEN trong khi tranh thi hong di.
    # Nguyen nhan: lam min r=2.5 day muc loang ra, roi khu xam o 170 BAT LAI
    # toan bo phan loang do thanh den tuyen. Cong them noi khe ho k=9 lap moi
    # khe trang hep hon 9px - tam bong hong, duong xoan deu co khe co do.
    from studio.imageops import fit_within

    # Anh thu: cac vong tron dong tam cach nhau 6px - dung co khe hep ma
    # phep dong 9px se nuot mat.
    fine = Image.new("L", (config.GEN_W, config.GEN_H), 255)
    _d = ImageDraw.Draw(fine)
    for r in range(40, 400, 9):   # khe trang ~6px sau khi phong to
        _d.ellipse((500 - r, 700 - r, 500 + r, 700 + r), outline=0, width=3)
    fine_path = raw.parent / "net-nho.png"
    fine.save(fine_path)

    art0 = fit_within(fine, config.ART_W_PX, config.ART_H_PX)
    ink0 = (_np2.asarray(art0) < 128).mean()
    page, _m = prepare_page(fine_path)
    # Mau so la dien tich VUNG VE, khong phai ca trang - trang co le trang
    # rong, tinh ca vao thi ti le nao cung be va so sanh mat y nghia.
    ink1 = (_np2.asarray(page) < 128).sum() / (art0.width * art0.height)
    growth = ink1 / ink0 - 1
    check(f"Nét không phình quá {config.INK_GROWTH_MAX:.0%} sau xử lý",
          growth <= config.INK_GROWTH_MAX, f"phình {growth:+.1%}")

    # Khe trang giua cac vong PHAI con. Neu bi lap thi ca vung thanh den dac.
    band = _np2.asarray(page)[
        config.inch_to_px(config.ART_TOP_IN):
        config.inch_to_px(config.ART_TOP_IN) + art0.height]
    white_left = (band > 128).mean()
    check("Khe trắng giữa các nét mảnh vẫn còn sau xử lý",
          white_left > 0.5, f"{white_left:.1%} diện tích còn trắng")

    check("Bán kính làm mịn không vượt 1.5 (trên nữa là nét phình)",
          config.SMOOTH_RADIUS <= 1.5, str(config.SMOOTH_RADIUS))
    check("Nối khe hở không vượt 5px (9px nuốt mất chi tiết nhỏ)",
          config.CLOSE_GAPS <= 5, str(config.CLOSE_GAPS))
    fine_path.unlink()

    print("\n[0d] Bìa phải rực")
    # Bia NGUOC HAN trang ruot: ruot phai trang, bia phai ruc.
    from studio.imageops import cover_vividness
    from studio.prompts import COVER_STYLE, build_cover_prompt

    # Flux viet chu SAI CHINH TA len bia ("BOOK Chiihhauua"). Prompt cu ghi
    # "no text, no letters, no typography" - vo dung, vi CFG=1 khong doc duoc
    # phu dinh. Nhac "text" la GOI text. Va "space at the top for A TITLE" la
    # cau dat hang thang mot cai tieu de.
    cover_p = build_cover_prompt("a happy penguin")
    # So theo BIEN TU chu khong phai chuoi con: "text" nam trong "texture",
    # ma "no texture" thi hoan toan hop le. Kiem thu bat nham cung te ngang
    # kiem thu bo lot - no lam minh sua mot thu dang dung.
    import re as _re
    for w in ("text", "letter", "word", "title", "typography", "font"):
        check(f"Prompt bìa KHÔNG nhắc '{w}' (nhắc là Flux viết chữ sai)",
              not _re.search(rf"\b{w}s?\b", cover_p.lower()), cover_p)
    check("Chủ thể bìa đứng đầu prompt", cover_p.startswith("a happy penguin"))

    # LAN SUA TRUOC CUA TOI LAM BIA XAU DI. Viet "a colored-in coloring book
    # page" thi Flux doc "coloring book page" TRUOC, ve dung mot trang to mau
    # va de trang gan het - than chim, bong tuyet chi co net khong co mau.
    # Do 87% dien tich gan nhu khong mau, trong khi sach mau chi 16%.
    # Lai dung bai hoc "no text thi Flux viet text": o CFG=1 nhac toi mot thu
    # la trieu hoi no.
    check("Prompt bìa KHÔNG chứa 'coloring book' (nhắc là Flux để trắng)",
          "coloring book" not in COVER_STYLE.lower(), COVER_STYLE)
    for w in ("clean black outlines", "flat colors filled neatly inside",
              "nothing left white or uncolored", "harmonious palette",
              "very soft shading", "clear separation between objects",
              "no gradients", "no texture", "no photorealism"):
        check(f"Prompt bìa đòi '{w}'", w in COVER_STYLE)

    # BON CAU TRONG BAN YEU CAU CUA BAO KHONG DUNG DUOC O DAY, bo di la CO Y.
    # Chung viet cho quy trinh to len anh CO SAN (img2img). Flux o day ve tu
    # so ngau nhien, khong co anh net nao de ma giu - bao no "dung sua net co
    # san" la bao dung sua mot thu khong ton tai.
    # Te hon: o CFG=1 khong doc duoc phu dinh, nen "no colors OUTSIDE THE
    # OUTLINES" chi to nhac no nghi toi chuyen mau tran ra ngoai.
    for w in ("existing", "preserve", "do not alter", "outside the outlines",
              "bleeding", "redraw"):
        check(f"Prompt bìa KHÔNG chứa '{w}' (chỉ có nghĩa với img2img)",
              w not in COVER_STYLE.lower())

    # Bang mau dat duoc theo tung cuon - hai cuon cung bo ma bia lech tong
    # nhau thi nhin khong ra mot bo.
    from studio.prompts import build_colour_hint
    tinted = build_cover_prompt("a turtle", main_colors="sea green",
                                secondary_colors="coral pink",
                                background_colors="sky blue")
    for w in ("main colors sea green", "secondary colors coral pink",
              "background in sky blue"):
        check(f"Bảng màu đặt được: '{w}'", w in tinted)
    check("Bảng màu đứng ngay sau chủ thể, trước khối phong cách",
          tinted.index("sea green") < tinted.index("professionally colored"))
    check("Bỏ trống bảng màu thì không ghép ô rỗng vào prompt",
          build_colour_hint() == ""
          and "main colors" not in build_cover_prompt("a turtle"))

    # Canh bia mac dinh lay dong DAU trong file theme - dai 23-26 tu, ba menh
    # de. Bat Flux dung ba thu cung luc tren tam anh QUAN TRONG NHAT cua cuon
    # sach la cach chac chan nhat de ra bo cuc phi ly.
    from studio.prompts import COVER_SUBJECT_MAX_WORDS, load_subjects
    # NGUOC HAN trang ruot: bia can canh GIAU nhat, khong phai gon nhat.
    # Lan truoc toi cat canh bia xuong 12 tu - sai. Trang ruot can gon vi tre
    # phai to duoc; bia can ram vi no la tam anh BAN HANG.
    long_scene = load_subjects("ocean")[0]
    cp = build_cover_prompt(long_scene)
    subject = cp.split(", professionally colored")[0]
    check("Cảnh bìa KHÔNG bị cắt cụt (bìa cần cảnh giàu)",
          subject == long_scene.rstrip("."),
          f"{len(long_scene.split())} → {len(subject.split())} từ")

    from studio.imageops import cover_outline_ratio
    line_art = Image.new("RGB", (256, 256), (255, 230, 60))
    ImageDraw.Draw(line_art).ellipse((30, 30, 226, 226), outline=(0, 0, 0),
                                     width=14)
    soft = Image.new("RGB", (256, 256), (255, 230, 60))
    check("Bìa có nét đen đạt ngưỡng",
          cover_outline_ratio(line_art) >= config.COVER_OUTLINE_MIN,
          f"{cover_outline_ratio(line_art):.1%}")
    check("Bìa không có nét đen bị bắt",
          cover_outline_ratio(soft) < config.COVER_OUTLINE_MIN,
          f"{cover_outline_ratio(soft):.1%}")

    rich = Image.new("RGB", (64, 64), (230, 40, 30))
    pale = Image.new("RGB", (64, 64), (245, 244, 250))
    s_rich, p_rich = cover_vividness(rich)
    s_pale, p_pale = cover_vividness(pale)
    check("Bìa rực đạt ngưỡng",
          s_rich >= config.COVER_SAT_MIN and p_rich <= config.COVER_PALE_MAX,
          f"bão hoà {s_rich:.0f}, nhạt {p_rich:.0%}")
    check("Bìa nhạt bị bắt",
          s_pale < config.COVER_SAT_MIN or p_pale > config.COVER_PALE_MAX,
          f"bão hoà {s_pale:.0f}, nhạt {p_pale:.0%}")

    # Do lai tren 4 bia that neu con. Nguong dat sao cho bat dung hai bia
    # nhat (chihuahua 83, ngay-hoi-bien 27) ma khong dung hai bia dat.
    covers = sorted((ROOT / "library").glob("*/cover-art.png"))
    if covers:
        # Nguong phai TACH BACH duoc, khong phai bat het hoac tha het.
        verdicts = {}
        for p in covers:
            with Image.open(p) as im:
                sv, pl = cover_vividness(im.convert("RGB"))
            verdicts[p.parent.name] = (
                sv >= config.COVER_SAT_MIN and pl <= config.COVER_PALE_MAX)
            print(f"      {p.parent.name:16s} bão hoà {sv:5.0f}  "
                  f"nhạt {pl:5.1%}  {'đạt' if verdicts[p.parent.name] else 'NHẠT'}")
        known_pale = {"chihuahua", "ngay-hoi-bien"}
        wrong = [k for k, ok in verdicts.items()
                 if ok == (k in known_pale)]
        check("Ngưỡng bìa phân loại đúng 4 bìa thật", not wrong, str(wrong))

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
    from studio.prompts import load_template
    for name in _themes():
        # Bộ có @template thì chủ thể cố tình chỉ là mảnh ngắn ("sunflowers
        # with broad round petals") — khuôn mới là câu hoàn chỉnh. Luật hình
        # dạng cảnh không áp cho loại này.
        if load_template(name):
            continue
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
    # Flux schnell duoc huan luyen quanh 1 MP. Vuot xa nguong do thi net di
    # loang choang - da do va xac nhan bang cach so voi anh ve tay trong UI.
    mp = config.GEN_W * config.GEN_H / 1e6
    check("Sinh ảnh quanh 1 MP (vùng Flux schnell được huấn luyện)",
          0.7 <= mp <= 1.6,
          f"{config.GEN_W}x{config.GEN_H} = {mp:.2f} MP, phóng "
          f"{config.ART_W_PX / config.GEN_W:.2f} lần")
    # COMPOSITIONS phải nói về BỐ TRÍ, không nói mật độ — nếu không nó đánh
    # nhau với DENSITY. Đây từng là lỗi thật.
    from studio.prompts import COMPOSITIONS, build_prompt
    clash = [c for c in COMPOSITIONS
             if any(w in c.lower()
                    for w in ("filling", "densely", "packed", "edge to edge",
                              "percent", "background"))]
    check("COMPOSITIONS không nói về mật độ (tránh đánh nhau với DENSITY)",
          not clash, f"{len(clash)} mục: {clash[:1]}")

    print("\n[12] Prompt không tự lặp")
    pr = build_prompt("a smiling fox sitting in tall grass",
                      "simple", "centered composition", "normal", "kawaii")
    words = len(pr.split())
    # Siet tu 180 xuong 100. Prompt Bao chay tay trong UI - cai cho ra net
    # dep hon han - chi 27 tu. Ban cua toi tung phinh len 163.
    check("Prompt dưới 100 từ (bản chạy tay cho nét đẹp chỉ 27 từ)",
          words < 100, f"{words} từ")
    check("Chủ thể đứng ĐẦU prompt, không bị chìm ở giữa",
          pr.startswith("a smiling fox"), pr[:34])

    # Phep do tren MOT chu the nga^n tu bia ra khong bat duoc gi. Cac dong
    # trong themes/ dai gap doi, va chinh chung moi la thu chay that.
    # Phai di qua make_prompts chu khong phai build_prompt: khau cat menh de
    # dai (shorten_subject) nam trong make_prompts. Goi thang build_prompt la
    # do mot duong ma studio khong bao gio chay.
    from studio.prompts import (KIDS_PRESET, load_subjects, list_themes,
                                make_prompts as _mk)
    n_long = max(
        len(pp.prompt.split())
        for t in list_themes()
        for pp in _mk(t, len(load_subjects(t)), "simple",
                     load_subjects(t), seed_start=1,
                     density="normal"))
    check("Dòng chủ thể DÀI NHẤT trong themes/ vẫn dưới 100 từ",
          n_long < 100, f"{n_long} từ")

    # Menh de duoi trong themes/ vua lam prompt tran nguong, vua bat Flux dung
    # ba thu cung luc - nguon goc may trang "logic chua hop ly".
    from studio.prompts import shorten_subject
    long_scene = ("a wise old owl on a fence post, holding a bell in its "
                  "talon, snow falling all around it in the night")
    cut = shorten_subject(long_scene, 14)
    check("Cắt mệnh đề ĐUÔI, giữ chủ thể ở đầu",
          cut.startswith("a wise old owl on a fence post")
          and "snow falling" not in cut, cut)
    check("Cắt theo dấu phẩy, không cắt cụt giữa mệnh đề",
          all(c.strip() in long_scene for c in cut.split(",")))
    check("Chủ thể dài quá vẫn được giữ nguyên, không cắt mất",
          shorten_subject("a very long single clause with no commas at all", 3)
          == "a very long single clause with no commas at all")

    # Moi y CHI duoc noi mot lan. Bản trước nói độ dày nét ba lần và nói
    # khoảng trắng hai lần — prompt phình ra mà không mạnh thêm.
    kid = build_prompt("a fox", composition="front view", **KIDS_PRESET)
    for phrase in ("white space", "thick", "simple"):
        check(f"Không nhắc lại '{phrase}' quá hai lần",
              kid.count(phrase) <= 2, f"{kid.count(phrase)} lần")
    check("Có cấm khung viền trong prompt ẢNH, không chỉ trong chỉ dẫn LLM",
          "no frame" in kid and "no border" in kid)
    check("Có đòi nét ĐỀU, không chỉ đòi nét dày", "even" in kid)

    # CANH VAT MOC MAT MUI CHAN.
    # Lan truoc toi viet "dot eyes and a small smile ON ANIMALS ONLY", tuong
    # chu "only" gioi han duoc pham vi. Khong. Flux chay CFG=1 nen khong phan
    # giai duoc dieu kien - he chu "dot eyes" co mat la moi thu deu moc mat.
    from studio.prompts import STYLE as _ST, load_style
    for w in ("eyes", "smile", "mouth", "nose"):
        check(f"Chuỗi kawaii KHÔNG nhắc '{w}' (chủ thể tự lo phần mặt)",
              w not in _ST["kawaii"], _ST["kawaii"])
    for w in ("no faces", "no eyes", "no arms", "no legs"):
        check(f"Chuỗi decorative có cấm '{w}'", w in _ST["decorative"])

    # Chu de tu khai phong cach. Vá bang mot dong CANH BAO la khong du: canh
    # bao thi doc xong van chay tiep duoc, va lenh `generate` go tay khong he
    # di qua recipe.
    for t in ("floral", "hoa-trong-chau", "mandala"):
        check(f"themes/{t}.txt tự khai @style: decorative",
              load_style(t) == "decorative", str(load_style(t)))
    for t in ("ocean", "khung-long", "giang-sinh"):
        check(f"themes/{t}.txt (con vật) KHÔNG ép decorative",
              load_style(t) in (None, "kawaii"), str(load_style(t)))

    from studio.recipe import Recipe as _R2, _theme_style
    check("Công thức bỏ trống style thì lấy theo chủ đề",
          _theme_style("mandala") == "decorative")
    check("Công thức ghi đè sai phong cách thì bị cảnh báo",
          any("mọc mắt mũi chân" in h
              for h in _R2(slug="x", title="X", theme="mandala",
                           style="kawaii").hints()))
    check("Có tả khoảng trống để tô, không chỉ tả nét",
          "areas to fill" in kid)

    # Flux chay CFG=1 nen BO QUA negative prompt. Moi thu muon cam phai nam
    # trong positive duoi dang "no X" - dung nhu prompt tay cua Bao.
    for must in ("extremely thick even black outlines",
                 "black and white vector line art",
                 "no gray", "no shading", "no thin or broken lines"):
        check(f"Positive prompt có {must!r}", must in pr)

    from studio.prompts import NEGATIVE
    check("NEGATIVE đặt nhóm lỗi nét lên đầu",
          NEGATIVE.startswith("thin lines"), NEGATIVE[:28])
    # Bản trước độ dày nét được nhắc ở cả 4 khối, prompt phình lên 180 từ.
    # Mỗi ý phải nói đúng một lần.
    for phrase, limit in (("line weight", 1), ("no shading", 1),
                          ("texture", 1), ("uncolored", 1)):
        n = pr.lower().count(phrase)
        check(f"'{phrase}' chỉ xuất hiện {limit} lần", n <= limit, f"{n} lần")
    check("Chủ thể có mặt trong prompt", "smiling fox" in pr)

    from studio.prompts import STYLE
    check("Có phong cách kawaii làm mặc định cho sách trẻ em",
          "kawaii" in STYLE and "kawaii" in STYLE["kawaii"])

    print("\n[13] Khuôn bố cục cố định (@template)")
    from studio.prompts import load_template, make_prompts

    tpl = load_template("hoa-trong-chau")
    check("Đọc được @template từ file theme",
          tpl and "{subject}" in tpl, (tpl or "")[:46])

    subs = load_subjects("hoa-trong-chau")
    with_tpl = make_prompts("x", 2, "medium", subs, seed_start=1,
                            density="normal", template=tpl)
    check("Chủ thể được ghép vào khuôn",
          "wooden bucket" in with_tpl[0].prompt)
    check("Hai trang khác nhau ở CHỦ THỂ, chung khuôn",
          "sunflowers" in with_tpl[0].prompt
          and "tulips" in with_tpl[1].prompt)
    # Khuôn đã quyết định bố cục; để thêm COMPOSITIONS và DENSITY vào nữa là
    # ba chỉ dẫn bố cục đánh nhau — đúng lỗi đã gặp ở COMPOSITIONS vs DENSITY
    check("Có khuôn thì KHÔNG kèm COMPOSITIONS",
          "front view" not in with_tpl[0].prompt)
    check("Có khuôn thì KHÔNG kèm DENSITY",
          "one simple background element" not in with_tpl[0].prompt)

    no_tpl = make_prompts("x", 1, "simple", load_subjects("giang-sinh"),
                          seed_start=1, density="normal")
    check("Không có khuôn thì vẫn dùng COMPOSITIONS + DENSITY",
          "front view" in no_tpl[0].prompt
          and "one simple background element" in no_tpl[0].prompt)

    # CẮT chữ cái lạc chứ không bỏ cả dòng — phần còn lại vẫn dùng được.
    # File khung-long.txt của Bao hỏng 19/24 dòng đúng kiểu này, bỏ hết thì
    # mất gần cả bộ.
    stray, _ = clean_lines(
        "e playful pteranodon soaring through the sky, "
        "two round clouds beside it, a wide hill below", 5)
    check("Cắt chữ cái lạc đầu dòng, giữ lại phần còn lại",
          len(stray) == 1 and stray[0].startswith("playful pteranodon"),
          repr(stray[0][:34]) if stray else "rỗng")
    letter_num, _ = clean_lines("b) tiny pterodactyls flying overhead, "
                                "a lake below, two hills behind", 5)
    check("Cắt cả đánh số bằng chữ cái ('b) ...')",
          len(letter_num) == 1 and letter_num[0].startswith("tiny"),
          repr(letter_num[0][:30]) if letter_num else "rỗng")
    check("Không loại nhầm mạo từ 'a'",
          len(clean_lines(
              "a playful pteranodon soaring through the sky, "
              "two round clouds beside it, a wide hill below", 5)[0]) == 1)

    print("\n[14] Độ dày nét")
    # Do NET RA cuoi cung, khong kiem tra co bat co nao. CLOSE_GAPS lam day
    # net san roi nen LINE_THICKEN mac dinh tat.
    # Muc nay TRUOC DAY doi CLOSE_GAPS >= 7. Tuc la chinh bo kiem thu dang
    # KHOA CHAT cai loi lam vo net: no bat buoc phai noi khe >= 7px, ma 9px
    # thi nuot mat tam bong hong. Kiem thu ma khoa mot gia tri sai thi con
    # nguy hon khong co kiem thu, vi no lam nguoi ta tin la da kiem tra roi.
    # Doi thanh KHOANG, va phan tren ([0c]) do KET QUA chu khong do tham so.
    check("Nối khe hở nằm trong khoảng an toàn 2-5px",
          2 <= config.CLOSE_GAPS <= 5, f"{config.CLOSE_GAPS}px")
    check("Ngưỡng đen đủ cao để nét xám thành đen tuyền",
          config.LEVELS_BLACK >= 150, f"{config.LEVELS_BLACK}")
    art = tmp / "line-test.png"
    im = Image.new("L", (config.GEN_W, config.GEN_H), 255)
    ImageDraw.Draw(im).ellipse((200, 300, 700, 900), outline=0, width=4)
    im.save(art)
    page, _ = prepare_page(art)
    a = __import__("numpy").array(page) < 128

    width_px = 2.0 * a.sum() / max(1, (a & ~_erode(a)).sum())
    # Net gia trong test mong hon net Flux that (do tren 4 anh that: 9.8-14.3px)
    check("Nét sau xử lý dày 6-18 px @300dpi",
          6 <= width_px <= 18, f"{width_px:.1f} px")
    # Net phai DEN TUYEN, khong duoc xam. Day la loi thay ro tren anh may:
    # net nen xam nhat nen in ra nhu bi mo.
    import numpy as _np
    g = _np.array(page)
    ink = g < 200
    faint = ((g >= 100) & ink).sum() / max(1, ink.sum())
    check("Dưới 10% pixel mực còn xám nhạt", faint < 0.10, f"{faint:.1%}")

    print("\n[16] Chống nhân vật chồng lên nhau")
    from studio.llm import scrub_overlap

    overlap_cases = [
        # (câu vào, có phải sửa không, vì sao)
        ("two dinosaurs hugging on a big rock, two clouds above them", True,
         "hai con vật ôm nhau"),
        ("a small dinosaur peeking out from behind a big tree, one hill behind",
         True, "một con nấp sau con kia"),
        ("a monkey riding an elephant, two trees beside them", True, "cưỡi"),
        ("two bears playing together in a field, one tree beside them", True,
         "chơi cùng nhau"),
        # Ba câu này PHẢI được tha
        ("a bouquet of sunflowers in a wooden bucket, one leaf beside it",
         False, "hoa cắm trong chậu là bình thường"),
        ("a cat sitting on a chair, one plant behind it", False,
         "con vật ngồi trên đồ vật là bình thường"),
        ("a brontosaurus eating leaves, one simple tree behind it", False,
         "vật nền đứng phía sau là mẫu câu tốt"),
    ]
    for text, should_fix, why in overlap_cases:
        new, notes = scrub_overlap(text)
        touched = (new != text) or bool(notes)
        check(f"{'Sửa' if should_fix else 'Tha'}: {why}",
              touched == should_fix, new[:44])

    # Câu phải còn ĐÚNG NGỮ PHÁP sau khi sửa. Bản đầu cho ra
    # "standing next to on a big rock" vì động từ không có tân ngữ.
    fixed, _ = scrub_overlap("two dinosaurs hugging on a big rock")
    check("Sửa xong câu không bị què",
          "next to on" not in fixed and "beside on" not in fixed, fixed)

    for name in _themes():
        dirty = [s for s in load_subjects(name)
                 if scrub_overlap(s)[0] != s or scrub_overlap(s)[1]]
        check(f"themes/{name}.txt không có cảnh chồng chéo",
              not dirty, f"{len(dirty)} dòng: {dirty[:1]}")

    print("\n[17] Workflow SDXL (negative prompt có tác dụng)")
    import studio.providers.comfyui as cu
    from studio.providers.base import GenRequest

    sdxl = cu.ComfyUIProvider(
        "http://x", ROOT / "workflows/sdxl_lineart.api.json",
        ROOT / "workflows/sdxl_lineart.map.json")
    flux = cu.ComfyUIProvider(
        "http://x", ROOT / "workflows/flux_lineart.api.json",
        ROOT / "workflows/flux_lineart.map.json")

    check("SDXL điều khiển được negative prompt",
          "negative" in sdxl.supported_params)
    # Flux chay CFG=1 nen negative bi bo qua - map co tinh khong khai bao
    check("Flux KHÔNG có negative (CFG=1 nên vô tác dụng)",
          "negative" not in flux.supported_params)
    check("SDXL điều khiển được CFG",
          "guidance" in sdxl.supported_params)

    # steps=None nghia la "giu nguyen gia tri trong workflow". Can vay vi
    # schnell chay 4 buoc con SDXL can 28 - nhet so co dinh vao .env la doi
    # workflow xong lai quen sua.
    req = GenRequest(prompt="p", negative="n", seed=1, width=832, height=1152,
                     steps=None, guidance=None)
    patched = sdxl._patch(req)
    check("steps=None thì giữ nguyên 28 bước của workflow SDXL",
          patched["3"]["inputs"]["steps"] == 28,
          str(patched["3"]["inputs"]["steps"]))
    check("guidance=None thì giữ nguyên CFG 7 của workflow",
          patched["3"]["inputs"]["cfg"] == 7.0)
    check("Negative prompt được ghi vào workflow",
          patched["7"]["inputs"]["text"] == "n")

    req2 = GenRequest(prompt="p", negative="n", seed=1, width=832, height=1152,
                      steps=12, guidance=5.0)
    p2 = sdxl._patch(req2)
    check("Truyền steps thì ghi đè được",
          p2["3"]["inputs"]["steps"] == 12)

    print("\n[18] LoRA")
    lora_req = GenRequest(prompt="p", negative="n", seed=1, width=832,
                          height=1152, steps=None, guidance=None,
                          lora="lineart.safetensors", lora_strength=0.85)
    no_lora = GenRequest(prompt="p", negative="n", seed=1, width=832,
                         height=1152, steps=None, guidance=None, lora=None)

    with_l = sdxl._patch(lora_req)
    check("Có LoRA thì sampler lấy model từ LoraLoader",
          with_l["3"]["inputs"]["model"] == ["10", 0])
    check("Ghi đúng tên file LoRA",
          with_l["10"]["inputs"]["lora_name"] == "lineart.safetensors")
    check("Một giá trị strength áp cho cả model lẫn clip",
          with_l["10"]["inputs"]["strength_model"] == 0.85
          and with_l["10"]["inputs"]["strength_clip"] == 0.85)
    check("CLIP cũng đi qua LoRA",
          with_l["6"]["inputs"]["clip"] == ["10", 1])

    # Khong khai LoRA thi GO HAN node ra, khong phai nap file rong.
    # Cach nay gon hon viec giu hai file workflow gan giong nhau.
    without = sdxl._patch(no_lora)
    check("Không khai LoRA thì node LoraLoader bị gỡ hẳn",
          "10" not in without)
    check("Gỡ xong sampler nối thẳng vào checkpoint",
          without["3"]["inputs"]["model"] == ["4", 0])
    check("Gỡ xong CLIP cũng nối thẳng vào checkpoint",
          without["6"]["inputs"]["clip"] == ["4", 1]
          and without["7"]["inputs"]["clip"] == ["4", 1])
    check("Không còn node nào trỏ tới node đã gỡ",
          not any(v == ["10", 0] or v == ["10", 1]
                  for n in without.values()
                  for v in n.get("inputs", {}).values()))

    # Flux khong co LoraLoader nen truyen lora vao cung khong sao
    check("Flux bỏ qua tham số lora, không lỗi",
          "10" not in flux._patch(lora_req) or True)

    from studio.recipe import Recipe as _R
    bad_strength = _R(slug="x", title="X", lora_strength=3.0)
    try:
        recipe_mod._validate(bad_strength)
        ok = False
    except RecipeError:
        ok = True
    check("Chặn lora_strength ngoài khoảng hợp lý", ok)

    print("\n[15] Lệnh measure")
    from studio.commands.measure import measure_image

    thin = tmp / "net-manh.png"
    thick = tmp / "net-day.png"
    im = Image.new("L", (600, 800), 255)
    ImageDraw.Draw(im).ellipse((100, 100, 500, 700), outline=0, width=2)
    im.save(thin)
    im = Image.new("L", (600, 800), 255)
    ImageDraw.Draw(im).ellipse((100, 100, 500, 700), outline=0, width=12)
    im.save(thick)

    m_thin = measure_image(thin)
    m_thick = measure_image(thick)
    check("Phân biệt được nét mảnh với nét dày",
          m_thick["width_px"] > m_thin["width_px"] * 2,
          f"{m_thin['width_px']:.1f} px so với {m_thick['width_px']:.1f} px")

    grey_img = tmp / "net-xam.png"
    im = Image.new("L", (600, 800), 255)
    ImageDraw.Draw(im).ellipse((100, 100, 500, 700), outline=150, width=12)
    im.save(grey_img)
    check("Phát hiện nét xám không đen hẳn",
          measure_image(grey_img)["grey"] > 0.9,
          f"{measure_image(grey_img)['grey']:.0%} mực xám")
    check("Không báo nhầm khi nét đã đen tuyền",
          m_thick["grey"] < 0.3, f"{m_thick['grey']:.0%}")

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
