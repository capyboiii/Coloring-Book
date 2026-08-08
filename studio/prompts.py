"""
Sinh prompt line art.

Khung prompt dưới đây KHÔNG phải tự nghĩ ra. Nó lấy từ prompt mà Bao đã chạy
tay trong ComfyUI và cho ra ảnh đẹp (con rùa biển trong output/ocean/):

    coloring book page for children, black and white line art,
    clean bold uniform outlines, thick even line weight,
    no shading, no grayscale, no color fill, no texture,
    pure white background, simple cute cartoon style,
    centered full-page composition,
    a smiling sea turtle swimming, a few round bubbles around it

Ba chữ quyết định chất lượng, rút ra từ prompt đó:

  · "thick even line weight"      -> nét dày đều, in ra không mất
  · "simple cute cartoon style"   -> neo phong cách, tránh ra kiểu phác thảo
  · "centered full-page composition" -> hình chiếm hết trang, không thừa trắng

Và điều kiện tiên quyết: **CHỦ THỂ PHẢI VIẾT BẰNG TIẾNG ANH VÀ CỤ THỂ.**
"a smiling sea turtle swimming" ra ảnh đẹp. "đại dương" thì Flux không hiểu,
nó bỏ qua và vẽ bừa — đó là lý do mẻ đầu ra toàn hoa lá.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path

# --------------------------------------------------------------------------
# Khung prompt
# --------------------------------------------------------------------------

# Lưu ý: prompt gốc đã chạy tốt có chuỗi "pure white background". Chuỗi đó
# vốn để chặn nền xám, nhưng Flux đọc nó thành "nền để TRỐNG" — góp phần
# đẻ ra mấy trang có mỗi con sứa giữa khoảng trắng mênh mông.
# Việc chặn nền xám giờ do bước khử xám trong imageops lo, nên ở đây nói
# theo cách không hàm ý bỏ trống.
# Mỗi ý CHỈ nói đúng một lần. Bản trước độ dày nét được nhắc ở cả bốn khối
# (BASE, STYLE, COMPLEXITY và cả DENSITY), prompt phình lên 180 từ và chủ thể
# bị chìm nghỉm ở giữa. Prompt dài không đồng nghĩa với prompt mạnh.
#
# Phân vai:
#   BASE_STYLE  thứ không bao giờ đổi: là line art, chưa tô màu, nét khép kín
#   STYLE       phong cách vẽ
#   COMPLEXITY  mức độ chi tiết
#   DENSITY     bố trí trên trang
# FLUX KHÔNG DÙNG NEGATIVE PROMPT.
#
# Schnell là mô hình guidance-distilled, workflow chạy ở CFG = 1.0, nên khối
# negative bị bỏ qua hoàn toàn — kể cả workflow Bao chạy tay trong giao diện.
#
# Vì vậy mọi thứ muốn CẤM đều phải viết ở đây, trong phần positive, dưới dạng
# "no X". Đúng như prompt tay của Bao: "No color / No shading / No gradients".
# Chuỗi NEGATIVE bên dưới chỉ để ghi vào metadata và để dùng nếu sau này đổi
# sang SDXL — nó không có tác dụng gì với Flux.
# Bản trước nói ĐỘ DÀY ba lần bằng ba cách: "extremely thick uniform black
# outlines", "heavy solid black lines", "bold black outlines only". Lặp lại
# một ý không làm nó mạnh hơn, chỉ đẩy chủ thể ra xa đầu prompt.
#
# Gộp lại còn một lần, lấy chỗ trống cho ba thứ trước giờ THIẾU HẲN:
#
#   · "even"        — nét ĐỀU. Trước chỉ đòi dày, không đòi đều. Mà đo được
#                     rằng chỗ hỏng luôn là chỗ nét mảnh: viền con vật dày thì
#                     đen đặc, cỏ mây đường nước mảnh thì xám và đứt.
#   · "large open white spaces to fill"
#                   — đây mới là yêu cầu THẬT của sách tô màu. Trẻ con cần
#                     mảng đủ to để đặt bút chì màu vào. Trước giờ prompt chỉ
#                     tả cái NÉT, chưa bao giờ tả cái KHOẢNG TRỐNG giữa các nét.
#   · "no frame, no border"
#                   — vá lỗ hổng. Luật này nằm trong chỉ dẫn cho LM Studio từ
#                     lâu nhưng KHÔNG HỀ có trong prompt ảnh, nên Flux vẫn vẽ
#                     khung viền trang trí. Khung viền vừa tốn mực in vừa toàn
#                     nét mảnh — đúng thứ hỏng nhiều nhất.
#
# Bỏ chữ "professional": mấy chữ khen chất lượng chung chung ("professional",
# "high quality", "8k") kéo Flux sang phía tả thực, kết cấu và đổ bóng.
# "black and white line art" và "no color fill" nằm trong prompt gốc đã chạy
# tốt (xem đầu file). Tôi làm MẤT cả hai lúc rút prompt từ 163 xuống 86 từ.
# Đó là lý do Flux vẫn trả về ảnh có màu: prompt không hề nói nó phải đen
# trắng nữa. Giờ trả lại.
#
# "no blush, no pink cheeks" thêm mới. Xem chú thích ở STYLE.
# Ngân sách từ rất chật (dưới 100 cho cả prompt), nên mỗi lần thêm phải cắt
# chỗ khác. Lần này gộp "clean vector style" vào "vector line art", bỏ
# "no gradients" (đã có "no shading"), và chuyển phần cấm má hồng xuống
# STYLE — đúng chỗ nó được gọi ra, thay vì cấm chung chung ở đây.
BASE_STYLE = (
    "black and white vector line art, children's coloring book page, "
    "extremely thick even black outlines, large white areas to fill, "
    "no color, no gray, no shading, no thin or broken lines, "
    "no frame, no border"
)

# --------------------------------------------------------------------------
# PHONG CÁCH VẼ — trục riêng, khác hẳn với độ tinh xảo và mật độ
# --------------------------------------------------------------------------
#
# Thêm trục này sau khi Bao đưa một cuốn sách mẫu làm chuẩn chất lượng. Nhìn
# ảnh mẫu thì rõ nó không phải "cartoon" chung chung mà là một phong cách rất
# cụ thể: kawaii/chibi. Đầu tròn to, thân nhỏ, mắt chấm, miệng một nét cong.
# Đồ vật (dứa, chuối, đàn ukulele, bóng) vẽ như ICON PHẲNG chứ không phải
# hình minh hoạ chi tiết. Nét đều tăm tắp từ nhân vật tới nền.
#
# Chuỗi "simple cute cartoon style" cũ quá mơ hồ nên Flux tự do diễn giải,
# ra kiểu vẽ tay nguệch ngoạc có texture lông lá.
# HAI LỖI TRONG CHUỖI kawaii CŨ, cả hai đều lộ ra khi soi ảnh thật:
#
# 1. MÁ HỒNG. Kiểu vẽ kawaii trong dữ liệu huấn luyện gần như luôn kèm hai
#    chấm hồng trên má. Gọi "kawaii" là gọi luôn cả má hồng — nó không phải
#    Flux làm bừa, mà là tôi đặt hàng mà không biết. Đo được: má hồng chiếm
#    ~0.4% diện tích nhưng đỏ chói, in ra là hỏng trang.
#    Nên thêm "plain white cheeks" ngay trong chuỗi phong cách, đúng chỗ nó
#    được gọi ra, chứ không chỉ cấm chung chung ở BASE_STYLE.
#
# 2. MẶT MỌC LÊN MỌI THỨ. "big round head, simple dot eyes, happy smile" nói
#    vô điều kiện, nên khi chủ thể là bó hoa hồng thì Flux vẫn phải gắn mặt
#    vào — ra bông hoa có mặt người. Đó chính là mấy trang Bao thấy "logic
#    chưa hợp lý".
#    Thêm "on animals and characters only" để buộc điều kiện. Với chủ đề hoa
#    lá đồ vật thì nên dùng style=decorative, và recipe giờ cảnh báo.
STYLE = {
    # KHÔNG nhắc tới mắt/miệng ở đây nữa. Lần trước tôi viết "dot eyes and a
    # small smile ON ANIMALS ONLY", tưởng chữ "only" sẽ giới hạn phạm vi.
    # Không. Flux chạy CFG=1 nên nó không phân giải được điều kiện — hễ chữ
    # "dot eyes" có mặt trong prompt là mọi thứ trong tranh đều mọc mắt.
    # Bỏ hẳn: chủ thể đã tự nói "a smiling sea turtle" rồi, thế là đủ để có
    # mặt ở đúng chỗ cần. Prompt tay đã chứng minh chạy tốt cũng chỉ ghi
    # "simple cute cartoon style", không hề tả mắt mũi.
    "kawaii": ("cute kawaii cartoon style, rounded chunky shapes, "
               "plain white cheeks"),
    "cartoon": "friendly cartoon style, rounded shapes, plain white cheeks",
    # Cấm rõ cả CHÂN TAY chứ không chỉ mặt: ảnh mandala ra một bông hoa có
    # mặt VÀ hai cái chân thò xuống dưới.
    "decorative": ("decorative ornamental line art, symmetrical patterns, "
                   "no faces, no eyes, no arms, no legs, not a character"),
}

# Bốn mức theo độ tuổi, khớp với AGE_DETAIL bên llm.py để chỉ dẫn cho
# LM Studio và prompt cho Flux nói cùng một thứ.
COMPLEXITY = {
    # "few large shapes" chứ không phải "large shapes": số lượng mới là thứ
    # quyết định. Hình to mà nhiều thì trang vẫn rối, và mỗi hình thêm vào là
    # thêm một chỗ Flux có thể vẽ nét mảnh.
    "simple": "few large shapes, minimal details, for ages 3 to 5",
    "medium": "simple details, for ages 5 to 8",
    "detailed": "moderately detailed, for ages 8 to 12",
    "intricate": "intricate decorative detail, adult coloring book",
}

# ⚠ FLUX BỎ QUA CHUỖI NÀY. Xem chú thích ở BASE_STYLE.
#
# Giữ lại vì hai lý do: ghi vào metadata từng ảnh để sau truy được, và dùng
# ngay nếu đổi sang SDXL hay model nào có CFG > 1.
#
# Nhóm nét đứng đầu vì đó là thứ hỏng nhiều nhất.
NEGATIVE = (
    "thin lines, uneven lines, broken lines, sketchy, soft edges, "
    "light lines, hatching, gray, shading, gradient, shadows, "
    "fur texture, cross-hatching, stippling, scribbles, "
    # Mấy chữ "chất lượng cao" quen tay lại chính là thứ kéo Flux sang phía
    # kết cấu, lông, ánh sáng và đổ bóng.
    "realistic, photorealistic, high quality, 8k, detailed illustration, "
    "3d render, watermark, signature, text, letters, "
    "cluttered, busy background, tiny details, dense forest, hundreds of leaves, "
    "scattered pebbles, grass blades, "
    "overlapping subjects, touching limbs, cropped limbs, cut off at the edge, "
    "top view, dramatic perspective, fisheye, "
    "angry, scary, aggressive"
)

# CHỈ nói về GÓC NHÌN và BỐ TRÍ, tuyệt đối không nói tới mật độ.
#
# Bản trước mọi mục đều có "filling the frame edge to edge" hoặc "densely
# packed" — hợp với density=rich nhưng đánh nhau trực tiếp với density=normal
# ("clear white space, uncluttered"). Prompt tự mâu thuẫn thì Flux chọn bừa.
#
# Giờ hai trục tách bạch: COMPOSITIONS lo bố trí, DENSITY lo mật độ.
# CHỈ có góc nhìn thẳng và hơi chếch. Bỏ hết "close-up", "circular",
# "foreground and background" — góc nhìn lạ làm Flux dựng phối cảnh, mà phối
# cảnh thì đẻ ra chi tiết nhỏ và vật chồng lên nhau.
COMPOSITIONS = [
    "front view",
    "slightly side view",
    "front view, sitting",
    "slightly side view, standing",
]

# Mật độ chi tiết — đây là cái cần chỉnh khi ảnh ra chỉ có một đối tượng
# nằm giữa trang trống hoác.
# Con số 60-80% là thứ quan trọng nhất ở đây. Nói "to" thì mơ hồ; nói tỉ lệ
# phần trăm thì Flux bám được. Nền tối đa một phần tư trang — phần còn lại
# phải là giấy trắng, vì trang tô màu đẹp luôn có nhiều khoảng trắng.
DENSITY = {
    "single": "one subject alone on plain white background",
    # "one or two simple background things" -> "one simple background element".
    # Cho phép hai thứ thì Flux gần như luôn vẽ hai, và thứ hai hay là cỏ/mây/
    # gợn nước — toàn nét mảnh. Cho đúng một thì nó chọn thứ to và chắc.
    #
    # Bỏ "lots of white space": BASE_STYLE đã có "large open white spaces to
    # fill" rồi. Nói hai lần không mạnh hơn, chỉ tốn chỗ — đúng cái lỗi vừa
    # sửa ở khối độ dày nét.
    "normal": ("one subject filling most of the page, "
               "one simple background element"),
    "rich": "one subject with a simple decorative background",
}

# Bộ dành cho sách trẻ con. Ba trục này phải đi CÙNG NHAU mới ăn: hình to
# (simple) + ít thứ trên trang (normal) + phong cách đầu tròn (kawaii).
# Đặt tên ở đây để lệnh và công thức sách khỏi phải nhớ, và để sau đổi thì
# đổi một chỗ.
KIDS_PRESET = {"complexity": "simple", "density": "normal", "style": "kawaii"}


# Số từ tối đa cho phần CHỦ THỂ, theo độ tuổi.
#
# Đây là cùng lúc lời giải cho HAI thứ Bao phàn nàn, nên đáng nói kỹ.
#
# Các dòng trong themes/ do LM Studio viết, dài 23-26 từ và có ba mệnh đề:
#     "a wise old owl on a fence post, holding a bell in its talon,
#      snow falling around it"
# Bắt Flux dựng ba thứ cùng lúc thì nó phải tự quyết cái nào che cái nào, to
# nhỏ ra sao — và đó chính là chỗ đẻ ra mấy trang "logic chưa hợp lý": con
# vật dính vào cột, đồ vật lơ lửng, tay chân mọc sai chỗ.
#
# Mệnh đề đuôi còn hại lần thứ hai: nó gần như luôn là nền ("snow falling
# around it", "seaweed filling the background") — toàn thứ vẽ bằng nét mảnh,
# đúng thứ hỏng nhiều nhất khi in.
#
# Cắt bớt mệnh đề đuôi vì thế vừa làm bố cục hợp lý hơn, vừa bớt nét mảnh,
# vừa kéo prompt về dưới ngưỡng 100 từ. Một thay đổi, ba cái lợi.
SUBJECT_MAX_WORDS = {
    "simple": 14,      # 3-5 tuổi: một chủ thể, một hành động
    "medium": 18,
    "detailed": 22,
    "intricate": 22,
}


def shorten_subject(subject: str, limit: int) -> str:
    """
    Bỏ bớt mệnh đề ở CUỐI cho tới khi vừa `limit` từ.

    Cắt theo dấu phẩy chứ không cắt giữa chừng: cắt cụt một mệnh đề sẽ để lại
    câu vô nghĩa kiểu "a wise old owl on a fence post holding a" và Flux vẽ ra
    thứ còn kỳ hơn.

    Mệnh đề ĐẦU luôn được giữ dù nó dài quá — đó là chủ thể, mất nó thì trang
    không còn gì.
    """
    clauses = [c.strip() for c in subject.split(",") if c.strip()]
    if not clauses:
        return subject.strip()

    kept, total = [clauses[0]], len(clauses[0].split())
    for c in clauses[1:]:
        n = len(c.split())
        if total + n > limit:
            break
        kept.append(c)
        total += n
    return ", ".join(kept)


@dataclass
class PagePrompt:
    index: int
    prompt: str
    negative: str
    seed: int
    subject: str

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Prompt cho ảnh bìa
# --------------------------------------------------------------------------

# BÌA CŨ HỎNG HAI CHỖ, cả hai đều thấy khi mở 4 ảnh bìa thật ra xem.
#
# 1. NHẠT THẾCH. Đo độ bão hoà trung bình (0-255):
#        manmat 202  ·  thu-hoa 115  ·  chihuahua 83  ·  ngay-hoi-bien 27
#    Bìa chim cánh cụt có 92% diện tích gần như không màu — nền trắng xoá,
#    đặt cạnh sách khác trên kệ là chìm nghỉm.
#    Prompt cũ CÓ ghi "vibrant saturated colors" nhưng nằm sau "full color"
#    và trước một đống ràng buộc khác, nên bị loãng. Giờ đưa màu lên đầu và
#    nói cụ thể: nền phải kín màu, không được để trắng.
#
# 2. FLUX VIẾT CHỮ SAI CHÍNH TẢ. Bìa chihuahua có dòng "BOOK Chiihhauua".
#    Prompt cũ ghi "no text, no letters, no words, no typography" — vô dụng,
#    vì Flux chạy CFG=1 nên không đọc được phủ định. Nhắc "text" là GỌI text.
#    Tệ hơn nữa: "vertical composition with space at the top for A TITLE" là
#    câu đặt hàng thẳng một cái tiêu đề. Flux giao đúng hàng.
#    Bỏ HẾT mọi chữ dính tới text/title/letters. Muốn chừa chỗ trên đầu thì
#    tả bằng hình ("simple open sky above"), không tả bằng chữ "title".
#    Đây đúng cùng một bài học với "dot eyes on animals only".
# BÌA — LẦN SỬA TRƯỚC CỦA TÔI LÀM HỎNG, ĐÂY LÀ BẢN CHỮA.
#
# Bao muốn bìa nhìn như một trang tô màu ĐÃ ĐƯỢC TÔ. Tôi hiểu đúng ý nhưng
# viết prompt sai hoàn toàn, và làm bìa xấu đi cả nét lẫn màu lẫn nội dung.
#
# Số đo, so bìa tôi vừa sinh với cuốn sách mẫu Bao đưa:
#
#                       bão hoà   nhạt    nét đen
#     sách mẫu Hawaii     131.9   15.9%    14.0%
#     bìa penguin tôi      23.6   87.0%    10.7%
#
# Nét đen thì tôi đạt (10.7 so với 14.0). Hỏng nằm nguyên ở phần MÀU: 87%
# diện tích gần như không màu, trong khi sách mẫu chỉ 16%.
#
# BỐN LỖI TRONG PROMPT CŨ:
#
# 1. Viết "a colored-in coloring book page". Flux đọc "coloring book page"
#    TRƯỚC rồi mới tới "colored-in", nên nó vẽ đúng một trang tô màu và để
#    trắng gần hết — thân chim, bông tuyết đều chỉ có nét, không có màu.
#    Đây LẠI LÀ đúng bài học "no text thì Flux viết text": ở CFG=1, nhắc tới
#    một thứ là triệu hồi nó. Prompt bìa từ giờ KHÔNG được chứa chữ
#    "coloring book" dưới bất kỳ dạng nào.
#
# 2. "flat color fills INSIDE THE OUTLINES" củng cố thêm cách đọc "tô vào
#    trong khung" — tức là tô một phần, còn lại để trắng.
#
# 3. "one big friendly subject, simple open sky above it" làm tranh trống
#    huếch. Sách mẫu có HAI con lợn, một con thỏ, đàn ukulele, hai cây dừa,
#    biển, đồi, mây, hoa — kín đặc từ mép này sang mép kia.
#
# 4. "no gradients, no shading, no soft edges" là tôi tự thêm. Sách mẫu CÓ
#    chuyển sắc nhẹ và có vân giấy. Cấm hết đi thì tranh bẹt và rẻ tiền.
#
# Bản này tả thẳng cái ĐÍCH — một bức tranh màu hoàn chỉnh, kín trang — thay
# vì tả cái quá trình "tô vào trang trắng".
# HAI YÊU CẦU CỦA BAO ĐÁNH NHAU TRỰC TIẾP, nên tách làm hai kiểu chọn được
# chứ không chồng lên nhau:
#
#     lần trước          lần này
#     "no texture"       "visible colored pencil texture"
#     "smooth even"      "natural uneven coloring"
#     "no gradients"     "soft pigment buildup", "layered coloring"
#     "no complex        "warm ambient lighting", "gentle shadows",
#      lighting"          "subtle highlights"
#
# Nhét cả hai vào một prompt thì nó tự cãi nhau, và Flux sẽ chọn bừa — đúng
# lỗi đã mắc ở COMPOSITIONS vs DENSITY hồi trước.
#
# Hai kiểu này là hai gu khác nhau, không phải cái nào đúng cái nào sai:
#   flat    kiểu vector hiện đại, giống cuốn "Cozy Hawaii" Bao đưa làm mẫu
#   pencil  kiểu tô tay bút chì màu, sách thiếu nhi cũ, ấm và có vân giấy
#
# Phần nào ĐÚNG VỚI CẢ HAI thì để ở đây; phần nào chỉ đúng với một kiểu thì
# đẩy xuống COVER_FINISH.
COVER_STYLE = (
    "children's book illustration, "
    "clean dark outlines with the colors filled neatly inside them, "
    # "simple harmonious palette" là chữ TÔI viết, và chính nó ghìm số màu
    # xuống. Giữ phần "hài hoà" vì đó là thứ làm bìa không loè loẹt, nhưng bỏ
    # chữ "simple" đi.
    "varied harmonious palette, bright child-friendly colors, "
    "clear separation between objects, cute and playful, "
    "a rich scene colored all the way to the edges, "
    # Nói THUẬN thay vì cấm: ở CFG=1 câu "nothing left white" chỉ tổ nhắc tới
    # màu trắng. Tả cái muốn có — nền cũng phải được tô — thì ăn hơn.
    "the sky and the ground and every background shape all fully colored, "
    "no photorealism"
)

COVER_FINISH = {
    # Đúng bốn nhóm Bao vừa đưa: chất liệu, cách tô, ánh sáng, phong cách.
    # Mỗi nhóm lấy 2-3 từ mạnh nhất — đưa hết 19 chuỗi vào thì prompt phình
    # lên gấp đôi và chủ thể lại chìm, đúng lỗi cũ.
    # Bao báo nét tô tay đã đạt, chỉ cần RỰC hơn. Nên chỉ động vào mấy chữ
    # làm nhạt màu, giữ nguyên phần tạo ra chất tay vẽ.
    #
    # Đo 3 bìa đã sinh: bão hoà 30-42/255, 79% diện tích gần như không màu.
    # Sách mẫu là 131.9 và 15.9%. Nhưng SỐ MÀU thì đã đủ rồi — 11-12 trên 12
    # cung màu, ngang sách mẫu. Nên vấn đề không phải "ít màu" mà là
    # MÀU NHẠT và GIẤY TRẮNG CÒN HỞ NHIỀU QUÁ.
    #
    # Ba chữ tôi tự đưa vào mà chính chúng làm nhạt:
    #   "vintage"             kiểu cũ = màu bạc màu. Bỏ.
    #   "soft pigment buildup" chữ "soft" ở đây làm mực nhạt đi, trong khi
    #                          bút chì màu thật hoàn toàn có thể đè rất đậm.
    #   "warm ambient light"  bó cả tranh vào tông ấm, mất hẳn xanh lá và
    #                          xanh dương.
    # Và "slight paper texture" mời gọi để hở giấy trắng — đổi sang "vân giấy
    # HIỆN LÊN QUA lớp màu", tức là vẫn có vân nhưng màu phủ kín bên trên.
    "pencil": (
        "hand-colored with colored pencils and soft crayons, "
        "visible pencil strokes, paper grain showing through the color, "
        "natural uneven coloring, layered strokes, "
        "heavy pigment buildup, richly saturated pencil colors, "
        "deep vivid tones, many different bright colors, "
        "soft natural shading, gentle shadows, bright cheerful light, "
        "warm storybook illustration, cozy children's picture book"
    ),
    # Kiểu cũ, giữ lại nguyên vẹn để đổi qua đổi lại mà không mất gì.
    "flat": (
        "professionally colored, bright flat colors, smooth even color, "
        "very soft shading only where needed to give a little depth, "
        "no gradients, no texture, no complex lighting"
    ),
}

DEFAULT_COVER_FINISH = "pencil"

# BỐN CÂU TRONG BẢN YÊU CẦU CỦA BAO KHÔNG DÙNG ĐƯỢC Ở ĐÂY, và bỏ đi là cố ý:
#
#     "Color the existing line-art illustration"
#     "while preserving the original line-art exactly"
#     "Do not alter, redraw, distort, or remove any existing black outlines"
#     "No colors outside the outlines" / "No color bleeding"
#
# Bốn câu đó viết cho quy trình TÔ LÊN MỘT ẢNH CÓ SẴN (img2img). Ở đây Flux
# vẽ từ con số ngẫu nhiên, KHÔNG có ảnh nét nào để mà giữ — bảo nó "đừng sửa
# nét có sẵn" là bảo nó đừng sửa một thứ không tồn tại.
#
# Tệ hơn: ở CFG=1 Flux không đọc được phủ định, nên "no colors OUTSIDE THE
# OUTLINES" chỉ có tác dụng nhắc nó nghĩ tới chuyện màu tràn ra ngoài. Đúng
# cái bẫy đã làm bìa penguin để trắng gần hết.
#
# Nên phần "giữ nét" được viết lại thành yêu cầu THUẬN: "clean black outlines
# with bright flat colors filled neatly INSIDE them".
#
# Muốn đúng nghĩa "tô lên ảnh nét có sẵn" thì phải dựng đường img2img —
# nạp một trang ruột đã duyệt, VAEEncode, chạy denoise thấp. Làm được, và
# làm xong thì bìa chính là một trang trong sách đã tô, khớp tuyệt đối với
# ruột. Nhưng đó là workflow mới chứ không phải sửa prompt.


# Giới từ mở đầu phần BỔ NGỮ. Cắt ở đây thì phần còn lại là chủ thể trần.
_PREPS = {"with", "in", "on", "at", "beside", "next", "under", "over",
          "through", "among", "near", "behind", "above", "below", "by",
          "around", "into", "onto", "from"}
_ARTICLES = {"a", "an", "the", "two", "three", "several", "some"}


def _head_noun(core: str) -> str:
    """
    Đoán danh từ chính của một mệnh đề, CHỈ để bắt trùng lặp.

    Không cần đúng ngữ pháp, chỉ cần đủ để "a red fox running" và "a brown fox
    sleeping" ra cùng một khoá. Lấy từ cuối thì ra "running" với "sleeping" —
    khác nhau, và hai con cáo lọt cả vào bìa.

    Cách làm: cắt ở giới từ đầu tiên (bỏ phần bổ ngữ), bỏ mạo từ và bỏ từ
    đuôi -ing (phân từ, không phải danh từ), rồi lấy từ còn lại cuối cùng.

        "a cat with a scarf"        -> cắt ở 'with' -> "a cat"     -> cat
        "a red fox running"         -> bỏ -ing      -> "a red fox" -> fox
        "a sea turtle swimming
         through a coral reef"      -> cắt ở 'through', bỏ -ing    -> turtle
    """
    words = []
    for w in core.lower().replace("-", " ").split():
        if w in _PREPS:
            break
        if w in _ARTICLES or w.endswith("ing"):
            continue
        words.append(w)
    return words[-1] if words else core.lower()


def summarise_scenes(subjects: list[str], count: int = 3,
                     offset: int = 0,
                     ending: str = "all together in one cheerful group scene"
                     ) -> str:
    """
    Gộp nhiều chủ thể trong sách thành MỘT cảnh chung cho bìa.

    VÌ SAO — bìa phải nói được cuốn sách có gì.

    Trước đây bìa lấy đúng `subjects[0]` và bìa sau lấy `subjects[1]`. Kết quả
    là một cuốn tên "Ngày hội biển" có bìa trước vẽ mỗi con chim cánh cụt và
    bìa sau vẽ con cú đậu dưới trăng — hai mặt chẳng liên quan gì tới nhau,
    cũng chẳng nói được bên trong sách có gì. Khách nhìn bìa không đoán nổi
    mình mua cái gì.

    Sách mẫu thương mại làm ngược lại: bìa là một cảnh có NHIỀU nhân vật của
    sách tụ lại. Đó vừa là bìa đẹp hơn vừa là quảng cáo trung thực hơn.

    Cách gộp:
      · lấy mệnh đề ĐẦU của mỗi dòng — đó là chủ thể, phần đuôi là nền
      · bỏ trùng theo danh từ chính, để không ra "một con lợn và một con lợn"
      · lấy RẢI ĐỀU trong danh sách chứ không lấy mấy dòng đầu, cho đủ đa dạng

    `offset` để bìa sau lấy bộ khác bìa trước — cùng sách, khác hình.

    Sách ít trang thì hai mặt sẽ trùng dàn nhân vật, không tránh được. Lúc đó
    `ending` mới là thứ tạo khác biệt: bìa trước là cảnh tụ tập đông vui, bìa
    sau là cảnh nhỏ và tĩnh hơn — đúng cách sách thật làm, vì bìa sau còn phải
    chừa chỗ cho chữ.
    """
    cores, seen = [], set()
    for s in subjects:
        core = s.split(",")[0].strip().rstrip(".")
        if not core:
            continue
        key = _head_noun(core)
        if key in seen:
            continue
        seen.add(key)
        cores.append(core)

    if not cores:
        return ""
    if len(cores) <= count:
        picked = cores
    else:
        step = len(cores) / count
        picked = [cores[int((i * step + offset) % len(cores))]
                  for i in range(count)]
        # Lấy rải đều vẫn có thể trùng khi danh sách ngắn
        picked = list(dict.fromkeys(picked))

    if len(picked) == 1:
        return picked[0]
    return ", ".join(picked[:-1]) + " and " + picked[-1] + ", " + ending


def build_colour_hint(main: str | None = None, secondary: str | None = None,
                      background: str | None = None) -> str:
    """
    Ghép phần chỉ định bảng màu vào prompt bìa.

    Bao yêu cầu ba ô [MAIN COLORS] / [SECONDARY COLORS] / [BACKGROUND] — đây
    là ý hay và tôi giữ nguyên: nó biến bảng màu thành thứ đặt được theo từng
    cuốn, thay vì phó mặc Flux bốc màu ngẫu nhiên mỗi lần chạy. Hai cuốn cùng
    bộ sách mà bìa lệch tông nhau thì nhìn không ra một bộ.

    Bỏ trống thì không ghép gì — thêm ô rỗng vào prompt chỉ tổ loãng.
    """
    parts = []
    if main:
        parts.append(f"main colors {main.strip().rstrip('.')}")
    if secondary:
        parts.append(f"secondary colors {secondary.strip().rstrip('.')}")
    if background:
        parts.append(f"background in {background.strip().rstrip('.')}")
    return ", ".join(parts)

# NGƯỢC HẲN trang ruột: bìa cần cảnh GIÀU nhất, không phải gọn nhất.
#
# Lần trước tôi cắt cảnh bìa xuống 12 từ, lấy lý do "một chủ thể rõ ràng".
# Sai. Trang ruột cần gọn vì trẻ phải tô được; bìa cần rậm vì nó là tấm ảnh
# bán hàng, phải đập vào mắt giữa hàng trăm cuốn khác trên kệ.
# Sách mẫu chứng minh cảnh rậm vẫn hợp lý được — rậm không phải nguyên nhân
# gây bố cục phi lý, mệnh đề mâu thuẫn mới là.
#
# Giữ một trần rộng để phòng dòng chủ thể dài bất thường, chứ trên thực tế
# các dòng trong themes/ (23-26 từ) không bị cắt.
COVER_SUBJECT_MAX_WORDS = 28


def build_cover_prompt(scene: str, main_colors: str | None = None,
                       secondary_colors: str | None = None,
                       background_colors: str | None = None,
                       finish: str = DEFAULT_COVER_FINISH) -> str:
    """
    Bìa KHÔNG bị ràng buộc đen trắng — đây là tranh màu hoàn chỉnh.

    `finish` chọn gu tô màu: 'pencil' (tô tay bút chì màu, có vân giấy) hoặc
    'flat' (mảng phẳng kiểu vector). Hai kiểu loại trừ nhau — xem COVER_FINISH.

    Chữ tiêu đề do Pillow ghép vào sau, nên prompt tuyệt đối không được nhắc
    tới chữ nghĩa dưới bất kỳ hình thức nào. Xem chú thích ở COVER_STYLE.
    """
    if finish not in COVER_FINISH:
        raise ValueError(
            f"finish phải là một trong {list(COVER_FINISH)}, nhận '{finish}'")
    scene = shorten_subject(scene.strip().rstrip("."),
                            COVER_SUBJECT_MAX_WORDS)
    # Bảng màu đặt NGAY SAU chủ thể, trước khối phong cách: nó nói về chủ
    # thể nên phải đứng cạnh chủ thể.
    hint = build_colour_hint(main_colors, secondary_colors, background_colors)
    parts = ([scene] + ([hint] if hint else [])
             + [COVER_FINISH[finish], COVER_STYLE])
    return ", ".join(parts)


def has_non_ascii(text: str) -> bool:
    """Dò dấu tiếng Việt — dấu hiệu chủ thể chưa dịch sang tiếng Anh."""
    return any(ord(c) > 127 for c in text)


def build_prompt(subject: str, complexity: str, composition: str,
                 density: str, style: str = "kawaii",
                 density_text: str | None = None) -> str:
    # Thứ tự: nền tảng -> PHONG CÁCH -> độ tinh xảo -> bố trí -> CHỦ THỂ ->
    # mật độ. Phong cách đặt sớm vì nó là thứ định hình mạnh nhất; chủ thể
    # đặt gần cuối theo đúng prompt đã chứng minh chạy tốt.
    # CHỦ THỂ ĐẶT LÊN ĐẦU. Prompt Bao chạy tay trong giao diện — cái cho ra
    # nét đẹp hơn hẳn — mở đầu bằng chủ thể rồi mới tới ràng buộc phong cách:
    #     "a small brontosaurus munching on tall grass, one simple tree
    #      behind it for children / No color / No shading / ..."
    # Bản của tôi nhét 100 từ phong cách lên trước, chủ thể chìm ở giữa.
    parts = [
        subject.strip().rstrip("."),
        composition,
        BASE_STYLE,
        STYLE[style],
        COMPLEXITY[complexity],
        DENSITY[density] if density_text is None else density_text,
    ]
    return ", ".join(p for p in parts if p)


def make_prompts(
    topic: str,
    count: int,
    complexity: str = "medium",
    subjects: list[str] | None = None,
    seed_start: int | None = None,
    density: str = "rich",
    style: str = "kawaii",
    template: str | None = None,
) -> list[PagePrompt]:
    """
    Trả về `count` prompt khác nhau.

    subjects    danh sách chủ thể tiếng Anh. Thiếu thì lặp lại chủ đề gốc và
                chỉ biến thiên bằng bố cục — cách này cho kết quả kém hơn hẳn.
    seed_start  cố định để tái tạo lại đúng mẻ ảnh cũ. None -> ngẫu nhiên.
    density     single | normal | rich. Xem DENSITY ở trên.
    """
    if complexity not in COMPLEXITY:
        raise ValueError(
            f"complexity phải là một trong {list(COMPLEXITY)}, nhận '{complexity}'"
        )
    if density not in DENSITY:
        raise ValueError(
            f"density phải là một trong {list(DENSITY)}, nhận '{density}'"
        )
    if style not in STYLE:
        raise ValueError(
            f"style phải là một trong {list(STYLE)}, nhận '{style}'"
        )

    if seed_start is None:
        seed_start = random.randint(1, 2**31 - 1)

    subjects = [s.strip() for s in (subjects or []) if s.strip()]

    out: list[PagePrompt] = []
    for i in range(count):
        subject = subjects[i % len(subjects)] if subjects else topic

        if template:
            # Khuôn đã quyết định CẢ bố cục lẫn cách bày trang, nên bỏ hẳn
            # COMPOSITIONS và DENSITY. Để cả ba là ba chỉ dẫn bố cục đánh
            # nhau — đúng cái lỗi vừa sửa ở COMPOSITIONS vs DENSITY.
            subject = template.replace("{subject}", subject)
            composition = ""
            page_density = ""
        else:
            # Cắt mệnh đề đuôi TRƯỚC khi ghép prompt. Xem SUBJECT_MAX_WORDS.
            subject = shorten_subject(subject, SUBJECT_MAX_WORDS[complexity])
            composition = COMPOSITIONS[i % len(COMPOSITIONS)]
            page_density = DENSITY[density]

        out.append(
            PagePrompt(
                index=i + 1,
                prompt=build_prompt(subject, complexity, composition,
                                    density, style,
                                    density_text=page_density),
                negative=NEGATIVE,
                seed=seed_start + i,
                subject=subject,
            )
        )
    return out


# --------------------------------------------------------------------------
# Bộ chủ thể dựng sẵn
# --------------------------------------------------------------------------

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"


def list_themes() -> list[str]:
    if not THEMES_DIR.exists():
        return []
    return sorted(p.stem for p in THEMES_DIR.glob("*.txt"))


def resolve_subjects_path(value: str) -> Path:
    """
    Nhận vào tên bộ dựng sẵn ('ocean') hoặc đường dẫn file.
    Tên bộ được ưu tiên tra trong themes/ trước.
    """
    candidate = THEMES_DIR / f"{value}.txt"
    if candidate.exists():
        return candidate

    path = Path(value)
    if path.exists():
        return path

    available = ", ".join(list_themes()) or "(chưa có bộ nào)"
    raise FileNotFoundError(
        f"Không tìm thấy '{value}'. Bộ dựng sẵn: {available}"
    )


def load_subjects(value: str) -> list[str]:
    """Đọc chủ thể: mỗi dòng một cái, bỏ dòng trống và dòng bắt đầu bằng #."""
    path = resolve_subjects_path(value)
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines
            if ln.strip() and not ln.startswith(("#", "@"))]


def load_style(value: str) -> str | None:
    """
    Đọc dòng `@style:` nếu file theme có khai báo.

    VÌ SAO CẦN — cảnh vật mọc mắt mũi chân.

    Soi 28 ảnh trong library/ thì thấy lỗi này chỉ xảy ra ở đúng ba bộ chủ đề:
    hoa, hoa trong chậu, và mandala. Hướng dương có mặt, hoa tulip mỗi bông
    hai con mắt, mandala mọc mặt và hai cái chân. Còn cá voi, gấu, khủng long
    thì không sao — chúng vốn phải có mặt.

    Nguyên nhân không phải Flux bậy: chủ đề hoa lá mà chạy `style=kawaii` thì
    đúng là đang đặt hàng "bông hoa dễ thương kiểu chibi", và Flux giao đúng
    hàng. Lỗi nằm ở chỗ chọn phong cách.

    Trước tôi vá bằng một dòng CẢNH BÁO trong recipe.hints(). Không đủ, vì
    hai lý do: cảnh báo thì đọc xong vẫn chạy tiếp được, và lệnh `generate`
    gõ tay không hề đi qua recipe.

    Nên chuyển thành: **chủ đề tự khai phong cách của nó**, ngay trong file
    theme, cạnh đúng đám chủ thể cần nó. Đây là cùng cơ chế với `@template:`.

        @style: decorative

    Ai gõ `--style` tay thì vẫn đè lên được, nhưng sẽ bị cảnh báo to.
    """
    path = resolve_subjects_path(value)
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln.lower().startswith("@style:"):
            style = ln.split(":", 1)[1].strip()
            if style not in STYLE:
                raise ValueError(
                    f"@style trong {path.name} là '{style}', "
                    f"phải là một trong {list(STYLE)}")
            return style
    return None


def load_template(value: str) -> str | None:
    """
    Đọc dòng `@template:` nếu file theme có khai báo.

    KHUÔN BỐ CỤC — thứ rút ra từ sách mẫu Bao đưa.

    Cuốn Flower Garden có 48 trang mà **cả 48 dùng chung một bố cục**: một bó
    hoa cắm trong chậu gỗ, đặt giữa trang. Chỉ đổi loại hoa. Nó KHÔNG bắt
    người vẽ nghĩ bố cục mới mỗi trang.

    Đó là lý do sách mẫu trang nào cũng hợp lý và cân đối, còn ảnh của mình
    thì trang lệch trang trống — vì mỗi dòng chủ thể của mình mô tả một cảnh
    khác nhau, và Flux phải tự dựng bố cục 24 lần, hỏng lúc nào không biết.

    Cú pháp trong file theme:

        @template: {subject} arranged in a wooden bucket, centered

    Rồi mỗi dòng chủ thể chỉ cần ghi ngắn gọn: `sunflowers`, `tulips`, `roses`.

    Có khuôn thì studio bỏ luôn phần xoay vòng COMPOSITIONS — khuôn đã quyết
    định bố cục rồi, thêm "close-up view" vào nữa là đánh nhau.
    """
    path = resolve_subjects_path(value)
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln.lower().startswith("@template:"):
            tpl = ln.split(":", 1)[1].strip()
            if "{subject}" not in tpl:
                raise ValueError(
                    f"@template trong {path.name} phải chứa {{subject}}")
            return tpl
    return None
