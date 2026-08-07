# Ghi chép — Qwen đốt sạch token vào suy luận, trả về rỗng

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`
**Triệu chứng:** `LỖI: Không lọc được cảnh nào` sau hơn 10 phút chờ

---

## Log nói gì

```json
"content": ""
"reasoning_content": "Thinking Process: ... Count: A(1) happy(2) Santa(3) Claus(4) waving(5) ..."
"finish_reason": "length"
"reasoning_tokens": 3999          // trên tổng 4000
"eval time": 315275 ms            // 5 phút 15 giây
```

Model **không hề trả lời**. Nó viết 24 cảnh trong đầu, rồi ngồi **đếm từ từng
chữ một** để kiểm luật *"mỗi dòng 15-30 từ"*:

```
Count: A(1) happy(2) Santa(3) Claus(4) waving(5) from(6) a(7) sleigh,(8)
three(9) red(10) bags(11) hanging(12) below,(13) ... -> 21 words. OK.
```

Làm vậy 19 lần thì hết 4000 token. `finish_reason: "length"`. Trường `content`
rỗng. Rồi vòng xin thêm gọi lại lần nữa — lại 5 phút, lại rỗng.

---

## Ba lỗi, một trong đó là của tôi

### 1. Luật đếm từ tự gây ra vòng đếm — lỗi thiết kế prompt

Tôi viết `Each line must be 15 to 30 words and must contain commas.`

Với model đám mây, luật này vô hại. Với model có chế độ suy luận, nó là mệnh
lệnh đi **kiểm tra** — và cách duy nhất để kiểm là đếm. Model làm đúng như
được bảo, chỉ là làm tới mức tự sát.

Sửa:

```diff
- Each line must be 15 to 30 words and must contain commas.
+ Write each line as one sentence of about twenty words, using commas to
+ separate the parts. Do not count the words.
```

Thêm dòng cuối chỉ dẫn: `Write the lines directly. Do not plan, do not draft,
do not check your work.`

Bài học: **đừng đặt ràng buộc mà mô hình phải đi kiểm chứng** khi mô hình đó
có chế độ suy luận. Ràng buộc kiểm được thì mình kiểm ở phía code (và
`clean_lines` vốn đã kiểm rồi), đừng bắt mô hình tự kiểm.

### 2. `strip_thinking()` không bao giờ chạy

Tôi viết hàm cắt `<think>...</think>` dựa trên giả định của mình về Qwen.

Nhưng **LM Studio tách phần suy nghĩ ra trường riêng** `reasoning_content`.
Trường `content` rỗng hoàn toàn. Regex của tôi chạy trên chuỗi rỗng, không cắt
gì cả, và mọi thứ vẫn hỏng.

Đây là lỗi kinh điển: viết hàm xử lý cho một định dạng chưa từng nhìn thấy
thật. Giữ `strip_thinking` lại (vẫn có server nhúng inline), nhưng thêm:

```python
if not content:
    reasoning = message.get("reasoning_content", "").strip()
    if reasoning:
        warn("suy luận chạy tràn hết token — đang vớt cảnh từ phần suy nghĩ")
        content = reasoning
```

Vớt được thật: trong log hỏng có sẵn 19 cảnh hoàn chỉnh nằm trong
`reasoning_content`. Mất trắng cả lượt chỉ vì đọc nhầm trường thì quá phí.

### 3. Không tắt suy luận ngay từ đầu

Gửi cả hai cách cùng lúc, vì tuỳ phiên bản mà cách nào ăn:

- `chat_template_kwargs: {"enable_thinking": false}` — llama.cpp / LM Studio
- hậu tố `/no_think` trong prompt — công tắc riêng của Qwen3

Máy chủ cũ không biết `chat_template_kwargs` sẽ trả HTTP 400; lúc đó bỏ trường
đó ra gọi lại, vẫn còn `/no_think` đỡ đòn.

---

## Thêm: chia nhỏ mẻ

Đòi 24 cảnh một lúc là yêu cầu nặng với model 9B. Đổi sang hỏi **8 cảnh mỗi
mẻ**, 3 mẻ là đủ 24.

Ba cái lợi:

- Yêu cầu ngắn → model nhỏ làm chắc tay hơn hẳn
- Một mẻ hỏng chỉ mất mẻ đó, không mất cả lượt
- `max_tokens` tính theo mẻ (`ask * 120 + 500`) thay vì cố định 4000

Từ mẻ thứ hai, prompt kèm **12 cảnh gần nhất** để tránh lặp. Chỉ 12 chứ không
phải tất cả — prompt dài làm model nhỏ lú thêm.

Có `on_progress` in ra `mẻ 2: đã có 8/24, xin thêm 8...` để không phải ngồi
nhìn màn hình đứng im 5 phút.

---

## Sửa thêm khi test

Chạy thử với server giả thì lọt dòng `Thinking Process:`.

Bộ lọc câu dẫn cũ dò danh sách từ khoá `here|below|these|sure|okay|scene|output`
— `Thinking` không có trong danh sách. Danh sách từ khoá luôn thiếu.

Thay bằng luật tổng quát: **bỏ mọi dòng kết thúc bằng `:`**. Tiêu đề và câu dẫn
luôn kết thúc bằng dấu hai chấm; một cảnh thì không bao giờ.

Cộng thêm: bỏ hẳn dòng dưới 6 từ thay vì chỉ cảnh báo. Rác kiểu `jellyfish`
lọt vào file theme là sinh ra một trang hỏng.

---

## Kiểm thử

Viết một **server LM Studio giả** để chạy end-to-end mà không cần model thật.
Nó tái hiện đúng kiểu hỏng ở trên: mẻ đầu trả `content` rỗng kèm
`reasoning_content`, các mẻ sau trả bình thường. Server giả cũng **khẳng định**
request có `/no_think` và `enable_thinking: false`.

Kết quả: 24/24 cảnh, mẻ đầu vớt từ `reasoning_content`, `Thinking Process:` bị
loại, cảnh báo hiện đủ.

Smoke test thêm hai mục cho luật `:` và luật 6 từ. 38/38 đạt.

---

## Việc tiếp theo cho Bao

```bash
python studio.py subjects "Giáng sinh" --count 24 --audience kids --dry-run
```

Giờ sẽ thấy tiến độ từng mẻ. Nhanh hơn nhiều vì không còn suy luận.

**Nên làm thêm:** tắt Reasoning thẳng trong LM Studio (cột cấu hình model bên
phải). Tắt ở nguồn chắc ăn hơn là gửi cờ qua API.

Vẫn hỏng thì theo thứ tự: `--batch 4` → `--max-tokens 8000` → nạp bản
**Instruct** thay vì bản có suy luận.
