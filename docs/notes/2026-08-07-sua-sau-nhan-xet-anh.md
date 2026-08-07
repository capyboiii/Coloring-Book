# Ghi chép — Sửa theo sáu nhận xét về chất lượng ảnh

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`

Bao xem mẻ ảnh và chỉ ra sáu vấn đề. Ghi lại từng cái đã sửa ở đâu.

---

## 1 & 3. Quá nhiều chi tiết nhỏ, nhiều nhân vật chồng chéo

**Gốc rễ nằm ở prompt tự mâu thuẫn.** `COMPOSITIONS` nói *"filling the frame
edge to edge"*, *"densely packed"*, trong khi `DENSITY normal` nói *"clear
white space, uncluttered"*. Hai chỉ dẫn đánh nhau thì Flux chọn bừa.

Bản trước tôi viết `COMPOSITIONS` cho `density=rich` (lúc đó đang chữa bệnh
trang trống hoác), rồi quên rằng nó cũng áp cho `normal`.

Tách lại vai trò cho sạch:

| Trục | Lo việc gì |
|---|---|
| `COMPOSITIONS` | GÓC NHÌN và BỐ TRÍ — centered, wide, close-up, symmetrical |
| `DENSITY` | MẬT ĐỘ — bao nhiêu thứ trên trang |

Có kiểm thử chặn: `COMPOSITIONS` chứa chữ *filling / densely / packed /
edge to edge* là test đỏ.

`DENSITY normal` viết lại cho sách trẻ em:
```
one clear main subject filling most of the page,
only two or three large simple background elements,
each object well separated with clear white space between them,
main subject clearly standing apart from the background,
uncluttered composition, nothing overlapping the main subject
```

---

## 2. Đường nét không đồng đều, đứt đoạn, mỏng

Đo trước khi sửa: cả trang chỉ có **4 đầu mút**. Nét gần như không đứt — cái
Bao cảm nhận là **gợn sóng và dày mỏng không đều**, viền lồi lõm.

Nguyên nhân: nét sinh ra dày ~3 px ở 928 px, phóng **2.34 lần** lên 2175 px
để in. Mọi gợn ở mức pixel bị khuếch đại thành cục.

Ba chỗ sửa, cộng dồn:

**a. Nâng độ phân giải sinh ảnh: 928×1920 → 1392×1920**

Nét dày ~4-5 px, chỉ còn phóng **1.56 lần**. Đây là đòn đánh vào gốc rễ.
Đổi lại số pixel gấp 2.25 lần nên mỗi ảnh lâu hơn khoảng gấp đôi.

GPU không chịu nổi thì hạ lại trong `.env`:
```
STUDIO_GEN_WIDTH=928
STUDIO_GEN_HEIGHT=1280
```

**b. Làm mịn trước khi khử xám** (`SMOOTH_RADIUS = 2.5`)

Thứ tự quan trọng: **phóng to → làm mịn → khử xám → nối khe hở**.

Làm mịn phải SAU khi phóng, vì cái gợn chỉ lộ ra ở khổ lớn. Làm trước khi
phóng thì phóng xong nó lồi lõm y như cũ.

**c. Nối khe hở bằng phép đóng hình thái** (`CLOSE_GAPS = 3`)

Giãn nét rồi co lại. Nối được chỗ đứt nhỏ mà không làm nét dày thêm.

**d. Prompt** — thêm đúng chữ Bao đề nghị:
```
thick clean outlines, bold continuous lines, no thin details,
uniform line weight throughout
```
và vào NEGATIVE: `thin faint lines, sketchy lines, broken lines`.

---

## 4. Yếu tố lạ hoặc đáng sợ với trẻ

Thêm `AUDIENCE_EXTRA["kids"]` vào chỉ dẫn gửi cho model sinh chủ thể:

```
- Exactly ONE main character. At most one small companion. Never a crowd.
- Characters must never overlap or hide each other.
- Show the whole animal. Never cut off a tail, a leg or a wing.
- No frightening animals. No bats, wolves, spiders, snakes, owls at night.
- No ornate frames, no decorative borders, no swirling patterns.
- Keep the scene sensible. Do not put objects where they do not belong.
```

Câu cuối là để chặn kiểu "cây thông Noel treo lơ lửng giữa rừng".

Và `lint_for_kids()` soi các file theme đã có. Chạy lên `themes/` bắt đúng
những gì Bao chê:

```
animals-in-forest  4. an owl perched in a tree branch, bats flying above
                       -> con vật có thể làm trẻ sợ (bats)
                   8. a wolf looking out over snow-covered trees
                       -> con vật có thể làm trẻ sợ (wolf)
forest-animals     a wolf howling on a rock  -> con vật có thể làm trẻ sợ
                   bats hanging from a branch -> con vật có thể làm trẻ sợ
```

Đã sửa hết thành puppy, koala, owl ban ngày.

### Hai báo động giả phải sửa regex

- `monster\w*` khớp luôn **monstera** (cây trầu bà) trong `floral.txt`
- `swirl\w*` khớp **swirling water** trong `ocean.txt` — đó là chuyển động
  thật, không phải hoa văn

Đổi sang biên từ chặt: `monsters?\b`, và hoa văn phải đi kèm danh từ
(`swirling pattern`, `decorative border`).

### Đếm nhân vật: đếm mạo từ, không đếm dấu phẩy

Thử đếm dấu phẩy trước, không ăn thua:

```
"a deer, a fawn, a sheep, a fox and a rabbit in a meadow"
   -> chỉ 3 dấu phẩy, nhưng 5 con vật
```

Đổi sang đếm mạo từ `a` / `an`. Câu trên ra 6 đối tượng, quá 4 là cảnh báo.
Cách này bắt đúng, và chạy trên `themes/` thật thì các bộ hợp lệ đều ở mức
1-3 đối tượng.

**Nó bắt luôn một dòng tôi tự viết** trong `giang-sinh.txt`:
*"a little girl hugging a teddy bear on a wooden bench, paper lanterns
hanging from a branch above, a wreath leaning against the bench"* — 5 đối
tượng. Đúng là hơi rối cho trẻ 3-7 tuổi. Đã rút gọn.

---

## 5. Giải phẫu lệch, đuôi chân bị cắt cụt

Vào `COMPLEXITY`:
```
whole subject fully visible, nothing cut off at the edges,
simple natural pose
```
Vào NEGATIVE: `cropped limbs, cut off at the edge`.

Và luật cho model sinh chủ thể: *"Show the whole animal. Never cut off a
tail, a leg or a wing."*

---

## 6. Không phân biệt được chính và phụ

Vào `DENSITY normal`:
```
main subject clearly standing apart from the background,
nothing overlapping the main subject
```

Vào `COMPLEXITY simple`:
```
no fur texture, no small leaves
```
— hai thứ này chính là chỗ nét nền dày ngang nét nhân vật.

---

## Đổi luôn độ tuổi: 4-8 → 3-7

Theo đúng con số Bao nói. Ảnh hưởng cả `AUDIENCE["kids"]` lẫn
`COMPLEXITY["simple"]`.

---

## Kiểm thử

Thêm mục `[10]` và `[11]`. Đáng chú ý:

- Sáu ca cho `lint_for_kids`, gồm **hai ca báo động giả** (monstera,
  swirling water) làm kiểm thử hồi quy
- Quét toàn bộ `themes/*.txt` phải đạt tiêu chuẩn trẻ em
- Chặn `COMPOSITIONS` nói về mật độ — chính lỗi prompt tự mâu thuẫn ở trên

88/88 đạt.

---

## Việc tiếp theo cho Bao

Ảnh cũ sinh bằng prompt cũ, không cứu được:

```bash
rm -rf library/giang-sinh
python studio.py generate "Giáng sinh của bé" --theme giang-sinh --count 4 \
    --complexity simple --density normal
```

Chạy 4 ảnh xem trước, vì **độ phân giải mới lâu hơn gấp đôi** — thử trước rồi
mới chạy 60.

Cần thấy: nét dày và đều hơn, viền bớt lồi lõm, ít chi tiết li ti, mỗi trang
một nhân vật chính rõ ràng, không con vật nào bị cắt cụt.

Nếu GPU không kham nổi 1392×1920, hạ lại trong `.env` — lúc đó phần làm mịn
và nối khe hở vẫn còn tác dụng, chỉ là ít hơn.
