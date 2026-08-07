# Ghi chép — Công thức sách và gói bàn giao cho web

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`
**Yêu cầu:** một công thức, chạy ra trọn gói, sau chỉ việc đăng lên web bán

---

## Vấn đề

Mọi tham số đang nằm rải trong lệnh gõ tay:

```bash
python studio.py generate "Đại dương kỳ thú" --theme ocean --count 60 \
    --complexity medium --density rich
python studio.py approve dai-duong-ky-thu --minutes 95
python studio.py build dai-duong-ky-thu --subtitle "..." --bg "#1B7A8C"
```

Ba tuần sau muốn in lại đúng cuốn đó thì không nhớ đã chạy `--complexity` gì,
`--density` gì. Và không có chỗ nào ghi giá bán, collection, mô tả — những thứ
web cần.

---

## Công thức: `books/<slug>.yaml`

```yaml
title: "Đại dương kỳ thú"
subtitle: "40 trang tô màu cho mọi lứa tuổi"

theme: ocean
pages: 40             # số hình trong sách
generate: 60          # sinh dư để còn chỗ loại
complexity: medium    # độ tinh xảo của NÉT
density: rich         # số ĐỐI TƯỢNG mỗi trang
seed:                 # điền số để sinh lại y hệt

cover:
  bg: "#1B7A8C"

collection: relaxation
price_usd: 14.99
tags: [ocean, animals, relaxation]
description: |
  Mô tả bán hàng...
```

Tái tạo được, sửa được, **commit vào git được** — khác hẳn lệnh gõ tay.

Tách `pages` khỏi `generate` vì hai con số khác nhau: sách cần 40 hình, nhưng
tỷ lệ giữ lại chỉ 50–70% nên phải sinh 60. Để trống `generate` thì tự tính
`pages × 1.5`.

### Kiểm tra trước khi chạy

`_validate()` chặn ngay nếu sai `complexity`, sai `density`, sai mã màu bìa,
hay `generate < pages`. Báo lỗi trong một giây thay vì để gen xong 60 ảnh mới
biết.

Có một luật mang tính kinh nghiệm: **`theme: mandala` cộng `density: rich`
bị chặn** — mandala vốn đã đối xứng và lấp kín trang, thêm "many different
elements" vào là phá đối xứng thành một mớ hỗn độn.

---

## `make`: chạy tiếp được, không gộp một lần

```bash
python studio.py make dai-duong-ky-thu --init   # tạo công thức mẫu
python studio.py make dai-duong-ky-thu          # lần 1: sinh ảnh
#   ... duyệt tay ...
python studio.py make dai-duong-ky-thu --minutes 95   # lần 2: dựng sách
```

Lệnh nhìn thư mục sách đang ở bước nào rồi làm bước kế tiếp:

| Trạng thái | Làm gì |
|---|---|
| `cần sinh ảnh` | Sinh ảnh + ảnh bìa, rồi **dừng** để duyệt |
| `cần duyệt` | Chép ảnh còn lại, dựng ruột + bìa + gói bán |
| `xong` | Báo đã xong, `--force` để dựng lại |

**Cố ý không gộp thành một lần chạy.** Ở giữa có bước duyệt bằng mắt người, và
đó là bước quan trọng nhất của Phase 1 — chỗ duy nhất bắt được lỗi mà máy
không thấy. Gộp lại là bỏ mất nó.

`--yes` bỏ qua bước duyệt, kèm cảnh báo, chỉ để chạy thử.

---

## `book.json`: ranh giới giữa studio và cửa hàng

Đây là phần quan trọng nhất về mặt kiến trúc, nối tiếp cuộc bàn hôm trước về
việc tách studio khỏi web.

`make` xuất ra `library/<slug>/out/book.json`. **Web chỉ đọc file này**, không
cần biết Flux, ComfyUI, prompt hay theme là gì:

```json
{
  "slug": "dai-duong-ky-thu",
  "title": "Đại dương kỳ thú",
  "price_usd": 14.99,
  "collection": "relaxation",
  "art_pages": 40,
  "pdf_pages": 82,
  "print": { "spine_in": 0.245, "cover_in": [17.495, 11.25], "dpi": 300 },
  "files": {
    "interior": "interior.pdf",
    "cover": "cover.pdf",
    "preview": "preview.pdf",
    "cover_image": "web/cover.webp",
    "preview_images": ["web/page-01.webp", "..."]
  },
  "source": {
    "theme": "ocean", "complexity": "medium", "density": "rich",
    "seed": null, "retention_rate": 0.63, "review_minutes": 95
  },
  "status": "ready"
}
```

Ba nhóm tách bạch:

- **Thông tin bán hàng** — lấy thẳng từ công thức
- **`files`** — hai file đầu KHÔNG được để public, ba file sau phát tự do
- **`source`** — tham số đã dùng và hai con số đo được, để sau còn truy được
  cuốn nào ra từ công thức nào

Có hợp đồng này rồi thì mai đổi Flux sang Midjourney, hay thuê hoạ sĩ vẽ tay,
cửa hàng vẫn chạy nguyên — nó chỉ cần một thư mục đúng định dạng.

---

## Kiểm thử

Mục `[8]` trong smoke test, chạy trên thư mục tạm:

```
✓ scaffold tạo được file công thức
✓ Đọc lại đúng tên sách
✓ generate mặc định lớn hơn pages
✓ Chặn complexity sai
✓ Chặn density sai
✓ Chặn màu bìa sai định dạng
✓ Chặn generate ít hơn pages
✓ Chặn mandala + density rich (phá đối xứng)
✓ Công thức hợp lệ thì không chặn
```

Cũng đã chạy thật end-to-end với 4 ảnh giả: `make --init` → sinh → duyệt →
dựng → `book.json`. Chạy lần ba thì báo "xong" đúng như mong đợi.

53/53 đạt.

---

## Việc tiếp theo cho Bao

Có sẵn `books/dai-duong-ky-thu.yaml` điền đủ. Bật ComfyUI rồi:

```bash
python studio.py make dai-duong-ky-thu
```

Nó sinh 60 ảnh + ảnh bìa rồi dừng. Duyệt tay, **bấm giờ**, chạy lại kèm
`--minutes <số phút>`.

Muốn cuốn khác thì `make <slug> --init` rồi sửa công thức. Đổi `theme` sang
`mandala`, `floral`, `forest-animals` là ra sách khác hẳn mà không đụng code.

Nhắc lại thứ tự ưu tiên: xong cuốn đầu → **đặt sách mẫu qua Lulu** → cầm trên
tay kiểm nét và lề gáy → rồi mới xây web.
