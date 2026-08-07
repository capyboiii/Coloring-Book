# Ghi chép — Bỏ tính năng "vớt", vì chính nó gây nhiễm bẩn

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`
**Tiếp theo:** [suy luận đốt hết token](2026-08-07-suy-luan-dot-het-token.md)

---

## Chuyện gì xảy ra

Sau lần sửa trước, `subjects` chạy tới cùng và trả về "23/24 cảnh". Nhìn có
vẻ gần thành công. Thực ra phần lớn 23 dòng đó là rác:

```
1. **Task:** Write page descriptions for a printed coloring book
2. **Audience:** Children aged 4 to 8 (cheerful, cute, easy to recognise)
3. **Format:** One scene per line. Plain text only. No numbering...
```

Đây là **prompt của tôi bị nhại lại**, được ghi vào như thể là nội dung sách.

---

## Vòng lặp tự nhiễm bẩn

Đây là phần đáng ghi lại nhất, vì nó do **tính năng tôi thêm vào để phòng thủ**
gây ra.

```
suy luận vẫn bật (cờ API không ăn)
        ↓
content rỗng, mọi thứ nằm trong reasoning_content
        ↓
tính năng "vớt" đọc reasoning_content        ← chỗ tôi làm sai
        ↓
lần này mô hình bị cắt TRƯỚC lúc kịp viết cảnh
→ vớt về toàn ghi chú kế hoạch, không phải cảnh
        ↓
ghi chú được lưu vào `collected` như cảnh hợp lệ
        ↓
vòng sau đưa 12 "cảnh" gần nhất vào prompt làm danh sách "đã viết"
        ↓
prompt giờ chứa mảnh vụn chính nó, với số đếm khác nhau (8, 6, 1)
        ↓
mô hình đọc thấy mâu thuẫn, đốt cả 4000 token để phân vân
```

Nguyên văn mô hình ở mẻ 5:

> *"**Critical Conflict:** The initial instruction says 6. The later
> instruction block says 8... **Decision:** The final instruction usually
> supersedes. However, the OUTPUT FORMAT constraint is quite rigid..."*

Nó dành trọn một lượt gọi để tranh luận với chính prompt của mình.

**Bài học:** tính năng cứu vãn chỉ đúng khi *biết chắc* thứ cứu được là hợp lệ.
Ở đây tôi cứu mù, và biến một thất bại sạch — báo lỗi rồi dừng — thành nhiễm
bẩn âm thầm chảy ngược vào vòng sau. Hỏng to bao giờ cũng hơn hỏng lặng lẽ.

---

## Đã sửa

### 1. Bỏ hẳn phần vớt, đổi thành báo lỗi

```python
if not content:
    reasoning = message.get("reasoning_content", "").strip()
    if reasoning:
        raise LLMError(
            "Mô hình chỉ suy luận mà không trả lời...\n"
            "  · LM Studio → cột cấu hình model → tắt Reasoning\n"
            "  · hoặc đặt system prompt của model thành: /no_think\n"
            "  · hoặc nạp bản Instruct")
```

Dừng ngay ở mẻ đầu, kèm cách sửa. Không chạy tiếp 5 mẻ để rồi ghi 23 dòng rác.

### 2. `/no_think` chuyển sang system message

Bản trước nối vào **cuối user prompt**. Mô hình đọc thấy nó lẫn trong chỉ dẫn
rồi mang ra bàn luận — nguyên văn: *"Then '/no_think'"*. Thêm nhiễu vào đúng
chỗ cần sạch nhất.

Giờ nó là `{"role": "system", "content": "/no_think"}` — đúng chỗ quy ước, và
không lẫn vào phần nội dung mô hình phải đọc hiểu.

### 3. `TOP_UP` không nhắc lại số lượng

```diff
  {base}
- You already wrote these scenes. Write {count} NEW scenes that are clearly
- different from every one of them:
+ Do not repeat any of these scenes, which already exist:
  {existing}
```

`base` đã là `INSTRUCTIONS` có sẵn "Write exactly N" và "Output exactly N
lines". Nói thêm lần nữa là ba chỗ cùng khai số lượng. Giờ chỉ còn hai chỗ
trong `INSTRUCTIONS`, và luôn cùng một giá trị.

### 4. Bỏ mọi dòng còn sót dấu sao

Prompt bị nhại lại luôn mang markdown nhấn mạnh; một cảnh thật thì không có
dấu sao nào.

Đặt kiểm tra **sau** bước cắt gạch đầu dòng — quan trọng, vì `*Idea 1:* Santa`
sau khi cắt dấu đầu dòng thành `Idea 1:* Santa`, không còn `**` và cũng không
còn bắt đầu bằng `*`. Bản đầu tôi viết `if "**" in line or line.startswith("*")`
và nó lọt. Test bắt được, đổi thành `if "*" in line`.

### 5. Báo cáo từng mẻ

Trả lời luôn câu Bao hỏi: vì sao xin 8 mà chỉ được 6.

```
mẻ 2: đã có 8/24, xin thêm 8...
       xin 8, dùng được 6  (1 trùng, 1 bị loại)
```

Và dừng sớm sau **hai mẻ liên tiếp** không ra cảnh mới — mô hình cạn ý cho chủ
đề đó, gọi tiếp chỉ tốn vài phút chờ.

---

## Kiểm thử

Server LM Studio giả giờ chạy hai kịch bản và **tự khẳng định** cấu trúc request:

```python
assert msgs[0]["role"] == "system" and msgs[0]["content"] == "/no_think"
assert "/no_think" not in user_prompt          # không lẫn vào phần nội dung
counts = set(re.findall(r"exactly (\d+)", user_prompt))
assert len(counts) == 1                        # số đếm không được mâu thuẫn
```

- **Kịch bản A** (suy luận vẫn bật): phải báo lỗi ở mẻ đầu, không ghi gì. ✓
- **Kịch bản B** (đã tắt): chạy trọn 24/24. ✓

Điều kiện `len(counts) == 1` là kiểm thử hồi quy cho đúng lỗi mâu thuẫn số đếm.

Smoke test thêm mục cho luật dấu sao, dùng đúng hai dòng rác từ log thật
(`**Task:**` và `*Idea 1:*`). 39/39 đạt.

Đã rà `themes/*.txt` — không file nào bị nhiễm rác.

---

## Việc tiếp theo cho Bao

```bash
python studio.py subjects "Giáng sinh" --count 24 --audience kids --dry-run
```

Suy luận đã tắt nên sẽ nhanh hơn hẳn và không còn rác. Đọc 24 dòng, sửa dòng
nào không ưng, bỏ `--dry-run` để ghi file.
