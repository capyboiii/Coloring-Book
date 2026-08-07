# Ghi chép — Lệnh `subjects`: chủ đề bất kỳ

**Ngày:** 2026-08-06
**Nhánh:** `feat/phase-1-pipeline`
**Kích hoạt bởi:** Bao hỏi "muốn gen nhiều chủ đề là phải sửa trực tiếp ở code à"

---

## Khoảng trống cần lấp

Câu trả lời cho câu hỏi trên là **không** — `themes/*.txt` là file văn bản
thuần, thả file mới vào là dùng được, không đụng dòng Python nào.

Nhưng có một khoảng trống thật: **24 dòng đó phải viết tay**, bằng tiếng Anh,
theo đúng công thức "nhân vật + hành động + 2-3 thứ lấp phần còn lại". Khoảng
20–30 phút mỗi chủ đề, và phải viết đúng kiểu thì ảnh mới đẹp.

Nghĩa là đường ống chạy được với mọi chủ đề, nhưng chỉ sau khi người ta bỏ ra
nửa tiếng viết nội dung. Đó là nút thắt.

---

## Đã làm gì

### `studio/llm.py` — gọi Claude

Dùng HTTP thẳng qua `requests` thay vì SDK: `requests` đã là phụ thuộc sẵn,
không phải thêm gói nào.

Prompt gửi đi có 7 quy tắc, trong đó ba cái quan trọng nhất rút từ chính những
lỗi đã gặp mấy hôm nay:

1. **Viết bằng tiếng Anh** — Flux không hiểu tiếng Việt (lỗi mẻ đầu tiên)
2. **Mỗi dòng là một CẢNH, không phải một vật** — kèm ví dụ đúng và ví dụ sai
   (lỗi ảnh con sứa giữa trang trống)
3. **Không dùng nhân vật có bản quyền** — Disney, Pokémon, Sonic. Đây là sách
   để bán.

Cộng thêm: chỉ mô tả nội dung, không nhắc "line art" hay "thick outlines" —
phần phong cách đã có sẵn trong `BASE_STYLE`, nhắc lại chỉ làm loãng prompt.

### `clean_lines()` — lọc kết quả

LLM trả về thứ bừa bộn hơn mình tưởng. Hàm này xử:

| Vấn đề | Xử lý |
|---|---|
| Bọc trong ` ``` ` | Bóc ra |
| Đánh số `1.` `-` `*` dù đã dặn đừng | Cắt bỏ |
| Dòng trùng nhau | Bỏ, có cảnh báo |
| Lọt tiếng Việt | **Bỏ hẳn**, có cảnh báo |
| Dòng cụt lủn không có dấu phẩy | Giữ nhưng cảnh báo — có thể là vật đơn lẻ |
| Dòng dưới 8 từ | Giữ nhưng cảnh báo |
| Ra thiếu so với số yêu cầu | Cảnh báo rõ `chỉ lấy được N/24` |

Tách hàm này khỏi phần gọi mạng để **kiểm thử được mà không cần API key**.

### `studio/commands/subjects.py`

```bash
python studio.py subjects "Giáng sinh" --count 24 --audience kids
# → themes/giang-sinh.txt
```

- `--audience kids|adults|all` đổi cách Claude viết cảnh
- `--dry-run` in ra xem trước, không ghi file
- Chặn ghi đè bộ đã có, trừ khi `--overwrite`
- In toàn bộ 24 cảnh ra màn hình để đọc lướt ngay
- File ghi ra có phần đầu ghi chú: chủ đề, ngày, model, và lệnh dùng tiếp theo

### `doctor` báo trạng thái API key

Không chặn — mọi lệnh khác chạy hoàn toàn offline, chỉ `subjects` cần key.
`doctor` nói rõ điều đó thay vì báo lỗi đỏ làm người ta tưởng hỏng.

---

## Kiểm thử

Thêm mục `[7]` vào smoke test, **không cần API key**. Đưa vào đúng loại rác mà
LLM hay trả về:

```
```
1. a smiling sea turtle swimming through a coral reef, small fish above it...
2. a cluster of jellyfish drifting upward, bubbles around them...
- a smiling sea turtle swimming through a coral reef, small fish above it...   ← trùng
* con cá heo nhảy trên sóng, chim biển bay phía trên                            ← tiếng Việt
jellyfish                                                                        ← cụt lủn
a manta ray gliding over a busy coral reef, tropical fish everywhere...
```
```

Cả 5 mục đạt. Tổng smoke test 35 mục.

---

## Vì sao không tự động hoá thêm nữa

Có thể nối thẳng `subjects` → `generate` thành một lệnh. Cố tình không làm.

Bộ chủ thể là **nội dung cuốn sách**. Đọc lướt 24 dòng mất 1 phút; gen 40 ảnh
mất hàng chục phút GPU rồi mới phát hiện có 6 cảnh nhạt thì đắt hơn nhiều.
Để người đọc qua một lượt là chỗ chặn rẻ nhất trong cả đường ống.

Cùng tinh thần với bước ② duyệt tay: máy làm phần nặng, mắt người chặn phần
mà máy không thấy.

---

## Việc tiếp theo cho Bao

1. Lấy API key ở https://console.anthropic.com/settings/keys
2. Thêm vào `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
3. Thử:

```bash
python studio.py subjects "Giáng sinh" --count 24 --audience kids --dry-run
```

`--dry-run` để xem trước, chưa ghi file. Ưng thì bỏ cờ đó đi.

Vài xu mỗi lần gọi.
