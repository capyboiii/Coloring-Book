# Phase 1 — Đường ống mỏng

**Thời gian:** 4–5 ngày
**Mục tiêu:** đi hết cả 5 bước và bán được **một** cuốn sách. Chấp nhận làm tay.

> Đừng xây công cụ ở phase này. Chỉ xây phần không thể làm tay.

---

## Quy trình sau Phase 1

| Bước | Cách làm | Thời gian |
|---|---|---|
| ① Tạo | `studio.py generate` | 1.5h |
| ② Duyệt | File Explorer, xóa tay | 2h |
| ③ Dựng | `studio.py build` | 1.5h |
| ④ Đăng | Sửa `books.yaml` + chạy đồng bộ | 1h |
| ⑤ Bán | Web tối giản | tự động |

---

## Việc cần làm

### A. Studio — dọn lại code đã có
Code ở nhánh `feat/phase-1-pipeline` dùng lại gần hết, chỉ đổi vai trò.

- [ ] Gộp `feat/phase-1-pipeline` vào nhánh làm việc
- [ ] Đổi `cli.py` thành `studio.py` với hai lệnh con: `generate`, `build`
- [ ] `generate <chủ đề> --count 40` → lưu vào `library/<slug>/raw/`
- [ ] Ghi `meta.json` mỗi ảnh: prompt, seed, chủ đề, ngày sinh
- [ ] `build <slug>` đọc `library/<slug>/approved/` → `interior.pdf`
- [ ] Sinh `preview.pdf`: 3 trang đầu, có watermark
- [ ] Sinh ảnh xem trước `.webp` hạ độ phân giải cho web

### B. Sinh bìa (làm tay ở phase này)
- [ ] Prompt bìa màu bằng Flux (bỏ ràng buộc line art)
- [ ] Ghép chữ tiêu đề bằng Canva hoặc Photoshop — **không để Flux viết chữ**

### C. Storefront tối giản (NestJS) — phần xây mới
- [ ] `GET /api/books` — danh sách
- [ ] `GET /api/books/:slug` — chi tiết + ảnh xem trước
- [ ] `POST /api/orders` — `{ bookSlug, email }` → trả link tải
- [ ] `GET /api/download/:token` — link ký, hết hạn 24h, tối đa 5 lượt
- [ ] Postgres: bảng `books`, `orders`
- [ ] Lệnh đồng bộ: đọc `books.yaml` → ghi vào Postgres + upload R2

### D. Frontend — 3 trang
- [ ] Danh sách sách (lưới bìa)
- [ ] Chi tiết sách (bìa lớn, 3–5 trang mẫu, nút nhận PDF)
- [ ] Nhận sách (nhập email → hiện link tải)

Chưa cần đẹp. Cần chạy được.

---

## Bẫy cần tránh

⚠️ **`interior.pdf` không bao giờ để public.** Bucket R2 để private, chỉ phát qua token đã ký. Sai chỗ này là mất trắng sản phẩm — người ta đoán được URL là tải hết.

⚠️ **Đừng xây công cụ duyệt ở phase này.** Làm tay 40 ảnh để biết nó thực sự tốn bao lâu. Con số đó quyết định Phase 2 nên làm gì.

⚠️ **Đừng làm nhiều hơn một cuốn.** Mục tiêu là chạy thông đường ống, không phải lấp đầy catalog.

---

## Định nghĩa "xong"

Ông gửi link cho một người bạn. Họ mở web, chọn sách, nhập email, tải được PDF về máy và mở ra xem được.

## Số liệu phải ghi lại

Hai con số này định hình toàn bộ các phase sau:

- [ ] **Tỷ lệ giữ lại:** duyệt 40 ảnh, giữ được bao nhiêu? (dự đoán 40–60%)
- [ ] **Thời gian duyệt:** bấm giờ thật, từ lúc mở thư mục tới lúc xong
