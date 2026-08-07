"""
Đo chất lượng nét trên một mẻ ảnh.

    python studio.py measure khung-long
    python studio.py measure khung-long --vs khung-long-q6

Vì sao cần lệnh này: từ đầu tới giờ mỗi lần sửa là một lần đoán, rồi nhìn ảnh
bằng mắt và cãi nhau xem có khá hơn không. Mắt người kém ở chỗ so hai thứ gần
giống nhau.

Và tôi đã tự bịp mình một lần bằng chỉ số sai: đếm "đầu mút" thấy 31 → 0 nên
tưởng đã vá xong chỗ đứt, trong khi khe hở còn nguyên — giãn nét làm đầu mút
cụt đi nên không đếm được nữa. Từ đó chỉ dùng những chỉ số kiểm chứng được
bằng mắt.

Bốn chỉ số, đo trên ẢNH GỐC chưa qua xử lý:

  dày nét   px. Dưới 8 px là dưới một ô latent của Flux, VAE tái tạo không nổi
  mực xám   % mực không đen hẳn. Cao = in ra chỗ đậm chỗ nhạt
  quầng mờ  % pixel gần trắng bám quanh nét. Dấu hiệu VAE tái tạo kém
  mảnh rời  số nét không nối nhau. Cao = đứt nhiều
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from .. import config
from ..imageops import colour_amount
from ..util import image_files, info


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "measure",
        help="Đo chất lượng nét trên ảnh gốc của một cuốn",
        description="Dùng để so hai lần chạy khác tham số, thay vì đoán bằng mắt",
    )
    p.add_argument("slug", help="Tên thư mục sách")
    p.add_argument("--vs", dest="other", default=None,
                   help="So với một cuốn khác")
    p.add_argument("--each", action="store_true",
                   help="In từng ảnh, không chỉ trung bình")
    p.set_defaults(func=run)


# --------------------------------------------------------------------------

def _erode(mask: np.ndarray) -> np.ndarray:
    out = mask.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out &= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def _dilate(mask: np.ndarray, r: int = 2) -> np.ndarray:
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def _components(mask: np.ndarray) -> int:
    """Đếm mảnh rời bằng flood fill lặp. Thuần numpy, khỏi cần scipy."""
    seen = np.zeros_like(mask)
    n = 0
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys[::37], xs[::37]):     # lấy mẫu thưa cho nhanh
        if seen[y, x]:
            continue
        n += 1
        blob = np.zeros_like(mask)
        blob[y, x] = True
        for _ in range(60):
            grown = _dilate(blob, 1) & mask
            if (grown == blob).all():
                break
            blob = grown
        seen |= blob
    return n


def measure_image(path) -> dict:
    """Đo một ảnh GỐC. Không chạy qua prepare_page — cố ý."""
    im = Image.open(path)
    g = np.array(im.convert("L"))

    black = g < 128
    ink = g < 200
    n_ink = max(1, int(ink.sum()))

    # Dày trung bình ~ 2 * diện tích / chu vi
    inner = _erode(black)
    perim = max(1, int((black & ~inner).sum()))
    width = 2.0 * int(black.sum()) / perim

    grey = int(((g >= 90) & (g < 200)).sum()) / n_ink
    halo = int(((g >= 200) & (g < 246) & _dilate(ink, 2)).sum()) / n_ink

    small = np.array(im.convert("L").resize((300, 400))) < 128
    return {
        "width_px": width,
        "grey": grey,
        "halo": halo,
        "parts": _components(small),
        "ink": float(black.mean()),
        "colour": colour_amount(im.convert("RGB")),
    }


def _summary(settings, slug: str, each: bool) -> dict | None:
    files = image_files(config.raw_dir(settings, slug))
    if not files:
        info(f"  {slug}: chưa có ảnh trong raw/")
        return None

    rows = [measure_image(f) for f in files]
    if each:
        info(f"  {'ảnh':<9}{'dày px':>8}{'xám':>7}{'quầng':>8}{'mảnh':>7}")
        for f, r in zip(files, rows):
            info(f"  {f.name:<9}{r['width_px']:>8.1f}{r['grey']:>7.0%}"
                 f"{r['halo']:>8.0%}{r['parts']:>7}")
        info("")

    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]} | {
        "n": len(rows)}


def _verdict(m: dict) -> list[str]:
    out = []
    # 8 px là một ô latent của Flux. Mảnh hơn thì VAE không tái tạo sạch được.
    if m["width_px"] < 8:
        out.append(f"nét {m['width_px']:.1f} px, mảnh hơn một ô latent (8 px) "
                   f"— đây là gốc của chuyện nét xám và đứt")
    if m["grey"] > 0.20:
        out.append(f"{m['grey']:.0%} mực còn xám — in ra sẽ chỗ đậm chỗ nhạt")
    if m["halo"] > 0.15:
        out.append(f"quầng mờ {m['halo']:.0%} — VAE tái tạo kém, thử bản "
                   f"lượng tử hoá cao hơn")
    if m["colour"] > 0.01:
        out.append(f"CÓ MÀU {m['colour']:.1%} — trang ruột phải trắng")
    return out


def run(args) -> int:
    settings = config.load_settings()

    info(f"Đo trên ẢNH GỐC, chưa qua xử lý — để tách bạch lỗi của Flux "
         f"với lỗi của khâu xử lý.")
    info("")

    info(f"── {args.slug} ──")
    a = _summary(settings, args.slug, args.each)
    if a is None:
        return 1

    b = None
    if args.other:
        info("")
        info(f"── {args.other} ──")
        b = _summary(settings, args.other, args.each)

    info("")
    if b:
        info(f"{'':<12}{args.slug[:14]:>15}{args.other[:14]:>15}{'đổi':>10}")
        for key, label, fmt in (
                ("width_px", "dày nét", "{:.1f} px"),
                ("grey", "mực xám", "{:.0%}"),
                ("halo", "quầng mờ", "{:.0%}"),
                ("parts", "mảnh rời", "{:.0f}")):
            va, vb = a[key], b[key]
            delta = vb - va
            arrow = "→" if abs(delta) < 1e-9 else ("↑" if delta > 0 else "↓")
            info(f"{label:<12}{fmt.format(va):>15}{fmt.format(vb):>15}"
                 f"{arrow + ' ' + fmt.format(abs(delta)):>10}")
        info("")
        info("dày nét càng cao càng tốt · xám, quầng, mảnh rời càng thấp càng tốt")
    else:
        info(f"  Số ảnh   : {a['n']:.0f}")
        info(f"  Dày nét  : {a['width_px']:.1f} px")
        info(f"  Mực xám  : {a['grey']:.0%}")
        info(f"  Quầng mờ : {a['halo']:.0%}")
        info(f"  Mảnh rời : {a['parts']:.0f}")

        problems = _verdict(a)
        if problems:
            info("")
            for p in problems:
                info(f"  ! {p}")
        else:
            info("")
            info("  Không có vấn đề đáng kể.")

    return 0
