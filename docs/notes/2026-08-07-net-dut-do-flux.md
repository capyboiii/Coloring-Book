# Ghi chép — Nét đứt là do Flux, không phải do phóng to

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`
**Câu hỏi của Bao:** *"mấy nét không liền, nét đứt là do Flux vẽ hay do mày kéo
to hơn rồi bị?"*

---

## Trả lời: do Flux

Đo cùng một ảnh ở ba giai đoạn:

| Giai đoạn | Mảnh rời | Đầu mút | Dày TB |
|---|---|---|---|
| 1. Flux gốc, đúng pixel gốc 1392, chưa đụng tới | 75 | **31** | 6.2 px |
| 2. Chỉ phóng to lên 2625 | 73 | 12 | 9.6 px |
| 3. Sau cả đường ống | 83 | 0 | 12.4 px |

**Ngay ở ảnh gốc đã có 31 đầu mút và 75 mảnh rời.** Phóng to không tạo thêm
chỗ đứt nào — số mảnh còn giảm nhẹ.

Nhìn ảnh phóng 3× thì càng rõ: đám mây trong ảnh gốc đã đứt khúc và xám nhạt
sẵn, khâu xử lý chỉ làm nó dày hơn chứ không tạo ra chỗ đứt.

---

## Và chỉ số của tôi đang nói dối

Bảng trên có chỗ đáng ngờ: đầu mút **31 → 0**, nghe như đã vá xong hết.

Nhưng nhìn ảnh thì khe hở vẫn còn nguyên.

Lý do: tôi đếm đầu mút bằng "pixel chỉ có 1 hàng xóm". Sau khi giãn nét thì
đầu mút cụt đi, có nhiều hàng xóm hơn, nên **không đếm được nữa** — dù khe hở
chẳng đi đâu cả.

Chỉ số đúng là **số mảnh rời**, và nó nói 75 → 83. Tức khâu xử lý của tôi
**không nối được gì**.

Bài học: chỉ số nào cũng phải đối chiếu với mắt trước khi tin. Cái đầu mút đã
suýt làm tôi kết luận "đã sửa xong" trong khi chưa sửa được gì.

---

## Sửa gì

### `CLOSE_GAPS` 3 → 9

Đóng 3 px chỉ nối được khe rộng ~2 px, trong khi khe của Flux rộng hơn nhiều.

| `CLOSE_GAPS` | Mảnh rời |
|---|---|
| 3 | 83 |
| 9 | **42** |
| 15 | 33 |

Chọn 9. Lớn hơn 13 thì chi tiết nhỏ bắt đầu dính vào nhau.

### `LEVELS_BLACK` 80 → 170 — đây mới là chỗ ăn tiền

Trong lúc đo, phát hiện một vấn đề riêng mà Bao mô tả là *"nét không đồng
đều"*: Flux vẽ **nét chính đen đậm, nét nền xám nhạt**.

Đo ra: **17.7% pixel mực nằm ở vùng xám 100–200**. Gần một phần năm số nét sẽ
in ra nhạt hơn phần còn lại.

Ngưỡng cũ là 80, nghĩa là chỉ pixel tối hơn 80 mới thành đen tuyền. Nét xám
150 vẫn ra xám 150 — in xong nhìn như bị mờ.

Đặt 170 thì mọi thứ tối hơn 170 đều thành đen tuyền. Đo lại: **17.7% → 5.4%**.

Nhìn ảnh so sánh thì đây là thay đổi thấy rõ nhất bằng mắt: từ nét xám nhạt
thành nét đen đặc và đều.

### `LINE_THICKEN` 3 → 0

`CLOSE_GAPS = 9` đã làm dày nét sẵn rồi. Bật thêm nữa thì nét lên 16–20 px,
chi tiết nhỏ bắt đầu bít lại. Vẫn giữ làm nút vặn cho sách bé 3 tuổi.

---

## Kết quả trên 4 ảnh thật

| Ảnh | Mảnh rời | Dày | Nét xám |
|---|---|---|---|
| 001 | 9 | 12.8 px | 6.9% |
| 002 | 23 | 9.8 px | 9.0% |
| 003 | 125 | 10.3 px | 8.3% |
| 004 | **42** (trước 83) | **14.3 px** | **5.4%** (trước 17.7%) |

Ảnh 003 có 125 mảnh vì nó vốn nhiều chi tiết nhỏ — đúng loại trang mà phần
sửa prompt hôm nay nhắm tới.

---

## Thứ vẫn chưa sửa được

Khe hở **lớn** thì đóng 9 px vẫn không nối nổi — nhìn ảnh so sánh, đường viền
dưới của đám mây vẫn đứt thành nét gạch.

Chỗ đó phải sửa ở khâu sinh ảnh, không phải khâu xử lý:

- Nâng số bước sinh (`STUDIO_STEPS`) từ 4 lên 6–8. Schnell chịu được, và
  nhiều bước hơn thì nét dứt khoát hơn.
- Hoặc đổi sang model line art chuyên dụng nếu sau này có.

Nhưng nét xám thì đã sửa xong, và đó là phần chiếm phần lớn cảm giác "nét
không đồng đều".

---

## Kiểm thử

Mục `[14]` viết lại — **đo kết quả ra, không kiểm tra cờ bật**:

```
✓ Có nối khe hở đủ rộng (Flux vẽ đứt sẵn từ ảnh gốc) — 9px
✓ Ngưỡng đen đủ cao để nét xám thành đen tuyền — 170
✓ Nét sau xử lý dày 6-18 px @300dpi — 7.3 px
✓ Dưới 10% pixel mực còn xám nhạt — 6.3%
```

Mục cuối là kiểm thử hồi quy cho đúng lỗi nét xám ở trên.

113/113 đạt.

---

## Việc tiếp theo cho Bao

Ảnh cũ vẫn dùng được — thay đổi nằm ở khâu **xử lý**, không phải khâu sinh.
Chạy lại `build` là ảnh cũ cũng được hưởng:

```bash
python studio.py make khung-long-cua-be --minutes <số phút>
```

Mở `interior.pdf` phóng 100%, nét phải đen đặc và đều, không còn chỗ xám nhạt.

Nếu vẫn thấy đứt ở đường dài, thử nâng số bước sinh:

```
STUDIO_STEPS=8
```

trong `.env` rồi gen lại. Chậm hơn nhưng nét dứt khoát hơn.
