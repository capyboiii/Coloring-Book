# Ghi chép — Khuôn bố cục cố định, làm dày nét, và 19/24 dòng hỏng

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`

Bao xem ảnh trong `library/` và nói chất lượng đang khá lên nhưng **tính logic
và nét vẽ** vẫn chưa bằng sách mẫu. Đo bằng số rồi sửa.

---

## Đo trước đã

```
file                       màu%   ink%  nét dày   phân bố mực theo chiều dọc
khunglong/002.png         0.02%  2.22%     0.00    6%   2%  27%  65%
khunglong/003.png         0.00%  6.87%     0.04    8%  10%  32%  51%
bienca/003.png            0.00%  4.67%     0.02    0%  22%  66%  12%
giang-sinh-cua-be/004     0.00%  2.49%     0.00    1%  22%  59%  19%
```

Ba kết luận:

- **Màu đã sạch** (0.00–0.03%) — phần sửa hôm trước ăn
- **Nét mảnh** — bào mòn 1 px là nét biến mất
- **Bố cục lệch có hệ thống** — dải trên cùng chỉ 0–8% mực, mọi thứ dồn xuống đáy

---

## Nét: đo lại cho đúng rồi mới sửa

Chỉ số "bào mòn 1px" gây hiểu nhầm. Đo độ dày thật bằng `2 × diện tích / chu vi`:

| `LINE_THICKEN` | Độ dày TB @300dpi |
|---|---|
| 0 (trước) | 6.3 px |
| **3** | **8.2 px** |
| 5 | 10.6 px |
| 7 | 13.3 px |

Sách trẻ em cần 6–10 px. Nét cũ **6.3 px** — mỏng nhưng chưa phải sợi tóc như
tôi tưởng lúc đầu. Đặt `LINE_THICKEN = 3` cho ra 8.2 px, đúng giữa khoảng.

Đây là phép **giãn** (`MinFilter`), khác với `CLOSE_GAPS` là giãn-rồi-co.
Giãn thì nét dày thêm thật.

Điểm đáng nói: **prompt không cãi lại được Flux**. `thick bold outlines` đã
nằm trong prompt từ lâu mà nét vẫn 6.3 px. Phép giãn thì không phụ thuộc model
— nét bao nhiêu cũng dày thêm đúng ngần ấy pixel.

---

## Bố cục: khuôn cố định `@template`

Đây là thứ rút ra từ sách mẫu, và là thay đổi có sức nặng nhất.

Cuốn *Flower Garden* có 48 trang mà **cả 48 dùng chung một bố cục**: một bó hoa
cắm trong chậu gỗ có đai sắt, đặt giữa trang. Chỉ đổi loại hoa.

Nó **không bắt người vẽ nghĩ bố cục mới mỗi trang.**

Còn `themes/*.txt` của mình thì mỗi dòng mô tả một cảnh khác hẳn nhau — Flux
phải tự dựng bố cục 24 lần, và hỏng lúc nào không biết. Đó chính là lý do
trang lệch trang trống.

Cú pháp mới trong file theme:

```
@template: a bouquet of {subject} arranged in a wooden bucket with metal bands, standing on a plain surface, centered on the page and filling most of the frame

sunflowers with broad round petals
tulips with smooth closed buds
open roses with layered petals
```

Chủ thể rút xuống chỉ còn tên hoa. Khuôn lo phần bố cục.

**Có khuôn thì studio bỏ luôn cả `COMPOSITIONS` lẫn `DENSITY`** — khuôn đã
quyết định rồi, thêm "close-up view" hay "clear white space between objects"
vào nữa là ba chỉ dẫn bố cục đánh nhau. Đúng cái lỗi đã gặp giữa
`COMPOSITIONS` và `DENSITY` hôm trước.

Prompt cũng gọn hẳn: 148 → **89 từ**.

Thêm `themes/hoa-trong-chau.txt` dựng đúng theo sách mẫu làm ví dụ.

---

## Và một lỗi nặng trong file Bao vừa sinh

Chạy kiểm thử thì `themes/khung-long.txt` chỉ qua được **5/24 dòng**:

```
b tiny pterodactyls flying overhead, a family of dinosaurs walking near a lake
c two stegosaurs sharing a rock as a seat, a patch of ferns nearby
d cute ankylosaurus grazing on bushes, a butterfly resting on its back
e playful tyrannosaurus chasing after a small velociraptor
```

**19/24 dòng có một chữ cái lạc dính ở đầu.** Qwen2.5-7B đánh số bằng chữ cái
rồi nhả ra không có dấu chấm.

Nguy hiểm ở chỗ: dòng vẫn dài, vẫn có dấu phẩy, vẫn viết thường — **mọi luật
lọc hiện có đều cho qua**. Nếu Bao chạy `generate` thì 19 trang sẽ có chữ "b",
"c", "d" lạc trong prompt.

Sửa hai tầng:

1. **Bỏ đánh số bằng chữ cái** — regex cắt gạch đầu dòng giờ nhận cả
   `a)` `b.` chứ không chỉ `1.` `-` `*`
2. **Cắt chữ cái lạc không có dấu chấm** — `^([b-z])\s+` thì cắt chữ cái đó,
   **giữ lại phần còn lại**. Ban đầu tôi viết là bỏ cả dòng, nhưng như vậy
   mất 19/24 dòng của Bao trong khi nội dung vẫn dùng được.

Đã sửa file: 19 dòng cắt chữ cái lạc, 1 dòng trùng thay bằng cảnh mới. Giờ
24/24 sạch.

---

## Kiểm thử

Thêm mục `[13]` và `[14]`:

```
✓ Đọc được @template từ file theme
✓ Chủ thể được ghép vào khuôn
✓ Có khuôn thì KHÔNG kèm COMPOSITIONS
✓ Có khuôn thì KHÔNG kèm DENSITY
✓ Không có khuôn thì vẫn dùng COMPOSITIONS + DENSITY
✓ Cắt chữ cái lạc đầu dòng, giữ lại phần còn lại
✓ Cắt cả đánh số bằng chữ cái ('b) ...')
✓ Nét sau xử lý dày 6-14 px @300dpi
```

Bộ có `@template` được miễn luật hình dạng cảnh — chủ thể cố tình chỉ là mảnh
ngắn, khuôn mới là câu hoàn chỉnh.

111/111 đạt.

---

## Việc tiếp theo cho Bao

Thử ngay bộ dựng theo sách mẫu:

```bash
python studio.py generate "Vườn hoa" --theme hoa-trong-chau --count 4 \
    --style cartoon --complexity medium --density normal
```

Bốn trang này phải **giống nhau về bố cục** — cùng một chậu gỗ, chỉ khác loại
hoa. Nếu đúng vậy thì khuôn ăn, và cách này áp được cho mọi chủ đề.

Khủng long chẳng hạn, thêm dòng này vào đầu `themes/khung-long.txt`:

```
@template: a single friendly {subject}, standing on simple ground, centered on the page and filling most of the frame
```

rồi rút mỗi dòng xuống còn tên loài. Bố cục sẽ hết lệch.
