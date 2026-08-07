# Đổi sang SDXL

Workflow đã dựng sẵn. Ông chỉ cần tải model và sửa hai dòng trong `.env`.

---

## Vì sao SDXL, không phải Flux

Ba lý do, xếp theo mức quan trọng.

### 1. Negative prompt CÓ tác dụng

Đây là lý do lớn nhất và là thứ tôi phát hiện muộn.

FLUX.1-schnell là mô hình **guidance-distilled**, chạy ở **CFG = 1.0**. Ở
CFG = 1 thì khối negative không tham gia vào phép tính — bị bỏ qua hoàn toàn.

Nghĩa là suốt thời gian qua, toàn bộ danh sách này **không hề có tác dụng**:

```
thin lines, uneven lines, broken lines, sketchy, soft edges,
light lines, hatching, gray, shading, gradient, shadows
```

SDXL chạy CFG thật (6–8). Với nó, mỗi từ trong danh sách đó là một lực đẩy
thật sự ra khỏi ảnh. Đúng thứ ta cần: **đẩy nét mảnh, nét đứt, nét xám ra.**

### 2. Nhẹ hơn và nhanh hơn nhiều

| | Flux schnell Q4 | SDXL |
|---|---|---|
| Dung lượng | 6.8 GB | 6.6 GB (hoặc 3.5 GB bản fp8) |
| Thời gian/ảnh | ~80 giây ở 2.67 MP | ~15–25 giây ở 1 MP |

Máy ông đang mất 80 giây một ảnh. Sinh 60 ảnh là 80 phút. Với SDXL còn khoảng
20–25 phút.

### 3. Hệ sinh thái LoRA cho line art

SDXL có hàng nghìn LoRA trên Civitai, trong đó nhiều bộ **huấn luyện riêng cho
sách tô màu** — nét dày, đều, khép kín. Flux có ít hơn hẳn.

Đây mới là chỗ ăn thua thật sự: một LoRA line art tốt hơn mọi câu chữ trong
prompt cộng lại.

### Giấy phép

SDXL base dùng **CreativeML OpenRAIL++-M** — cho phép dùng thương mại.

⚠️ **LoRA thì mỗi bộ một giấy phép.** Trên Civitai mỗi trang model có mục
*Permissions*. Phải đọc trước khi dùng cho sách bán. Có bộ ghi rõ "no
commercial use".

---

## Cài

### 1. Tải checkpoint

Bỏ vào `ComfyUI/models/checkpoints/`:

| Model | Dung lượng | Ghi chú |
|---|---|---|
| [sd_xl_base_1.0.safetensors](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/sd_xl_base_1.0.safetensors) | 6.6 GB | Bản gốc, chắc chắn dùng thương mại được |

Muốn nét đẹp hơn nữa thì tìm trên Civitai một checkpoint hoặc LoRA
**coloring book / line art / lineart SDXL**, rồi đọc kỹ mục *Permissions*.

### 2. Sửa `.env`

```
STUDIO_WORKFLOW=workflows/sdxl_lineart.api.json
STUDIO_WORKFLOW_MAP=workflows/sdxl_lineart.map.json
STUDIO_STEPS=
STUDIO_GUIDANCE=
```

Hai dòng cuối **để trống** — studio sẽ dùng nguyên 28 bước và CFG 7 ghi trong
workflow. Nếu nhét số cố định vào đó thì lúc quay lại Flux sẽ chạy 28 bước với
schnell, ra ảnh hỏng.

Tên checkpoint khác thì sửa trong `workflows/sdxl_lineart.api.json`:

```json
"4": { "class_type": "CheckpointLoaderSimple",
       "inputs": { "ckpt_name": "ten-file-cua-ong.safetensors" } }
```

### 3. Kiểm tra rồi chạy thử

```bash
python studio.py doctor
python studio.py generate "Khủng long" --theme khung-long --count 4 \
    --slug khung-long-sdxl --style kawaii --complexity simple --density normal
python studio.py measure khung-long --vs khung-long-sdxl
```

`doctor` sẽ in ra `Tham số dùng: guidance, height, negative, prompt, seed,
steps, width` — có chữ **negative** nghĩa là workflow này dùng được negative
prompt, khác hẳn Flux.

---

## Quay lại Flux

Chỉ cần đổi hai dòng trong `.env` về:

```
STUDIO_WORKFLOW=workflows/flux_lineart.api.json
STUDIO_WORKFLOW_MAP=workflows/flux_lineart.map.json
```

Không mất gì cả. Cả hai workflow nằm cạnh nhau, và mọi phần khác của studio —
prompt, chủ thể, xử lý ảnh, dựng PDF — không quan tâm ông dùng model nào.

---

## Đừng bỏ qua bước đo

Đây là lần thứ hai đổi model. Lần trước tôi đổi độ phân giải vì *suy luận* và
làm hỏng chất lượng suốt mấy vòng mà không biết.

```bash
python studio.py measure khung-long --vs khung-long-sdxl
```

Ghi kết quả vào bảng cuối
[thu-nghiem-chat-luong-net.md](thu-nghiem-chat-luong-net.md) để lần sau khỏi
thử lại.

Và vẫn nên **vẽ một ảnh trong giao diện ComfyUI** với cùng model để đối chứng
— đó là cách ông đã bắt được lỗi lần trước.
