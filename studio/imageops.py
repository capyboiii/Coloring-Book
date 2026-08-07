"""
Xử lý ảnh line art cho in ấn.

Ba việc chính:
  1. Khử xám  — Flux hay trả về nền xám nhạt và vùng đổ bóng. In ra sẽ bẩn.
  2. Phóng to — Flux sinh ~1MP, in 300 DPI cần 2175x3000. Phải upscale.
  3. Đo       — ink_ratio và độ mảnh nét, để biết trang nào hỏng mà không
                cần mở từng ảnh.

Thứ tự QUAN TRỌNG: phóng to TRƯỚC rồi mới khử xám. Làm ngược lại sẽ ra
viền răng cưa vì nội suy trên ảnh đã nhị phân hoá.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config


# --------------------------------------------------------------------------
# Khử xám
# --------------------------------------------------------------------------

def build_levels_lut(black_point: int, white_point: int) -> list[int]:
    """
    Bảng tra 256 giá trị:
      <= black_point  -> 0   (đen tuyền)
      >= white_point  -> 255 (trắng tinh)
      ở giữa          -> nội suy tuyến tính

    Cách này khác threshold cứng ở chỗ giữ lại dải chuyển tiếp mỏng ở viền
    nét, nên in ra nét mượt chứ không răng cưa.
    """
    if not 0 <= black_point < white_point <= 255:
        raise ValueError("Phải thoả 0 <= black_point < white_point <= 255")

    lut = []
    span = white_point - black_point
    for v in range(256):
        if v <= black_point:
            lut.append(0)
        elif v >= white_point:
            lut.append(255)
        else:
            lut.append(int(round((v - black_point) * 255 / span)))
    return lut


def apply_levels(
    img: Image.Image,
    black_point: int = config.LEVELS_BLACK,
    white_point: int = config.LEVELS_WHITE,
) -> Image.Image:
    if img.mode != "L":
        img = img.convert("L")
    return img.point(build_levels_lut(black_point, white_point))


# --------------------------------------------------------------------------
# Đo chất lượng
# --------------------------------------------------------------------------

@dataclass
class Metrics:
    ink_ratio: float        # tỉ lệ pixel là nét
    thin_line_score: float  # 1.0 = nét dày, gần 0 = nét mảnh sắp mất khi in
    border_touch: bool      # nét có chạm vùng ngoài safety margin không
    width: int
    height: int
    colour_ratio: float = 0.0  # tỉ lệ pixel CÓ MÀU — trang ruột phải bằng 0

    def problems(self) -> list[str]:
        out = []
        # Đặt đầu tiên vì đây là lỗi nặng nhất: trang ruột mà đã tô sẵn thì
        # trẻ không còn gì để tô.
        if self.colour_ratio > config.COLOUR_RATIO_MAX:
            out.append(f"ẢNH ĐÃ BỊ TÔ MÀU ({self.colour_ratio:.1%} pixel có "
                       f"màu) — trang ruột phải để trắng cho trẻ tô")
        if self.ink_ratio < config.INK_RATIO_MIN:
            out.append(f"gần như trắng (ink {self.ink_ratio:.2%})")
        if self.ink_ratio > config.INK_RATIO_MAX:
            out.append(f"quá đen (ink {self.ink_ratio:.2%})")
        if self.thin_line_score < config.THIN_LINE_MAX:
            out.append(f"nét mảnh, dễ mất khi in ({self.thin_line_score:.2f})")
        if self.border_touch:
            out.append("nét chạm mép, sẽ bị xén")
        return out

    def to_dict(self) -> dict:
        return {
            "ink_ratio": round(self.ink_ratio, 5),
            "thin_line_score": round(self.thin_line_score, 3),
            "colour_ratio": round(self.colour_ratio, 5),
            "border_touch": self.border_touch,
            "width": self.width,
            "height": self.height,
            "problems": self.problems(),
        }


def colour_amount(img: Image.Image, threshold: int = 30) -> float:
    """
    Tỉ lệ pixel thực sự có màu.

    Đo bằng độ lệch giữa ba kênh RGB: ảnh đen trắng thì R=G=B nên lệch bằng 0.
    Vùng được tô màu thì lệch lớn.

    Cần thiết vì `prepare_page` chuyển sang thang xám ngay từ đầu — lúc đó
    quả cầu màu vàng thành xám nhạt rồi thành trắng, nhìn PDF không thấy gì
    lạ. Nhưng ảnh gốc thì đã hỏng, và mấy ảnh khác trong cùng mẻ cũng vậy.
    Phải bắt TRƯỚC khi khử màu.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")
    small = img.resize((256, 256), Image.BILINEAR)
    r, g, b = small.split()
    px_r, px_g, px_b = r.load(), g.load(), b.load()

    coloured = 0
    for y in range(256):
        for x in range(256):
            vals = (px_r[x, y], px_g[x, y], px_b[x, y])
            if max(vals) - min(vals) > threshold:
                coloured += 1
    return coloured / (256 * 256)


def _ink_ratio(img: Image.Image, threshold: int = 128) -> float:
    hist = img.convert("L").histogram()
    ink = sum(hist[:threshold])
    total = sum(hist)
    return ink / total if total else 0.0


def measure(img: Image.Image) -> Metrics:
    gray = img.convert("L")
    ink = _ink_ratio(gray)

    # Bào mòn nét 1 pixel. MaxFilter làm vùng sáng nở ra, tức vùng tối co lại.
    # Nếu sau khi co mà nét biến mất gần hết thì nét vốn đã quá mảnh.
    eroded = gray.filter(ImageFilter.MaxFilter(3))
    ink_after = _ink_ratio(eroded)
    thin_score = (ink_after / ink) if ink > 0 else 0.0

    # Vùng ngoài safety margin: 5% mỗi cạnh, xấp xỉ 0.5in trên khổ 11in
    w, h = gray.size
    band_x = max(1, int(w * 0.05))
    band_y = max(1, int(h * 0.05))
    edges = [
        gray.crop((0, 0, w, band_y)),
        gray.crop((0, h - band_y, w, h)),
        gray.crop((0, 0, band_x, h)),
        gray.crop((w - band_x, 0, w, h)),
    ]
    border_touch = any(_ink_ratio(e) > 0.002 for e in edges)

    return Metrics(
        ink_ratio=ink,
        thin_line_score=thin_score,
        border_touch=border_touch,
        width=w,
        height=h,
    )


# --------------------------------------------------------------------------
# Chuẩn bị ảnh in
# --------------------------------------------------------------------------

def fit_within(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """Phóng/thu giữ nguyên tỉ lệ để lọt hẳn vào khung. Không cắt xén."""
    scale = min(box_w / img.width, box_h / img.height)
    new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(new_size, Image.LANCZOS)


def prepare_page(
    path: Path,
    autocontrast: bool = False,
    black_point: int = config.LEVELS_BLACK,
    white_point: int = config.LEVELS_WHITE,
) -> tuple[Image.Image, Metrics]:
    """
    Đọc một ảnh raw -> trả về trang in đủ khổ 2625x3375 px (đã gồm bleed)
    và số đo chất lượng của phần hình.
    """
    with Image.open(path) as src:
        rgb = src.convert("RGB")
        # Đo màu TRƯỚC khi chuyển thang xám — sau đó là không còn dấu vết
        colour_ratio = colour_amount(rgb)
        gray = rgb.convert("L")

    if autocontrast:
        gray = ImageOps.autocontrast(gray, cutoff=1)

    # 1. Phóng to vào vùng vẽ an toàn
    art = fit_within(gray, config.ART_W_PX, config.ART_H_PX)

    # 2. Khử xám sau khi phóng
    art = apply_levels(art, black_point, white_point)

    metrics = measure(art)
    metrics.colour_ratio = colour_ratio

    # 3. Dán vào trang trắng đủ khổ, canh giữa vùng vẽ
    page = Image.new("L", (config.PAGE_W_PX, config.PAGE_H_PX), 255)
    left = config.inch_to_px(config.ART_LEFT_IN) + (config.ART_W_PX - art.width) // 2
    top = config.inch_to_px(config.ART_TOP_IN) + (config.ART_H_PX - art.height) // 2
    page.paste(art, (left, top))

    return page, metrics


def blank_page() -> Image.Image:
    """Trang trắng mặt sau — sách tô màu in một mặt để bút không lem."""
    return Image.new("L", (config.PAGE_W_PX, config.PAGE_H_PX), 255)


# --------------------------------------------------------------------------
# Ảnh xem trước cho web
# --------------------------------------------------------------------------

def load_font(size: int) -> ImageFont.ImageFont:
    for name in (
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
        "arialbd.ttf",
        "Arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow cũ chưa nhận tham số size
        return ImageFont.load_default()


def watermark(img: Image.Image, text: str = config.WATERMARK_TEXT) -> Image.Image:
    """Đóng dấu chéo mờ. Không chống được kẻ quyết tâm, nhưng đủ ngăn
    người ta lấy ảnh preview đem in thay vì mua."""
    base = img.convert("RGBA")
    layer = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(layer)

    font = load_font(max(28, base.width // 9))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    step_x, step_y = int(tw * 1.6), int(th * 4.5)
    for y in range(-th, base.height + step_y, step_y):
        for x in range(-tw, base.width + step_x, step_x):
            draw.text((x, y), text, font=font, fill=(0, 0, 0, 38))

    layer = layer.rotate(30, resample=Image.BICUBIC, expand=False)
    return Image.alpha_composite(base, layer).convert("RGB")


def web_preview(
    page: Image.Image,
    width: int = config.PREVIEW_WEB_WIDTH,
    mark: bool = True,
) -> Image.Image:
    """Hạ độ phân giải + đóng dấu, dùng cho trang chi tiết sách trên web."""
    ratio = width / page.width
    small = page.resize((width, round(page.height * ratio)), Image.LANCZOS)
    small = small.convert("RGB")
    return watermark(small) if mark else small
