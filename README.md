# Coloring Book Studio

Công cụ tạo sách tô màu bằng Flux (ComfyUI local) và xuất file in đúng chuẩn Lulu.

Đây là **Phase 1** của [roadmap](docs/roadmap.md) — phủ ba bước đầu trong năm bước:

```
① TẠO  →  ② DUYỆT  →  ③ DỰNG  →  ④ ĐĂNG  →  ⑤ BÁN
generate   xoá tay     build      chưa làm    chưa làm
           + approve
```

---

## Cài đặt

Cần Python 3.10+ và một ComfyUI đang chạy có model Flux.

```bash
pip install -r requirements.txt
cp .env.example .env      # sửa COMFYUI_URL nếu cần
python studio.py doctor   # kiểm tra trước khi chạy thật
```

`doctor` phải xanh hết trước khi sang bước sau. Nó bắt lỗi sai tên model,
sai định dạng workflow, sai số node — những lỗi mà nếu không bắt sớm thì
phải chạy 40 lượt GPU mới biết.

---

## Dùng

### ① Sinh ảnh

```bash
python studio.py generate "đại dương kỳ thú" --count 40
```

Ảnh ra ở `library/dai-duong-ky-thu/raw/`, kèm file `.json` ghi lại prompt và
seed của từng ảnh để sinh lại y hệt khi cần.

Muốn kiểm soát nội dung từng trang thì cấp danh sách chủ thể:

```bash
python studio.py generate "đại dương" --count 40 \
    --subjects workflows/subjects.example.txt \
    --complexity detailed
```

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `--complexity simple` | Nét dày, mảng lớn — cho trẻ nhỏ |
| `--complexity medium` | Mặc định |
| `--complexity detailed` | Nhiều chi tiết — sách người lớn |
| `--seed 12345` | Cố định seed để tái tạo đúng mẻ cũ |
| `--overwrite` | Sinh đè. Mặc định bỏ qua ảnh đã có nên chạy lại được sau khi đứt |

Lệnh này **chạy tiếp được**. Đứt giữa chừng thì chạy lại, nó bỏ qua ảnh đã xong.

### ② Duyệt bằng tay

Mở `library/<slug>/raw/` bằng File Explorer, xoá ảnh xấu. **Bấm giờ.**

```bash
python studio.py approve dai-duong-ky-thu --minutes 95
```

Lệnh này chép ảnh còn lại sang `approved/`, soi chất lượng từng ảnh, và ghi
lại hai con số mà roadmap cần: **tỷ lệ giữ lại** và **thời gian duyệt**.

Phase 1 cố tình không xây màn hình duyệt. Phải làm tay một lần để biết nó
thực sự tốn bao lâu — con số đó quyết định Phase 2 làm gì.

### ③ Dựng file

```bash
python studio.py build dai-duong-ky-thu
```

Ra ba thứ trong `library/<slug>/out/`:

| File | Dùng để |
|---|---|
| `interior.pdf` | Gửi nhà in / bán cho khách. **Không bao giờ để public** |
| `preview.pdf` | 3 trang đầu, hạ DPI, đóng dấu. Phát tự do |
| `web/*.webp` | Ảnh cho trang chi tiết sách |

---

## Spec in ấn

Mọi con số nằm ở [`studio/config.py`](studio/config.py). Theo Lulu Book Creation Guide:

| | |
|---|---|
| Khổ trim | 8.5 × 11 in |
| Khổ file PDF | **8.75 × 11.25 in** (bleed 0.125 in mỗi cạnh — bắt buộc) |
| Vùng vẽ an toàn | 7.25 × 10 in (safety 0.5 in + gutter 0.25 in) |
| Độ phân giải | 300 DPI → **2625 × 3375 px** mỗi trang |
| In | **Một mặt** — sau mỗi trang hình là một trang trắng |

**Vì sao in một mặt:** bút màu, nhất là marker, thấm xuyên giấy. In hai mặt
là hỏng hình ở mặt sau. Đổi lại số trang và chi phí in tăng gấp đôi — 40 hình
thành sách 80 trang. Tính giá bán từ con số 80, không phải 40.

**Vì sao có gutter:** gáy keo nuốt mất phần mép trong. Không chừa gutter thì
hình bị cụt ở rìa trái. Đây là lỗi phổ biến nhất khi tự xuất bản sách tô màu.

---

## Xử lý ảnh

Flux trả về ảnh ~1MP, nền hơi xám, đôi khi có vùng đổ bóng. Pipeline làm ba việc:

1. **Phóng to** vào vùng vẽ bằng LANCZOS
2. **Khử xám** bằng levels — `≤80 → đen tuyền`, `≥200 → trắng tinh`, ở giữa nội suy
3. **Đo** `ink_ratio` và độ mảnh nét, cảnh báo trang hỏng

Thứ tự quan trọng: **phóng to trước, khử xám sau**. Làm ngược lại thì viền nét
bị răng cưa vì nội suy trên ảnh đã nhị phân hoá.

Dùng levels thay vì threshold cứng để giữ dải chuyển tiếp mỏng ở viền — in ra
nét mượt hơn nhiều.

---

## Đổi workflow ComfyUI

Workflow phải là bản export **API format** (Settings → bật Dev mode → nút
`Save (API Format)`), không phải file kéo thả thông thường.

Thay workflow khác thì chỉ cần sửa số node trong
[`workflows/flux_lineart.map.json`](workflows/flux_lineart.map.json),
không phải đụng vào code:

```json
{
  "prompt":   { "node": "6",  "field": "text" },
  "seed":     { "node": "25", "field": "noise_seed" },
  "width":    { "node": "5",  "field": "width" },
  "height":   { "node": "5",  "field": "height" }
}
```

Studio kiểm tra file map ngay lúc khởi động — sai node là báo lỗi luôn, không
đợi chạy xong 40 ảnh mới biết.

> Flux là mô hình guidance-distilled nên **không dùng negative prompt**.
> Chuỗi negative vẫn được ghi vào metadata để dùng nếu sau đổi sang SDXL.

---

## Kiểm thử

```bash
pip install -r requirements-dev.txt
python tests/smoke_test.py
```

Chạy toàn bộ đường ống bằng ảnh giả, **không cần GPU**. Kiểm tra khổ PDF, số
trang, bố cục và phần khử xám. Chạy cái này mỗi lần sửa `imageops.py` hoặc
`build.py`.

---

## Bố cục thư mục

```
studio.py                    điểm vào CLI
studio/
    config.py                mọi con số về in ấn
    prompts.py               sinh prompt biến thể
    imageops.py              khử xám, phóng to, đo chất lượng
    providers/
        base.py              giao diện chung
        comfyui.py           client HTTP nói chuyện với ComfyUI
    commands/
        doctor.py  generate.py  approve.py  build.py
workflows/
    flux_lineart.api.json    workflow Flux
    flux_lineart.map.json    tham số nằm ở node nào
    subjects.example.txt     mẫu danh sách chủ thể
tests/smoke_test.py
library/                     thư viện sách — KHÔNG commit
```

⚠️ `library/` nằm trong `.gitignore`. Nó chứa `interior.pdf` là sản phẩm bán.
Đẩy lên repo công khai là mất trắng.

---

## Chưa có ở Phase 1

- Sinh bìa — làm tay: Flux vẽ bìa màu, ghép chữ bằng Canva.
  **Không để Flux viết chữ**, nó sai chính tả.
- Màn hình duyệt (Phase 2)
- Storefront và API (Phase 4)
- Thanh toán (Phase 5)
