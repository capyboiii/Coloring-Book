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
Start every line with a lowercase letter.
Output exactly {count} lines. Plain text only.
No numbering. No bullets. No blank lines. No headings. No explanation.
Do not write anything before or after the {count} lines.\
"""

# Chỉ nối thêm danh sách cần tránh. KHÔNG nhắc lại số lượng ở đây — bản trước
# vừa nhúng cả INSTRUCTIONS (đã có "Write exactly N") vừa nói "Write N NEW
# scenes", nên prompt có số đếm ở hai chỗ. Mỗi mẻ lại xin số khác nhau
# (8, 8, 6, 1) nên mô hình đọc thấy mâu thuẫn và bỏ cả lượt ra phân vân.
TOP_UP = """\
{base}

Do not repeat any of these scenes, which already exist:

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


# Dấu hiệu mô hình đang suy luận NGAY TRONG content, không tách ra
# `reasoning_content`. Tắt reasoning trong LM Studio đôi khi chỉ làm nó
# ngừng TÁCH TRƯỜNG, còn mô hình vẫn suy luận y như cũ — chỉ khác là giờ
# nguyên khối suy nghĩ nằm lẫn trong câu trả lời.
REASONING_MARKERS = (
    "thinking process",
    "analyze the request",
    "deconstruct the",
    "let me think",
    "drafting scenes",
    "constraint checklist",
)


def looks_like_reasoning(text: str) -> bool:
    head = text[:400].lower()
    return any(m in head for m in REASONING_MARKERS)


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

        # Dấu hai chấm Ở BẤT KỲ ĐÂU. Ghi chú của mô hình luôn có nó
        # ("Formula:", "Draft:", "Top section:", "Wait, re-reading the end
        # of the prompt:"), còn một cảnh thì không bao giờ cần tới nó.
        if ":" in line:
            warnings.append(f"bỏ tiêu đề/ghi chú: {line[:50]!r}")
            continue

        # Dấu nháy kép chỉ xuất hiện khi mô hình trích lại chỉ dẫn:
        #     Content only (no "line art", "black and white", etc.)
        if '"' in line:
            warnings.append(f"bỏ dòng trích chỉ dẫn: {line[:50]!r}")
            continue

        # Tới đây dấu gạch đầu dòng đã bị cắt ở trên. Còn sót dấu sao nào nữa
        # nghĩa là markdown nhấn mạnh — chỉ có trong ghi chú của mô hình,
        # không bao giờ trong một cảnh:
        #     "**Task:** Write exactly 8 scene descriptions..."
        #     "*Idea 1:* Santa on a roof"
        # Một cảnh thật thì không chứa dấu sao nào cả.
        if "*" in line:
            warnings.append(f"bỏ ghi chú của mô hình: {line[:50]!r}")
            continue

        # Ký hiệu công thức trong ghi chú: "subject + action + 2-3 things"
        if "+" in line:
            warnings.append(f"bỏ ghi chú dạng công thức: {line[:50]!r}")
            continue

        # Ngưỡng 6 từ, KHÔNG đặt ngưỡng dấu phẩy.
        #
        # Bản đầu tôi đặt >=12 từ và >=2 dấu phẩy vì rác trong log đều ngắn.
        # Nhưng đem chạy lại trên chính themes/ tự viết tay thì mandala rớt
        # 24/24 ("a lotus mandala with eight large petals" — 7 từ, 0 phẩy) và
        # floral rớt 5/24. Lọc theo rác chứ không theo cảnh thật là sai.
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

        lines.append(line)

    # --- Lượt hai: chữ hoa đầu dòng ---------------------------------------
    #
    # Chỉ dẫn yêu cầu mọi cảnh bắt đầu bằng chữ thường. Ghi chú của mô hình
    # thì luôn viết hoa: "Formula", "Content only", "One sentence", "All 8
    # scenes", "Only drawable", "Draft", "Wait". Đây là thứ tách được rác
    # khỏi cảnh mà không cần đặt ngưỡng độ dài — vốn đã chứng minh là hỏng.
    #
    # Áp dụng luôn, KHÔNG đặt ngưỡng tỉ lệ. Bản đầu tôi để "chỉ áp dụng nếu
    # >=30% dòng viết thường", nhưng gặp mẻ chỉ có 1 cảnh thật lẫn trong 3
    # dòng ghi chú thì tỉ lệ là 25% và luật không chạy — đúng lúc cần nhất.
    #
    # Rủi ro ngược lại là mô hình phớt lờ luật viết thường và bị xoá sạch.
    # Xử bằng cách: nếu xoá hết thì trả lại nguyên trạng kèm cảnh báo.
    if lines:
        kept, dropped = [], []
        for ln in lines:
            (dropped if ln[:1].isupper() else kept).append(ln)

        if kept:
            for ln in dropped:
                warnings.append(f"bỏ dòng viết hoa đầu, là ghi chú chứ không "
                                f"phải cảnh: {ln[:50]!r}")
            lines = kept
        elif dropped:
            warnings.append(
                "mọi dòng đều viết hoa đầu — mô hình phớt lờ luật viết "
                "thường, nên bỏ qua bộ lọc này. Kiểm kỹ kết quả.")

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

    # `/no_think` đặt ở SYSTEM chứ không nối vào cuối user prompt. Bản trước
    # nối vào cuối, mô hình đọc thấy nó lẫn trong chỉ dẫn rồi mang ra bàn
    # luận ("Then '/no_think'") — thêm nhiễu vào đúng chỗ cần sạch.
    messages = []
    if not think:
        messages.append({"role": "system", "content": "/no_think"})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if not think:
        payload["chat_template_kwargs"] = {"enable_thinking": False}

    r = _post(payload, timeout)

    # Máy chủ cũ không biết chat_template_kwargs thì bỏ ra gọi lại,
    # vẫn còn system /no_think đỡ đòn.
    if r.status_code == 400 and "chat_template_kwargs" in payload:
        warnings.append("máy chủ không nhận chat_template_kwargs, "
                        "chỉ dựa vào system /no_think")
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

    # LM Studio để phần suy nghĩ ở TRƯỜNG RIÊNG `reasoning_content`, không
    # phải thẻ <think> trong content. Suy luận chạy tràn thì content rỗng.
    #
    # Bản trước "vớt" nội dung từ trường đó. ĐÃ BỎ, vì nó biến một thất bại
    # sạch thành nhiễm bẩn âm thầm: khi mô hình bị cắt TRƯỚC lúc kịp viết
    # cảnh, phần vớt được chỉ là ghi chú kế hoạch — chính prompt bị nhại lại
    # ("**Task:** Write exactly 8 scene descriptions..."). Mấy dòng đó được
    # lưu như cảnh, rồi vòng sau đưa lại vào prompt làm danh sách "đã viết",
    # khiến mô hình đọc thấy số đếm mâu thuẫn và đốt sạch token để phân vân.
    #
    # Thà hỏng to còn hơn ghi rác vào file rồi người dùng tưởng là được.
    if not content:
        reasoning = (message.get("reasoning_content") or "").strip()
        if reasoning:
            raise LLMError(
                "Mô hình chỉ suy luận mà không trả lời "
                f"({len(reasoning)} ký tự suy nghĩ, content rỗng).\n"
                "Chế độ suy luận vẫn đang bật. Tắt tại nguồn:\n"
                "  · LM Studio → cột cấu hình model → tắt Reasoning\n"
                "  · hoặc đặt system prompt của model thành: /no_think\n"
                "  · hoặc nạp bản Instruct\n"
                "Kiểm tra nhanh: gọi thử một câu và xem reasoning_content có "
                "rỗng chưa."
            )
        raise LLMError("Mô hình trả về rỗng, không rõ lý do")

    if finish == "length":
        warnings.append(
            "chạm giới hạn token, câu trả lời bị cắt giữa chừng. "
            "Giảm --batch hoặc tăng --max-tokens.")

    return content, finish, warnings


def generate_subjects(topic: str, count: int = 24, audience: str = "all",
                      model: str | None = None, timeout: int = 600,
                      temperature: float = 0.85, batch: int = 8,
                      max_tokens: int | None = None, think: bool = False,
                      on_progress=None, on_result=None
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
    empty_rounds = 0

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
                base=base, existing="\n".join(collected[-12:]))
        else:
            prompt = base

        if on_progress:
            on_progress(rnd, len(collected), count, ask)

        tokens = max_tokens or (ask * 120 + 500)
        raw, _finish, warns = _chat(
            model, prompt, timeout, temperature, tokens, think)
        warnings.extend(warns)

        # Bắt ngay ở mẻ đầu. Không có chốt này thì phải grind 6 mẻ, mất
        # 15 phút, để cuối cùng thu về một file toàn ghi chú của mô hình.
        if rnd == 1 and not think and looks_like_reasoning(raw):
            raise LLMError(
                "Mô hình VẪN đang suy luận, chỉ khác là phần suy nghĩ giờ nằm "
                "lẫn trong câu trả lời thay vì ở trường riêng.\n"
                f"Nó bắt đầu bằng: {raw[:80]!r}...\n\n"
                "Tắt Reasoning trong LM Studio chỉ làm nó ngừng TÁCH TRƯỜNG, "
                "chứ mô hình vẫn suy luận như cũ.\n\n"
                "Cách chắc ăn nhất: nạp model KHÔNG CÓ chế độ suy luận.\n"
                "  Việc này chỉ là viết 24 câu tiếng Anh — model instruct 7-8B "
                "làm trong vài giây,\n"
                "  còn model suy luận thì mất 5 phút mỗi mẻ và ra kết quả tệ hơn.\n"
                "  Gợi ý: Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct, "
                "Mistral-7B-Instruct\n\n"
                "Nếu muốn giữ model này, thử: --think (để nó suy luận xong hẳn "
                "rồi trả lời) kèm --max-tokens 8000 --batch 4"
            )

        lines, warns = clean_lines(raw, ask)
        warnings.extend(warns)
        dropped = sum(1 for w in warns if w.startswith("bỏ "))

        added = dupes = 0
        for line in lines:
            key = line.lower()
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            collected.append(line)
            added += 1

        # Báo cáo từng mẻ: vì sao xin 8 mà chỉ được 6. Không có dòng này thì
        # nhìn tiến độ nhảy 8 → 14 → 18 rất khó hiểu.
        if on_result:
            on_result(rnd, ask, added, dupes, dropped)

        if added == 0:
            empty_rounds += 1
            warnings.append(f"mẻ {rnd} không thêm được cảnh nào")
            # Hai mẻ liên tiếp trắng tay nghĩa là mô hình đã cạn ý cho chủ đề
            # này. Gọi tiếp chỉ tốn thêm vài phút chờ mà không được gì.
            if empty_rounds >= 2:
                warnings.append(
                    "hai mẻ liên tiếp không ra cảnh mới — mô hình cạn ý cho "
                    "chủ đề này, dừng sớm")
                break
        else:
            empty_rounds = 0

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
