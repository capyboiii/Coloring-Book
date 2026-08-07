# Ghi chép — Lấy sách mẫu làm chuẩn, thêm trục phong cách

**Ngày:** 2026-08-07
**Nhánh:** `feat/phase-1-pipeline`
**Chuẩn chất lượng:** [`docs/mau/chuan-chat-luong.png`](../mau/chuan-chat-luong.png)

Bao đưa một cuốn sách tô màu thương mại làm chuẩn: *"tôi chỉ yêu cầu chất
lượng hình ảnh ngang cái ảnh tôi đính kèm đó"*.

Có một cái mốc cụ thể thay đổi hẳn cách sửa. Trước đó tôi chỉ đang chữa từng
triệu chứng.

---

## Ảnh mẫu khác ảnh của mình ở đâu

Nhìn kỹ thì nó không phải "cartoon" chung chung mà là **một phong cách rất cụ
thể**:

| Đặc điểm | Ảnh mẫu | Ảnh mình đang ra |
|---|---|---|
| Nhân vật | Đầu tròn to, thân nhỏ, mắt chấm, miệng một nét cong | Tỉ lệ thực hơn, mặt nhiều chi tiết |
| Đồ vật | Vẽ như **icon phẳng** — quả dứa là hình bầu dục kẻ ô + lá | Vẽ như minh hoạ chi tiết |
| Nét | Đều tăm tắp, từ nhân vật tới nền | Chỗ dày chỗ mỏng, lông lá có texture |
| Mật độ | **Nhiều** đồ vật, nhưng mỗi món TO và tách nhau rõ | Đồ nhỏ li ti, dính chùm |
| Nền | Một đường chân trời, vài mảng lớn | Cỏ, đá, bướm, hoa li ti khắp nơi |

Điểm thứ tư đáng chú ý: **trang mẫu không hề ít đồ**. Cảnh picnic có dứa,
chuối, kem, bóng, đàn ukulele. Cái sai của mình không phải "nhiều đồ" mà là
**đồ nhỏ và dính vào nhau**.

Tên của phong cách đó là **kawaii / chibi**. Prompt của mình chỉ nói
`"simple cute cartoon style"` — quá mơ hồ nên Flux tự do diễn giải.

---

## Thêm trục thứ ba: `style`

Trước có hai trục, giờ ba, và chúng thật sự độc lập:

| Trục | Lo việc gì | Giá trị |
|---|---|---|
| `style` | Vẽ theo **lối** nào | kawaii · cartoon · decorative |
| `complexity` | **Nhiều hay ít** chi tiết | simple · medium · detailed |
| `density` | Trang có **bao nhiêu thứ** | single · normal · rich |

`STYLE["kawaii"]` tả đúng ảnh mẫu:

```
kawaii chibi style, big round head and small rounded body,
simple dot eyes and one small curved smile,
every object drawn as a simple flat icon,
no fur texture, no hatching, no stippling,
characters facing forward in a relaxed pose
```

Chuỗi `every object drawn as a simple flat icon` là chuỗi ăn tiền nhất — nó
chặn đúng cái bệnh vẽ quả dứa thành hình minh hoạ thực vật.

Sách trẻ em: `--style kawaii --complexity simple --density normal`.
Mandala người lớn: `--style decorative --complexity detailed --density normal`.

---

## Bài học: prompt dài không phải prompt mạnh

Thêm `STYLE` xong, in prompt ra thì nó dài **180 từ** và độ dày nét bị nhắc ở
**cả bốn khối**:

```
BASE       "thick clean outlines, bold continuous lines, no thin details"
BASE       "uniform line weight throughout"
STYLE      "even consistent line weight everywhere"
COMPLEXITY "thick clean rounded outlines"
```

Chủ thể — thứ quan trọng nhất — nằm chìm ở giữa đống lặp đó.

Phân lại vai cho sạch, mỗi ý chỉ nói **đúng một lần**:

| Khối | Chỉ được nói về |
|---|---|
| `BASE_STYLE` | Thứ không bao giờ đổi: là line art, chưa tô màu, nét khép kín |
| `STYLE` | Phong cách vẽ |
| `COMPLEXITY` | Mức độ chi tiết |
| `DENSITY` | Bố trí trên trang |

180 từ → **148 từ**, và mỗi cụm chỉ xuất hiện một lần.

Có kiểm thử chặn: prompt quá 180 từ hoặc lặp cụm là test đỏ. Ràng buộc này sẽ
còn giá trị mỗi lần ai đó muốn "thêm một chuỗi nữa cho chắc" — chính là cách
tôi đã làm hỏng nó lần này.

---

## Một điều thành thật về giới hạn

Ảnh mẫu có **dàn nhân vật nhất quán** — vẫn con mèo đó, con thỏ đó, cô bé đó,
xuyên suốt cả cuốn. Đó là dấu hiệu của một cuốn sách được thiết kế, không phải
gom nhặt.

**Flux không làm được chuyện này bằng prompt.** Mỗi ảnh sinh độc lập nên nhân
vật sẽ khác nhau từng trang. Muốn nhất quán thì cần LoRA huấn luyện riêng hoặc
IP-Adapter tham chiếu một ảnh nhân vật — cả hai đều ngoài phạm vi Phase 1.

Nói ra để đừng kỳ vọng nhầm: sau lần sửa này ảnh sẽ **giống ảnh mẫu về phong
cách và độ sạch của nét**, nhưng **chưa giống về tính nhất quán nhân vật**.

---

## Kiểm thử

Thêm mục `[12]`:

```
✓ Prompt dưới 180 từ (dài quá thì chủ thể bị chìm) — 148 từ
✓ 'line weight' chỉ xuất hiện 1 lần
✓ 'no shading' chỉ xuất hiện 1 lần
✓ 'texture' chỉ xuất hiện 1 lần
✓ 'uncolored' chỉ xuất hiện 1 lần
✓ Chủ thể có mặt trong prompt
✓ Có phong cách kawaii làm mặc định cho sách trẻ em
```

99/99 đạt.

---

## Việc tiếp theo cho Bao

```bash
rm -rf library/giang-sinh
python studio.py generate "Giáng sinh của bé" --theme giang-sinh --count 4 \
    --style kawaii --complexity simple --density normal
```

Bốn ảnh thôi, vì độ phân giải mới lâu gấp đôi.

So với ảnh mẫu, cần thấy: đầu tròn to mắt chấm, đồ vật vẽ như icon phẳng, nét
đều, không còn cỏ đá bướm li ti.

Chưa đạt thì chỉnh thẳng `STYLE["kawaii"]` trong `studio/prompts.py` — nó là
một chuỗi văn bản, sửa xong chạy lại là thấy ngay. Nhưng **giữ nguyên tắc mỗi
ý nói một lần**, đừng nối thêm chuỗi cho chắc; đó chính là cách prompt phình
lên 180 từ.
