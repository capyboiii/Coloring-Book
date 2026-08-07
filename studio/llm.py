"""
Gọi mô hình chạy local trong LM Studio để sinh bộ chủ thể từ một chủ đề.

LM Studio phơi ra API tương thích OpenAI ở http://localhost:1234/v1 nên chỉ
cần POST /chat/completions như bình thường. Không cần API key, không tốn tiền,
không gửi gì ra ngoài.

Đổi lại, mô hình 9B có chế độ suy luận hỏng theo cách rất tốn kém. Lần chạy
đầu tiên thất bại như sau:

    "content": ""
    "reasoning_content": "Thinking Process: ... Count: A(1) happy(2) Santa(3)..."
    "finish_reason": "length"
    "reasoning_tokens": 3999    ← trên tổng 4000

Mô hình đốt sạch 4000 token vào việc **đếm từ từng chữ một** để kiểm tra luật
"mỗi dòng 15-30 từ", rồi hết token trước khi kịp viết câu trả lời. Mất 5 phút
mỗi lần gọi và trả về rỗng.

Ba chỗ đã sửa vì chuyện đó:

  1. TẮT chế độ suy luận (enable_thinking=false + /no_think).
  2. BỎ luật đếm từ — chính nó gây ra vòng đếm vô tận. Nói "một câu, khoảng
     20 từ" thay vì đặt ngưỡng cứng để mô hình phải đi kiểm.
  3. CHIA NHỎ: hỏi 8 cảnh mỗi lần thay vì 24. Yêu cầu ngắn thì mô hình nhỏ
     làm chắc tay hơn nhiều.

Và hai chỗ phòng thủ:

  4. LM Studio để phần suy nghĩ ở trường RIÊNG `reasoning_content`, không phải
     thẻ <think> trong content. Vẫn cắt <think> phòng khi, nhưng phải đọc cả
     trường kia — lần chạy hỏng ở trên có sẵn cảnh dùng được nằm trong đó.
  5. finish_reason == "length" thì cảnh báo rõ, đừng để im lặng trả về thiếu.
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
4. Write each line as one sentence of about twenty words, using commas to
   separate the parts. Do not count the words.
5. All {count} scenes must be clearly different from each other. Do not repeat
   the same animal, object or layout twice.
6. Only things that can be drawn with outlines. Avoid fog, light rays,
   reflections, shadows.
7. Never use copyrighted characters such as Disney, Pokemon, Sanrio or Sonic.

Write the lines directly. Do not plan, do not draft, do not check your work.

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

        # Dòng kết thúc bằng ':' luôn là tiêu đề hoặc câu dẫn, không bao giờ
        # là một cảnh. Luật này chắc hơn nhiều so với dò danh sách từ khoá —
        # bản trước dò "here/below/sure/..." nên vẫn để lọt "Thinking Process:"
        if line.endswith(":"):
            warnings.append(f"bỏ tiêu đề/câu dẫn: {line[:50]!r}")
            continue

        # Dưới 6 từ thì chắc chắn không phải cảnh, bỏ hẳn chứ không chỉ cảnh
        # báo. Rác kiểu này lọt vào file theme là sinh ra một trang hỏng.
        words = len(line.split())
        if words < 6:
            warnings.append(f"bỏ dòng quá ngắn ({words} từ): {line[:50]!r}")
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

        if words < 10:
            warnings.append(f"dòng hơi ngắn ({words} từ), có thể nhạt: "
                            f"{line[:60]!r}")

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


def _post(payload: dict, timeout: int):
    try:
        return requests.post(
            f"{base_url()}/chat/completions", json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise LLMError(f"Gọi LM Studio lỗi: {exc}") from exc


def _chat(model: str, prompt: str, timeout: int, temperature: float,
          max_tokens: int, think: bool) -> tuple[str, str, list[str]]:
    """
    Trả về (nội dung, finish_reason, cảnh báo).

    Tắt suy luận bằng hai cách cùng lúc, vì tuỳ phiên bản mà cách nào ăn:
      · chat_template_kwargs.enable_thinking=false  — llama.cpp / LM Studio
      · hậu tố /no_think trong prompt               — công tắc riêng của Qwen3
    """
    warnings: list[str] = []
    if not think:
        prompt = f"{prompt}\n\n/no_think"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if not think:
        payload["chat_template_kwargs"] = {"enable_thinking": False}

    r = _post(payload, timeout)

    # Máy chủ cũ không biết chat_template_kwargs thì bỏ ra gọi lại,
    # vẫn còn /no_think đỡ đòn.
    if r.status_code == 400 and "chat_template_kwargs" in payload:
        warnings.append("máy chủ không nhận chat_template_kwargs, "
                        "chỉ dựa vào /no_think")
        payload.pop("chat_template_kwargs")
        r = _post(payload, timeout)

    if r.status_code != 200:
        raise LLMError(f"LM Studio trả HTTP {r.status_code}: {r.text[:400]}")

    choices = r.json().get("choices") or []
    if not choices:
        raise LLMError("LM Studio không trả về nội dung nào")

    message = choices[0].get("message", {}) or {}
    finish = choices[0].get("finish_reason", "") or ""
    content = (message.get("content") or "").strip()

    # LM Studio để phần suy nghĩ ở TRƯỜNG RIÊNG, không phải thẻ <think>.
    # Suy luận chạy tràn thì content rỗng còn cảnh nằm hết trong đó.
    if not content:
        reasoning = (message.get("reasoning_content") or "").strip()
        if reasoning:
            warnings.append(
                "mô hình trả về rỗng vì suy luận chạy tràn hết token — "
                "đang vớt cảnh từ phần suy nghĩ, chất lượng sẽ kém hơn")
            content = reasoning

    if finish == "length":
        warnings.append(
            "chạm giới hạn token, câu trả lời bị cắt giữa chừng. "
            "Giảm --batch hoặc tăng --max-tokens.")

    return content, finish, warnings


def generate_subjects(topic: str, count: int = 24, audience: str = "all",
                      model: str | None = None, timeout: int = 600,
                      temperature: float = 0.85, batch: int = 8,
                      max_tokens: int | None = None, think: bool = False,
                      on_progress=None
                      ) -> tuple[list[str], list[str], str]:
    """
    Trả về (danh sách cảnh, cảnh báo, tên model đã dùng).

    Hỏi theo từng mẻ nhỏ (mặc định 8) thay vì đòi 24 cảnh một lúc. Mô hình 9B
    làm yêu cầu ngắn chắc tay hơn hẳn, và nếu một mẻ hỏng thì chỉ mất mẻ đó
    chứ không mất cả lượt.
    """
    if audience not in AUDIENCE:
        raise LLMError(f"audience phải là một trong {list(AUDIENCE)}")

    model = _resolve_model(model)
    batch = max(1, min(batch, count))

    collected: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()

    # Cho phép hụt vài mẻ rồi vẫn còn cơ hội bù
    max_rounds = -(-count // batch) + 3

    for rnd in range(1, max_rounds + 1):
        missing = count - len(collected)
        if missing <= 0:
            break

        ask = min(batch, missing)
        base = INSTRUCTIONS.format(
            topic=topic, count=ask, audience=AUDIENCE[audience])

        if collected:
            # Chỉ đưa lại 12 cảnh gần nhất — đủ để tránh lặp mà không phình
            # prompt, vì prompt dài làm mô hình nhỏ lú thêm.
            prompt = TOP_UP.format(
                base=base, count=ask, existing="\n".join(collected[-12:]))
        else:
            prompt = base

        if on_progress:
            on_progress(rnd, len(collected), count, ask)

        tokens = max_tokens or (ask * 120 + 500)
        raw, _finish, warns = _chat(
            model, prompt, timeout, temperature, tokens, think)
        warnings.extend(warns)

        lines, warns = clean_lines(raw, ask)
        warnings.extend(warns)

        added = 0
        for line in lines:
            key = line.lower()
            if key not in seen:
                seen.add(key)
                collected.append(line)
                added += 1

        if added == 0:
            warnings.append(f"mẻ {rnd} không thêm được cảnh nào")
            if rnd >= 2 and not collected:
                break

    if not collected:
        raise LLMError(
            "Không lọc được cảnh nào.\n"
            "Thường là do chế độ suy luận: mô hình đốt hết token vào phần "
            "suy nghĩ rồi trả về rỗng.\n"
            "  · Tắt Reasoning trong LM Studio (bên phải, phần cấu hình model)\n"
            "  · Hoặc giảm mẻ:  --batch 4\n"
            "  · Hoặc nới trần: --max-tokens 8000\n"
            "  · Hoặc nạp model không có chế độ suy luận (Instruct)"
        )

    if len(collected) < count:
        warnings.append(f"chỉ lấy được {len(collected)}/{count} cảnh")

    return collected[:count], warnings, model
