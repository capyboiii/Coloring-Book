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

---

## Cập nhật 2026-08-07 — vẽ trong giao diện đẹp hơn chạy qua code

Bao phát hiện bằng cách đơn giản nhất: **vẽ thẳng trong giao diện ComfyUI thì
nét đều và rõ, chạy qua code thì xấu.** Cùng model, cùng máy.

ComfyUI nhúng workflow vào file PNG nên so được ngay:

| | Giao diện | Code |
|---|---|---|
| Model | flux1-schnell-Q4_K_S | *cùng* |
| Sampler | 4 bước, euler/simple | *cùng* |
| **Kích thước** | **832 × 1088 = 0.91 MP** | **1392 × 1920 = 2.67 MP** |
| **Prompt** | **27 từ** | **163 từ** |

Hai khác biệt, và cả hai đều do tôi gây ra.

### Độ phân giải — tôi suy luận sai

Tôi nâng từ 928 lên 1392 với lập luận: latent to hơn thì nét chiếm nhiều ô
hơn, đỡ bị VAE làm hỏng. Nghe hợp lý, nhưng sai vì bỏ qua hai chuyện:

1. **FLUX.1-schnell được huấn luyện quanh 1 MP.** Đẩy lên 2.67 MP là ra ngoài
   vùng nó quen — nét bắt đầu đi loạng choạng, dày mỏng thất thường.
2. **Ảnh nhỏ phải phóng nhiều hơn để đạt khổ in** (2.6 lần thay vì 1.56 lần),
   mà chính phép nội suy LANCZOS khi phóng lại là một bộ làm mượt rất tốt.
   Nâng độ phân giải sinh đã vô tình lấy mất cái đó.

Đã hạ về **832 × 1152 = 0.96 MP**, sát với thứ giao diện đang dùng.

### Prompt — 163 từ so với 27

Prompt chạy tay của Bao:

```
a small brontosaurus munching on tall grass, one simple tree behind it for children
No color
No shading
No texture
No lighting
No gradients
Black outlines only
```

Chủ thể **đứng đầu**, rồi tới vài ràng buộc ngắn gọn.

Bản của tôi nhét hơn 100 từ phong cách lên trước, chủ thể chìm ở giữa. Mỗi
vòng sửa tôi lại thêm một chuỗi, lần nào cũng thấy có lý, và cộng dồn thành
163 từ loãng toẹt.

Đã rút xuống **72 từ** và **đưa chủ thể lên đầu**.

### Bài học

Đừng suy luận về hành vi của model rồi tin luôn. Phải đo, và **phải có một bản
đối chứng chạy tay** để so. Nếu Bao không tự vẽ trong giao diện thì tôi còn
loay hoay chỉnh khâu xử lý ảnh rất lâu nữa — trong khi lỗi nằm ở hai tham số
tôi tự đặt.

Kiểm thử giờ chặn cả hai: prompt phải dưới 100 từ, và độ phân giải phải nằm
trong 0.7–1.6 MP.

---

## Cập nhật — nhấn mạnh nét, và một hiểu lầm về negative prompt

Bao đề nghị ba nhóm từ khoá. Đã đưa hết vào, nhưng **chỗ đưa vào khác với chỗ
Bao nghĩ.**

### Flux bỏ qua negative prompt

Schnell là mô hình **guidance-distilled**, workflow chạy ở **CFG = 1.0**. Ở
CFG = 1 thì phần negative không tham gia vào phép tính — nó bị bỏ qua hoàn
toàn. Kể cả workflow Bao chạy tay trong giao diện cũng vậy.

Đó chính là lý do prompt tay của Bao viết `No color / No shading / No
gradients` **trong phần positive**. Cách đó đúng, và là cách duy nhất chạy
được với Flux.

Nên cả ba nhóm từ khoá đều gộp vào `BASE_STYLE`:

```
professional children's coloring book page, clean vector style,
extremely thick uniform black outlines, heavy solid black lines,
bold black outlines only,
no gray, no shading, no gradients, no thin or broken lines
```

Chuỗi `NEGATIVE` vẫn giữ, nhưng chỉ để ghi vào metadata từng ảnh và để dùng
ngay nếu sau này đổi sang SDXL hay model nào có CFG > 1. Đã sắp lại cho nhóm
lỗi nét đứng đầu.

### Vẫn giữ prompt ngắn

Prompt lên 86 từ, vẫn dưới ngưỡng 100 mà kiểm thử chặn. Chủ thể vẫn đứng đầu.

Đây là chỗ phải cân: thêm từ nhấn mạnh nét thì mạnh hơn, nhưng thêm quá thì
loãng và chủ thể chìm — đúng cái đã làm hỏng bản 163 từ. Nếu sau này muốn thêm
nữa thì phải bớt chỗ khác, đừng nối thêm.
