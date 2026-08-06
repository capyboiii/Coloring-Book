# Phase 5 — Ra tiền thật

**Thời gian:** 2–3 tuần
**Mục tiêu:** từ demo thành cửa hàng có doanh thu

Làm theo đúng thứ tự này. Mỗi mục sau chỉ đáng làm khi mục trước đã chạy.

---

## 1. Thanh toán — Stripe
- [ ] Stripe Checkout, chế độ test trước
- [ ] Webhook xác nhận thanh toán → mới phát link tải
- [ ] Hóa đơn gửi qua email
- [ ] Chuyển sang chế độ live

**Bán được tiền trước, mọi thứ khác sau.** Không có bước này thì các bước dưới không có ý nghĩa.

## 2. Bảo vệ nội dung
- [ ] Nhúng watermark mờ mang email người mua vào `interior.pdf`
- [ ] Link tải hết hạn, giới hạn lượt

Không chống được sao chép — hàng số luôn bị sao chép. Nhưng nó ngăn phát tán hàng loạt, vì file rò rỉ truy được về người mua.

## 3. Lulu — thêm sách in
- [ ] Đăng ký sandbox: https://developers.sandbox.lulu.com/
- [ ] Cache token OAuth (token có hạn, đừng gọi lại mỗi request)
- [ ] `POST /validate-interior/` → poll tới `VALIDATED`/`NORMALIZED`
- [ ] `POST /print-job-cover-dimensions/` → kích thước bìa theo số trang
- [ ] Dựng PDF bìa đúng kích thước → `POST /validate-cover/`
- [ ] `POST /print-jobs/` → theo dõi trạng thái
- [ ] Chuyển sang production

**Sản phẩm:** `0850X1100.BW.STD.SS.060UW444.MXX`
8.5×11" · đen trắng · đóng ghim · giấy trắng 60# · bìa matte

⚠️ Dùng định dạng có dấu chấm. Định dạng cũ 27 ký tự ngừng hỗ trợ **1/2/2027**.
⚠️ `shipping_address` bắt buộc có số điện thoại.
⚠️ Lulu tải file từ **URL công khai** — bucket phải cho phép, hoặc dùng link ký hạn dài.

**Bán kèm:** mua sách in tặng PDF giảm 50%. Chi phí biên bằng 0, biên lợi nhuận rất tốt. Crayonahub làm đúng cách này.

## 4. Email marketing
- [ ] Bản tin hàng tuần cho danh sách thu ở Phase 4
- [ ] Thông báo sách mới
- [ ] Mã giảm giá cho lần mua đầu

## 5. Đo lường
- [ ] Cuốn nào bán chạy
- [ ] Chủ đề nào hút lưu lượng
- [ ] Tỷ lệ xem trước → mua

Số liệu này quyết định ông sản xuất gì tiếp. Không có nó, ông đoán mò.

---

## Định nghĩa "xong"

Một người lạ, không quen ông, trả tiền thật và nhận được sách.
