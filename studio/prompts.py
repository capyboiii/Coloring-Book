"""
Sinh prompt line art.

Khung prompt dưới đây KHÔNG phải tự nghĩ ra. Nó lấy từ prompt mà Bao đã chạy
tay trong ComfyUI và cho ra ảnh đẹp (con rùa biển trong output/ocean/):

    coloring book page for children, black and white line art,
    clean bold uniform outlines, thick even line weight,
    no shading, no grayscale, no color fill, no texture,
    pure white background, simple cute cartoon style,
    centered full-page composition,
    a smiling sea turtle swimming, a few round bubbles around it

Ba chữ quyết định chất lượng, rút ra từ prompt đó:

  · "thick even line weight"      -> nét dày đều, in ra không mất
  · "simple cute cartoon style"   -> neo phong cách, tránh ra kiểu phác thảo
  · "centered full-page composition" -> hình chiếm hết trang, không thừa trắng

Và điều kiện tiên quyết: **CHỦ THỂ PHẢI VIẾT BẰNG TIẾNG ANH VÀ CỤ THỂ.**
"a smiling sea turtle swimming" ra ảnh đẹp. "đại dương" thì Flux không hiểu,
nó bỏ qua và vẽ bừa — đó là lý do mẻ đầu ra toàn hoa lá.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path

# --------------------------------------------------------------------------
# Khung prompt
# --------------------------------------------------------------------------

# Lưu ý: prompt gốc đã chạy tốt có chuỗi "pure white background". Chuỗi đó
# vốn để chặn nền xám, nhưng Flux đọc nó thành "nền để TRỐNG" — góp phần
# đẻ ra mấy trang có mỗi con sứa giữa khoảng trắng mênh mông.
# Việc chặn nền xám giờ do bước khử xám trong imageops lo, nên ở đây nói
# theo cách không hàm ý bỏ trống.
# Mỗi ý CHỈ nói đúng một lần. Bản trước độ dày nét được nhắc ở cả bốn khối
# (BASE, STYLE, COMPLEXITY và cả DENSITY), prompt phình lên 180 từ và chủ thể
# bị chìm nghỉm ở giữa. Prompt dài không đồng nghĩa với prompt mạnh.
#
# Phân vai:
#   BASE_STYLE  thứ không bao giờ đổi: là line art, chưa tô màu, nét khép kín
#   STYLE       phong cách vẽ
#   COMPLEXITY  mức độ chi tiết
#   DENSITY     bố trí trên trang
BASE_STYLE = (
    "coloring book page, black and white line art, "
    "clean closed outlines with even line weight, "
    "completely uncolored, blank white shapes for a child to fill in, "
    "no shading, no grayscale, no color fill"
)

# --------------------------------------------------------------------------
# PHONG CÁCH VẼ — trục riêng, khác hẳn với độ tinh xảo và mật độ
# --------------------------------------------------------------------------
#
# Thêm trục này sau khi Bao đưa một cuốn sách mẫu làm chuẩn chất lượng. Nhìn
# ảnh mẫu thì rõ nó không phải "cartoon" chung chung mà là một phong cách rất
# cụ thể: kawaii/chibi. Đầu tròn to, thân nhỏ, mắt chấm, miệng một nét cong.
# Đồ vật (dứa, chuối, đàn ukulele, bóng) vẽ như ICON PHẲNG chứ không phải
# hình minh hoạ chi tiết. Nét đều tăm tắp từ nhân vật tới nền.
#
# Chuỗi "simple cute cartoon style" cũ quá mơ hồ nên Flux tự do diễn giải,
# ra kiểu vẽ tay nguệch ngoạc có texture lông lá.
STYLE = {
    "kawaii": (
        "kawaii chibi style, big round head and small rounded body, "
        "simple dot eyes and one small curved smile, "
        "every object drawn as a simple flat icon, "
        "no fur texture, no hatching, no stippling, "
        "characters facing forward in a relaxed pose"
    ),
    "cartoon": (
        "friendly cartoon style, rounded shapes, simple expressive faces, "
        "no fur texture, no hatching"
    ),
    "decorative": (
        "decorative ornamental line art, symmetrical flowing patterns"
    ),
}

COMPLEXITY = {
    "simple": (
        "thick bold outlines, big chunky shapes, large open areas to color, "
        "very few details, no tiny scattered elements, "
        "whole subject fully visible, nothing cut off at the edges, "
        "for young children aged 3 to 7"
    ),
    "medium": (
        "moderate detail, whole subject fully visible, "
        "nothing cut off at the edges"
    ),
    "detailed": (
        "intricate ornamental detail, many areas to color, adult coloring book"
    ),
}

# Flux là mô hình guidance-distilled nên KHÔNG dùng negative prompt.
# Giữ lại để ghi vào metadata và để dùng nếu sau này đổi sang SDXL.
NEGATIVE = (
    "shading, gradient, grayscale, gray fill, solid black fill, "
    "fur texture, hatching, cross-hatching, stippling, scribbles, "
    "photorealistic, 3d render, watermark, signature, text, letters, "
    "thin faint lines, sketchy lines, broken lines, uneven line weight, "
    "blurry, cluttered, busy background, tiny details, fine patterns, "
    "scattered small leaves, grass blades, pebbles, "
    "overlapping characters, cropped limbs, cut off at the edge, "
    "ornate decorative frame, realistic proportions, detailed illustration"
)

# CHỈ nói về GÓC NHÌN và BỐ TRÍ, tuyệt đối không nói tới mật độ.
#
# Bản trước mọi mục đều có "filling the frame edge to edge" hoặc "densely
# packed" — hợp với density=rich nhưng đánh nhau trực tiếp với density=normal
# ("clear white space, uncluttered"). Prompt tự mâu thuẫn thì Flux chọn bừa.
#
# Giờ hai trục tách bạch: COMPOSITIONS lo bố trí, DENSITY lo mật độ.
COMPOSITIONS = [
    "centered composition",
    "wide composition spanning the width of the page",
    "vertical composition",
    "close-up view of the subject",
    "scene with a clear foreground and background",
    "symmetrical composition",
    "circular composition",
    "subject seen slightly from the side",
]

# Mật độ chi tiết — đây là cái cần chỉnh khi ảnh ra chỉ có một đối tượng
# nằm giữa trang trống hoác.
DENSITY = {
    "single": (
        "single subject, plain white background, no background elements"
    ),
    # Chỉnh theo đúng sách mẫu Bao đưa. Trang mẫu KHÔNG ít đồ — cảnh picnic
    # có dứa, chuối, kem, bóng, đàn ukulele. Nhưng mỗi món đều TO, vẽ đơn
    # giản, và tách nhau bằng khoảng trắng rõ ràng. Cái sai của mẻ trước là
    # đồ nhỏ li ti và dính chùm, chứ không phải nhiều đồ.
    "normal": (
        "one main subject in the middle, a few large objects around it, "
        "clear white space between every object, nothing overlapping, "
        "simple horizon line and one or two large background shapes only"
    ),
    "rich": (
        "a rich detailed scene filling the entire page, "
        "many different elements throughout the composition, "
        "background filled with additional details, "
        "no large empty white areas, "
        "elements reaching the top and bottom edges of the page"
    ),
}


@dataclass
class PagePrompt:
    index: int
    prompt: str
    negative: str
    seed: int
    subject: str

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Prompt cho ảnh bìa
# --------------------------------------------------------------------------

COVER_STYLE = (
    "book cover illustration, full color, vibrant saturated colors, "
    "clean cartoon style, bold clear shapes, cheerful and inviting, "
    "vertical composition with space at the top for a title, "
    "no text, no letters, no words, no typography, no watermark"
)


def build_cover_prompt(scene: str) -> str:
    """
    Bìa KHÔNG bị ràng buộc đen trắng — đây là ảnh màu.

    Chuỗi "no text, no letters" là bắt buộc: Flux viết chữ sai chính tả,
    nên chữ tiêu đề do Pillow ghép vào sau.
    """
    return f"{COVER_STYLE}, {scene.strip().rstrip('.')}"


def has_non_ascii(text: str) -> bool:
    """Dò dấu tiếng Việt — dấu hiệu chủ thể chưa dịch sang tiếng Anh."""
    return any(ord(c) > 127 for c in text)


def build_prompt(subject: str, complexity: str, composition: str,
                 density: str, style: str = "kawaii",
                 density_text: str | None = None) -> str:
    # Thứ tự: nền tảng -> PHONG CÁCH -> độ tinh xảo -> bố trí -> CHỦ THỂ ->
    # mật độ. Phong cách đặt sớm vì nó là thứ định hình mạnh nhất; chủ thể
    # đặt gần cuối theo đúng prompt đã chứng minh chạy tốt.
    parts = [
        BASE_STYLE,
        STYLE[style],
        COMPLEXITY[complexity],
        composition,
        subject.strip().rstrip("."),
        DENSITY[density] if density_text is None else density_text,
    ]
    return ", ".join(p for p in parts if p)


def make_prompts(
    topic: str,
    count: int,
    complexity: str = "medium",
    subjects: list[str] | None = None,
    seed_start: int | None = None,
    density: str = "rich",
    style: str = "kawaii",
    template: str | None = None,
) -> list[PagePrompt]:
    """
    Trả về `count` prompt khác nhau.

    subjects    danh sách chủ thể tiếng Anh. Thiếu thì lặp lại chủ đề gốc và
                chỉ biến thiên bằng bố cục — cách này cho kết quả kém hơn hẳn.
    seed_start  cố định để tái tạo lại đúng mẻ ảnh cũ. None -> ngẫu nhiên.
    density     single | normal | rich. Xem DENSITY ở trên.
    """
    if complexity not in COMPLEXITY:
        raise ValueError(
            f"complexity phải là một trong {list(COMPLEXITY)}, nhận '{complexity}'"
        )
    if density not in DENSITY:
        raise ValueError(
            f"density phải là một trong {list(DENSITY)}, nhận '{density}'"
        )
    if style not in STYLE:
        raise ValueError(
            f"style phải là một trong {list(STYLE)}, nhận '{style}'"
        )

    if seed_start is None:
        seed_start = random.randint(1, 2**31 - 1)

    subjects = [s.strip() for s in (subjects or []) if s.strip()]

    out: list[PagePrompt] = []
    for i in range(count):
        subject = subjects[i % len(subjects)] if subjects else topic

        if template:
            # Khuôn đã quyết định CẢ bố cục lẫn cách bày trang, nên bỏ hẳn
            # COMPOSITIONS và DENSITY. Để cả ba là ba chỉ dẫn bố cục đánh
            # nhau — đúng cái lỗi vừa sửa ở COMPOSITIONS vs DENSITY.
            subject = template.replace("{subject}", subject)
            composition = ""
            page_density = ""
        else:
            composition = COMPOSITIONS[i % len(COMPOSITIONS)]
            page_density = DENSITY[density]

        out.append(
            PagePrompt(
                index=i + 1,
                prompt=build_prompt(subject, complexity, composition,
                                    density, style,
                                    density_text=page_density),
                negative=NEGATIVE,
                seed=seed_start + i,
                subject=subject,
            )
        )
    return out


# --------------------------------------------------------------------------
# Bộ chủ thể dựng sẵn
# --------------------------------------------------------------------------

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"


def list_themes() -> list[str]:
    if not THEMES_DIR.exists():
        return []
    return sorted(p.stem for p in THEMES_DIR.glob("*.txt"))


def resolve_subjects_path(value: str) -> Path:
    """
    Nhận vào tên bộ dựng sẵn ('ocean') hoặc đường dẫn file.
    Tên bộ được ưu tiên tra trong themes/ trước.
    """
    candidate = THEMES_DIR / f"{value}.txt"
    if candidate.exists():
        return candidate

    path = Path(value)
    if path.exists():
        return path

    available = ", ".join(list_themes()) or "(chưa có bộ nào)"
    raise FileNotFoundError(
        f"Không tìm thấy '{value}'. Bộ dựng sẵn: {available}"
    )


def load_subjects(value: str) -> list[str]:
    """Đọc chủ thể: mỗi dòng một cái, bỏ dòng trống và dòng bắt đầu bằng #."""
    path = resolve_subjects_path(value)
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines
            if ln.strip() and not ln.startswith(("#", "@"))]


def load_template(value: str) -> str | None:
    """
    Đọc dòng `@template:` nếu file theme có khai báo.

    KHUÔN BỐ CỤC — thứ rút ra từ sách mẫu Bao đưa.

    Cuốn Flower Garden có 48 trang mà **cả 48 dùng chung một bố cục**: một bó
    hoa cắm trong chậu gỗ, đặt giữa trang. Chỉ đổi loại hoa. Nó KHÔNG bắt
    người vẽ nghĩ bố cục mới mỗi trang.

    Đó là lý do sách mẫu trang nào cũng hợp lý và cân đối, còn ảnh của mình
    thì trang lệch trang trống — vì mỗi dòng chủ thể của mình mô tả một cảnh
    khác nhau, và Flux phải tự dựng bố cục 24 lần, hỏng lúc nào không biết.

    Cú pháp trong file theme:

        @template: {subject} arranged in a wooden bucket, centered

    Rồi mỗi dòng chủ thể chỉ cần ghi ngắn gọn: `sunflowers`, `tulips`, `roses`.

    Có khuôn thì studio bỏ luôn phần xoay vòng COMPOSITIONS — khuôn đã quyết
    định bố cục rồi, thêm "close-up view" vào nữa là đánh nhau.
    """
    path = resolve_subjects_path(value)
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln.lower().startswith("@template:"):
            tpl = ln.split(":", 1)[1].strip()
            if "{subject}" not in tpl:
                raise ValueError(
                    f"@template trong {path.name} phải chứa {{subject}}")
            return tpl
    return None
