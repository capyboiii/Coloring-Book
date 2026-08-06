# Ghi chép — Khớp workflow với ComfyUI thật

**Ngày:** 2026-08-06 (tiếp theo [ghi chép Phase 1](2026-08-06-phase-1-studio.md))
**Nhánh:** `feat/phase-1-pipeline`

---

## Việc đã làm

Đọc trực tiếp `ComfyUI_windows_portable/ComfyUI/models/` trên máy Bao rồi vá
workflow cho khớp. Không đoán.

### Thực tế trong máy

```
models/unet/    flux1-schnell-Q4_K_S.gguf     6.8 GB
models/vae/     ae.safetensors                335 MB
models/clip/    clip_l.safetensors            246 MB
                t5xxl_fp8_e4m3fn.safetensors  4.9 GB
custom_nodes/   ComfyUI-GGUF                  đã cài
ComfyUI         0.30.0
```

### Lệch so với workflow ban đầu

Bốn chỗ, ba trong đó sẽ làm workflow chạy lỗi ngay:

| Chỗ | Workflow cũ | Thực tế | Hậu quả nếu không sửa |
|---|---|---|---|
| Model | `flux1-dev.safetensors` | `flux1-schnell-Q4_K_S.gguf` | Không tìm thấy file |
| Node nạp UNET | `UNETLoader` | `UnetLoaderGGUF` | `UNETLoader` không đọc được `.gguf` |
| T5 | `t5xxl_fp16.safetensors` | `t5xxl_fp8_e4m3fn.safetensors` | Không tìm thấy file |
| Bước sinh | 20 | **4** | Chạy dư 5 lần thời gian, không đẹp hơn |

Đã kiểm tra `custom_nodes/ComfyUI-GGUF/nodes.py`: node tên đúng là
`UnetLoaderGGUF`, chỉ nhận một input `unet_name`. CLIP vẫn dùng
`DualCLIPLoader` chuẩn vì hai file clip là `.safetensors`, không phải GGUF.

Cũng đã xác nhận trong `folder_paths.py` rằng ComfyUI 0.30 gộp
`models/clip` vào nhóm `text_encoders`, nên `DualCLIPLoader` nhìn thấy hai file
đó dù chúng nằm ở thư mục `clip` cũ.

---

## Phát hiện quan trọng: giấy phép

**FLUX.1-schnell là Apache 2.0 — được dùng thương mại.**
**FLUX.1-dev có giấy phép phi thương mại**, muốn bán sách phải mua giấy phép
riêng từ Black Forest Labs.

Nghĩa là workflow ban đầu tôi viết (mặc định `flux1-dev`) sẽ đẩy dự án vào thế
vi phạm giấy phép ngay khi bán cuốn đầu tiên. Máy Bao đang có **schnell** —
đúng model cần cho việc bán sách.

Đã ghi rõ điều này vào README để sau này không ai vô tình đổi sang dev.

---

## Sửa gì trong code

### 1. `workflows/flux_lineart.api.json`

- `UNETLoader` → `UnetLoaderGGUF`, trỏ tới `flux1-schnell-Q4_K_S.gguf`
- `t5xxl_fp16` → `t5xxl_fp8_e4m3fn`
- `steps` 20 → 4
- **Bỏ hẳn node `FluxGuidance`** — schnell không dùng guidance.
  `CLIPTextEncode` nối thẳng vào `BasicGuider`.

### 2. Xử lý việc thiếu guidance cho tử tế

Bỏ node FluxGuidance đồng nghĩa file map không còn khoá `guidance`. Nếu để
nguyên, `--guidance` sẽ âm thầm không có tác dụng — kiểu lỗi khó chịu nhất
vì không có dấu hiệu gì.

Thêm `supported_params` vào `ImageProvider`:

```python
supported_params: frozenset[str] = frozenset()
```

`ComfyUIProvider` gán từ chính các khoá trong file map. `generate` in ra
`guidance: workflow không dùng`, và nếu người dùng cố gõ `--guidance` thì
cảnh báo rõ ràng thay vì im lặng.

### 3. `doctor` in ra model đang gọi

Thêm `ComfyUIProvider.models()` quét workflow tìm `unet_name`, `vae_name`,
`clip_name1/2`, `ckpt_name`:

```
Model workflow đang gọi
  VAE         : ae.safetensors
  CLIP 1      : t5xxl_fp8_e4m3fn.safetensors
  CLIP 2      : clip_l.safetensors
  UNET        : flux1-schnell-Q4_K_S.gguf
  Tham số dùng: height, prompt, seed, steps, width
```

Lần sau lệch tên model là đối chiếu với `ComfyUI/models/` thấy ngay, không phải
đọc JSON.

### 4. Mặc định `STUDIO_STEPS` 20 → 4

Sửa cả `config.py` lẫn `.env.example`, kèm chú thích rằng đổi sang flux-dev
thì phải nâng lại lên 20–25.

---

## Kiểm chứng

`doctor` chạy đúng, in ra đủ 4 model và 5 tham số. Phần kết nối ComfyUI báo lỗi
là **đúng như mong đợi** — sandbox không với tới `127.0.0.1:8188` trên máy Bao.
Trên máy thật sẽ xanh.

Smoke test vẫn **đạt toàn bộ** sau khi sửa.

---

## Việc tiếp theo cho Bao

1. Bật ComfyUI, chạy `python studio.py doctor` — phải xanh hết
2. `python studio.py generate "đại dương" --count 4` xem chất lượng line art
3. Schnell bám prompt kém hơn dev. Nếu hình ra chưa ưng thì **chỉnh prompt và
   dùng `--subjects` trước**, đừng vội đổi model — đổi sang dev là vướng giấy phép.
4. Ưng rồi mới chạy `--count 40`, duyệt tay và **bấm giờ**

---

## Nguồn

- [FLUX.1-schnell trên Hugging Face (Apache 2.0)](https://huggingface.co/black-forest-labs/FLUX.1-schnell)
- [LICENSE-FLUX1-schnell](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-schnell)
- [Commercial Usage and Licensing — black-forest-labs/flux](https://deepwiki.com/black-forest-labs/flux/5-commercial-usage-and-licensing)
