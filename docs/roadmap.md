# Coloring Book — Roadmap

Thiết kế quanh **một quy trình duy nhất** mà ông sẽ lặp lại mỗi khi ra sách mới.

---

## Quy trình

```
① TẠO        ②  DUYỆT       ③ DỰNG          ④ ĐĂNG        ⑤ BÁN
chủ đề    →  giữ/bỏ     →  chọn trang   →  lên web   →  khách mua
→ 40 ảnh     → 24 trang    → PDF + bìa      → catalog     → nhận PDF
   (GPU)       (mắt ông)      (tự động)       (1 lệnh)      (tự động)
```

Bước ② là bước duy nhất **bắt buộc có ông**. Bốn bước còn lại phải tiến tới tự động hoàn toàn.

---

## Nguyên tắc chia phase

Không xây từng bộ phận rồi ghép cuối cùng. **Phase 1 chạy trọn cả 5 bước ngay**, dù mọi thứ làm bằng tay. Các phase sau chỉ rút ngắn thời gian.

Lý do: sau Phase 1 ông đã có một cuốn sách bán được thật. Nếu không ai mua, ông biết điều đó sau 5 ngày chứ không phải sau 3 tuần.

**Thước đo xuyên suốt: thời gian ra một cuốn sách.**

| | Sau Phase 1 | Sau Phase 2 | Sau Phase 3 | Sau Phase 4 |
|---|---|---|---|---|
| Tạo | 1.5h | 1.5h | 1.5h | 1.5h |
| Duyệt | 2h | **30ph** | 30ph | 30ph |
| Dựng | 1.5h | 1.5h | **10ph** | 10ph |
| Đăng | 1h | 1h | **5ph** | 5ph |
| **Tổng** | **~6h** | **~4h** | **~2.5h** | **~2.5h** |

---

## Phase 1 — Đường ống mỏng: 1 cuốn sách bán được
**4–5 ngày** · Mục tiêu: đi hết 5 bước, chấp nhận làm tay

Đừng xây công cụ ở phase này. Xây đúng phần không thể làm tay.

| Bước | Cách làm ở Phase 1 | Trạng thái |
|---|---|---|
| ① Tạo | `python studio.py generate "đại dương" --count 40` | Đã có ở nhánh `feat/phase-1-pipeline` |
| ② Duyệt | Mở File Explorer, xóa ảnh xấu bằng tay | Làm tay |
| ③ Dựng | `python studio.py build <slug>` → PDF + preview | Sửa lại từ code cũ |
| ④ Đăng | Sửa file `books.yaml`, chạy lệnh đồng bộ | Làm tay |
| ⑤ Bán | Web tối giản: danh sách → chi tiết → nhập email → link tải | **Xây mới** |

### Phần phải xây mới

**Storefront tối giản (NestJS)**
```
GET  /api/books              danh sách
GET  /api/books/:slug        chi tiết + ảnh xem trước
POST /api/orders             { bookSlug, email } → trả link tải
GET  /api/download/:token    link ký, hết hạn 24h, tối đa 5 lượt
```

**Frontend 3 trang:** danh sách sách → chi tiết sách → nhận link tải.

Chưa cần đẹp. Cần chạy được.

⚠️ **`interior.pdf` không bao giờ để public.** Bucket private, chỉ phát qua token đã ký. Sai chỗ này là mất trắng sản phẩm.

**Xong khi:** ông gửi link cho một người bạn, họ chọn sách, nhập email, tải được PDF về máy.

---

## Phase 2 — Rút ngắn bước Duyệt
**2 ngày** · Từ 2h xuống 30 phút mỗi cuốn

Đây là bước tốn sức nhất và cũng dễ tối ưu nhất.

**Màn hình duyệt** — trang HTML tĩnh đọc thư mục ảnh:

- Lưới ảnh, xem lớn khi hover
- Phím tắt: `A` giữ · `D` bỏ · `R` đánh dấu vẽ lại · `←/→` di chuyển
- Thanh tiến độ "đã duyệt 23/40"
- Xuất ra `approved.json`

Vì sao đáng làm sớm: ông sẽ duyệt **hàng nghìn ảnh** trong năm đầu. Tiết kiệm 1.5h mỗi cuốn, ra 4 cuốn/tháng là 72 giờ một năm.

**Kèm theo — tự động loại ảnh hỏng trước khi ông nhìn:**
- `ink_ratio < 0.5%` → trang gần như trắng
- `ink_ratio > 40%` → trang đen kịt

Hai bộ lọc này thường bỏ được 10–15% số ảnh mà không cần ông xem.

**Xong khi:** duyệt 40 ảnh trong dưới 10 phút.

---

## Phase 3 — Tự động bước Dựng và Đăng
**2–3 ngày** · Từ 2.5h xuống 15 phút mỗi cuốn

**3.1 Một lệnh ra sách**
```bash
python studio.py publish dai-duong --title "Đại dương kỳ thú" --price 79000
```
Lệnh này làm hết: chọn trang đã duyệt → dựng `interior.pdf` → sinh bìa màu → ghép chữ tiêu đề → xuất `preview.pdf` có watermark → tạo ảnh xem trước `.webp` → upload R2 → ghi bản ghi vào Postgres.

**3.2 Sinh bìa**
Flux vẽ bìa màu (bỏ ràng buộc line art), Pillow ghép chữ tiêu đề lên.
**Không để Flux viết chữ** — nó sai chính tả.

**3.3 Ảnh minh họa đã tô màu** ⭐

Đây là phần bán hàng, không phải phần kỹ thuật. Khách không mua "hình trắng đen" — họ mua **kết quả sau khi tô**. Dùng img2img/ControlNet từ chính file line art: giữ nguyên nét, chỉ thêm màu. Mỗi cuốn cần ít nhất một ảnh như vậy.

**Xong khi:** từ thư mục ảnh đã duyệt tới sách hiện trên web, chỉ một lệnh.

---

## Phase 4 — Storefront đúng nghĩa cửa hàng
**3–4 ngày**

| Việc | Ghi chú |
|---|---|
| Bộ sưu tập | Phân theo *khoảnh khắc*: "Thư giãn một mình", "Làm quà tặng", "Cho bé". Không phân theo chủ đề |
| Trang chi tiết | Bìa lớn, lật xem 3–5 trang mẫu, ảnh đã tô màu, độ tuổi, số trang |
| Tải bản xem trước | 3 trang có watermark, tải tự do — để khách thử trước khi mua |
| Thu email | "Trang tô màu miễn phí mỗi tuần". Kênh bán hàng rẻ nhất |
| SEO | Mô hình catalog sống bằng lưu lượng tự nhiên. Không có SEO thì không có khách |
| Trang pháp lý | Điều khoản, hoàn tiền (**hàng số không hoàn**), IP & DMCA |

**Xong khi:** người lạ tìm thấy web qua link, duyệt, tin tưởng, và tải sách.

---

## Phase 5 — Ra tiền thật
**2–3 tuần**

Theo đúng thứ tự này:

1. **Stripe** — bán được tiền trước, mọi thứ khác sau
2. **Watermark mang email người mua** vào PDF — không chống được sao chép, nhưng ngăn phát tán hàng loạt
3. **Lulu in ấn** — thêm sách giấy. Bán kèm PDF giảm 50%: chi phí biên bằng 0, biên lợi nhuận rất tốt
4. **Email marketing** — nuôi danh sách đã thu ở Phase 4
5. **Đo lường** — cuốn nào bán chạy, chủ đề nào hút khách. Số liệu này quyết định ông sản xuất gì tiếp

---

## Tổng thời gian

| Mốc | Cộng dồn |
|---|---|
| Phase 1 — bán được cuốn đầu tiên | **4–5 ngày** |
| Phase 2 | ~1 tuần |
| Phase 3 | ~1.5 tuần |
| Phase 4 — demo hoàn chỉnh | **~2.5 tuần** |
| Phase 5 | +2–3 tuần |

---

## Vì sao thứ tự này

Phase 1 cố tình làm tay ở bốn trên năm bước. Nghe có vẻ lãng phí, nhưng nó cho ông biết **chỗ nào thực sự đau** trước khi xây công cụ.

Rất có thể sau Phase 1 ông sẽ phát hiện bước Duyệt nhanh hơn dự đoán, còn bước sinh bìa mới là chỗ mất thời gian. Lúc đó Phase 2 và 3 đổi chỗ cho nhau — và ông đã tránh được việc xây một công cụ duyệt tinh vi cho vấn đề không tồn tại.

**Việc nên làm ngay:** sinh 40 ảnh một chủ đề, duyệt bằng tay, bấm giờ. Con số đó định hình cả kế hoạch.
