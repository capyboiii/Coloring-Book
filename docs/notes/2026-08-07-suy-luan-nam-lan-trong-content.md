# Ghi chép — "Tắt reasoning" chỉ tắt việc tách trường

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`
**Tiếp theo:** [bỏ tính năng vớt](2026-08-07-vot-rac-tu-suy-nghi.md)

---

## Phát hiện

Bao tắt reasoning trong LM Studio rồi chạy lệnh kiểm tra:

```
content: 'Thinking Process:\n\n1.  **Analyze the Request:**\n    *   Task: Say hello...'
reasoning: 0 ky tu
```

`reasoning_content` **rỗng thật** — nhưng phần suy nghĩ vẫn còn nguyên, chỉ là
nó chuyển vào `content`.

Tắt Reasoning trong LM Studio làm nó **ngừng TÁCH TRƯỜNG**, chứ mô hình vẫn
suy luận y như cũ.

Hậu quả: chốt chặn tôi thêm hôm qua (`content` rỗng thì báo lỗi) không bao giờ
chạy, vì `content` không rỗng — nó đầy ắp ghi chú. Lệnh chạy trọn 6 mẻ, mất
hơn 10 phút, rồi ghi ra 24 dòng mà phần lớn là chỉ dẫn của tôi bị nhại lại.

---

## Sửa: chặn sớm

Thêm `looks_like_reasoning()` dò các dấu hiệu ở 400 ký tự đầu:
`thinking process`, `analyze the request`, `deconstruct the`, `let me think`,
`drafting scenes`, `constraint checklist`.

Phát hiện ở **mẻ đầu** thì dừng luôn, kèm chẩn đoán và lời khuyên đổi model.
Không có chốt này thì phải grind 6 mẻ mới biết hỏng.

---

## Sửa: lọc theo hình dạng câu

Bỏ cách dò danh sách từ khoá — nó luôn thiếu. Dùng đặc điểm cấu trúc:

| Luật | Bắt được |
|---|---|
| Có `:` ở bất kỳ đâu | `Formula:` `Draft:` `Wait, re-reading the end of the prompt:` |
| Có `"` | `Content only (no "line art", "black and white", etc.)` |
| Có `*` (sau khi cắt gạch đầu dòng) | `**Task:**` `*Idea 1:*` |
| Có `+` | `subject + action + 2-3 other things` |
| Dưới 6 từ | `jellyfish` `No copyrighted characters` |
| **Chữ hoa ở đầu dòng** | `One sentence per line...` `All 8 scenes...` `Only drawable...` |

Luật cuối là luật mạnh nhất, và nó đến từ một thay đổi ở prompt: thêm dòng
`Start every line with a lowercase letter.` vào `OUTPUT FORMAT`. Cảnh thì viết
thường, ghi chú thì luôn viết hoa. Tách được rác mà không cần đặt ngưỡng độ
dài — vốn đã chứng minh là hỏng, xem dưới.

---

## Hai lần tự bắn vào chân, cả hai đều do test bắt

### Lần 1: lọc theo hình dạng của RÁC thay vì của CẢNH

Ban đầu tôi đặt ngưỡng `>=12 từ` và `>=2 dấu phẩy`, vì mọi dòng rác trong log
đều ngắn và ít phẩy. Chạy thử trên chính `themes/` tự viết tay:

```
ocean            24/24 qua duoc bo loc
mandala           0/24 qua duoc bo loc      ← xoá sạch
floral           19/24 qua duoc bo loc
forest-animals   24/24 qua duoc bo loc
```

`"a lotus mandala with eight large petals"` — 7 từ, 0 dấu phẩy — là một dòng
hoàn toàn hợp lệ. Mandala vốn là một chủ thể đối xứng, không phải cảnh nhiều
lớp.

Hạ xuống `>=6 từ`, bỏ hẳn ngưỡng dấu phẩy. Và thêm **kiểm thử hồi quy: mọi
file trong `themes/` phải qua bộ lọc nguyên vẹn**. Bộ lọc mà loại nội dung do
chính mình viết ra thì nó đang lọc sai thứ.

*(Một dòng có sửa thật: `"a peacock feather mandala"` — 4 từ, quá mỏng. Sửa
nội dung chứ không nới bộ lọc.)*

### Lần 2: ngưỡng 30% làm luật viết hoa im lặng ở đúng lúc cần nhất

Luật chữ hoa lúc đầu chỉ chạy nếu `>=30%` số dòng viết thường — để phòng
trường hợp mô hình phớt lờ luật viết thường và bị xoá sạch.

Test cho mẻ có 1 cảnh thật lẫn trong 3 dòng ghi chú: tỉ lệ 25%, luật không
chạy, 3 dòng rác lọt qua. Đúng lúc cần nhất thì nó im.

Đổi thành: **áp dụng luôn, nhưng nếu xoá hết thì trả lại nguyên trạng kèm cảnh
báo.** Vừa bắt được rác lẫn trong ít cảnh thật, vừa không xoá sạch khi mô hình
không tuân thủ.

---

## Kết quả

Rác thật lấy từ log của Bao, 9 dòng vào — 2 dòng ra, đúng 2 cảnh thật:

```
+ a cheerful snowman wearing a striped scarf, two children rolling
  snowballs beside him, pine trees filling the background
+ a lotus mandala with eight large petals
```

Và cả 96 dòng trong `themes/` đều qua nguyên vẹn.

Smoke test 43/43 đạt.

---

## Lời khuyên thật cho Bao

Mọi thứ ở trên chỉ là **chống đỡ**. Gốc rễ là dùng sai công cụ.

Việc này chỉ là **viết 24 câu tiếng Anh**. Một model instruct 7-8B làm trong
vài giây. Model suy luận mất 5 phút mỗi mẻ, và ra kết quả *tệ hơn* vì nó dành
phần lớn công sức để tranh luận với chính prompt.

Nạp một trong mấy model này rồi chạy lại:

- **Qwen2.5-7B-Instruct**
- **Llama-3.1-8B-Instruct**
- **Mistral-7B-Instruct**

Nếu vẫn muốn giữ Qwen3.5 9B: `--think --max-tokens 8000 --batch 4` để nó suy
luận xong hẳn rồi mới trả lời. Chậm nhưng ra kết quả sạch.
