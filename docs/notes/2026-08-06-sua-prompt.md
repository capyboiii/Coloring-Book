# Ghi chép — Sửa prompt sau mẻ ảnh đầu tiên

**Ngày:** 2026-08-06
**Nhánh:** `feat/phase-1-pipeline`
**Kích hoạt bởi:** Bao chạy `generate "đại dương" --count 4`, ảnh ra xấu.

---

## Chẩn đoán

Không đoán. Mở thẳng 4 ảnh trong `library/dai-duong/raw/` ra xem, và đọc
`.json` đi kèm để biết prompt thật đã chạy.

### Ảnh ra thế nào

| Ảnh | Thực tế |
|---|---|
| 001 | Bó hoa lá. **Không có gì liên quan đại dương.** Nét mảnh như sợi tóc. 40% trang trên trống trơn |
| 002 | Cảnh vườn/sa mạc có cây hoa. Vẫn không phải biển. **45% trang trên trống** |

### Prompt thật đã chạy

```
black and white line art coloring book page, clean bold uniform outlines,
pure white background, no shading, no grayscale, no hatching, no cross-hatching,
no color, high contrast, crisp vector-like linework, moderate detail,
balanced open areas and pattern, consistent medium line weight,
đại dương,
```

### Đối chứng: prompt của Bao chạy tay thì đẹp

Trong `ComfyUI/output/ocean/` có ảnh con rùa biển **rất đẹp** — nét dày, chủ đề
rõ, dễ thương. ComfyUI nhúng workflow vào metadata file PNG nên đọc lại được
nguyên văn prompt đã dùng:

```
coloring book page for children, black and white line art,
clean bold uniform outlines, thick even line weight,
no shading, no grayscale, no color fill, no texture,
pure white background, simple cute cartoon style,
centered full-page composition,
a smiling sea turtle swimming, a few round bubbles around it
```

Có bản đối chứng thì việc chẩn đoán thành ra dễ.

---

## Ba nguyên nhân

### 1. Chủ thể viết bằng tiếng Việt — nguyên nhân nặng nhất

`đại dương` lọt thẳng vào prompt. Flux/T5 chỉ hiểu tiếng Anh. Nó **không báo
lỗi**, chỉ lặng lẽ bỏ qua chuỗi đó rồi vẽ theo phần style còn lại — mà phần
style thì trung tính, nên nó rơi về thứ Flux vẽ nhiều nhất: hoa lá.

Đây là lỗi do tôi thiết kế sai. Tôi có ghi "viết bằng tiếng Anh" trong file
`subjects.example.txt`, nhưng `topic` truyền qua CLI thì đi thẳng vào prompt
không qua kiểm tra nào.

### 2. Từ tả nét quá yếu

| Prompt của tôi | Prompt chạy tốt |
|---|---|
| `consistent medium line weight` | **`thick even line weight`** |
| `crisp vector-like linework` | **`simple cute cartoon style`** |

"medium" và "vector-like" đẩy Flux về phía nét mảnh. In 300 DPI là mất nét.

### 3. Bố cục tự chống lại mình

Danh sách `ARRANGEMENTS` cũ có:

- `"with generous negative space around the subject"`
- `"balanced open areas and pattern"`

Đây **chính là** thứ đẻ ra mấy ảnh trống hơn nửa trang. Khách mua sách tô màu
là mua diện tích tô được — chừa trắng nửa trang là tự bắn vào chân mình.

---

## Đã sửa gì

### `studio/prompts.py` — viết lại khung prompt

`BASE_STYLE` mới bám sát prompt đã chứng minh là chạy tốt:

```
coloring book page, black and white line art,
clean bold uniform outlines, thick even line weight,
no shading, no grayscale, no color fill, no texture,
pure white background
```

`COMPLEXITY` — cả ba mức đều giữ chữ "thick", kể cả mức `detailed`:

| Mức | Chuỗi |
|---|---|
| simple | `simple cute cartoon style, very thick bold outlines, large open areas...` |
| medium | `simple clean cartoon style, thick even outlines, moderate detail` |
| detailed | `decorative illustration style, thick clear outlines, intricate ornamental detail...` |

`COMPOSITIONS` — mọi mục đều nói "full-page" hoặc "filling". Bỏ sạch
`ARRANGEMENTS` có chữ negative space, thay bằng `EXTRAS` chỉ thêm phụ kiện.

`EXTRAS` chỉ áp dụng khi chủ thể **chưa có dấu phẩy**. Chủ thể kiểu
`"a smiling sea turtle swimming, a few round bubbles around it"` đã tự mang
mệnh đề phụ rồi, nối thêm nữa thành thừa và làm loãng prompt.

### Bốn bộ chủ thể dựng sẵn — `themes/`

| Bộ | Số chủ thể | Hợp với |
|---|---|---|
| `ocean` | 24 | `--complexity medium` |
| `mandala` | 24 | `--complexity detailed`, sách người lớn |
| `floral` | 24 | `--complexity detailed` — Flux vẽ hoa giỏi nhất |
| `forest-animals` | 24 | `--complexity simple`, sách trẻ em |

Mọi chủ thể viết theo đúng mẫu đã chứng minh: **chủ thể + hành động + một chi
tiết phụ**, bằng tiếng Anh.

```
a smiling sea turtle swimming, a few round bubbles around it
```

`--theme` nhận cả tên bộ dựng sẵn lẫn đường dẫn file. Thêm `--list-themes`.

### `generate` chặn tiếng Việt

Chủ đề có ký tự ngoài ASCII mà không có `--theme` thì **dừng luôn**, kèm bốn
cách sửa cụ thể. Chặn ở đây rẻ hơn nhiều so với để chạy hết 40 lượt GPU rồi
mới biết hỏng. Có `--force` cho ai vẫn muốn chạy.

Nếu có `--theme` mà trong file có chủ thể tiếng Việt thì chỉ cảnh báo, không chặn.

Không có `--theme` cũng cảnh báo: cả 40 ảnh dùng chung một chủ thể thì tỷ lệ
giữ lại sẽ rất thấp.

### Ghi thêm vào `book.json`

Lưu `theme` và `subject_count` để sau truy lại được mẻ ảnh này sinh từ bộ nào.

---

## Prompt trước và sau

**Trước** (ra bó hoa):

```
black and white line art coloring book page, clean bold uniform outlines,
pure white background, ... moderate detail, balanced open areas and pattern,
consistent medium line weight, đại dương
```

**Sau** (`--theme ocean`):

```
coloring book page, black and white line art, clean bold uniform outlines,
thick even line weight, no shading, no grayscale, no color fill, no texture,
pure white background, simple clean cartoon style, thick even outlines,
moderate detail, centered full-page composition,
a smiling sea turtle swimming, a few round bubbles around it
```

Câu thứ hai gần như trùng khít với prompt đã cho ra ảnh đẹp.

---

## Bài học

**ComfyUI nhúng nguyên workflow vào metadata file PNG.** Bất cứ lúc nào có một
ảnh đẹp, đọc metadata ra là lấy được prompt. Đây là cách gỡ lỗi rẻ nhất và
chính xác nhất — hơn hẳn ngồi đoán rồi thử.

```python
from PIL import Image; import json
print(json.loads(Image.open('anh.png').info['prompt']))
```

**Và: đọc ảnh trước khi sửa prompt.** Nếu chỉ nghe "ảnh xấu úa" rồi viết lại
prompt theo cảm tính thì đã bỏ sót nguyên nhân thật là cái chuỗi tiếng Việt.

---

## Việc tiếp theo cho Bao

```bash
python studio.py generate "Đại dương kỳ thú" --theme ocean --count 4
```

Chạy 4 ảnh xem trước. Ưng thì `--count 40`.

Nếu nét vẫn mảnh, thử theo thứ tự này:

1. `--complexity simple` — chuỗi "very thick bold outlines"
2. Nâng `STUDIO_STEPS` lên 6–8 (schnell chịu được, quá 8 thì kém đi)
3. Hạ `LEVELS_BLACK` trong `config.py` từ 80 xuống ~110 để nét đen đậm hơn khi in
4. Sửa `BASE_STYLE` trong `studio/prompts.py`

**Đừng đổi sang FLUX.1-dev** — vướng giấy phép thương mại.
