# Phase 3 — Tự động Dựng và Đăng

**Thời gian:** 2–3 ngày
**Mục tiêu:** 2.5 giờ → 15 phút mỗi cuốn

---

## Việc cần làm

### A. Một lệnh ra sách
```bash
python studio.py publish dai-duong \
    --title "Đại dương kỳ thú" \
    --subtitle "24 trang tô màu cho bé 3-8 tuổi" \
    --price 79000 \
    --collection for-kids
```

Lệnh này làm hết:

- [ ] Đọc trang đã duyệt từ `approved.json`
- [ ] Dựng `interior.pdf`
- [ ] Sinh bìa màu bằng Flux
- [ ] Ghép chữ tiêu đề lên bìa bằng Pillow
- [ ] Xuất `preview.pdf` có watermark
- [ ] Tạo ảnh xem trước `.webp`
- [ ] Upload toàn bộ lên R2
- [ ] Ghi bản ghi vào Postgres
- [ ] In ra URL trang sách để kiểm tra

### B. Sinh bìa tự động
- [ ] Prompt bìa riêng (bỏ ràng buộc line art, có màu)
- [ ] Ghép tiêu đề bằng Pillow, font đọc từ cấu hình
- [ ] **Không để Flux viết chữ** — nó sai chính tả

### C. Ảnh minh họa đã tô màu ⭐
Đây là phần bán hàng, không phải phần kỹ thuật.

- [ ] Workflow img2img hoặc ControlNet từ chính file line art
- [ ] Giữ nguyên đường nét, chỉ thêm màu
- [ ] Mỗi cuốn ít nhất một ảnh

**Vì sao quan trọng:** khách không mua "hình vẽ trắng đen", họ mua **kết quả sau khi tô**. Trang bán hàng chỉ có line art trắng đen sẽ trông trống trải và khó thuyết phục.

---

## Định nghĩa "xong"

Từ thư mục ảnh đã duyệt tới sách hiện trên web: **một lệnh, dưới 15 phút**.
