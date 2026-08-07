"""
Gọi Claude để sinh bộ chủ thể từ một chủ đề.

Đây là phần lấp khoảng trống lớn nhất còn lại của Phase 1: đường ống chạy
được với mọi chủ đề, nhưng biến một chủ đề thành 24 cảnh tiếng Anh thì trước
giờ phải viết tay 20-30 phút.

Dùng HTTP thẳng thay vì SDK: `requests` đã là phụ thuộc sẵn, không cần thêm gì.
"""

from __future__ import annotations

import os
import re

import requests

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"


class LLMError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Prompt gửi cho Claude
# --------------------------------------------------------------------------

INSTRUCTIONS = """\
Bạn đang giúp làm sách tô màu in bằng máy. Nhiệm vụ: từ chủ đề dưới đây, viết \
đúng {count} mô tả CẢNH bằng tiếng Anh, mỗi cảnh là một trang tô màu.

Chủ đề: {topic}
Đối tượng: {audience}

Quy tắc bắt buộc:
1. Viết bằng TIẾNG ANH. Mô hình sinh ảnh không hiểu tiếng Việt.
2. Mỗi dòng là một CẢNH, không phải một vật đơn lẻ. Công thức:
   nhân vật chính + hành động + 2-3 thứ khác lấp phần còn lại của trang.
3. Chỉ mô tả NỘI DUNG. Không nhắc tới "line art", "black and white",
   "coloring page", "thick outlines" — phần phong cách đã có sẵn ở chỗ khác.
4. Mỗi dòng 15-30 từ. Dùng dấu phẩy ngăn các mệnh đề.
5. {count} cảnh phải KHÁC NHAU rõ rệt. Đừng lặp lại cùng một con vật hay cùng \
một bố cục.
6. Chỉ dùng hình ảnh có thể vẽ được bằng nét viền. Tránh thứ chỉ thể hiện được \
bằng đổ bóng như sương mù, ánh sáng, phản chiếu.
7. KHÔNG dùng nhân vật có bản quyền (Disney, Pokémon, Sanrio, Sonic...). Đây là \
sách để bán.

Ví dụ đúng, chủ đề đại dương:
a smiling sea turtle swimming through a coral reef, schools of small fish above it, seaweed and starfish along the sea floor below
a cluster of round jellyfish drifting upward, bubbles rising all around them, coral reef and swaying seaweed below

Ví dụ SAI (quá cụt, sẽ ra một vật giữa trang trống):
a sea turtle
jellyfish

Trả về ĐÚNG {count} dòng, mỗi dòng một cảnh. Không đánh số, không gạch đầu \
dòng, không giải thích, không mở đầu kết luận. Chỉ {count} dòng.\
"""

AUDIENCE = {
    "kids": "trẻ em 4-8 tuổi — cảnh vui tươi, dễ thương, dễ nhận ra",
    "adults": "người lớn — cảnh tinh xảo, nhiều hoạ tiết trang trí, thư giãn",
    "all": "mọi lứa tuổi",
}


# --------------------------------------------------------------------------
# Làm sạch kết quả
# --------------------------------------------------------------------------

def clean_lines(text: str, count: int) -> tuple[list[str], list[str]]:
    """
    Lọc kết quả thô của LLM thành danh sách cảnh dùng được.

    Trả về (danh sách cảnh, danh sách cảnh báo). Tách riêng để kiểm thử được
    mà không cần gọi API.
    """
    warnings: list[str] = []

    # LLM hay bọc trong ```
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text.strip(), flags=re.MULTILINE)

    lines: list[str] = []
    seen: set[str] = set()

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Bỏ "1. ", "- ", "* " nếu LLU vẫn đánh số dù đã dặn
        line = re.sub(r"^\s*(?:\d+[.)]\s*|[-*•]\s*)", "", line)
        line = line.strip().rstrip(".")
        if not line:
            continue

        if any(ord(c) > 127 for c in line):
            warnings.append(f"bỏ dòng có ký tự ngoài ASCII: {line[:50]!r}")
            continue

        key = line.lower()
        if key in seen:
            warnings.append(f"bỏ dòng trùng: {line[:50]!r}")
            continue
        seen.add(key)

        if "," not in line:
            warnings.append(
                f"dòng không có dấu phẩy, có thể là vật đơn lẻ chứ không phải "
                f"cảnh: {line[:60]!r}")

        words = len(line.split())
        if words < 8:
            warnings.append(f"dòng quá ngắn ({words} từ): {line[:60]!r}")

        lines.append(line)

    if len(lines) < count:
        warnings.append(f"chỉ lấy được {len(lines)}/{count} cảnh")

    return lines[:count], warnings


# --------------------------------------------------------------------------
# Gọi API
# --------------------------------------------------------------------------

def generate_subjects(topic: str, count: int = 24, audience: str = "all",
                      model: str | None = None,
                      timeout: int = 120) -> tuple[list[str], list[str], str]:
    """Trả về (danh sách cảnh, cảnh báo, tên model đã dùng)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise LLMError(
            "Thiếu ANTHROPIC_API_KEY.\n"
            "  1. Lấy key ở https://console.anthropic.com/settings/keys\n"
            "  2. Thêm vào file .env:  ANTHROPIC_API_KEY=sk-ant-...\n"
            "Mỗi lần sinh một bộ chủ thể tốn khoảng vài xu."
        )

    if audience not in AUDIENCE:
        raise LLMError(f"audience phải là một trong {list(AUDIENCE)}")

    model = model or os.environ.get("STUDIO_LLM_MODEL", DEFAULT_MODEL)
    prompt = INSTRUCTIONS.format(
        topic=topic, count=count, audience=AUDIENCE[audience])

    try:
        resp = requests.post(
            API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise LLMError(f"Không gọi được API: {exc}") from exc

    if resp.status_code == 401:
        raise LLMError("API key sai hoặc hết hạn (HTTP 401)")
    if resp.status_code == 429:
        raise LLMError("Bị giới hạn tần suất (HTTP 429). Đợi một lát rồi thử lại.")
    if resp.status_code != 200:
        raise LLMError(f"API trả lỗi HTTP {resp.status_code}: {resp.text[:400]}")

    blocks = resp.json().get("content", [])
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    if not text.strip():
        raise LLMError("API trả về rỗng")

    lines, warnings = clean_lines(text, count)
    if not lines:
        raise LLMError(f"Không lọc được cảnh nào từ kết quả:\n{text[:500]}")
    return lines, warnings, model
