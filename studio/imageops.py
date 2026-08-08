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
    colour_ratio: float = 0.0  # tỉ lệ pixel có MẢNG MÀU ĐẬM (má hồng, vật tô)
    colour_tint: float = 0.0   # độ ám màu TRUNG BÌNH trên nét (ảnh phủ sắc)

    def problems(self) -> list[str]:
        out = []
        # Đặt đầu tiên vì đây là lỗi nặng nhất: trang ruột mà đã tô sẵn thì
        # trẻ không còn gì để tô.
        #
        # HAI phép đo, vì có HAI kiểu hỏng khác hẳn nhau và một phép chỉ bắt
        # được một kiểu. Đo trên 20 ảnh thật của Bao mới thấy:
        #   · mảng màu đậm  má hồng trên mặt nhân vật — chỉ 0.4% diện tích
        #                   nhưng chói. Bản cũ để ngưỡng 1% nên lọt hết.
        #   · ám màu        cả ảnh phủ một lớp sắc nâu nhạt. Lệch kênh chỉ
        #                   8-30 nên bản cũ (chỉ đếm lệch > 30) đo ra ĐÚNG
        #                   0.00% và báo sạch.
        if self.colour_ratio > config.COLOUR_RATIO_MAX:
            out.append(f"CÓ MẢNG MÀU ({self.colour_ratio:.2%} diện tích) — "
                       f"thường là má hồng nhân vật; trang ruột phải trắng")
        if self.colour_tint > config.COLOUR_TINT_MAX:
            out.append(f"ẢNH BỊ ÁM MÀU (lệch kênh {self.colour_tint:.1f}) — "
                       f"cả trang phủ một lớp sắc, không phải đen trắng thật")
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
            "colour_tint": round(self.colour_tint, 2),
            "border_touch": self.border_touch,
            "width": self.width,
            "height": self.height,
            "problems": self.problems(),
        }


def colour_report(img: Image.Image) -> tuple[float, float]:
    """
    Trả về (tỉ lệ mảng màu đậm, độ ám màu trung bình trên nét).

    Đo bằng độ lệch giữa ba kênh RGB: ảnh đen trắng thật thì R=G=B nên lệch
    bằng 0. Cần thiết vì `prepare_page` chuyển sang thang xám ngay từ đầu —
    lúc đó má hồng thành xám nhạt rồi thành trắng, nhìn PDF không thấy gì lạ.
    Nhưng ảnh gốc thì đã hỏng. Phải bắt TRƯỚC khi khử màu.

    VÌ SAO HAI SỐ CHỨ KHÔNG PHẢI MỘT
    Bản cũ chỉ đếm pixel lệch > 30 rồi so với ngưỡng 1%. Chạy trên 20 ảnh
    thật thì nó bỏ lọt CẢ HAI kiểu hỏng mà Bao nhìn thấy bằng mắt:

      má hồng   chỉ chiếm 0.4% diện tích, dưới ngưỡng 1% -> báo sạch
      ám màu    lệch kênh chỉ 8-30, dưới ngưỡng 30 -> đo ra ĐÚNG 0.00%

    Hai kiểu hỏng ngược nhau: một cái ĐẬM mà HẸP, một cái NHẠT mà RỘNG. Không
    có con số đơn nào bắt được cả hai, nên tách làm hai.

    Ngưỡng lấy từ số đo thật, không phải bịa:
      mảng màu  ảnh bẩn 0.37-21%   ảnh sạch <= 0.15%   -> cắt ở 0.2%
      ám màu    ảnh bẩn 8.1 va 82  ảnh sạch <= 2.6     -> cắt ở 4.0
    """
    import numpy as np

    if img.mode != "RGB":
        img = img.convert("RGB")
    a = np.asarray(img.resize((256, 256), Image.BILINEAR), dtype=np.int16)
    spread = a.max(axis=2) - a.min(axis=2)

    # Lệch > 60 mới tính là mảng màu thật. Nhét ngưỡng thấp vào đây sẽ đếm cả
    # nhiễu nén JPEG quanh nét đen.
    patch = float((spread > 60).mean())

    # Ám màu chỉ đo trên pixel CÓ MỰC. Nền trắng luôn trung tính nên tính cả
    # nền vào sẽ pha loãng con số xuống gần 0 với mọi ảnh.
    ink = a.mean(axis=2) < 200
    tint = float(spread[ink].mean()) if ink.any() else 0.0
    return patch, tint


def colour_amount(img: Image.Image, threshold: int = 30) -> float:
    """Giữ lại cho code cũ. Chỉ trả về phần mảng màu."""
    return colour_report(img)[0]


def cover_outline_ratio(img: Image.Image) -> float:
    """
    Tỉ lệ pixel là NÉT ĐEN. Bìa phải trông như trang tô màu đã được tô, nên
    nét đen phải còn nguyên chứ không tan vào mảng màu.

    Đo trên 4 bìa cũ: thu-hoa 14.2% (nhìn ra ngay là line art đã tô),
    manmat 7.3%, ngay-hoi-bien 5.5%, chihuahua 1.8% (gần như không có nét).
    """
    import numpy as np

    a = np.asarray(img.convert("RGB").resize((512, 512), Image.BILINEAR))
    return float((a.mean(axis=2) < 70).mean())


def cover_vividness(img: Image.Image) -> tuple[float, float]:
    """
    Trả về (độ bão hoà trung bình 0-255, tỉ lệ diện tích gần như không màu).

    Ngược hẳn với trang ruột: ruột phải TRẮNG, bìa phải RỰC. Cùng một dải đo
    nhưng ngưỡng nằm ở hai đầu đối nhau.

    Vì sao cần: mở 4 ảnh bìa thật ra đo thì chênh nhau một trời một vực —
    mandala 202/255 còn chim cánh cụt 27/255 với 92% diện tích gần trắng.
    Bìa nhạt như thế đặt cạnh sách khác trên kệ là chìm nghỉm, mà nhìn từng
    ảnh một thì không thấy vấn đề gì. Phải có số mới so được.
    """
    import numpy as np

    hsv = np.asarray(img.convert("HSV").resize((256, 256), Image.BILINEAR))
    sat = hsv[:, :, 1].astype(np.int16)
    return float(sat.mean()), float((sat < 60).mean())


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
    border: int = config.PAGE_BORDER_PX,
) -> tuple[Image.Image, Metrics]:
    """
    Đọc một ảnh raw -> trả về trang in đủ khổ 2625x3375 px (đã gồm bleed)
    và số đo chất lượng của phần hình.
    """
    with Image.open(path) as src:
        rgb = src.convert("RGB")
        # Đo màu TRƯỚC khi chuyển thang xám — sau đó là không còn dấu vết
        colour_ratio, colour_tint = colour_report(rgb)
        gray = rgb.convert("L")

    if autocontrast:
        gray = ImageOps.autocontrast(gray, cutoff=1)

    # 1. Phóng to vào vùng vẽ an toàn
    art = fit_within(gray, config.ART_W_PX, config.ART_H_PX)

    # 2. Làm mịn viền. Phải làm SAU khi phóng: cái gợn chỉ lộ ra ở khổ lớn,
    #    làm mịn trước khi phóng thì phóng xong nó lại lồi lõm như cũ.
    if config.SMOOTH_RADIUS > 0:
        art = art.filter(ImageFilter.GaussianBlur(config.SMOOTH_RADIUS))

    # 3. Khử xám sau cùng, ép lại thành nét đen dứt khoát chứ không mờ
    art = apply_levels(art, black_point, white_point)

    # 4. Đóng khe hở: giãn nét rồi co lại. Nối được chỗ đứt nhỏ mà không
    #    làm nét dày thêm.
    if config.CLOSE_GAPS > 1:
        k = config.CLOSE_GAPS
        art = art.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))

    # 5. Làm dày nét — chỉ giãn, không co lại.
    #    MinFilter lấy giá trị nhỏ nhất trong cửa sổ, nên vùng tối (nét) nở
    #    ra. Đây là cách duy nhất chắc chắn ăn: không phụ thuộc Flux vẽ nét
    #    dày hay mảnh.
    if config.LINE_THICKEN > 1:
        art = art.filter(ImageFilter.MinFilter(config.LINE_THICKEN))

    metrics = measure(art)
    metrics.colour_ratio = colour_ratio
    metrics.colour_tint = colour_tint

    # 3. Dán vào trang trắng đủ khổ, canh giữa vùng vẽ
    page = Image.new("L", (config.PAGE_W_PX, config.PAGE_H_PX), 255)
    left = config.inch_to_px(config.ART_LEFT_IN) + (config.ART_W_PX - art.width) // 2
    top = config.inch_to_px(config.ART_TOP_IN) + (config.ART_H_PX - art.height) // 2
    page.paste(art, (left, top))

    if border > 0:
        draw_page_border(page, border)

    return page, metrics


def draw_page_border(page: Image.Image, width: int = config.PAGE_BORDER_PX,
                     radius: int = config.PAGE_BORDER_RADIUS_PX) -> None:
    """
    Vẽ khung đen quanh vùng vẽ của trang.

    Vẽ SAU khi đã đo chất lượng, và cố ý như vậy. `measure()` có một chỉ số
    "nét chạm mép" để bắt hình bị xén; nếu vẽ khung trước thì trang nào cũng
    có nét sát mép và chỉ số đó báo động giả ở cả 40 trang.

    Khung nằm trên đường bao VÙNG VẼ AN TOÀN chứ không phải mép giấy, nên nó
    cách mép xén 0.5 in — máy xén lệch vài mm cũng không cắt phải.
    """
    inset = config.inch_to_px(config.PAGE_BORDER_INSET_IN)
    x0 = config.inch_to_px(config.ART_LEFT_IN) - inset
    y0 = config.inch_to_px(config.ART_TOP_IN) - inset
    x1 = x0 + config.ART_W_PX + 2 * inset
    y1 = y0 + config.ART_H_PX + 2 * inset

    draw = ImageDraw.Draw(page)
    if radius > 0:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=radius,
                               outline=0, width=width)
    else:
        draw.rectangle((x0, y0, x1, y1), outline=0, width=width)


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
