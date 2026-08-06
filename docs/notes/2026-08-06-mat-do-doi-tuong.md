# Ghi chép — Ép ảnh có nhiều đối tượng hơn

**Ngày:** 2026-08-06
**Nhánh:** `feat/phase-1-pipeline`
**Kích hoạt bởi:** sau khi sửa prompt lần một, ảnh đã đúng chủ đề và nét đã dày,
nhưng nhiều trang chỉ có một đối tượng nằm giữa khoảng trắng mênh mông
(ví dụ: cụm sứa chiếm ~40% trang, còn lại trống).

---

## Vì sao chuyện này quan trọng

Khách mua sách tô màu là mua **diện tích tô được**. Một trang chỉ có con sứa ở
giữa thì tô 5 phút là xong, cảm giác bị hớ. Đây không phải chuyện thẩm mỹ —
nó là chuyện giá trị sản phẩm.

---

## Ba nguyên nhân

### 1. Chủ thể trong `themes/*.txt` viết như một VẬT, không phải một CẢNH

```
a cluster of round jellyfish drifting upward
```

Câu này mô tả đúng một thứ. Flux vẽ đúng một thứ. Không sai — chỉ là thiếu.

Đây là đòn bẩy lớn nhất. Prompt chung không cứu được một chủ thể viết cụt lủn.

### 2. `"pure white background"` trong `BASE_STYLE` phản tác dụng

Chuỗi này lấy từ prompt gốc đã chạy tốt, mục đích là chặn nền xám. Nhưng Flux
đọc nó thành **"nền để trống"**. Nó vừa chống nền xám vừa chống luôn cả nội
dung nền.

Mà việc chặn nền xám thì bước khử xám trong `imageops.py` đã lo rồi — levels ép
mọi giá trị ≥200 về trắng tinh. Nói lại trong prompt là thừa, và ở đây còn hại.

### 3. Không có cách nào điều chỉnh mật độ

`--complexity` chỉ nói về độ tinh xảo của **nét**, không nói gì về **số lượng
đối tượng**. Hai chuyện khác nhau mà chỉ có một nút vặn.

---

## Đã sửa gì

### Thêm trục `--density`

Tách hẳn khỏi `--complexity`:

| Trục | Điều khiển | Giá trị |
|---|---|---|
| `--complexity` | nét vẽ tinh xảo tới đâu | simple / medium / **detailed** |
| `--density` | trang có bao nhiêu thứ để tô | single / normal / **rich** (mặc định) |

```python
DENSITY = {
    "single": "single subject, plain white background, no background elements",
    "normal": "with several background elements around the subject",
    "rich":   "a rich detailed scene filling the entire page, "
              "many different elements throughout the composition, "
              "background filled with additional details, "
              "no large empty white areas, "
              "elements reaching the top and bottom edges of the page",
}
```

Mặc định `rich`. Sách trẻ em nên là `--complexity simple --density rich`:
nét to dễ tô, nhưng trang vẫn đầy.

`DENSITY` thay chỗ `EXTRAS` cũ — trong `EXTRAS` có mục
`"with no background, subject only"` đang trực tiếp chống lại mục tiêu này.

### Sửa `BASE_STYLE`

```diff
- pure white background
+ white paper, unshaded
```

Giữ được ý "không tô màu, không đổ bóng" mà bỏ hàm ý "để trống".

> Đây là chỗ **đi chệch khỏi prompt gốc đã chứng minh**. Cần xác nhận bằng ảnh
> thật. Nếu nền bắt đầu ra xám thì quay lại chuỗi cũ và bù bằng `--density`.

### `COMPOSITIONS` mạnh tay hơn

| Cũ | Mới |
|---|---|
| `centered full-page composition` | `full-page scene filling the frame edge to edge` |
| `close-up view filling the whole page` | `densely packed composition filling every corner` |
| `full page scene, subject large and centered` | `busy full-page composition, elements from top to bottom` |

Bỏ hẳn chữ "centered" và "subject" — hai chữ này kéo Flux về phía một-vật-ở-giữa.

### `NEGATIVE` thêm ba cụm

`empty space, blank margins, single isolated object`

(Flux không dùng negative prompt, nhưng vẫn ghi vào metadata phòng khi đổi sang SDXL.)

### Viết lại toàn bộ `themes/*.txt` thành cảnh

Mỗi dòng giờ có **nhân vật chính + hành động + 2-3 thứ lấp phần còn lại**:

```
Trước: a cluster of round jellyfish drifting upward

Sau:   a cluster of round jellyfish drifting upward,
       bubbles rising all around them,
       coral reef and swaying seaweed below
```

Làm cho `ocean`, `forest-animals`, `floral` — 24 cảnh mỗi bộ.

**`mandala` giữ nguyên**, và thêm cảnh báo: mandala vốn đã đối xứng và lấp kín
trang, `--density rich` sẽ phá đối xứng ra một mớ hỗn độn. `generate` tự cảnh
báo nếu ai đó chạy `--theme mandala --density rich`.

---

## Rủi ro

Schnell chỉ chạy 4 bước. Nhồi quá nhiều đối tượng vào một prompt có thể làm ảnh
ra rối và nát nét, đúng cái vừa sửa xong ở lần trước.

Nếu gặp: hạ xuống `--density normal`, hoặc nâng `STUDIO_STEPS` lên 6–8.

**Chạy `--count 4` xem trước rồi mới chạy 40.**

---

## Việc tiếp theo cho Bao

```bash
python studio.py generate "Đại dương kỳ thú" --theme ocean --count 4 --overwrite
```

Cần `--overwrite` vì thư mục đã có 4 ảnh cũ.

So với ảnh cũ. Ba câu hỏi:

1. Trang có đầy hơn không?
2. Nét có còn dày không, hay đã bắt đầu nát?
3. Nền có bị xám trở lại không? (do đổi `pure white background`)

Câu 2 và 3 là hai rủi ro của lần sửa này. Nếu dính, ghi lại rồi bảo tôi.
