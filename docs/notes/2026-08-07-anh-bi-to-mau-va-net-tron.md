# Ghi chép — Ảnh ruột bị tô màu sẵn, nét mảnh, bố cục rối

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`
**Phản hồi của Bao:** nét phải tròn và đầy đủ, bố cục đừng quá phức tạp, và
**một số trang ruột bị tô màu sẵn** — chỉ bìa mới được có màu.

---

## Chẩn đoán

Mở thẳng 10 ảnh trong `library/giang-sinh/raw/` và đo bằng số:

```
file      màu?    ink%   xám giữa%
002.png    4.4    23.8       28.6   ← CÓ MÀU
010.png    0.9    15.0       13.9   ← có màu nhẹ
còn lại    ~0.1
```

Rồi đọc prompt thật của ảnh 002 trong `raw/002.json`:

> `an elf decorating a Christmas tree with colorful ornaments,`
> `fairy lights twinkling all around`

**Chính file chủ thể yêu cầu màu.** Prompt ảnh có `no color fill`, nhưng chủ
thể lại nói `with colorful ornaments`. Hai chỉ dẫn đánh nhau và chủ thể thắng,
vì nó cụ thể hơn.

Quét cả 5 file theme:

```
themes/giang-sinh.txt      8 dòng có từ chỉ MÀU,  5 dòng có hiệu ứng ÁNH SÁNG
themes/ocean.txt           0                      0
themes/mandala.txt         0                      0
themes/floral.txt          0                      0
themes/forest-animals.txt  0                      0
```

Bốn bộ tôi viết tay thì sạch. Bộ do model sinh ra thì đầy — vì chỉ dẫn tôi
gửi cho model **không hề cấm nói tới màu**.

Cộng thêm: sách chạy với `complexity: medium` + `density: rich` — sai hẳn cho
sách trẻ em. `rich` ép "many different elements throughout, background filled
with additional details", ra trang dày đặc chi tiết li ti.

---

## Sửa ở bốn tầng

### 1. Chỉ dẫn cho model sinh chủ thể (`llm.py`)

Thêm hai luật, kèm ví dụ đúng/sai lấy thẳng từ ảnh hỏng:

```
8. NEVER name a colour. The child chooses the colours.
   Say "a scarf", never "a red scarf".
9. NEVER describe light. No glowing, twinkling, shining.
   An outline cannot draw light.

BAD  an elf decorating a tree with colorful ornaments, fairy lights twinkling
FIXED an elf decorating a tree with round ornaments, paper garlands looping
```

### 2. Lọc tự động (`scrub_colour_and_light`)

Xử hai loại khác nhau:

- **Màu thì cắt sạch** — `"a red scarf"` → `"a scarf"`, nghĩa không đổi
- **Ánh sáng thì chỉ cảnh báo** — nó thường là cả mệnh đề
  (`"lights twinkling all around"`), cắt một từ sẽ làm câu què

Một lỗi bắt được khi chạy thật: `"a flock of brightly colored penguins"` →
`"a flock of brightly penguins"`. Phải cắt cả trạng từ đi kèm. Đã có kiểm thử
riêng cho chuyện này.

### 3. Prompt ảnh (`prompts.py`)

Ba nhóm sửa, theo đúng ba điều Bao nói:

**Nét tròn và đầy đủ** — thêm vào `BASE_STYLE`:
```
smooth rounded outlines, fully closed shapes, no broken or open lines
```

**Không tô màu** — nói theo hướng khẳng định, không chỉ phủ định:
```
completely uncolored, blank white shapes for a child to fill in
```

**Bố cục đơn giản** — `complexity: simple` viết lại:
```
very thick rounded outlines, big chunky shapes with soft curved edges,
large open areas to color, very few details,
no tiny elements, no fine patterns, for young children aged 4 to 8
```

Và `density: normal` viết lại cho rõ, vì trước đây nó mơ hồ:
```
one clear main subject filling most of the page,
a few large background elements around it,
uncluttered composition with room to breathe
```

### 4. Lưới chặn cuối: đo màu trên ảnh (`imageops.py`)

Ba tầng trên đều là *phòng ngừa*. Vẫn cần lưới chặn, vì Flux có thể tô màu
ngay cả khi prompt sạch.

`colour_amount()` đo tỉ lệ pixel có màu bằng độ lệch giữa ba kênh RGB. Ảnh đen
trắng thì R=G=B nên lệch bằng 0.

**Phải đo TRƯỚC khi chuyển thang xám.** `prepare_page` convert sang `L` ngay
từ đầu — lúc đó quả cầu vàng thành xám nhạt rồi thành trắng, nhìn PDF không
thấy gì lạ. Nhưng ảnh gốc đã hỏng, và mấy ảnh khác cùng mẻ cũng vậy.

Chạy lại trên 10 ảnh cũ, bắt đúng hai ảnh:

```
002.png  màu 10.48%  <-- ẢNH ĐÃ BỊ TÔ MÀU
010.png  màu  1.33%  <-- ẢNH ĐÃ BỊ TÔ MÀU
```

Ngưỡng 1%, đặt trong `config.COLOUR_RATIO_MAX`. **Chỉ áp cho trang ruột** —
bìa thì ngược lại, bìa phải có màu.

---

## Góp ý công thức

`Recipe.hints()` — góp ý chứ không chặn, vì đây là kinh nghiệm chứ không phải
luật:

```
! audience=kids nhưng complexity=detailed. Trẻ 4-8 tuổi cần nét dày, mảng lớn
! audience=kids nhưng density=rich. Trang quá rối, trẻ nhỏ khó tô
```

`make` in ra ngay đầu, trước khi đốt GPU.

---

## Đã dọn

- `themes/giang-sinh.txt`: bỏ từ chỉ màu ở 8 dòng, viết lại tay 6 dòng tả ánh
  sáng. Ví dụ:
  `"stars shining brightly overhead"` → `"simple star shapes scattered across
  the sky"`
- Thêm `books/giang-sinh.yaml` với `complexity: simple`, `density: normal`,
  `audience: kids`

Có kiểm thử quét toàn bộ `themes/*.txt`, đỏ ngay nếu file nào lọt từ chỉ màu
hay ánh sáng.

62/62 đạt.

---

## Việc tiếp theo cho Bao

Gen lại từ đầu — ảnh cũ sinh bằng prompt cũ nên không cứu được:

```bash
rm -rf library/giang-sinh
python studio.py make giang-sinh
```

Công thức đã đặt sẵn `simple` + `normal` + `kids`.

Chạy 4 ảnh xem trước cho nhanh thì:

```bash
python studio.py generate "Giáng sinh của bé" --theme giang-sinh --count 4 \
    --complexity simple --density normal
```

So với ảnh cũ, cần thấy: nét dày hơn và bo tròn, hình to hơn, ít chi tiết li
ti hơn, và **không còn màu**. Nếu vẫn còn ảnh có màu thì `approve` sẽ báo
`ẢNH ĐÃ BỊ TÔ MÀU` — xoá ảnh đó đi là xong, không phải soi từng cái.
