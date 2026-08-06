# Coloring Book — Roadmap (bản 2)

Viết lại sau khi đổi mô hình kinh doanh.

---

## Mô hình

**Trước:** khách nhập chủ đề → AI sinh tại chỗ → khách mua cuốn vừa sinh
**Giờ:** **ông** sinh và tuyển chọn sách → đăng lên web → khách duyệt và mua

Giống Crayonahub. Sản phẩm là **hàng có sẵn**, không phải dịch vụ theo yêu cầu.

### Phạm vi demo

| Mục | Quyết định |
|---|---|
| Tùy biến | Không. Khách mua sách có sẵn |
| Sản phẩm | **Chỉ PDF tải về** |
| Thanh toán | Không. Đặt hàng là xong |
| Lulu in ấn | **Ngoài phạm vi demo** → Phase 5 |

---

## Vì sao thay đổi này làm dự án dễ hơn rất nhiều

Không phải chỉ bớt việc — nó xóa hẳn những bài toán khó nhất:

| Vấn đề cũ | Tình trạng |
|---|---|
| Khách chờ 12 phút | ❌ Biến mất. Sách sinh sẵn từ trước |
| GPU phải online 24/7 | ❌ Biến mất. **Production không cần GPU** |
| Hàng đợi, giới hạn 1 job/lần | ❌ Biến mất |
| Model vẽ hỏng đi thẳng vào file in | ❌ Biến mất. Ông duyệt từng trang |
| Lọc nội dung người dùng nhập | ❌ Biến mất. Prompt do ông kiểm soát |
| Lulu từ chối file | ❌ Hoãn tới Phase 5 |

**Hệ quả quan trọng nhất:** web production chỉ là một cửa hàng tĩnh bán file. Deploy lên VPS $5/tháng là đủ. GPU chỉ chạy trên laptop ông, lúc nào rảnh thì chạy, hỏng cũng không ai biết.

**Rủi ro dịch chuyển từ kỹ thuật sang nội dung.** Câu hỏi sống còn giờ không còn là "hệ thống có chạy không" mà là **"ông có đủ sách đẹp để bán không"**. Kế hoạch dưới đây phản ánh điều đó — phần lớn công sức nằm ở khâu sản xuất và tuyển chọn.

---

## Kiến trúc

```
┌──── OFFLINE (máy ông, không ai thấy) ────┐
│  Studio CLI/Python                       │
│  Gemini → Flux → vector hóa → duyệt      │
│  → dựng sách → xuất PDF + ảnh preview    │
└───────────────┬──────────────────────────┘
                │  đăng sách
                ▼
┌──── ONLINE (VPS $5, không cần GPU) ──────┐
│  NestJS  ── Postgres (catalog, đơn hàng) │
│     │                                     │
│     └──── R2 (PDF + ảnh preview)          │
│                                           │
│  Frontend: duyệt → xem trước → nhận PDF   │
└───────────────────────────────────────────┘
```

Ranh giới rõ ràng: **studio không bao giờ chạy khi có khách truy cập.**

---

## Phase 1 — Studio: sinh và tuyển chọn
**2–3 ngày** · Phần lớn đã có sẵn ở nhánh `feat/phase-1-pipeline`

Code Phase 1 cũ **dùng lại gần như toàn bộ**: Gemini, ComfyUI client, nhị phân hóa, vector hóa, PDF. Chỉ đổi vai trò — từ API phục vụ khách thành công cụ cho ông.

### Việc còn phải làm

**1.1 Sinh hàng loạt**
```bash
python studio.py generate "khủng long" --count 40
```
Sinh dư thật nhiều. Tỷ lệ giữ lại thực tế khoảng 40–60%.

**1.2 Màn hình duyệt** ⭐ *quan trọng nhất phase này*

Trang HTML tĩnh: lưới ảnh, phím tắt `A` = giữ, `D` = bỏ, `R` = vẽ lại.

Ông sẽ duyệt hàng trăm ảnh. Chênh lệch giữa công cụ tốt và duyệt thủ công bằng File Explorer là hàng chục giờ mỗi tháng. Đừng tiếc thời gian làm cái này.

**1.3 Kho trang đã duyệt**
```
library/
  <slug>/
    approved/  page-001.png  page-001.svg  meta.json
    rejected/
```
`meta.json` giữ prompt, seed, chủ đề, ngày sinh — để về sau tái tạo hoặc tìm lại.

**Xong khi:** có 40+ trang đã duyệt trong kho, đủ dựng 1–2 cuốn sách.

---

## Phase 2 — Dựng sách thành sản phẩm bán được
**2–3 ngày**

**2.1 Định nghĩa cuốn sách**
```yaml
slug: dai-duong-ky-thu
title: "Đại dương kỳ thú"
subtitle: "24 trang tô màu cho bé 3-8 tuổi"
audience: kids
pages: [ocean/page-003, ocean/page-007, ...]
cover: covers/ocean-color.png
price_vnd: 79000
```

**2.2 Sinh file sản phẩm**

| File | Dùng để |
|---|---|
| `interior.pdf` | **Hàng bán.** Không watermark |
| `preview.pdf` | 3 trang đầu, có watermark. Cho tải tự do |
| `page-XX.webp` | Ảnh xem trước trên web, hạ độ phân giải |
| `cover.png` | Ảnh bìa trong catalog |

**2.3 Bìa màu**
Sinh bằng Flux (bỏ ràng buộc line art), ghép chữ tiêu đề bằng Pillow — **không để Flux viết chữ**, nó sai chính tả.

**Xong khi:** `python studio.py publish dai-duong-ky-thu` → ra đủ bộ file + bản ghi trong Postgres.

---

## Phase 3 — Storefront API
**2–3 ngày**

NestJS. Không có GPU, không có hàng đợi — chỉ CRUD và phục vụ file.

```
GET  /api/books                 danh sách, lọc theo bộ sưu tập
GET  /api/books/:slug           chi tiết + ảnh xem trước
GET  /api/collections           For Kids / For Adults / Relaxation / Gifts
POST /api/orders                { bookSlug, email } → tạo đơn + link tải
GET  /api/download/:token       link ký, hết hạn sau 24h, giới hạn 5 lượt
```

**Điểm cần làm đúng:** `interior.pdf` **không bao giờ** để public. Chỉ phát qua token đã ký. Bucket R2 để private, NestJS ký URL tạm thời.

**Xong khi:** curl tạo đơn → nhận link → tải được PDF; đổi token thì bị từ chối.

---

## Phase 4 — Frontend → 🎯 DEMO
**3–4 ngày**

Bốn màn hình:

1. **Trang chủ** — sách nổi bật, bộ sưu tập. Học Crayonahub: phân loại theo *khoảnh khắc* ("Thư giãn một mình", "Làm quà tặng") chứ không theo chủ đề
2. **Danh sách** — lưới bìa sách, lọc theo bộ sưu tập
3. **Chi tiết sách** — bìa lớn, lật xem 3–5 trang mẫu, mô tả, số trang, độ tuổi, nút **Nhận bản PDF**
4. **Nhận sách** — nhập email → hiện link tải + gửi email

**Việc quan trọng nhất ở phase này không phải code mà là hình ảnh bán hàng.** Khách mua sách tô màu không mua "hình vẽ trắng đen" — họ mua kết quả sau khi tô. Cần ít nhất một ảnh minh họa trang **đã tô màu** cho mỗi cuốn. Dùng img2img hoặc ControlNet từ chính file line art, giữ nguyên nét, chỉ thêm màu.

**Xong khi:** người lạ mở link, duyệt sách, chọn một cuốn, nhập email, tải được PDF về máy.

---

## Phase 5 — Lên sản phẩm thật
**2–3 tuần**

Theo thứ tự ưu tiên:

| Bước | Ghi chú |
|---|---|
| 1. Thanh toán Stripe | Bán được tiền trước, mọi thứ khác sau |
| 2. Bảo vệ nội dung | Watermark mờ mang email người mua vào PDF. Không chống được sao chép nhưng ngăn phát tán hàng loạt |
| 3. **Lulu in ấn** | Sách in + PDF. Bán kèm PDF giảm 50% như Crayonahub — biên lợi nhuận rất tốt vì chi phí biên bằng 0 |
| 4. Email marketing | "Trang tô màu miễn phí mỗi tuần" — Crayonahub dùng để thu email, hiệu quả |
| 5. Trang pháp lý | Điều khoản, chính sách hoàn tiền (**hàng số không hoàn**), IP & DMCA |
| 6. SEO | Đây là mô hình catalog — lưu lượng tự nhiên là kênh sống còn |

---

## Tổng thời gian

| Mốc | Thời gian |
|---|---|
| Phase 1 (đã có phần lớn) | **2–3 ngày** |
| Phase 2–3 | **4–6 ngày** |
| Phase 4 (demo chạy được) | **3–4 ngày** |
| **Tổng đến demo** | **~2 tuần** |

Nhanh hơn kế hoạch cũ khoảng một tuần, chủ yếu vì bỏ hàng đợi, bỏ Lulu, bỏ thanh toán.

---

## Rủi ro còn lại

| Rủi ro | Mức | Ghi chú |
|---|---|---|
| **Không đủ sách đẹp để bán** | **Cao** | Rủi ro lớn nhất giờ. Một cuốn 24 trang cần duyệt ~50 ảnh. Đây là công việc lặp lại, không phải kỹ thuật |
| Thị trường nhạy cảm với "AI art" | Trung bình | Cân nhắc kỹ việc có ghi rõ dùng AI hay không. Không có câu trả lời đúng cho mọi trường hợp |
| Bị sao chép PDF | Trung bình | Hàng số luôn bị sao chép. Watermark mang email người mua là biện pháp thực dụng nhất |
| Cạnh tranh giá | Trung bình | Etsy đầy sách tô màu $2–5. Phải cạnh tranh bằng tuyển chọn và thương hiệu |

---

## Việc nên làm ngay

Không phải code. Là **sinh thử 40 ảnh cùng một chủ đề rồi tự duyệt bằng tay**.

Nó trả lời hai câu hỏi mà không dòng code nào trả lời được:

1. Tỷ lệ giữ lại thực tế là bao nhiêu? (dự đoán 40–60%)
2. Duyệt 40 ảnh mất bao lâu?

Hai con số đó quyết định ông sản xuất được bao nhiêu cuốn mỗi tuần — tức là quyết định cả mô hình kinh doanh. Biết chúng trước khi viết công cụ sẽ giúp ông làm đúng công cụ cần thiết.
