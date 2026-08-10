# Bảng lệnh — LM Studio → Flux → sách

Một cuốn sách đi qua bốn bước. Bước ③ là mắt người, cố tình giữ bằng tay.

```
①  subjects   LM Studio viết 40 cảnh tiếng Anh từ một chủ đề tiếng Việt
②  generate   Flux vẽ 60 ảnh
③  ông duyệt  mở raw/, xoá ảnh xấu          <- không có lệnh, đây là việc tay
④  approve    chốt lại
⑤  build      dựng interior.pdf + cover.pdf + preview
```

---

## Bật hai thứ trước

| | |
|---|---|
| **ComfyUI** | chạy `run_nvidia_gpu.bat` — cần cho bước ② |
| **LM Studio** | tab Developer → nạp model → **Start Server** — chỉ bước ① cần |

```bash
python studio.py doctor
```

Nói cho ông biết đang gọi model nào, ComfyUI có sống không, LM Studio có
sống không. Chạy cái này trước khi nghi ngờ bất cứ điều gì khác.

---

## ① Sinh chủ đề mới bằng LM Studio

Chỉ cần khi muốn chủ đề **chưa có sẵn** trong `themes/`.

```bash
python studio.py subjects "Ngày hội biển" --count 40 --for kids
```

Ra file `themes/ngay-hoi-bien.txt`. **Mở ra đọc trước khi vẽ** — sửa một dòng
văn bản rẻ hơn nhiều so với vẽ lại 40 ảnh.

```bash
python studio.py subjects "Ngày hội biển" --dry-run    # in ra xem, chưa ghi file
python studio.py subjects --list-models                 # xem LM Studio đang nạp gì
```

Model hay trả về rỗng thì hạ `--batch 4`.

Đã có sẵn 8 bộ, bỏ qua bước này được:

```bash
python studio.py generate x --list-themes
```

---

## ② Flux vẽ

**Sách trẻ con:**

```bash
python studio.py generate "Đại dương kỳ thú" --theme ocean --count 60 \
    --slug dai-duong --for kids
```

**Sách người lớn:**

```bash
python studio.py generate "Mandala thư giãn" --theme mandala --count 60 \
    --slug mandala-1 --for adults
```

`--for` quyết định luôn độ chi tiết, mật độ và phong cách vẽ. Chủ đề nào có
nhu cầu riêng thì tự khai trong file của nó — mandala khai `@density: normal`
vì `rich` sẽ phá đối xứng, hoa lá khai `@style: decorative` vì `kawaii` làm
hoa mọc mặt người. Chủ đề đã khai `@audience: adults` thì gõ `--for` cũng
không cần.

Sinh **dư 50%** so với số trang cần: tỷ lệ giữ lại thực tế 50-70%.

| Nút vặn | Chọn |
|---|---|
| `--for` | `kids` hoặc `adults` — quyết định cả ba trục vẽ |
| `--count` | số ảnh sinh |
| `--seed 12345` | cố định để sinh lại y hệt |
| `--overwrite` | vẽ đè ảnh đã có (mặc định bỏ qua, để chạy tiếp được) |

Đứt giữa chừng thì chạy lại đúng lệnh cũ — nó bỏ qua ảnh đã có.

---

## ③ Ông duyệt

```
library/dai-duong/raw/
```

Mở thư mục đó, **xoá ảnh xấu**. Bấm giờ từ lúc mở tới lúc xong.

Đây là bước cố tình giữ bằng tay. Máy đã lọc được ảnh dính màu và nét mảnh,
nhưng "hình này có hợp lý không" thì chưa máy nào thay được mắt ông.

---

## ④ Chốt

```bash
python studio.py approve dai-duong --minutes 25
```

In ra tỷ lệ giữ lại và thời gian duyệt. **Hai con số này quyết định Phase 2
nên làm gì** — đừng bỏ trống `--minutes`.

```bash
python studio.py approve dai-duong --check-only   # chỉ soi, không chép
```

---

## ⑤ Dựng sách

```bash
python studio.py build dai-duong --pages 40
```

Ra `library/dai-duong/out/`:

| File | Được phát? |
|---|---|
| `interior.pdf` | **KHÔNG.** Đây là sản phẩm bán. |
| `cover.pdf` | **KHÔNG.** Gửi nhà in. |
| `preview.pdf` | phát tự do |
| `web/*.webp` | phát tự do |
| `book.json` | web đọc từ đây |

---

## Đo chất lượng

```bash
python studio.py measure dai-duong
python studio.py measure dai-duong --each          # từng ảnh
python studio.py measure dai-duong --vs mandala-1  # so hai mẻ
```

Mốc hiện tại của Flux schnell Q4: mực xám 20%, quầng mờ 14%, mảnh rời 39.

---

## Chạy trọn gói bằng công thức

Làm đi làm lại một cuốn thì viết công thức, khỏi nhớ tham số:

```bash
python studio.py make dai-duong --init      # tạo books/dai-duong.yaml
#   ... mở file đó sửa số trang, giá, mô tả ...
python studio.py make dai-duong             # lần 1: sinh ảnh rồi DỪNG
#   ... duyệt tay ...
python studio.py make dai-duong --minutes 25   # lần 2: dựng nốt
python studio.py make --list
```

Trong file YAML nhớ **bỏ trống dòng `style:`** — để chủ đề tự khai.

---

## Ba lỗi hay gặp

**Chủ thể tiếng Việt.** Flux không hiểu, không báo lỗi, chỉ lặng lẽ vẽ bừa.
Mẻ đầu tiên gõ "đại dương" ra toàn hoa lá đúng vì lý do này. Studio chặn sẵn.

**Quên bật ComfyUI.** `doctor` nói ngay.

**Đổi ba tham số cùng lúc rồi không biết cái nào ăn.** Đổi một thứ, đo, rồi
mới đổi tiếp.
