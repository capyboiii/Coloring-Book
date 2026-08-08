# Dùng LoRA line art

Code đã sẵn sàng. Việc còn lại là **chọn LoRA** — phần đó tôi không làm hộ được,
và dưới đây nói rõ vì sao.

---

## Vì sao LoRA mới là thứ ăn thua

Ta đã thử gần hết những cách khác và đo được kết quả:

| Cách | Kết quả đo |
|---|---|
| Sửa prompt (nhiều vòng) | Cải thiện rồi chững lại |
| Nâng độ phân giải | **Tệ đi** — ra ngoài vùng model quen |
| Đổi sang SDXL base | **Tệ đi** — xám 20%→30%, quầng 14%→45% |
| Vector hoá sau xử lý | Nhẹ — xám 5.6%→4.1% |

Lý do chung: **prompt chỉ hướng model, không dạy được model.** SDXL base chưa
bao giờ được huấn luyện để vẽ line art sách tô màu, nên bảo gì nó cũng vẽ theo
kiểu minh hoạ có sắc độ.

LoRA thì khác — nó **huấn luyện lại một phần trọng số** cho đúng phong cách đó.
Đây là công cụ duy nhất ta chưa dùng mà thật sự thay đổi được model.

---

## Vì sao tôi không chọn hộ được

Ba lý do thật:

1. **Tôi không tải và xem được LoRA.** Chất lượng chỉ biết khi chạy thử.
2. **Giấy phép mỗi bộ một khác.** Trang Civitai nào cũng có mục *Permissions*.
   Có bộ ghi rõ *"no commercial use"* — dùng cho sách bán là vi phạm. Đây là
   thứ ông phải tự đọc, không nên tin bên thứ ba.
3. Danh sách "LoRA tốt nhất" thay đổi liên tục.

Cái tôi làm được là **dựng sẵn chỗ cắm và bộ đo**, để ông thử vài bộ rồi so
bằng số thay vì bằng cảm giác.

---

## Cách chọn

Trên [civitai.com](https://civitai.com), lọc **Base model: SDXL 1.0**, tìm:

```
coloring book    lineart    line art    coloring page    kids coloring
```

Xem ba thứ, theo thứ tự:

1. **Permissions** — phải cho phép dùng thương mại
2. **Ảnh mẫu** — nét có dày và đều không, có bị xám không
3. **Trigger words** — có bộ cần từ khoá riêng trong prompt mới ăn.
   Nếu có, thêm vào đầu `BASE_STYLE` trong `studio/prompts.py`.

Tải file `.safetensors` bỏ vào `ComfyUI/models/loras/`.

---

## Cách dùng

Trong công thức sách, `books/<slug>.yaml`:

```yaml
lora: coloring-book-lineart-sdxl.safetensors
lora_strength: 0.9    # 0.6-1.0
```

Hoặc thử nhanh không cần công thức:

```bash
python studio.py generate "Khủng long" --theme khung-long --count 4 \
    --slug thu-lora --lora ten-file.safetensors --lora-strength 0.9 \
    --style kawaii --complexity simple --density normal
```

**Để trống `lora` thì studio tự gỡ node `LoraLoader` ra** và nối thẳng
checkpoint vào sampler. Không cần giữ hai file workflow gần giống nhau — sửa
một cái là quên sửa cái kia.

---

## Chỉnh strength

`lora_strength` là nút vặn quan trọng nhất sau khi đã chọn được LoRA:

| Giá trị | Hiện tượng |
|---|---|
| 0.5 – 0.7 | LoRA ảnh hưởng nhẹ, giữ được nhiều đặc tính model gốc |
| **0.8 – 1.0** | Khoảng thường dùng |
| trên 1.0 | LoRA lấn át, chủ thể bắt đầu biến dạng và mọi trang na ná nhau |

Thử 0.7 / 0.9 / 1.0 vào ba slug khác nhau rồi đo.

---

## Đo, đừng đoán

Đây là điểm quan trọng nhất của cả tài liệu này.

```bash
python studio.py generate "Khủng long" --theme khung-long --count 4 \
    --slug lora-07 --lora <file> --lora-strength 0.7 \
    --style kawaii --complexity simple --density normal

python studio.py generate "Khủng long" --theme khung-long --count 4 \
    --slug lora-09 --lora <file> --lora-strength 0.9 \
    --style kawaii --complexity simple --density normal

python studio.py measure lora-07 --vs lora-09
```

Mốc để so — đây là số đo thật của Flux hiện tại:

| | Flux Q4 @832 | SDXL base @832 |
|---|---|---|
| mực xám | 20% | 30% |
| quầng mờ | 14% | 45% |
| mảnh rời | 39 | 87 |

**SDXL + LoRA phải thắng cả hai cột này thì mới đáng đổi.** Nếu không thắng,
quay lại Flux — đổi hai dòng trong `.env`, không mất gì.

Ghi kết quả vào bảng cuối
[thu-nghiem-chat-luong-net.md](thu-nghiem-chat-luong-net.md).

---

## Nếu LoRA cũng không đủ

Nói trước cho khỏi kỳ vọng nhầm.

Cuốn sách mẫu ông đưa — 48 trang nét vector, dàn nhân vật nhất quán — nhiều
khả năng **không phải AI thuần**. Nó có dấu hiệu của AI vẽ rồi người dọn lại
bằng phần mềm vector, hoặc hoạ sĩ vẽ tay.

Nếu qua vài LoRA mà vẫn chưa tới, thì lựa chọn thật sự là:

- **Chấp nhận mức hiện tại** và bán ở phân khúc thấp hơn
- **Dọn tay** vài trang đẹp nhất trong Inkscape, dùng làm trang mẫu và bìa
- **Thuê hoạ sĩ** vẽ 40 trang cho cuốn đầu, dùng AI cho các cuốn sau

Cả ba đều là lựa chọn hợp lý. Đuổi bằng được độ sạch của sách vector chỉ bằng
model local có thể là mục tiêu không tới được, và biết điều đó sớm thì đỡ tốn
thời gian hơn.
