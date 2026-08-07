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
DETAIL LEVEL: {detail}

Write exactly {count} scene descriptions in English. One scene per line.

RULES
1. English only. Never use Vietnamese or any other language.
2. ONE main subject per line. Name it and say what it is doing. Then add AT
   MOST two simple background things. The subject is the star of the page;
   the background is a hint, not a scene.
3. Describe CONTENT only. Never mention "line art", "black and white",
   "coloring page", "outlines" or any drawing style.
4. Write each line as one sentence of about fifteen words. Do not count them.
5. All {count} lines must use a clearly different main subject.
6. Only things that can be drawn with outlines. Avoid fog, light rays,
   reflections, shadows.
7. Never use copyrighted characters such as Disney, Pokemon, Sanrio or Sonic.
8. NEVER name a colour. No red, green, blue, golden, colourful, rainbow.
   The child chooses the colours. Say "a scarf", never "a red scarf".
9. NEVER describe light. No glowing, twinkling, shining, sparkling, gleaming.
   An outline cannot draw light.
10. Subjects must NEVER touch, overlap or hide each other. Write "standing
    next to", never "hugging", "riding", "behind" or "peeking out of".
11. Front view or slightly from the side. Never from above, never a dramatic
    or unusual angle.
12. Keep everything cute, friendly, happy, smiling. Never scary, angry or
    realistic.

Write the lines directly. Do not plan, do not draft, do not check your work.
{extra}

GOOD EXAMPLES
a happy elephant holding a balloon, standing on simple grass with two flowers
a smiling sea turtle swimming, two round bubbles above it and one coral below
a cheerful fire truck parked on a plain road, one simple tree behind it

BAD (a whole scene instead of one subject — the page becomes cluttered)
a jungle with many animals, trees, rivers, birds and insects
BAD (dense background — nothing left to colour comfortably)
a fox in a dense forest with hundreds of leaves and scattered pebbles
FIXED
a smiling fox sitting on a simple grassy field with two flowers

BAD (subjects overlap — limbs end up fused together)
three bears hugging inside a house
FIXED
three bears standing side by side, one simple house behind them

BAD (names colours and light — the picture comes out already coloured)
an elf decorating a tree with colorful ornaments, fairy lights twinkling
FIXED
an elf decorating a tree with round ornaments, two wrapped boxes beside it

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
    "kids": "children aged 3 to 7 — cheerful, cute, easy to recognise",
    "adults": "adults — intricate, decorative, relaxing",
    "all": "all ages",
}

# Ba mức chi tiết theo độ tuổi. Cùng một chủ đề nhưng cảnh viết cho bé 4 tuổi
# phải khác hẳn cảnh viết cho bé 10 tuổi.
AGE_DETAIL = {
    "simple": "very simple, large shapes, minimal details, for ages 3 to 5",
    "medium": "simple details and one cute accessory, for ages 5 to 8",
    "detailed": "moderately detailed, for ages 8 to 12",
    "intricate": "intricate and decorative, for adults",
}

# Luật riêng cho sách trẻ em. Rút từ nhận xét thật khi Bao xem mẻ ảnh đầu:
# quá nhiều nhân vật chồng chéo, dơi và sói làm trẻ sợ, khung viền hoa văn
# rối mắt, đuôi và chân bị cắt cụt.
AUDIENCE_EXTRA = {
    "kids": """
EXTRA RULES FOR YOUNG CHILDREN
- Exactly ONE main character. At most one small companion, standing apart.
- Only one or two background things. Leave the page mostly empty around them.
- Show the whole animal. Never cut off a tail, a leg or a wing.
- No frightening animals. No bats, wolves, spiders, snakes, owls at night.
- No ornate frames, no decorative borders, no swirling patterns.
- Every shape must be big enough for a small hand to colour inside.
- Keep the scene sensible. Do not put objects where they do not belong.
""",
    "adults": "",
    "all": "",
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


# Từ chỉ MÀU và ÁNH SÁNG trong mô tả cảnh là nguyên nhân trực tiếp khiến
# Flux trả về ảnh ĐÃ TÔ MÀU. Prompt ảnh có "no color fill" nhưng chủ thể lại
# nói "with colorful ornaments" — hai chỉ dẫn đánh nhau, và chủ thể thắng vì
# nó cụ thể hơn.
# Trạng từ đi kèm phải cắt cùng, nếu không "brightly colored penguins" thành
# "brightly penguins" — câu què.
COLOUR_WORDS = re.compile(
    r"\b(?:(?:brightly|richly|vividly|deeply|softly)\s+)?"
    r"(red|green|blue|yellow|orange|purple|pink|golden|gold|silver|"
    r"brown|grey|gray|colou?rful|colou?red|rainbow|scarlet|crimson|"
    r"turquoise|violet)\b", re.IGNORECASE)

LIGHT_WORDS = re.compile(
    r"\b(glow\w*|twinkl\w*|shin\w*|shimmer\w*|sparkl\w*|gleam\w*|"
    r"light rays?|sunshine|sunlight|moonlight|sunset|sunrise|reflection\w*)\b", re.IGNORECASE)


def scrub_colour_and_light(line: str) -> tuple[str, list[str]]:
    """
    Bỏ từ chỉ màu, và báo nếu có từ chỉ ánh sáng.

    Màu thì cắt được sạch: "a red scarf" -> "a scarf", nghĩa không đổi.
    Ánh sáng thì không, vì nó thường là cả mệnh đề ("lights twinkling all
    around") — cắt một từ sẽ làm câu què. Chỉ cảnh báo để người sửa tay.
    """
    notes = []

    found_colour = set(m.group(0).lower() for m in COLOUR_WORDS.finditer(line))
    if found_colour:
        line = COLOUR_WORDS.sub("", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        notes.append(f"bỏ từ chỉ màu ({', '.join(sorted(found_colour))})")

    found_light = set(m.group(0).lower() for m in LIGHT_WORDS.finditer(line))
    if found_light:
        notes.append(f"còn từ tả ánh sáng ({', '.join(sorted(found_light))}) "
                     f"— nét viền không vẽ được ánh sáng, nên sửa tay")

    return line, notes


# Sách trẻ em có thêm ràng buộc mà sách người lớn không có
# Dùng biên từ chặt. Bản đầu viết `monster\w*` nên khớp luôn "monstera"
# (cây trầu bà) trong themes/floral.txt — báo động giả.
SCARY = re.compile(
    r"\b(bats?|wolf|wolves|spiders?|snakes?|skeletons?|ghosts?|"
    r"witch(?:es)?|monsters?)\b", re.IGNORECASE)

# Chỉ bắt hoa văn trang trí, không bắt chuyển động tự nhiên. Bản đầu viết
# `swirl\w*` nên "swirling water" trong themes/ocean.txt cũng dính.
ORNATE = re.compile(
    r"\b(ornate|intricate|filigree|elaborate|framed by|"
    r"(?:decorative|patterned|swirling)\s+(?:border|frame|pattern)s?)\b",
    re.IGNORECASE)


def lint_for_kids(line: str) -> list[str]:
    """
    Soi một cảnh theo tiêu chuẩn sách trẻ em. Cảnh báo, không loại.

    Ba thứ hay hỏng, rút từ nhận xét thật khi xem mẻ ảnh đầu:
    quá nhiều thứ trên một trang, con vật đáng sợ, khung viền hoa văn.
    """
    notes = []

    # Đếm mạo từ để ước lượng số đối tượng riêng lẻ. Đếm dấu phẩy không ăn
    # thua: "a deer, a fawn, a sheep, a fox and a rabbit" chỉ có 3 dấu phẩy
    # nhưng tới 5 con vật — đúng kiểu trang mà Bao chê là chồng chéo.
    things = len(re.findall(r"\b(?:a|an)\s+\w", line, re.IGNORECASE))
    if things > 4:
        notes.append(f"khoảng {things} đối tượng riêng lẻ — trang sẽ chồng "
                     f"chéo, trẻ không biết tô cái nào trước")

    if line.count(",") > 3:
        notes.append(f"{line.count(',') + 1} mệnh đề — nhiều thứ quá cho trẻ nhỏ")

    scary = {m.group(0).lower() for m in SCARY.finditer(line)}
    if scary:
        notes.append(f"con vật có thể làm trẻ sợ ({', '.join(sorted(scary))})")

    ornate = {m.group(0).lower() for m in ORNATE.finditer(line)}
    if ornate:
        notes.append(f"hoa văn/khung viền rối mắt ({', '.join(sorted(ornate))})")

    return notes


def looks_like_scene(line: str) -> bool:
    """
    Dòng này có hình dạng của một cảnh thật không?

    Cảnh thật dài và nhiều mệnh đề:
        "a smiling sea turtle swimming through a coral reef, schools of
         small fish above it, seaweed and starfish along the sea floor"
        -> 22 từ, 2 dấu phẩy

    Ghi chú của mô hình thì ngắn và ít dấu phẩy:
        "One sentence per line, about twenty words (approximate)"  -> 8 từ

    KHÔNG dùng hàm này làm điều kiện loại trực tiếp — mandala hợp lệ kiểu
    "a lotus mandala with eight large petals" (7 từ, 0 phẩy) sẽ rớt oan.
    Chỉ dùng để tha cho những dòng vướng luật yếu bên dưới.
    """
    return len(line.split()) >= 12 and line.count(",") >= 2


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

        # Bỏ đánh số và gạch đầu dòng nếu mô hình vẫn làm dù đã dặn.
        #
        # Có cả ĐÁNH SỐ BẰNG CHỮ CÁI: "a) ...", "b. ...". Qwen2.5-7B hay dùng
        # kiểu này, và tệ hơn là nhả ra không có dấu chấm — "b tiny
        # pterodactyls flying overhead". Lúc đó chỉ còn mỗi chữ cái lạc dính
        # vào đầu câu, mà dòng thì vẫn dài và có dấu phẩy nên mọi luật khác
        # đều cho qua. Một file 24 cảnh của Bao hỏng 19 dòng đúng kiểu này.
        line = re.sub(r"^\s*(?:\d+[.)]\s*|[a-z][.)]\s+|[-*•]\s*)", "", line,
                      flags=re.IGNORECASE)
        line = line.strip().strip('"').rstrip(".")
        if not line:
            continue

        # Dấu hai chấm Ở BẤT KỲ ĐÂU. Ghi chú của mô hình luôn có nó
        # ("Formula:", "Draft:", "Top section:", "Wait, re-reading the end
        # of the prompt:"), còn một cảnh thì không bao giờ cần tới nó.
        if ":" in line:
            warnings.append(f"bỏ tiêu đề/ghi chú: {line[:50]!r}")
            continue

        # Dấu nháy kép THƯỜNG là mô hình trích lại chỉ dẫn:
        #     Content only (no "line art", "black and white", etc.)
        # nhưng một cảnh thật cũng có thể có. Chỉ bỏ khi dòng đó KHÔNG có
        # hình dạng của một cảnh — xem looks_like_scene().
        if '"' in line and not looks_like_scene(line):
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

        # Chữ cái lạc ở đầu dòng, không có dấu chấm nên luật trên không bắt.
        # CẮT chữ cái đó chứ không bỏ cả dòng — phần còn lại thường vẫn là
        # một cảnh hoàn chỉnh dùng được. Mạo từ hợp lệ dài một chữ chỉ có "a".
        stray = re.match(r"^([b-z])\s+(.*)", line, re.IGNORECASE)
        if stray:
            line = stray.group(2)
            warnings.append(
                f"cắt chữ cái lạc {stray.group(1)!r} ở đầu: {line[:44]!r}")

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

        line, notes = scrub_colour_and_light(line)
        for n in notes:
            warnings.append(f"{n}: {line[:45]!r}")

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
    # NHƯNG tha cho dòng có hình dạng cảnh thật. Chạy thật với Qwen2.5-7B
    # cho chủ đề Giáng sinh thì hai cảnh hoàn toàn hợp lệ bị loại oan:
    #     "Santa Claus sitting at a table writing letters to children, ..."
    #     "Mrs. Claus baking pies while singing Christmas songs, ..."
    # Danh từ riêng thì viết hoa là đúng. Chủ đề nào cũng có thể có.
    #
    # Rủi ro ngược lại là mô hình phớt lờ luật viết thường và bị xoá sạch.
    # Xử bằng cách: nếu xoá hết thì trả lại nguyên trạng kèm cảnh báo.
    if lines:
        kept, dropped = [], []
        for ln in lines:
            suspect = ln[:1].isupper() and not looks_like_scene(ln)
            (dropped if suspect else kept).append(ln)

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
                      detail: str = "simple",
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
            topic=topic, count=ask, audience=AUDIENCE[audience],
            detail=AGE_DETAIL.get(detail, AGE_DETAIL["simple"]),
            extra=AUDIENCE_EXTRA[audience])

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
