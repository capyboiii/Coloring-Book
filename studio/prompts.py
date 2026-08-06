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

BASE_STYLE = (
    "coloring book page, black and white line art, "
    "clean bold uniform outlines, thick even line weight, "
    "no shading, no grayscale, no color fill, no texture, "
    "pure white background"
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
    "thin faint lines, sketchy lines, blurry, cropped, empty space"
)

# Mọi mục đều nói "full-page" hoặc "filling". Bản cũ có
# "generous negative space" và "balanced open areas" — chính hai chuỗi đó
# đẻ ra mấy ảnh trống hơn nửa trang phía trên.
COMPOSITIONS = [
    "centered full-page composition",
    "full-page composition filling the frame",
    "full page scene, subject large and centered",
    "decorative circular composition filling the page",
    "symmetrical full-page composition",
    "close-up view filling the whole page",
    "full-page scene with foreground and background",
    "subject framed by a decorative border filling the page",
]

# Thêm biến thiên mà không đụng tới bố cục
EXTRAS = [
    "with a few small decorative elements around it",
    "with simple background elements",
    "with a decorative patterned background",
    "with no background, subject only",
]


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
                 extra: str) -> str:
    # Thứ tự bám theo prompt đã chạy tốt: style -> phong cách -> bố cục ->
    # CHỦ THỂ -> phụ kiện. Chủ thể nằm gần cuối, ngay trước phần phụ.
    parts = [
        BASE_STYLE,
        COMPLEXITY[complexity],
        composition,
        subject.strip().rstrip("."),
        extra,
    ]
    return ", ".join(p for p in parts if p)


def make_prompts(
    topic: str,
    count: int,
    complexity: str = "medium",
    subjects: list[str] | None = None,
    seed_start: int | None = None,
) -> list[PagePrompt]:
    """
    Trả về `count` prompt khác nhau.

    subjects    danh sách chủ thể tiếng Anh. Thiếu thì lặp lại chủ đề gốc và
                chỉ biến thiên bằng bố cục — cách này cho kết quả kém hơn hẳn.
    seed_start  cố định để tái tạo lại đúng mẻ ảnh cũ. None -> ngẫu nhiên.
    """
    if complexity not in COMPLEXITY:
        raise ValueError(
            f"complexity phải là một trong {list(COMPLEXITY)}, nhận '{complexity}'"
        )

    if seed_start is None:
        seed_start = random.randint(1, 2**31 - 1)

    subjects = [s.strip() for s in (subjects or []) if s.strip()]

    out: list[PagePrompt] = []
    for i in range(count):
        subject = subjects[i % len(subjects)] if subjects else topic
        composition = COMPOSITIONS[i % len(COMPOSITIONS)]

        # Chủ thể có dấu phẩy nghĩa là nó đã tự mang mệnh đề phụ
        # ("..., a few round bubbles around it"). Thêm EXTRAS vào nữa
        # thành thừa và làm loãng prompt.
        extra = "" if "," in subject else EXTRAS[
            (i // len(COMPOSITIONS)) % len(EXTRAS)
        ]

        out.append(
            PagePrompt(
                index=i + 1,
                prompt=build_prompt(subject, complexity, composition, extra),
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
