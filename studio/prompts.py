"""
Sinh prompt line art.

Vấn đề cần giải: từ MỘT chủ đề ("đại dương") phải ra 40 prompt KHÁC NHAU.
Nếu chỉ đổi seed, 40 ảnh sẽ na ná nhau và tỷ lệ giữ lại rất thấp.

Cách làm: ghép chủ đề với các trục biến thiên (chủ thể phụ, bố cục, hoạ tiết
nền) theo thứ tự xoay vòng, cộng thêm seed khác nhau.

Muốn kiểm soát chặt hơn thì dùng --subjects <file.txt>, mỗi dòng một chủ thể.
Đó mới là cách cho ra cuốn sách có chủ đích. Bộ sinh tự động dưới đây chỉ để
chạy nhanh mẻ đầu.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, asdict

# --------------------------------------------------------------------------
# Khung prompt
# --------------------------------------------------------------------------

BASE_STYLE = (
    "black and white line art coloring book page, "
    "clean bold uniform outlines, pure white background, "
    "no shading, no grayscale, no hatching, no cross-hatching, no color, "
    "high contrast, crisp vector-like linework"
)

COMPLEXITY = {
    "simple": (
        "very simple shapes, thick bold outlines, large open areas to color, "
        "minimal detail, suitable for young children"
    ),
    "medium": (
        "moderate detail, balanced open areas and pattern, "
        "consistent medium line weight"
    ),
    "detailed": (
        "intricate detailed linework, ornate decorative patterns, "
        "many small areas to color, adult coloring book complexity"
    ),
}

# Flux là mô hình guidance-distilled nên KHÔNG dùng negative prompt như SD.
# Giữ lại chuỗi này để ghi vào metadata và để dùng nếu sau này đổi sang SDXL.
NEGATIVE = (
    "shading, gradient, grayscale, gray fill, solid black fill, texture, "
    "photorealistic, 3d render, watermark, signature, text, letters, "
    "thin faint lines, blurry, cropped, frame, border"
)

COMPOSITIONS = [
    "centered single subject filling the frame",
    "full page scene with foreground and background",
    "decorative circular mandala composition",
    "symmetrical vertical composition",
    "close-up detail view",
    "wide panoramic scene",
    "subject framed by a decorative botanical border",
    "repeating pattern filling the whole page",
]

ARRANGEMENTS = [
    "arranged in a flowing organic layout",
    "arranged in a balanced symmetrical layout",
    "with generous negative space around the subject",
    "densely filling the page edge to edge",
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


def build_prompt(subject: str, complexity: str, composition: str,
                 arrangement: str) -> str:
    parts = [
        BASE_STYLE,
        COMPLEXITY[complexity],
        subject.strip().rstrip("."),
        composition,
        arrangement,
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

    subjects  danh sách chủ thể do người dùng cấp. Nếu ngắn hơn count thì
              phần còn lại lấy chủ đề gốc và biến thiên bằng bố cục.
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
        if subjects:
            subject = subjects[i % len(subjects)]
        else:
            subject = topic

        composition = COMPOSITIONS[i % len(COMPOSITIONS)]
        arrangement = ARRANGEMENTS[(i // len(COMPOSITIONS)) % len(ARRANGEMENTS)]

        out.append(
            PagePrompt(
                index=i + 1,
                prompt=build_prompt(subject, complexity, composition, arrangement),
                negative=NEGATIVE,
                seed=seed_start + i,
                subject=subject,
            )
        )
    return out


def load_subjects(path) -> list[str]:
    """Đọc file chủ thể: mỗi dòng một chủ thể, bỏ dòng trống và dòng bắt đầu #."""
    from pathlib import Path

    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
