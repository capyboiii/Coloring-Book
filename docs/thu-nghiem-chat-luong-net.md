# Quy trình thử nghiệm chất lượng nét

Đo, đổi một thứ, đo lại. Không đoán bằng mắt.

---

## Vì sao đo thay vì nhìn

Mắt người kém ở chỗ so hai thứ gần giống nhau. Và chỉ số sai còn tệ hơn không
có chỉ số: có lần tôi đếm "đầu mút" thấy 31 → 0 nên tưởng đã vá xong chỗ đứt,
trong khi khe hở còn nguyên — giãn nét làm đầu mút cụt đi nên không đếm được
nữa.

Bốn chỉ số dưới đây đều kiểm chứng được bằng mắt khi phóng to ảnh.

```bash
python studio.py measure khung-long
python studio.py measure khung-long --each          # từng ảnh
python studio.py measure khung-long --vs khung-long-q6   # so hai lần chạy
```

| Chỉ số | Nghĩa | Tốt là |
|---|---|---|
| **dày nét** | px ở ảnh gốc | **≥ 8** — xem dưới |
| **mực xám** | % mực không đen hẳn | < 15% |
| **quầng mờ** | % pixel gần trắng bám quanh nét | < 12% |
| **mảnh rời** | số nét không nối nhau | càng thấp càng liền |

Đo trên **ảnh gốc chưa qua xử lý**, để tách bạch lỗi của Flux với lỗi của khâu
xử lý.

---

## Vì sao mốc 8 px

Flux không vẽ thẳng ra pixel. Nó làm việc trong không gian **latent nhỏ hơn 8
lần**, rồi VAE giải mã ngược lại.

```
ảnh 1392 × 1920  →  latent 174 × 240
1 ô latent = 8 × 8 pixel ảnh
```

Nét hiện tại dày **5.3 px**, tức **0.66 ô latent**. Nó nằm gọn trong một ô, nên
decoder phải dựng lại từ thông tin không đủ — ra xám, gợn, và đứt quãng.

Số đo khớp với chuyện đó:

| Ảnh | Dày nét | Mực xám | Quầng mờ |
|---|---|---|---|
| 001 | 6.6 px | 14% | 9% |
| **002** | **4.2 px** | **28%** | **18%** |
| 003 | 4.9 px | 20% | 14% |
| 004 | 5.4 px | 16% | 15% |

Ảnh nét mảnh nhất cũng là ảnh xám nhất và quầng mờ nhiều nhất. Nhìn ảnh cũng
thấy đúng vậy: **viền con vật dày thì đen đặc, còn cỏ mây đường nước mảnh thì
xám và đứt.**

---

## Ba hướng cải thiện, xếp theo mức ăn thua

### 1. Đổi bản lượng tử hoá — thử trước, rẻ nhất

Đang dùng **Q4_K_S** (6.8 GB), nén 4-bit nên mất khá nhiều độ chính xác.

Tải một trong hai, bỏ vào `ComfyUI/models/unet/`:

| Bản | Dung lượng | Ghi chú |
|---|---|---|
| [flux1-schnell-Q6_K.gguf](https://huggingface.co/city96/FLUX.1-schnell-gguf/blob/main/flux1-schnell-Q6_K.gguf) | 9.8 GB | Cân bằng tốt |
| [flux1-schnell-Q8_0.gguf](https://huggingface.co/city96/FLUX.1-schnell-gguf/blob/main/flux1-schnell-Q8_0.gguf) | 12.7 GB | Sạch nhất, nặng nhất |

Vẫn là schnell, vẫn giấy phép Apache 2.0 nên bán sách được.

Rồi sửa một dòng trong `workflows/flux_lineart.api.json`:

```json
"12": { "class_type": "UnetLoaderGGUF",
        "inputs": { "unet_name": "flux1-schnell-Q6_K.gguf" } }
```

Chạy 4 ảnh vào một slug riêng rồi so:

```bash
python studio.py generate "Khủng long" --theme khung-long --count 4 \
    --slug khung-long-q6 --style kawaii --complexity simple --density normal
python studio.py measure khung-long --vs khung-long-q6
```

**Kỳ vọng:** quầng mờ và mực xám giảm. Dày nét có thể không đổi mấy.

### 2. Nâng độ phân giải sinh — đánh thẳng vào gốc

Latent to hơn thì nét chiếm nhiều ô hơn. Có bằng chứng: ở 928 px nét chỉ
2.7 px, lên 1392 px thành 5.3 px.

Trong `.env`:

```
STUDIO_GEN_WIDTH=1856
STUDIO_GEN_HEIGHT=2560
```

Phải giữ đúng tỉ lệ 0.725 và chia hết cho 16 — `config.py` có `assert` chặn nếu
sai.

**Đổi lại:** số pixel gấp 1.8 lần so với hiện tại, mỗi ảnh lâu hơn tương ứng,
và tốn VRAM hơn. Thử 4 ảnh trước xem GPU có kham nổi.

### 3. Bớt yêu cầu chi tiết mảnh

Cỏ, mây, gợn nước — chính là thứ luôn hỏng, vì chúng vốn được vẽ mảnh. Phần
sửa prompt đã đi hướng này rồi (`density: normal`, `no tiny scattered
elements`), nhưng có thể mạnh tay hơn: `--density single` thì chủ thể đứng một
mình trên nền trắng, không còn cỏ mây để mà hỏng.

---

## Thứ KHÔNG giúp

**Tăng số bước sinh.** Schnell được *chưng cất* để chạy đúng 4 bước. Đẩy lên 8
thường không cải thiện, có khi còn sinh nhiễu. Đây là chỗ dễ khuyên sai.

**Đổi sang FLUX.1-dev.** Nét sẽ đẹp hơn thật, nhưng dev có **giấy phép phi
thương mại** — bán sách bằng nó là vi phạm.

---

## Ghi lại kết quả

Mỗi lần thử, ghi vào bảng này để lần sau khỏi thử lại:

| Ngày | Thay đổi | Dày nét | Xám | Quầng | Mảnh rời |
|---|---|---|---|---|---|
| 2026-08-07 | Q4_K_S, 1392×1920, 4 bước | 5.3 px | 20% | 14% | 39 |
| | | | | | |
