"""
Cảnh dạng đồ thị — chống lỗi logic đối tượng.

VẤN ĐỀ
Bao đo được cứ 40 ảnh thì khoảng 10 ảnh sai logic: vật lơ lửng không tựa vào
đâu, hai con vật dính vào nhau, đồ vật nằm sai chỗ. Flux không hiểu ngữ cảnh,
nó chỉ khớp cụm từ.

VÌ SAO CHỮA Ở PROMPT KHÔNG ĂN
Flux schnell chạy CFG=1 nên không đọc được ràng buộc. Đã dính ba lần trong dự
án này: "no text" ra chữ, "dot eyes on animals only" ra mắt khắp nơi, "no
colors outside the outlines" ra bìa trắng gần hết. Thêm câu cấm vào prompt chỉ
tổ triệu hồi đúng thứ mình cấm.

CÁI KHÁC BIỆT THẬT SỰ CỦA ĐỒ THỊ
Không phải ở chỗ nó "rõ ràng hơn" cho Flux — mà ở chỗ **máy kiểm được**.

    prose:  "a panda, a bamboo shoot and a sunflower"
            -> muốn biết cây tre đứng ở đâu thì phải hiểu tiếng Anh

    graph:  OBJECTS: bamboo shoot, sunflower
            RELATIONSHIPS: bamboo_shoot --behind--> panda
            -> `sunflower` không xuất hiện trong quan hệ nào. Sai. Bắt bằng
               ba dòng code, không cần model nào cả.

Bắt buộc mô hình điền vào ô cũng làm chính nó phải nghĩ tới chỗ đứng của từng
vật — thứ mà viết văn xuôi tự do thì bỏ qua lúc nào không hay.

ĐỒ THỊ KHÔNG ĐI THẲNG VÀO FLUX
Flux ăn văn xuôi. "panda --sitting_on--> ground" là cú pháp máy, T5 mã hoá ra
thì mũi tên và gạch dưới chỉ tốn token. Nên đồ thị được **duỗi lại thành câu**
bằng code — và vì duỗi bằng code nên mọi vật CHẮC CHẮN có chỗ đứng, không phụ
thuộc hôm đó mô hình có nhớ hay không.

    -> a panda sitting on the ground, eating bamboo,
       a bamboo shoot behind it, a sunflower beside it

Muốn thử đưa đồ thị thô vào Flux để so thì có `graph_text()`. Đo rồi hãy tin.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .llm import COLOUR_WORDS, LIGHT_WORDS

# --------------------------------------------------------------------------
# Từ vựng quan hệ
# --------------------------------------------------------------------------
#
# Danh sách đóng, cố ý. Mở cho mô hình tự đặt tên quan hệ thì nó đẻ ra
# "interacting_with", "near_to", "associated_with" — nghe thì được nhưng
# không nói được vật nằm ở đâu, tức là mất sạch cái lợi của đồ thị.

# Quan hệ TỰA — vật có chỗ đứng. Chủ thể bắt buộc phải có ít nhất một cái.
SUPPORT = {
    "sitting_on": "sitting on",
    "standing_on": "standing on",
    "lying_on": "lying on",
    "perched_on": "perched on",
    "floating_in": "floating in",
    "swimming_in": "swimming in",
    "flying_over": "flying over",
    "growing_in": "growing in",
    "growing_on": "growing on",
    "planted_in": "planted in",
}

# Quan hệ VỊ TRÍ — vật này nằm đâu so với vật kia
BESIDE = {
    "beside": "beside",
    "next_to": "next to",
    "behind": "behind",
    "above": "above",
    "below": "below",
    "under": "under",
    "in_front_of": "in front of",
    "around": "around",
    "inside": "inside",
    "on_top_of": "on top of",
}

RELATIONS = {**SUPPORT, **BESIDE}

# Quan hệ CẤM — đây đúng là mấy thứ làm hỏng hình. Hai con vật chạm nhau thì
# Flux nhập chân tay chúng vào nhau thành một cục.
FORBIDDEN = {
    "riding": "cưỡi", "hugging": "ôm", "holding": "cầm", "carrying": "bế",
    "climbing_on": "trèo lên", "hiding_behind": "nấp sau",
    "peeking_from": "thò ra từ", "touching": "chạm", "overlapping": "chồng lên",
    "wearing": "mặc", "sitting_in": "ngồi trong",
}

ARROW = re.compile(r"^\s*(.+?)\s*--\s*([a-z_]+)\s*-->\s*(.+?)\s*$", re.I)

# re.M là BẮT BUỘC, không phải cho đẹp.
#
# Thiếu nó thì `$` chỉ khớp cuối CHUỖI, nên `FIELD.search(<cả khối>)` luôn trả
# về None — và `parse_many` dùng đúng phép đó để lọc khối hợp lệ. Kết quả:
# đọc từng dòng thì chạy, đọc cả khối thì rỗng. Mẻ nào cũng "dùng được 0" mà
# không báo gì, vì không có đồ thị nào để mà loại.
#
# Kiểm thử của tôi chỉ gọi `parse_block` nên không đụng vào đường này. Đúng
# cái lỗi đã mắc hai lần trong dự án: kiểm thử một đường, chạy thật một đường
# khác.
FIELD = re.compile(r"^\s*(SUBJECT|ACTION|OBJECTS|RELATIONSHIPS|CONSTRAINTS)"
                   r"\s*:\s*(.*)$", re.I | re.M)

# Mô hình nhỏ hay gói nhãn vào markdown hoặc đánh số. Gỡ trước khi đọc thay vì
# nhồi thêm nhánh vào FIELD — dễ đọc hơn và không làm biểu thức phình ra.
DECOR = re.compile(r"^\s*(?:[-*+•]\s*|\d+[.)]\s*)?[*_#`]*\s*"
                   r"(SUBJECT|ACTION|OBJECTS|RELATIONSHIPS|CONSTRAINTS)"
                   r"[*_#`]*\s*:\s*", re.I)


# Chèn dấu ngắt vào giữa hai quan hệ viết liền nhau, xem parse_block()
SPLIT = re.compile(r"(-->\s*[\w ]+?)(?=\s+[\w_]+\s*--\s*[a-z_]+\s*-->)", re.I)


def tidy(text: str) -> str:
    """Bỏ markdown và đánh số quanh nhãn, để phần đọc chỉ lo một dạng."""
    return "\n".join(DECOR.sub(lambda m: m.group(1).upper() + ": ", ln)
                     for ln in text.splitlines())

# Chỗ đứng mặc định — không phải "vật" mà là nền, nên không cần khai ở OBJECTS
GROUNDS = {"ground", "grass", "floor", "snow", "sand", "water", "sea",
           "sea floor", "sky", "air", "path", "road", "table", "branch",
           "rock", "pond", "river"}


def _norm(name: str) -> str:
    """`Bamboo Shoot` và `bamboo_shoot` phải ra cùng một khoá."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _phrase(name: str) -> str:
    """Ngược lại: `bamboo_shoot` -> `bamboo shoot` để ghép vào câu."""
    return _norm(name).replace("_", " ")


@dataclass
class Relation:
    src: str
    kind: str
    dst: str


@dataclass
class SceneGraph:
    subject: str = ""
    action: str = ""
    objects: list[str] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)

    # ----------------------------------------------------------------- kiểm
    def problems(self, max_objects: int = 2) -> list[str]:
        """
        Danh sách lỗi. Rỗng nghĩa là cảnh vẽ ra được.

        Đây là phần đáng giá nhất của cả module: mấy phép kiểm dưới đây chạy
        bằng code thuần, không gọi model, không đoán — nên chúng chạy giống
        nhau mọi lần và giải thích được vì sao loại.
        """
        out = []
        if not self.subject:
            out.append("thiếu SUBJECT")
        if not self.action:
            out.append("thiếu ACTION")

        names = {_norm(o) for o in self.objects}
        subj = _norm(self.subject)

        # 1. Chủ thể phải TỰA vào một cái gì đó. Đây là lỗi hay gặp nhất:
        #    con vật lơ lửng giữa trang vì không ai nói nó đứng ở đâu.
        if subj and not any(r.src == subj and r.kind in SUPPORT
                            for r in self.relations):
            out.append(f"'{self.subject}' không tựa vào đâu — thiếu quan hệ "
                       f"kiểu {', '.join(sorted(SUPPORT)[:3])}...")

        # 2. Mọi vật khai ra đều phải có mặt trong ít nhất một quan hệ.
        #    Vật khai rồi bỏ đó chính là vật sẽ lơ lửng trong tranh.
        used = {r.src for r in self.relations} | {r.dst for r in self.relations}
        for name in sorted(names - used):
            out.append(f"'{_phrase(name)}' khai ở OBJECTS nhưng không có "
                       f"quan hệ nào — sẽ lơ lửng")

        # 3. Quan hệ chỉ được nối những thứ đã khai, hoặc nền.
        known = names | {subj} | {_norm(g) for g in GROUNDS}
        for r in self.relations:
            for side in (r.src, r.dst):
                if side and side not in known:
                    out.append(f"quan hệ nhắc '{_phrase(side)}' mà không khai "
                               f"ở OBJECTS")
            if r.kind in FORBIDDEN:
                out.append(f"quan hệ '{r.kind}' ({FORBIDDEN[r.kind]}) làm hai "
                           f"vật dính vào nhau — Flux sẽ nhập chúng làm một")
            elif r.kind not in RELATIONS:
                out.append(f"quan hệ '{r.kind}' không có trong từ vựng")

        # 4. Đông quá thì trang rối và trẻ khó tô.
        if len(names) > max_objects:
            out.append(f"{len(names)} vật nền, quá {max_objects}")

        # 5. Màu và ánh sáng: trang ruột phải để trắng cho trẻ tô, mà nét thì
        #    không vẽ được ánh sáng.
        blob = " ".join([self.subject, self.action] + self.objects)
        if COLOUR_WORDS.search(blob):
            out.append("có từ chỉ màu — trang ruột phải để trắng")
        if LIGHT_WORDS.search(blob):
            out.append("có từ chỉ ánh sáng — nét không vẽ được ánh sáng")
        return list(dict.fromkeys(out))

    # ---------------------------------------------------------------- duỗi
    def to_prompt(self) -> str:
        """
        Duỗi đồ thị thành câu cho Flux.

        Duỗi bằng CODE chứ không nhờ mô hình viết lại, và đó là cả điểm mấu
        chốt: mọi vật chắc chắn được nêu kèm chỗ đứng, không phụ thuộc hôm đó
        mô hình có nhớ hay không.

        Thứ tự: chủ thể + chỗ tựa, rồi hành động, rồi từng vật kèm vị trí.
        Chủ thể đứng ĐẦU — điều kiện đã chứng minh là quan trọng nhất.
        """
        subj = _norm(self.subject)
        parts = []

        support = next((r for r in self.relations
                        if r.src == subj and r.kind in SUPPORT), None)
        head = f"a {_phrase(self.subject)}"
        if support:
            head += f" {SUPPORT[support.kind]} the {_phrase(support.dst)}"
        parts.append(head)

        if self.action:
            parts.append(self.action.strip().rstrip("."))

        for r in self.relations:
            if r is support or r.src == subj:
                continue
            if r.kind not in RELATIONS:
                continue
            # "sunflower --beside--> panda" -> "a sunflower beside it"
            target = "it" if r.dst == subj else f"the {_phrase(r.dst)}"
            parts.append(f"a {_phrase(r.src)} {RELATIONS[r.kind]} {target}")

        return ", ".join(parts)

    def graph_text(self) -> str:
        """
        Đồ thị ở dạng chữ, để thử đưa thẳng vào Flux mà so với `to_prompt()`.

        Tôi không nghĩ cách này thắng — Flux ăn văn xuôi, mũi tên và gạch dưới
        chỉ tốn token của T5. Nhưng tôi đã đoán sai về hành vi model đủ nhiều
        lần trong dự án này để không chặn đường đo.
        """
        rel = " ".join(f"{r.src} --{r.kind}--> {r.dst}" for r in self.relations)
        return (f"SUBJECT: {self.subject} ACTION: {self.action} "
                f"OBJECTS: {' '.join(_norm(o) for o in self.objects)} "
                f"RELATIONSHIPS: {rel} "
                f"CONSTRAINTS: objects are separate, no object overlaps the "
                f"{_norm(self.subject)} unnaturally, all objects fully visible")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["prompt"] = self.to_prompt()
        d["problems"] = self.problems()
        return d


# --------------------------------------------------------------------------
# Đọc kết quả mô hình
# --------------------------------------------------------------------------

def parse_block(block: str) -> SceneGraph:
    """
    Đọc MỘT khối đồ thị. Trường thiếu thì để trống, `problems()` lo báo.

    Cố ý dễ tính ở khâu đọc và khó tính ở khâu kiểm: mô hình nhỏ hay lệch
    định dạng lặt vặt (dùng dấu `;` thay `,`, viết hoa khác đi), mà những
    chuyện đó không ảnh hưởng gì tới việc cảnh có vẽ được hay không.
    """
    block = tidy(block)
    g = SceneGraph()
    current = None
    buf: dict[str, list[str]] = {}

    for line in block.splitlines():
        m = FIELD.match(line)
        if m:
            current = m.group(1).upper()
            buf.setdefault(current, []).append(m.group(2))
        elif current and line.strip():
            buf.setdefault(current, []).append(line)

    def take(key: str) -> str:
        return " ".join(buf.get(key, [])).strip()

    g.subject = take("SUBJECT").strip(" .,")
    g.action = take("ACTION").strip(" .,")
    g.objects = [o.strip() for o in re.split(r"[,;]", take("OBJECTS"))
                 if o.strip() and o.strip().lower() not in ("none", "-")]

    # Mô hình nhỏ ngăn cách các quan hệ tuỳ hứng: có lúc `;`, có lúc `,`, có
    # lúc chỉ một dấu cách. Nên chèn `;` vào trước khi tách: chỗ nào một đích
    # bị theo sau bởi `<từ> --<quan hệ>-->` thì đó là ranh giới.
    # Không tách bằng dấu cách đơn thuần được — đích có thể nhiều chữ
    # ("sea floor"), tách ra là mất.
    rels = SPLIT.sub(r"\1;", take("RELATIONSHIPS"))
    for chunk in re.split(r"[;,\n]", rels):
        m = ARROW.match(chunk)
        if m:
            g.relations.append(Relation(_norm(m.group(1)),
                                        m.group(2).strip().lower(),
                                        _norm(m.group(3))))
    return g


def parse_many(text: str) -> list[SceneGraph]:
    """Tách nhiều khối. Mỗi khối mở đầu bằng `SUBJECT:`."""
    text = tidy(text)
    blocks = re.split(r"\n(?=\s*SUBJECT\s*:)", text.strip(), flags=re.I)
    return [parse_block(b) for b in blocks if FIELD.search(b or "")]


# --------------------------------------------------------------------------
# Lưu trữ
# --------------------------------------------------------------------------

def save(path: Path, topic: str, graphs: list[SceneGraph]) -> None:
    """
    Ghi đồ thị ra file .graph.json bên cạnh file .txt.

    File .txt vẫn là mặt tiếp xúc của cả hệ thống — `generate`, `cover`,
    `recipe` đều đọc nó. Đồ thị nằm riêng, dùng để tra lại sau và để chạy
    kiểm mà không phải gọi model lần nữa. Đổi định dạng .txt thì phải sửa
    năm chỗ khác, không đáng.
    """
    path.write_text(json.dumps(
        {"topic": topic, "scenes": [g.to_dict() for g in graphs]},
        ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path) -> list[SceneGraph]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for s in data.get("scenes", []):
        g = SceneGraph(subject=s.get("subject", ""),
                       action=s.get("action", ""),
                       objects=list(s.get("objects", [])))
        g.relations = [Relation(**r) for r in s.get("relations", [])]
        out.append(g)
    return out
