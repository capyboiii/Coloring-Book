# Ghi chép — Đổi `subjects` sang model local trong LM Studio

**Ngày:** 2026-08-06
**Nhánh:** `feat/phase-1-pipeline`
**Thay thế:** bản gọi API Claude viết trước đó trong cùng ngày

---

## Vì sao đổi

Bao đã có LM Studio với Qwen3.5 9B chạy sẵn trên máy. Gọi API hãng nghĩa là
phải giữ một API key, tốn tiền mỗi lần gọi, và phải có mạng — trong khi cả
phần còn lại của studio chạy hoàn toàn offline.

Sinh 24 dòng mô tả không phải việc khó. Model 9B làm được, chỉ cần chỉ dẫn
chặt hơn và lọc kỹ hơn.

Sau khi đổi, **toàn bộ studio chạy offline**. Không API key nào, không tốn xu
nào, không có gì rời khỏi máy.

---

## LM Studio nói chuyện thế nào

API tương thích OpenAI ở `http://localhost:1234/v1`:

```
GET  /v1/models             xem model nào đang nạp
POST /v1/chat/completions   giống hệt OpenAI
```

Không cần API key. Bật server ở tab **Developer → Start Server**.

---

## Ba chỗ phải xử thêm mà gọi API hãng không gặp

Đây là phần đáng ghi lại. Model 9B không phải model đám mây thu nhỏ — nó hỏng
theo những cách khác.

### 1. Chỉ dẫn phải viết bằng tiếng Anh

Bản gọi Claude viết chỉ dẫn bằng tiếng Việt, chạy tốt. Với model 9B thì không:
nó bám chỉ dẫn tiếng Anh chặt hơn tiếng Việt rõ rệt, mà đầu ra vốn cũng phải
là tiếng Anh.

Chủ đề đầu vào vẫn để tiếng Việt được — Qwen hiểu đủ để nắm ý.

Chỉ dẫn cũng viết lại thành gạch đầu dòng ngắn, mệnh lệnh, thay vì văn xuôi.
Thêm mục `OUTPUT FORMAT` nói thẳng "không đánh số, không gạch đầu dòng, không
giải thích" — model nhỏ cần được dặn rõ ràng hơn.

### 2. Cắt khối `<think>`

Qwen3 có chế độ suy luận, nhả ra nguyên khối `<think>...</think>` trước câu
trả lời. Không cắt là cả đoạn lảm nhảm lọt thẳng vào file theme.

```python
def strip_thinking(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL|re.I)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL|re.I)   # bị cụt token
    return text.strip()
```

Dòng thứ hai xử trường hợp model bị cắt token giữa chừng: có thẻ mở mà không
có thẻ đóng. Không có dòng này thì regex đầu không khớp và toàn bộ phần suy
nghĩ lọt qua.

### 3. Vòng xin thêm cho đủ số

Model nhỏ hiếm khi ra đủ 24 dòng trong một lần — nó dừng sớm, hoặc lặp lại
cảnh đã viết.

Thêm vòng gọi tối đa 3 lần. Từ lần thứ hai, prompt kèm theo **danh sách đã
có** và yêu cầu viết những cảnh khác hẳn. Dừng sớm nếu một vòng không thêm
được cảnh mới nào — nghĩa là model đã cạn ý, gọi thêm chỉ tốn thời gian.

### Lọc thêm: câu dẫn

Model nhỏ hay chèn `Here are the scenes:` hoặc `Sure! Below are...`. Thêm bộ
lọc bỏ dòng bắt đầu bằng here/below/these/sure/okay/scene/output **mà không có
dấu phẩy** — điều kiện dấu phẩy để không bỏ nhầm một cảnh thật bắt đầu bằng
"Below the surface, ...".

---

## Thay đổi khác

- `--list-models` xem LM Studio đang nạp gì
- `--temperature` (mặc định 0.85) — cao thì đa dạng hơn nhưng dễ lạc đề
- `--model` chọn model cụ thể; để trống thì **tự lấy model đầu tiên đang nạp**
- Timeout nâng lên 600s: model chạy máy nhà chậm hơn API hãng nhiều
- `doctor` liệt kê model LM Studio đang nạp, và nói rõ đây là **tuỳ chọn** —
  không kết nối được thì mọi lệnh khác vẫn chạy bình thường
- `.env.example`: bỏ `ANTHROPIC_API_KEY`, thêm `LMSTUDIO_URL`

---

## Kiểm thử

Mục `[7]` viết lại cho đúng loại rác model 9B trả về — giờ có cả khối `<think>`
và câu dẫn:

```
<think>
The user wants ocean scenes. Let me think about what to include.
</think>
Here are the scenes:
```
1. a smiling sea turtle swimming through a coral reef, ...
- a smiling sea turtle swimming through a coral reef, ...      ← trùng
* con cá heo nhảy trên sóng, chim biển bay phía trên           ← tiếng Việt
jellyfish                                                       ← cụt lủn
```
```

Có kiểm thử riêng cho `<think>` bị cụt token — lỗi này dễ bỏ sót nhất vì nó
chỉ xảy ra khi model chạm giới hạn token.

Vẫn **không cần LM Studio đang chạy** để chạy test: phần lọc tách hẳn khỏi
phần gọi mạng. 37/37 đạt.

---

## Việc tiếp theo cho Bao

1. Bật LM Studio → tab **Developer** → nạp Qwen3.5 9B → **Start Server**
2. Kiểm tra:

```bash
python studio.py subjects --list-models
python studio.py doctor
```

3. Thử một chủ đề, xem trước đã:

```bash
python studio.py subjects "Giáng sinh" --count 24 --audience kids --dry-run
```

Đọc 24 dòng đó. Nếu nhiều dòng cụt lủn hoặc lặp ý, thử theo thứ tự:

1. `--temperature 1.0` cho đa dạng hơn
2. `--count 12` chạy hai lần rồi ghép tay — model nhỏ làm ít thì chắc tay hơn
3. Nạp model to hơn nếu máy chịu được

---

## Nguồn

- [LM Studio — OpenAI Compatibility Endpoints](https://lmstudio.ai/docs/developer/openai-compat)
- [LM Studio — as a Local LLM API Server](https://lmstudio.ai/docs/developer/core/server)
