# Coloring Book Studio

Công cụ tạo sách tô màu bằng Flux (ComfyUI local) và xuất file in đúng chuẩn Lulu.

Đây là **Phase 1** của [roadmap](docs/roadmap.md) — phủ ba bước đầu trong năm bước:

```
① TẠO  →  ② DUYỆT  →  ③ DỰNG  →  ④ ĐĂNG  →  ⑤ BÁN
generate   xoá tay     build      chưa làm    chưa làm
           + approve
```

Cả cuốn sách — ruột, bìa, và gói bàn giao cho web — ra từ **một công thức**:

```bash
python studio.py make dai-duong-ky-thu --init   # tạo books/dai-duong-ky-thu.yaml
#   ... sửa công thức: chủ đề, số trang, giá ...
python studio.py make dai-duong-ky-thu          # lần 1: sinh ảnh
#   ... mở raw/ xoá ảnh xấu, bấm giờ ...
python studio.py make dai-duong-ky-thu --minutes 95   # lần 2: dựng sách
```

Chủ đề mới thì thêm một lệnh ở đầu để sinh bộ chủ thể:

```bash
python studio.py subjects "Giáng sinh" --count 24 --audience kids
```

---

## Công thức sách

Một file YAML trong [`books/`](books/) ghi hết mọi thứ cần để ra một cuốn:

```yaml
title: "Đại dương kỳ thú"
subtitle: "40 trang tô màu cho mọi lứa tuổi"

theme: ocean          # bộ chủ thể trong themes/
pages: 40             # số hình trong sách
generate: 60          # sinh dư để còn chỗ loại
complexity: medium    # độ tinh xảo của NÉT
density: rich         # số ĐỐI TƯỢNG mỗi trang
seed:                 # điền số để sinh lại y hệt

cover:
  bg: "#1B7A8C"

collection: relaxation
price_usd: 14.99
tags: [ocean, animals, relaxation]
description: |
  Mô tả bán hàng...
```

**Vì sao cần:** trước đây mọi tham số nằm rải trong lệnh gõ tay. Ba tuần sau
muốn in lại đúng cuốn cũ thì không nhớ đã chạy `--complexity` gì, `--density`
gì. Ghi vào file thì tái tạo được, sửa được, và **commit vào git được**.

Công thức bị kiểm tra trước khi chạy — sai `complexity`, sai mã màu, hay
`generate` ít hơn `pages` là báo lỗi ngay chứ không đợi gen xong 60 ảnh.

### `make` chạy tiếp được

Nó nhìn thư mục sách đang ở bước nào rồi làm bước kế tiếp:

| Trạng thái | `make` làm gì |
|---|---|
| `cần sinh ảnh` | Sinh ảnh + ảnh bìa, rồi **dừng** để ông duyệt |
| `cần duyệt` | Chép ảnh còn lại, dựng ruột + bìa + gói bán |
| `xong` | Báo đã xong. `--force` để dựng lại |

Không có cách nào gộp thành đúng một lần chạy, vì ở giữa có bước duyệt bằng
mắt người — và đó là bước **cố tình** giữ lại. `--yes` bỏ qua bước duyệt, chỉ
nên dùng khi chạy thử.

### Gói bàn giao cho web

`make` xuất ra `library/<slug>/out/book.json` — đây là **ranh giới giữa studio
và cửa hàng**. Web chỉ đọc file này, không cần biết Flux hay ComfyUI là gì:

```json
{
  "slug": "dai-duong-ky-thu",
  "title": "Đại dương kỳ thú",
  "price_usd": 14.99,
  "collection": "relaxation",
  "art_pages": 40,
  "print": { "spine_in": 0.24, "cover_in": [17.49, 11.25] },
  "files": {
    "interior": "interior.pdf",      // ⚠ KHÔNG để public
    "cover": "cover.pdf",            // ⚠ gửi nhà in
    "preview": "preview.pdf",        // phát tự do
    "cover_image": "web/cover.webp",
    "preview_images": ["web/page-01.webp", "..."]
  },
  "source": { "theme": "ocean", "seed": null, "retention_rate": 0.63 }
}
```

`source` giữ lại tham số đã dùng và hai con số đo được, để sau còn biết cuốn
nào ra từ công thức nào.

`generate` vẽ luôn ảnh bìa màu cùng lúc với các trang ruột. `build` ghép nó
thành `cover.pdf` hoàn chỉnh. Không cần lệnh bìa riêng.

---

## Cài đặt

Cần Python 3.10+ và một ComfyUI đang chạy có model Flux
(xem [Model và workflow](#model-và-workflow-comfyui)).

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

### ⓪ Sinh bộ chủ thể cho chủ đề mới

Bốn bộ dựng sẵn (`ocean`, `mandala`, `floral`, `forest-animals`) là file văn
bản viết tay. Chủ đề nằm ngoài bốn cái đó thì để **model local trong LM Studio**
viết:

```bash
python studio.py subjects "Giáng sinh" --count 24 --audience kids
# → themes/giang-sinh.txt
```

**Chuẩn bị:** bật LM Studio → tab **Developer** → nạp model (Qwen3.5 9B) →
**Start Server**. Không cần API key, không tốn tiền, không gửi gì ra ngoài.

```bash
python studio.py subjects --list-models   # xem model nào đang nạp
```

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `--audience kids` | Cảnh vui tươi dễ thương, cho trẻ 4–8 tuổi |
| `--audience adults` | Cảnh tinh xảo nhiều hoạ tiết, sách thư giãn |
| `--dry-run` | In ra xem trước, không ghi file |
| `--model <tên>` | Chọn model cụ thể. Mặc định lấy model đang nạp |
| `--temperature 0.85` | Cao thì đa dạng hơn nhưng dễ lạc đề |
| `--batch 8` | Hỏi bao nhiêu cảnh mỗi lần. Trả rỗng thì hạ xuống 4 |
| `--think` | Bật chế độ suy luận. **Mặc định tắt** |
| `--name <tên>` | Đặt tên bộ khác với slug suy từ chủ đề |

Cổng khác 1234 thì đặt `LMSTUDIO_URL` trong `.env`. **Chỉ lệnh này cần LM
Studio** — mọi lệnh khác không đụng tới.

#### Vì sao mặc định tắt suy luận

Lần chạy đầu với Qwen3.5 9B thất bại thế này:

```json
"content": ""
"reasoning_content": "... Count: A(1) happy(2) Santa(3) Claus(4) ..."
"finish_reason": "length"
"reasoning_tokens": 3999          // trên tổng 4000
```

Model đốt sạch 4000 token vào việc **đếm từ từng chữ một** để kiểm luật *"mỗi
dòng 15–30 từ"*, rồi hết token trước khi kịp viết câu trả lời. Mất 5 phút mỗi
lần gọi và trả về rỗng.

Ba chỗ sửa vì chuyện đó:

1. **Tắt suy luận** — gửi `enable_thinking=false` kèm hậu tố `/no_think`, hai
   cách cùng lúc vì tuỳ phiên bản mà cách nào ăn.
2. **Bỏ luật đếm từ** — chính nó gây ra vòng đếm vô tận. Giờ nói *"một câu,
   khoảng hai mươi từ, đừng đếm"*.
3. **Chia nhỏ** — hỏi 8 cảnh mỗi mẻ thay vì 24. Yêu cầu ngắn thì model nhỏ làm
   chắc tay hơn nhiều, và một mẻ hỏng chỉ mất mẻ đó.

#### Nên dùng model KHÔNG có chế độ suy luận

Việc này chỉ là viết 24 câu tiếng Anh. Model instruct 7–8B làm trong vài giây.
Model suy luận mất 5 phút mỗi mẻ và ra kết quả **tệ hơn**, vì nó dành phần lớn
công sức tranh luận với chính prompt.

Gợi ý: **Qwen2.5-7B-Instruct**, **Llama-3.1-8B-Instruct**, **Mistral-7B-Instruct**.

> **Cảnh báo:** tắt *Reasoning* trong LM Studio chỉ làm nó **ngừng tách trường**
> `reasoning_content` — mô hình vẫn suy luận y như cũ, chỉ khác là nguyên khối
> suy nghĩ giờ nằm lẫn trong `content`. Lệnh có dò dấu hiệu này và **dừng ngay
> ở mẻ đầu** kèm chẩn đoán, thay vì chạy 6 mẻ mất 10 phút rồi ghi ra file rác.

Vẫn muốn giữ model suy luận thì: `--think --max-tokens 8000 --batch 4` — để nó
suy luận xong hẳn rồi mới trả lời. Chậm nhưng sạch.

Kiểm tra trong 10 giây thay vì chờ 10 phút:

```bash
python -c "import requests; r=requests.post('http://localhost:1234/v1/chat/completions', json={'model':'qwen/qwen3.5-9b','messages':[{'role':'user','content':'Say hello in 5 words.'}],'max_tokens':200}).json()['choices'][0]['message']; print('content:', repr(r.get('content'))); print('reasoning:', len(r.get('reasoning_content') or ''), 'ky tu')"
```

Cần thấy `reasoning: 0` **và** `content` bắt đầu thẳng bằng câu trả lời. Nếu
`content` mở đầu bằng `Thinking Process:` thì model vẫn đang suy luận.

#### Lọc kết quả

- **Không vớt nội dung từ `reasoning_content`.** Bản trước có làm, và đó là
  sai lầm: khi mô hình bị cắt trước lúc kịp viết cảnh, thứ vớt được chỉ là ghi
  chú kế hoạch — tức prompt bị nhại lại. Mấy dòng đó bị lưu như cảnh, rồi vòng
  sau đưa lại vào prompt làm danh sách "đã viết", khiến mô hình đọc thấy số đếm
  mâu thuẫn và đốt sạch token để phân vân. Thà hỏng to còn hơn ghi rác vào file.
Lọc theo **hình dạng câu**, không dò danh sách từ khoá — danh sách từ khoá
luôn thiếu, còn hình dạng thì không đổi:

| Luật | Bắt được |
|---|---|
| Có `:` ở bất kỳ đâu | `Formula:` · `Wait, re-reading the prompt:` |
| Có `"` | `Content only (no "line art", ...)` |
| Có `*` sau khi cắt gạch đầu dòng | `**Task:**` · `*Idea 1:*` |
| Có `+` | `subject + action + 2-3 things` |
| Dưới 6 từ | `jellyfish` |
| **Chữ hoa ở đầu dòng** | `One sentence per line...` · `All 8 scenes...` |

Luật cuối mạnh nhất, và đến từ một dòng thêm vào prompt:
`Start every line with a lowercase letter.` Cảnh viết thường, ghi chú luôn viết
hoa. Nếu mô hình phớt lờ luật viết thường (mọi dòng đều hoa) thì bỏ qua luật
này kèm cảnh báo, thay vì xoá sạch.

Cộng thêm: bỏ dòng trùng, bỏ dòng lọt tiếng Việt.

#### Đọc tiến độ

```
mẻ 2: đã có 8/24, xin thêm 8...
       xin 8, dùng được 6  (1 trùng, 1 bị loại)
```

Mẻ sau thường ít hơn mẻ trước, và đó là **bình thường**: mô hình dần cạn ý cho
một chủ đề nên bắt đầu lặp lại, mà cảnh trùng thì bị loại. Hai mẻ liên tiếp
không ra cảnh mới thì lệnh dừng sớm thay vì chờ thêm vài phút vô ích.

Ra thiếu thì hạ `--batch 4`, hoặc tự thêm vào file cho đủ — nó là file văn bản.

> **Đọc lướt file một lượt trước khi chạy 40 ảnh.** File `.txt` sửa tay thoải
> mái — sửa một dòng rẻ hơn nhiều so với gen lại 40 ảnh rồi mới thấy sai.

### ① Sinh ảnh

```bash
python studio.py generate "Đại dương kỳ thú" --theme ocean --count 40
```

Ảnh ra ở `library/dai-duong-ky-thu/raw/`, kèm file `.json` ghi lại prompt và
seed của từng ảnh để sinh lại y hệt khi cần.

> **`--theme` gần như bắt buộc.** Không có nó thì cả 40 ảnh dùng chung một
> chủ thể, chỉ khác bố cục — tỷ lệ giữ lại sẽ rất thấp. Xem
> [Vì sao ảnh xấu](#vì-sao-ảnh-xấu).

Bộ chủ thể dựng sẵn trong [`themes/`](themes/):

```bash
python studio.py generate x --list-themes
#   floral           24 chủ thể
#   forest-animals   24 chủ thể
#   mandala          24 chủ thể
#   ocean            24 chủ thể
```

`--theme` cũng nhận đường dẫn file `.txt` tự viết.

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `--theme ocean` | Bộ chủ thể dựng sẵn, hoặc file `.txt` |
| `--complexity` | Độ tinh xảo của **nét**: `simple` / `medium` / `detailed` |
| `--density` | Số **đối tượng** trên trang: `single` / `normal` / `rich` (mặc định) |
| `--seed 12345` | Cố định seed để tái tạo đúng mẻ cũ |
| `--overwrite` | Sinh đè. Mặc định bỏ qua ảnh đã có nên chạy lại được sau khi đứt |

`--complexity` và `--density` là hai trục khác nhau, dễ nhầm:

- **complexity** = nét vẽ tinh xảo tới đâu. `simple` nét rất dày cho trẻ nhỏ.
- **density** = trang có bao nhiêu thứ để tô. `rich` lấp kín, `single` một chủ thể trên nền trắng.

Sách trẻ em nên là `--complexity simple --density rich`: nét to dễ tô, nhưng
trang vẫn đầy. Ngoại lệ là mandala — dùng `--density normal`, vì `rich` sẽ phá
mất tính đối xứng.

Lệnh này **chạy tiếp được**. Đứt giữa chừng thì chạy lại, nó bỏ qua ảnh đã xong.

Nếu chủ đề gõ bằng tiếng Việt mà không có `--theme`, lệnh **dừng lại** kèm
hướng dẫn. Đây là chủ ý — xem mục dưới.

---

## Vì sao ảnh xấu

Mẻ đầu tiên gõ `generate "đại dương"` ra toàn hoa lá, nét mảnh như sợi tóc,
nửa trang trên trống trơn. Ba nguyên nhân, đã sửa hết:

**1. Chủ thể viết bằng tiếng Việt.** Flux chỉ hiểu tiếng Anh. Nó không báo lỗi
mà lặng lẽ bỏ qua rồi vẽ bừa. Giờ `generate` chặn thẳng và chỉ cách sửa.

**2. Từ ngữ tả nét quá yếu.** `"consistent medium line weight"` cho ra nét mảnh
đến mức in 300 DPI là mất. Đổi thành `"thick even line weight"` — chính chữ
trong prompt đã chạy tốt.

**3. Bố cục tự chống lại mình.** Danh sách bố cục cũ có
`"generous negative space"` và `"balanced open areas"`. Đó chính là thứ đẻ ra
mấy ảnh trống hơn nửa trang. Giờ mọi mục đều nói `"full-page"` hoặc
`"filling the frame"`.

Khung prompt hiện tại không phải tự nghĩ ra. Nó lấy từ prompt Bao đã chạy tay
trong ComfyUI và cho ra ảnh đẹp — ComfyUI nhúng prompt vào file PNG nên đọc
lại được:

```
coloring book page for children, black and white line art,
clean bold uniform outlines, thick even line weight,
no shading, no grayscale, no color fill, no texture,
pure white background, simple cute cartoon style,
centered full-page composition,
a smiling sea turtle swimming, a few round bubbles around it
```

**Cách viết chủ thể cho đúng:** cụ thể, tiếng Anh, mô tả cả **một cảnh** chứ
không phải một vật.

```
Đúng:  a smiling sea turtle swimming through a coral reef,
       schools of small fish above it,
       seaweed and starfish along the sea floor below

Nhạt:  a smiling sea turtle swimming, a few round bubbles around it
Hỏng:  sea turtle
Hỏng:  đại dương
```

### Ảnh chỉ có một đối tượng giữa trang trống

Đợt sau vẫn còn: con sứa nằm giữa, quanh nó trống hoác. Ba chỗ đã sửa:

1. **`--density rich` thành mặc định** — thêm chuỗi
   `"many different elements throughout, no large empty white areas,
   elements reaching the top and bottom edges"`.
2. **Bỏ `"pure white background"` khỏi `BASE_STYLE`.** Chuỗi đó vốn để chặn nền
   xám, nhưng Flux đọc thành *"nền để trống"*. Việc chặn nền xám giờ đã do bước
   khử xám lo, nên không cần nói trong prompt nữa.
3. **Viết lại `themes/*.txt` thành cảnh.** Đây là đòn bẩy lớn nhất — prompt
   chung không cứu được một chủ thể viết cụt lủn.

Vẫn chưa ưng thì chỉnh `themes/*.txt` và `BASE_STYLE` trong
[`studio/prompts.py`](studio/prompts.py) trước — **đừng đổi sang FLUX.1-dev**,
vướng giấy phép thương mại.

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

### Bìa

**`build` dựng bìa tự động**, không cần lệnh riêng:

```bash
python studio.py build dai-duong-ky-thu --subtitle "40 trang tô màu"
```

Ảnh bìa màu đã được `generate` vẽ sẵn ở bước ① và nằm tại
`library/<slug>/cover-art.png`. `build` chỉ việc ghép nó thành bìa hoàn chỉnh.

Chia hai chỗ như vậy vì **độ dày gáy phụ thuộc số trang cuối cùng**, mà số
trang thì phải duyệt xong mới biết. Ảnh vẽ được sớm; bìa thì không.

Muốn dựng lại bìa mà không đụng ruột thì có lệnh riêng:

```bash
python studio.py cover dai-duong-ky-thu --bg "#8C1B4A"
python studio.py cover dai-duong-ky-thu --image bia-tu-ve.png
```

Bìa là **một trang PDF trải ngang**: bìa sau, gáy, bìa trước:

```
┌────────────┬──┬────────────┐
│  bìa sau   │gáy│  bìa trước │   cao 11.25 in
└────────────┴──┴────────────┘
   8.5 in     ↑     8.5 in
              └ dày theo số trang
```

Công thức gáy của Lulu cho bìa mềm đóng keo:

```
gáy = (số trang / 444) + 0.06 in
```

444 là số trang trên mỗi inch giấy tiêu chuẩn, `0.06` là phần keo gáy. Sách 80
trang → gáy 0.240 in → khổ bìa 17.490 × 11.250 in.

**Sửa ruột là phải dựng lại bìa.** Số trang đổi thì gáy đổi theo, dùng lại bìa
cũ là hình tràn sang gáy khi in.

| Tuỳ chọn | Thuộc lệnh | Ý nghĩa |
|---|---|---|
| `--cover-scene "..."` | `generate` | Mô tả ảnh bìa bằng tiếng Anh. Mặc định lấy cảnh đầu trong bộ chủ thể |
| `--no-cover` | `generate`, `build` | Bỏ qua phần bìa |
| `--subtitle "..."` | `build`, `cover` | Dòng nhỏ dưới tiêu đề |
| `--bg "#1B7A8C"` | `build`, `cover` | Màu nền bìa sau và dải chữ |
| `--image anh.png` | `cover` | Dùng ảnh có sẵn thay vì ảnh Flux đã vẽ |

Ảnh bìa dùng workflow riêng
([`flux_cover.api.json`](workflows/flux_cover.api.json)) — cùng model schnell
nhưng bỏ ràng buộc đen trắng để ra ảnh màu.

**Chữ do Pillow ghép, không phải Flux vẽ.** Flux viết chữ sai chính tả, nên
prompt bìa có `no text, no letters, no words`. Font DejaVu hiển thị được dấu
tiếng Việt.

Gáy mỏng hơn 0.25 in thì bỏ chữ gáy — in lên sẽ tràn sang mặt bìa. Lệnh tự
cảnh báo khi gặp.

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

## Model và workflow ComfyUI

Workflow mặc định đã khớp sẵn với ComfyUI trên máy Bao:

| Vai trò | File | Node |
|---|---|---|
| UNET | `flux1-schnell-Q4_K_S.gguf` | `UnetLoaderGGUF` |
| VAE | `ae.safetensors` | `VAELoader` |
| CLIP | `t5xxl_fp8_e4m3fn.safetensors` + `clip_l.safetensors` | `DualCLIPLoader` |

Cần custom node [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) — đã cài sẵn.

### Vì sao schnell chứ không phải dev

**FLUX.1-schnell là Apache 2.0 — dùng thương mại thoải mái.**
**FLUX.1-dev có giấy phép phi thương mại**, muốn bán sách phải mua giấy phép
riêng từ Black Forest Labs. Với dự án bán sách thì schnell là lựa chọn đúng
về mặt pháp lý, không chỉ vì nó nhanh hơn.

Hệ quả kỹ thuật:

- Schnell chưng cất còn **4 bước** — `STUDIO_STEPS=4`, đừng để 20.
- Schnell **không dùng guidance**, nên workflow không có node `FluxGuidance`
  và file map không có khoá `guidance`. Studio tự nhận biết, `--guidance`
  sẽ bị bỏ qua kèm cảnh báo thay vì âm thầm không có tác dụng.
- Bù lại schnell bám prompt kém hơn dev một chút. Nếu line art ra không ưng,
  hãy chỉnh prompt và cấp `--subjects` trước khi nghĩ tới chuyện đổi model.

### Thay workflow khác

Chỉ cần sửa số node trong
[`workflows/flux_lineart.map.json`](workflows/flux_lineart.map.json),
không phải đụng vào code:

```json
{
  "prompt": { "node": "6",  "field": "text" },
  "seed":   { "node": "25", "field": "noise_seed" },
  "width":  { "node": "5",  "field": "width" },
  "height": { "node": "5",  "field": "height" },
  "steps":  { "node": "17", "field": "steps" }
}
```

Studio kiểm tra file map ngay lúc khởi động — sai node là báo lỗi luôn, không
đợi chạy xong 40 ảnh mới biết. `studio.py doctor` in ra đúng tên model mà
workflow đang gọi, đối chiếu với `ComfyUI/models/` là thấy ngay lệch chỗ nào.

Workflow phải là bản export **API format** (Settings → bật Dev mode → nút
`Save (API Format)`), không phải file kéo thả thông thường.

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
    recipe.py                đọc + kiểm tra công thức sách
    prompts.py               sinh prompt biến thể
    imageops.py              khử xám, phóng to, đo chất lượng
    llm.py                   gọi LM Studio sinh bộ chủ thể
    providers/
        base.py              giao diện chung
        comfyui.py           client HTTP nói chuyện với ComfyUI
    commands/
        make.py                  ← lệnh dùng thường ngày
        doctor.py  subjects.py  generate.py
        approve.py  build.py  cover.py
books/                       công thức sách, mỗi cuốn một file .yaml
workflows/
    flux_lineart.api.json    workflow Flux đen trắng (ruột)
    flux_lineart.map.json    tham số nằm ở node nào
    flux_cover.api.json      workflow Flux màu (bìa)
    flux_cover.map.json
themes/                      bộ chủ thể dựng sẵn, tiếng Anh
    ocean.txt  mandala.txt  floral.txt  forest-animals.txt
tests/smoke_test.py
library/                     thư viện sách — KHÔNG commit
```

⚠️ `library/` nằm trong `.gitignore`. Nó chứa `interior.pdf` là sản phẩm bán.
Đẩy lên repo công khai là mất trắng.

---

## Chưa có ở Phase 1

- Màn hình duyệt (Phase 2)
- Storefront và API (Phase 4)
- Thanh toán (Phase 5)
