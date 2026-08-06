# Phase 2 — Rút ngắn bước Duyệt

**Thời gian:** 2 ngày
**Mục tiêu:** 2 giờ → 30 phút mỗi cuốn

Bước tốn sức nhất, cũng là bước dễ tối ưu nhất.

> Chỉ bắt đầu phase này sau khi đã có số liệu thật từ Phase 1. Nếu duyệt tay chỉ mất 40 phút thì hãy làm Phase 3 trước.

---

## Việc cần làm

### A. Lọc tự động trước khi ông nhìn
- [ ] Loại ảnh có `ink_ratio < 0.5%` — gần như trang trắng
- [ ] Loại ảnh có `ink_ratio > 40%` — trang đen kịt, thường do threshold sai
- [ ] Ghi log số ảnh bị loại tự động

Hai bộ lọc này thường bỏ được 10–15% mà không cần ông xem.

### B. Màn hình duyệt
Trang HTML tĩnh đọc thư mục ảnh, không cần server.

- [ ] Lưới ảnh, xem lớn khi hover hoặc bấm
- [ ] Phím tắt: `A` giữ · `D` bỏ · `R` đánh dấu vẽ lại · `←/→` di chuyển
- [ ] Thanh tiến độ "đã duyệt 23/40"
- [ ] Hoàn tác thao tác vừa rồi (`Ctrl+Z`)
- [ ] Xuất `approved.json` để `studio.py build` đọc

### C. Vẽ lại hàng loạt
- [ ] `studio.py regenerate <slug>` — vẽ lại các ảnh đã đánh dấu `R`, giữ nguyên prompt, đổi seed

---

## Vì sao đáng làm sớm

Ông sẽ duyệt **hàng nghìn ảnh** trong năm đầu. Tiết kiệm 1.5h mỗi cuốn, ra 4 cuốn/tháng là **72 giờ một năm**.

---

## Định nghĩa "xong"

Duyệt 40 ảnh trong dưới 10 phút, không phải rời tay khỏi bàn phím.
