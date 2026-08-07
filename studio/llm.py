"""
Gọi mô hình chạy local trong LM Studio để sinh bộ chủ thể từ một chủ đề.

LM Studio phơi ra API tương thích OpenAI ở http://localhost:1234/v1 nên chỉ
cần POST /chat/completions như bình thường. Không cần API key, không tốn tiền,
không gửi gì ra ngoài.

Đổi lại: mô hình 9B yếu hơn hẳn mô hình đám mây. Ba chỗ phải xử lý thêm mà
gọi API hãng không gặp:

  1. Chỉ dẫn viết bằng TIẾNG ANH — mô hình nhỏ bám chỉ dẫn tiếng Anh tốt hơn
     nhiều, dù chủ đề đầu vào là tiếng Việt.
  2. Qwen3 có chế độ suy nghĩ, nhả ra <think>...</think> trước câu trả lời.
     Không cắt là rác lọt vào file theme.
  3. Hiếm khi ra đủ số dòng trong một lần. Có vòng xin thêm cho đủ.
"""

from __future__ import annotations

import os
import re

import requests

DEFAULT_URL = "http://localhost:1234/v1"


class LLMError(RuntimeError):
    pass


def base_url() -> str:
    return os.environ.get("LMSTUDIO_URL", DEFAULT_URL).rstrip("/")


# --------------------------------------------------------------------------
# Chỉ dẫn gửi cho mô hình
# --------------------------------------------------------------------------
#
# Viết bằng tiếng Anh có chủ đích. Qwen 9B bám chỉ dẫn tiếng Anh chặt hơn
# tiếng Việt rõ rệt, mà đầu ra vốn cũng phải là tiếng Anh.

INSTRUCTIONS = """\
You write page descriptions for a printed coloring book.

TOPIC: {topic}
AUDIENCE: {audience}

Write exactly {count} scene descriptions in English. One scene per line.

RULES
1. English only. Never use Vietnamese or any other language.
2. Each line is a SCENE, not a single object. Use this formula:
   main subject + what it is doing + 2 or 3 other things filling the rest of the page.
3. Describe CONTENT only. Never mention "line art", "black and white",
   "coloring page", "outlines" or any drawing style.
4. Each line must be 15 to 30 words and must contain commas.
5. All {count} scenes must be clearly different from each other. Do not repeat
   the same animal, object or layout twice.
6. Only things that can be drawn with outlines. Avoid fog, light rays,
   reflections, shadows.
7. Never use copyrighted characters such as Disney, Pokemon, Sanrio or Sonic.

GOOD EXAMPLES (topic: ocean)
a smiling sea turtle swimming through a coral reef, schools of small fish above it, seaweed and starfish along the sea floor below
a cluster of round jellyfish drifting upward, bubbles rising all around them, coral reef and swaying seaweed below

BAD EXAMPLES (too short, will produce one object on an empty page)
a sea turtle
jellyfish

OUTPUT FORMAT
Output exactly {count} lines. Plain text only.
No numbering. No bullets. No blank lines. No headings. No explanation.
Do not write anything before or after the {count} lines.\
"""

TOP_UP = """\
{base}

You already wrote these scenes. Write {count} NEW scenes that are clearly
different from every one of them:

{existing}\
"""

AUDIENCE = {
    "kids": "children aged 4 to 8 — cheerful, cute, easy to recognise",
    "adults": "adults — intricate, decorative, relaxing",
    "all": "all ages",
}


# --------------------------------------------------------------------------
# Làm sạch kết quả
# --------------------------------------------------------------------------

def strip_thinking(text: str) -> str:
    """
    Cắt khối <think>...</think> của mô hình suy luận.

    Qwen3 nhả ra cả quá trình suy nghĩ. Không cắt là nguyên đoạn lảm nhảm
    lọt vào file theme.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Có trường hợp mô hình bị cắt token giữa chừng, thẻ mở không có thẻ đóng
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def clean_lines(text: str, count: int) -> tuple[list[str], list[str]]:
    """
    Lọc kết quả thô thành danh sách cảnh dùng được.

    Trả về (danh sách cảnh, danh sách cảnh báo). Tách riêng khỏi phần gọi mạng
    để kiểm thử được mà không cần LM Studio đang chạy.
    """
    warnings: list[str] = []

    text = strip_thinking(text)
    # Mô hình hay bọc trong ```
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text.strip(), flags=re.MULTILINE)

    lines: list[str] = []
    seen: set[str] = set()

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Bỏ "1. ", "- ", "* " nếu mô hình vẫn đánh số dù đã dặn
        line = re.sub(r"^\s*(?:\d+[.)]\s*|[-*•]\s*)", "", line)
        line = line.strip().strip('"').rstrip(".")
        if not line:
            continue

        # Mô hình nhỏ hay chèn câu dẫn kiểu "Here are 24 scenes:"
        if re.match(r"^(here|below|these|sure|okay|scene[s]?\b|output)\b",
                    line, flags=re.IGNORECASE) and "," not in line:
            warnings.append(f"bỏ câu dẫn: {line[:50]!r}")
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

    return lines[:count], warnings


# --------------------------------------------------------------------------
# Gọi LM Studio
# --------------------------------------------------------------------------

def list_models(timeout: int = 15) -> list[str]:
    try:
        r = requests.get(f"{base_url()}/models", timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as exc:
        raise LLMError(
            f"Không kết nối được LM Studio tại {base_url()}.\n"
            f"  · LM Studio đã bật chưa? Tab Developer -> Start Server\n"
            f"  · Đã nạp model chưa?\n"
            f"  · Cổng mặc định 1234. Khác thì đặt LMSTUDIO_URL trong .env\n"
            f"Chi tiết: {exc}"
        ) from exc
    return [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]


def _resolve_model(model: str | None) -> str:
    if model:
        return model
    env = os.environ.get("STUDIO_LLM_MODEL", "").strip()
    if env:
        return env

    models = list_models()
    if not models:
        raise LLMError(
            "LM Studio đang chạy nhưng chưa nạp model nào. "
            "Nạp Qwen vào rồi thử lại."
        )
    return models[0]


def _chat(model: str, prompt: str, timeout: int, temperature: float) -> str:
    try:
        r = requests.post(
            f"{base_url()}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 4000,
                "stream": False,
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise LLMError(f"Gọi LM Studio lỗi: {exc}") from exc

    if r.status_code != 200:
        raise LLMError(f"LM Studio trả HTTP {r.status_code}: {r.text[:400]}")

    choices = r.json().get("choices") or []
    if not choices:
        raise LLMError("LM Studio không trả về nội dung nào")
    return choices[0].get("message", {}).get("content", "") or ""


def generate_subjects(topic: str, count: int = 24, audience: str = "all",
                      model: str | None = None, timeout: int = 600,
                      temperature: float = 0.85,
                      max_attempts: int = 3
                      ) -> tuple[list[str], list[str], str]:
    """
    Trả về (danh sách cảnh, cảnh báo, tên model đã dùng).

    Mô hình 9B hiếm khi ra đủ số dòng trong một lần — nó hay dừng sớm hoặc lặp
    lại. Nên có vòng xin thêm, mỗi vòng đưa lại danh sách đã có và yêu cầu viết
    những cảnh KHÁC.
    """
    if audience not in AUDIENCE:
        raise LLMError(f"audience phải là một trong {list(AUDIENCE)}")

    model = _resolve_model(model)

    base = INSTRUCTIONS.format(
        topic=topic, count=count, audience=AUDIENCE[audience])

    collected: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for attempt in range(1, max_attempts + 1):
        missing = count - len(collected)
        if missing <= 0:
            break

        if attempt == 1:
            prompt = base
        else:
            prompt = TOP_UP.format(
                base=INSTRUCTIONS.format(
                    topic=topic, count=missing, audience=AUDIENCE[audience]),
                count=missing,
                existing="\n".join(collected),
            )

        raw = _chat(model, prompt, timeout, temperature)
        lines, warns = clean_lines(raw, missing)
        warnings.extend(warns)

        added = 0
        for line in lines:
            key = line.lower()
            if key not in seen:
                seen.add(key)
                collected.append(line)
                added += 1

        if attempt > 1:
            warnings.append(f"lần gọi {attempt}: xin thêm được {added} cảnh")

        if added == 0 and attempt > 1:
            warnings.append("mô hình không nghĩ thêm được cảnh mới, dừng lại")
            break

    if not collected:
        raise LLMError(
            "Không lọc được cảnh nào. Model quá nhỏ hoặc chưa nạp đúng model. "
            "Thử model to hơn, hoặc chạy lại."
        )

    if len(collected) < count:
        warnings.append(f"chỉ lấy được {len(collected)}/{count} cảnh")

    return collected[:count], warnings, model
