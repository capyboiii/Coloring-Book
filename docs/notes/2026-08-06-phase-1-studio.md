# Ghi chép — Phase 1, phần Studio

**Ngày:** 2026-08-06
**Nhánh:** `feat/phase-1-pipeline`
**Phạm vi:** bước ① TẠO, ② DUYỆT, ③ DỰNG. Chưa đụng tới ④ ĐĂNG và ⑤ BÁN.

---

## Bối cảnh trước khi làm

Repo đã có `docs/roadmap.md` và `docs/phases/*.md`. Roadmap nhắc tới nhánh
`feat/phase-1-pipeline` như thể đã có sẵn code, nhưng kiểm tra thì **nhánh đó
không tồn tại** — cả local lẫn origin chỉ có `main` và `docs/roadmap-v2`.
Nên toàn bộ code dưới đây viết mới từ đầu.

Ba quyết định chốt trước khi code:

| Câu hỏi | Chọn | Vì sao |
|---|---|---|
| Nguồn sinh ảnh | ComfyUI local | Đã có GPU, không tốn phí mỗi ảnh |
| Phạm vi phiên này | Chỉ `studio.py` | Chưa có ảnh thật thì build web cũng chưa test được gì |
| Lưu trữ | Local trước | R2 + Postgres để dành Phase 4 |

---

## Đã làm gì

### 1. Khung dự án

Tạo nhánh `feat/phase-1-pipeline` từ `docs/roadmap-v2`.

```
studio.py                    CLI, 4 lệnh con
studio/config.py             mọi con số in ấn
studio/util.py               slugify tiếng Việt, đọc/ghi JSON
studio/prompts.py            sinh prompt biến thể
studio/imageops.py           khử xám, phóng to, đo chất lượng
studio/providers/            base.py + comfyui.py
studio/commands/             doctor, generate, approve, build
workflows/                   workflow Flux + file map node
tests/smoke_test.py          kiểm thử không cần GPU
```

`.gitignore` chặn `library/` — nơi chứa `interior.pdf`. Đây là sản phẩm bán,
lọt lên repo công khai là mất trắng.

### 2. Chốt spec in ấn (`studio/config.py`)

Tra Lulu Book Creation Guide rồi quy ngược ra kích thước ảnh cần gen:

| Thông số | Giá trị |
|---|---|
| Trim | 8.5 × 11 in |
| Bleed | 0.125 in mỗi cạnh — **bắt buộc kể cả khi hình không tràn lề** |
| Khổ file PDF | 8.75 × 11.25 in |
| Safety margin | 0.5 in từ mép trim |
| Gutter | 0.25 in ở mép trong |
| Vùng vẽ an toàn | **7.25 × 10 in** |
| @300 DPI | trang 2625 × 3375 px, vùng vẽ 2175 × 3000 px |

Hai chi tiết dễ sai:

- **Gutter luôn ở bên trái.** Sách tô màu in một mặt nên mọi trang có hình đều
  là trang lẻ (recto, nằm bên phải khi mở sách), gáy ở bên trái. Không phải
  lật gương theo trang chẵn/lẻ như sách chữ.
- **In một mặt nhân đôi số trang.** 40 hình → 80 trang. Chi phí in cũng nhân đôi.

### 3. Kích thước sinh ảnh: 928 × 1280

Chọn con số này vì `928/1280 = 0.725` — đúng bằng tỉ lệ vùng vẽ `7.25/10`,
và cả hai chia hết cho 16 nên Flux không phải nội suy. Có `assert` trong
`config.py` chặn nếu ai đó sửa lệch tỉ lệ.

Không gen thẳng 2625 × 3375: quá nặng và Flux vốn không cho chất lượng tốt ở
độ phân giải đó. Gen ~1.2MP rồi upscale.

### 4. ComfyUI provider

Client HTTP thuần, dùng polling thay vì websocket:

```
POST /prompt        → prompt_id
GET  /history/{id}  → hỏi lại mỗi 1.5s tới khi có outputs
GET  /view          → tải PNG về
```

Điểm đáng nói: **workflow tách rời khỏi code**. Tham số nằm ở node nào được
khai trong `workflows/flux_lineart.map.json`:

```json
"prompt": { "node": "6",  "field": "text" },
"seed":   { "node": "25", "field": "noise_seed" }
```

`_validate_map()` chạy ngay lúc khởi tạo, đối chiếu từng node và từng field
với workflow thật. Sai là ném lỗi ngay — không để chạy 40 ảnh xong mới biết.
Đổi sang workflow khác chỉ cần sửa file map, không đụng code.

Viết sẵn lớp trừu tượng `ImageProvider` để sau muốn thêm fal.ai hay Replicate
thì chỉ thêm một file.

> Flux là mô hình **guidance-distilled** nên không có negative prompt. Chuỗi
> negative vẫn ghi vào metadata phòng khi đổi sang SDXL.

### 5. Prompt engine

Vấn đề: từ một chủ đề phải ra 40 prompt **khác nhau**. Chỉ đổi seed thì 40 ảnh
na ná nhau, tỷ lệ giữ lại sẽ rất thấp.

Cách làm: ghép chủ đề với 8 kiểu bố cục × 4 kiểu sắp xếp, xoay vòng, cộng seed
tăng dần. Ba mức `--complexity` (simple/medium/detailed) đổi mô tả độ dày nét
và mật độ chi tiết.

Cách tốt hơn là cấp `--subjects file.txt` liệt kê chủ thể từng trang — có
`workflows/subjects.example.txt` làm mẫu. Bộ sinh tự động chỉ để chạy nhanh mẻ đầu.

### 6. Xử lý ảnh (`imageops.py`)

**Thứ tự: phóng to TRƯỚC, khử xám SAU.** Làm ngược lại thì nội suy trên ảnh đã
nhị phân hoá, viền nét ra răng cưa.

Khử xám bằng **levels** thay vì threshold cứng:

```
≤ 80   → 0   (đen tuyền)
≥ 200  → 255 (trắng tinh)
ở giữa → nội suy tuyến tính
```

Threshold cứng cho ra viền răng cưa. Levels giữ được dải chuyển tiếp mỏng ở
viền nét nên in mượt hơn, mà vẫn ép sạch nền xám và vùng đổ bóng của Flux.

Ba phép đo tự động:

| Đo | Cách | Bắt lỗi gì |
|---|---|---|
| `ink_ratio` | tỉ lệ pixel < 128 | trang trắng trơn hoặc đen kịt |
| `thin_line_score` | bào mòn 1px bằng MaxFilter rồi so ink còn lại | nét mảnh sẽ mất khi in |
| `border_touch` | có nét trong dải 5% mép không | hình sẽ bị xén |

Ba phép đo này là nền cho bộ lọc tự động ở Phase 2.

### 7. Bốn lệnh CLI

| Lệnh | Việc |
|---|---|
| `doctor` | Kiểm tra thư viện, in bảng spec, thử kết nối ComfyUI + validate workflow |
| `generate` | Sinh N ảnh vào `raw/`, ghi prompt + seed từng ảnh, **chạy tiếp được** sau khi đứt |
| `approve` | Chép `raw/` còn lại sang `approved/`, soi chất lượng, ghi số liệu |
| `build` | Dựng `interior.pdf` + `preview.pdf` + `web/*.webp` |

`approve --minutes 95` ghi lại **thời gian duyệt** và tính ra phút/100 ảnh.
Cùng với **tỷ lệ giữ lại**, đây là hai con số roadmap yêu cầu đo ở Phase 1.

`build` xếp trang: bìa lót → trang trắng → (hình → trang trắng) × N.
Trang trắng không nhúng ảnh, chỉ `showPage()` — vừa đúng vừa nhẹ file.
Tổng số trang luôn chẵn, đúng yêu cầu đóng gáy keo.

### 8. Kiểm thử không cần GPU

`tests/smoke_test.py` sinh ảnh line art giả bằng Pillow (**cố ý để nền xám 244**
để thử phần khử xám), rồi chạy `approve` + `build` và kiểm tra kết quả.

Kết quả chạy — 16/16 đạt:

```
[1] Cấu hình khổ giấy
  ✓ Khổ file PDF 8.75 x 11.25 in
  ✓ Pixel/trang 2625 x 3375
  ✓ Vùng vẽ 7.25 x 10 in
  ✓ Lề trái = bleed + safety + gutter — 0.875 in
[2] Khử xám
  ✓ Nền xám 244 bị ép về trắng tinh 255
  ✓ Trang ra đúng khổ đầy đủ — (2625, 3375)
  ✓ ink_ratio trong khoảng hợp lệ — 5.133%
[3] approve   ✓ chép đủ ảnh, ghi số liệu
[4] build     ✓ interior.pdf 0.6 MB · preview.pdf 0.8 MB · 3 ảnh webp
[5] Nội dung PDF
  ✓ interior.pdf có đúng 10 trang (bìa lót 2 + 4 hình × 2)
  ✓ Số trang chẵn
  ✓ MediaBox = 8.750 x 11.250 in
```

Cũng đã thử `doctor` khi ComfyUI **chưa chạy** để xác nhận thông báo lỗi có ích
chứ không phải stack trace.

---

## Quyết định kỹ thuật và lý do

| Quyết định | Vì sao |
|---|---|
| Levels thay vì threshold cứng | Giữ khử răng cưa ở viền nét, in mượt hơn |
| Phóng to trước rồi mới khử xám | Ngược lại sẽ ra viền răng cưa |
| Polling thay vì websocket ComfyUI | Ít phụ thuộc; chạy hàng loạt thì trễ vài giây không quan trọng |
| Map node ở file JSON riêng | Đổi workflow không phải sửa code |
| Validate map lúc khởi động | Bắt lỗi trước khi đốt 40 lượt GPU |
| Trang trắng không nhúng ảnh | File nhẹ hơn nhiều, và đúng nghĩa "trang trắng" |
| `generate` bỏ qua ảnh đã có | Đứt giữa chừng thì chạy lại được, không mất công |
| Ghi prompt + seed từng ảnh | Tái tạo lại đúng một trang khi cần |

---

## Chưa làm

- **Sinh bìa** — Phase 1 làm tay. Flux vẽ bìa màu, ghép chữ bằng Canva.
  Không để Flux viết chữ, nó sai chính tả.
- **Màn hình duyệt** — cố ý để Phase 2. Phải làm tay một lần mới biết nó thực
  sự tốn bao lâu.
- **Storefront, API, R2, Postgres** — Phase 4.
- **Thanh toán** — Phase 5.

---

## Việc tiếp theo cho Bao

1. `pip install -r requirements.txt` rồi `python studio.py doctor`
2. Sửa `workflows/flux_lineart.api.json` cho khớp **tên model thật** trong
   `ComfyUI/models/` của ông (`flux1-dev.safetensors`, `ae.safetensors`,
   `t5xxl_fp16.safetensors`, `clip_l.safetensors`)
3. Chạy thử `--count 4` trước để xem chất lượng line art ra sao, rồi mới chạy 40
4. Duyệt tay và **bấm giờ thật**, chạy `approve <slug> --minutes <số>`
5. `build`, mở `interior.pdf` phóng 100% xem nét có đủ dày không
6. **Đặt một cuốn mẫu qua Lulu.** Đây là việc quan trọng nhất và cũng dễ bị
   trì hoãn nhất. Chỉ khi cầm sách thật mới biết nét có mảnh quá không và lề
   gáy có nuốt hình không.

Hai con số ở bước 4 định hình Phase 2. Nếu duyệt nhanh hơn dự đoán thì nên
đảo Phase 2 và Phase 3 cho nhau.
