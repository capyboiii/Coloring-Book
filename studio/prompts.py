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
BASE_STYLE = (
    "coloring book page, black and white line art, "
    "clean bold uniform outlines, thick even line weight, "
    "no shading, no grayscale, no color fill, no texture, "
    "white paper, unshaded"
)

COMPLEXITY = {
    "simple": (
        "simple cute cartoon style, very thick bold outlines, "
        "large open areas to color, minimal detail, for young children"
    ),
    "medium": (
        "simple clean cartoon style, thick even outlines, moderate detail"
    ),
    "detailed": (
        "decorative illustration style, thick clear outlines, "
        "intricate ornamental detail, many areas to color, "
        "adult coloring book"
    ),
}

# Flux là mô hình guidance-distilled nên KHÔNG dùng negative prompt.
# Giữ lại để ghi vào metadata và để dùng nếu sau này đổi sang SDXL.
NEGATIVE = (
    "shading, gradient, grayscale, gray fill, solid black fill, texture, "
    "photorealistic, 3d render, watermark, signature, text, letters, "
    "thin faint lines, sketchy lines, blurry, cropped, "
    "empty space, blank margins, single isolated object"
)

# Mọi mục đều nói "full-page" hoặc "filling". Bản cũ có
# "generous negative space" và "balanced open areas" — chính hai chuỗi đó
# đẻ ra mấy ảnh trống hơn nửa trang phía trên.
COMPOSITIONS = [
    "full-page scene filling the frame edge to edge",
    "busy full-page composition, elements from top to bottom",
    "layered scene with foreground, middle ground and background",
    "decorative circular composition filling the page",
    "symmetrical full-page composition filling the frame",
    "wide scene spanning the full width of the page",
    "densely packed composition filling every corner",
    "scene framed by a decorative border filling the page",
]

# Mật độ chi tiết — đây là cái cần chỉnh khi ảnh ra chỉ có một đối tượng
# nằm giữa trang trống hoác.
DENSITY = {
    "single": (
        "single subject, plain white background, no background elements"
    ),
    "normal": (
        "with several background elements around the subject"
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


def has_non_ascii(text: str) -> bool:
    """Dò dấu tiếng Việt — dấu hiệu chủ thể chưa dịch sang tiếng Anh."""
    return any(ord(c) > 127 for c in text)


def build_prompt(subject: str, complexity: str, composition: str,
                 density: str) -> str:
    # Thứ tự bám theo prompt đã chạy tốt: style -> phong cách -> bố cục ->
    # CHỦ THỂ -> mật độ. Chủ thể nằm gần cuối, ngay trước phần mật độ.
    parts = [
        BASE_STYLE,
        COMPLEXITY[complexity],
        composition,
        subject.strip().rstrip("."),
        DENSITY[density],
    ]
    return ", ".join(p for p in parts if p)


def make_prompts(
    topic: str,
    count: int,
    complexity: str = "medium",
    subjects: list[str] | None = None,
    seed_start: int | None = None,
    density: str = "rich",
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

    if seed_start is None:
        seed_start = random.randint(1, 2**31 - 1)

    subjects = [s.strip() for s in (subjects or []) if s.strip()]

    out: list[PagePrompt] = []
    for i in range(count):
        subject = subjects[i % len(subjects)] if subjects else topic
        composition = COMPOSITIONS[i % len(COMPOSITIONS)]

        out.append(
            PagePrompt(
                index=i + 1,
                prompt=build_prompt(subject, complexity, composition, density),
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
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
