"""
Cấu hình trung tâm — mọi con số về in ấn nằm ở đây.

Nguồn spec: Lulu Book Creation Guide
  - Bleed 0.125 in mỗi cạnh, BẮT BUỘC kể cả khi hình không tràn lề
  - Safety margin 0.5 in tính từ mép trim
  - Gutter (lề gáy) 0.2-0.3 in, bắt buộc khi sách > 60 trang
  - Coloring book in 1 MẶT để bút không lem sang trang sau
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv là tuỳ chọn
    pass


# --------------------------------------------------------------------------
# Spec in ấn
# --------------------------------------------------------------------------

DPI = 300

TRIM_W_IN = 8.5   # khổ sách sau khi xén
TRIM_H_IN = 11.0

BLEED_IN = 0.125  # Lulu yêu cầu
SAFETY_IN = 0.5   # chi tiết quan trọng phải nằm trong vùng này
GUTTER_IN = 0.25  # lề gáy thêm vào mép trong

# Khổ file PDF = khổ trim + bleed hai bên
PAGE_W_IN = TRIM_W_IN + 2 * BLEED_IN   # 8.75
PAGE_H_IN = TRIM_H_IN + 2 * BLEED_IN   # 11.25

# Vùng vẽ an toàn thực tế (đã trừ safety + gutter)
ART_W_IN = TRIM_W_IN - 2 * SAFETY_IN - GUTTER_IN  # 7.25
ART_H_IN = TRIM_H_IN - 2 * SAFETY_IN              # 10.0

# Vị trí vùng vẽ tính từ mép file PDF (không phải mép trim).
# Sách in 1 mặt: mọi trang có hình đều là trang lẻ (recto, nằm bên phải),
# nên gutter LUÔN ở bên trái. Không cần lật gương theo trang chẵn/lẻ.
ART_LEFT_IN = BLEED_IN + SAFETY_IN + GUTTER_IN  # 0.875
ART_TOP_IN = BLEED_IN + SAFETY_IN               # 0.625


def inch_to_px(inches: float) -> int:
    return int(round(inches * DPI))


def inch_to_pt(inches: float) -> float:
    """ReportLab làm việc bằng point: 1 inch = 72 pt."""
    return inches * 72.0


PAGE_W_PX = inch_to_px(PAGE_W_IN)   # 2625
PAGE_H_PX = inch_to_px(PAGE_H_IN)   # 3375
ART_W_PX = inch_to_px(ART_W_IN)     # 2175
ART_H_PX = inch_to_px(ART_H_IN)     # 3000


# --------------------------------------------------------------------------
# Sinh ảnh
# --------------------------------------------------------------------------

# Tỉ lệ đúng bằng vùng vẽ an toàn (7.25:10 = 0.725) và chia hết cho 16
# để Flux không phải nội suy.
#
# 832x1152 = 0.96 MP.
#
# Tôi đã từng nâng lên 1392x1920 (2.67 MP) với lập luận: latent to hơn thì nét
# chiếm nhiều ô hơn, đỡ bị VAE làm hỏng. Lập luận đó SAI, và Bao phát hiện ra
# bằng cách đơn giản nhất — vẽ thẳng trong giao diện ComfyUI thì nét đẹp hơn
# hẳn so với chạy qua code.
#
# Đọc metadata nhúng trong file PNG thì thấy giao diện dùng 832x1088 = 0.91 MP.
# Hai lý do nó thắng:
#
#   1. FLUX.1-schnell được huấn luyện quanh 1 MP. Đẩy lên 2.67 MP là ra ngoài
#      vùng nó quen, nét bắt đầu đi loạng choạng và dày mỏng thất thường.
#   2. Ảnh nhỏ phải phóng NHIỀU hơn để đạt khổ in (2.6 lần thay vì 1.56 lần),
#      mà chính phép nội suy LANCZOS khi phóng lại là một bộ làm mượt. Nâng độ
#      phân giải sinh đã vô tình lấy mất cái đó.
#
# Bài học: đừng suy luận về hành vi của model rồi tin luôn. Phải đo, và phải
# so với một bản đối chứng chạy tay.
#
# Máy khoẻ muốn thử lại độ phân giải cao thì sửa trong .env — nhưng nhớ đo
# bằng `studio.py measure` và so với ảnh vẽ tay trong giao diện.
GEN_W = int(os.environ.get("STUDIO_GEN_WIDTH", "832"))
GEN_H = int(os.environ.get("STUDIO_GEN_HEIGHT", "1152"))

assert abs(GEN_W / GEN_H - ART_W_IN / ART_H_IN) < 0.005, (
    f"Tỉ lệ sinh ảnh {GEN_W}x{GEN_H} lệch vùng vẽ "
    f"{ART_W_IN}x{ART_H_IN} in. Phải giữ đúng 0.725.")
assert GEN_W % 16 == 0 and GEN_H % 16 == 0, "Kích thước phải chia hết cho 16"


# --------------------------------------------------------------------------
# Bìa
# --------------------------------------------------------------------------
#
# Bìa là MỘT trang PDF duy nhất trải ngang: bìa sau | gáy | bìa trước.
#
#   ┌────────────┬──┬────────────┐
#   │  bìa sau   │gáy│  bìa trước │   cao = 11.25 in (đã gồm bleed)
#   └────────────┴──┴────────────┘
#    8.5 in      ↑   8.5 in
#                └ dày theo số trang
#
# Công thức gáy của Lulu cho bìa mềm đóng keo:
#     gáy = (số trang / 444) + 0.06 in
# 444 là số trang trên mỗi inch của giấy tiêu chuẩn.
# 0.06 in là phần keo gáy.
#
# Sách 80 trang -> gáy 0.24 in. Sai con số này là bìa lệch hẳn khi in.

SPINE_PAGES_PER_INCH = 444.0
SPINE_GLUE_IN = 0.06

# Dưới ngưỡng này thì gáy quá mỏng, chữ in lên sẽ tràn sang mặt bìa
SPINE_TEXT_MIN_IN = 0.25

# Kích thước Flux sinh ảnh bìa màu (tỉ lệ xấp xỉ bìa trước có bleed)
COVER_GEN_W = 896
COVER_GEN_H = 1152


def spine_width_in(page_count: int) -> float:
    """Độ dày gáy theo số trang, đơn vị inch."""
    return page_count / SPINE_PAGES_PER_INCH + SPINE_GLUE_IN


def cover_size_in(page_count: int) -> tuple[float, float]:
    """Khổ file bìa (rộng, cao) tính bằng inch, đã gồm bleed."""
    width = 2 * TRIM_W_IN + spine_width_in(page_count) + 2 * BLEED_IN
    height = TRIM_H_IN + 2 * BLEED_IN
    return width, height


# --------------------------------------------------------------------------
# Xử lý ảnh
# --------------------------------------------------------------------------

# Khử xám bằng levels thay vì threshold cứng: giữ được khử răng cưa ở viền nét
# nhưng vẫn ép nền về trắng tinh và nét về đen tuyền.
# 170 chứ không phải 80.
#
# Flux vẽ nét không đều màu: nét chính đen đậm, còn nét nền (mây, cỏ xa) thì
# XÁM NHẠT. Đo trên ảnh thật: 17.7% pixel mực nằm ở vùng xám 100-200, tức gần
# một phần năm số nét in ra sẽ nhạt hơn phần còn lại.
#
# Với ngưỡng 80 thì nét xám 150 vẫn ra xám 150 — in xong nhìn như bị mờ.
# Với 170 thì mọi thứ tối hơn 170 đều thành đen tuyền, nét đều hẳn.
# Đo lại: 17.7% -> 5.4% pixel còn xám.
LEVELS_BLACK = 170   # <= giá trị này -> đen tuyền
LEVELS_WHITE = 200   # >= giá trị này -> trắng tinh

# NGƯỠNG CỤC BỘ — chữa lỗi "nét chỗ mờ chỗ đậm".
#
# Flux vẽ có phân cấp: chủ thể chính nét đen đậm, còn nền (cây, người ở xa,
# hoa cỏ) nét xám nhạt. Đo trên ảnh thật: vùng con chó có 50.7% mực là đen
# tuyền, vùng cậu bé phía sau chỉ 28.7%.
#
# NGƯỠNG TOÀN CỤC KHÔNG CHỮA ĐƯỢC, và đây là lý do:
# nét mờ (215) và nền trắng ngà (240) nằm gần nhau trên thang xám. Hạ ngưỡng
# đen xuống đủ thấp để bắt nét mờ thì cũng bắt luôn nền — bóng đổ mờ dưới
# chân con vật biến thành vệt xám bẩn giữa trang. Đo được: với 170/200 thì
# 29.6% lượng mực bị đẩy thành trắng, tức là XOÁ MẤT nét mờ chứ không làm
# đậm nó.
#
# Ngưỡng cục bộ so mỗi điểm với TRUNG BÌNH VÙNG QUANH NÓ. Nét mờ vẫn là chỗ
# tối hơn hẳn hàng xóm nên thành đen; còn mảng bóng mờ thì đổi rất từ từ nên
# không đâu tối hơn hàng xóm, thành trắng sạch. Nó phân biệt bằng CẤU TRÚC
# chứ không bằng độ sáng tuyệt đối — đúng thứ cần.
#
# Đo trên 10 ảnh thật:
#     cách cũ  11.74% mực,  7.37% mực còn xám nhờ
#     cách mới 11.26% mực,  0.00% mực còn xám nhờ
#
# Cửa sổ 101 px ở khổ in (~0.34 in): đủ rộng để một nét mảnh không tự kéo
# trung bình vùng xuống theo mình.
ADAPTIVE_INK = True     # False = quay lại ngưỡng toàn cục
ADAPTIVE_WINDOW = 101   # px, phải là số lẻ
ADAPTIVE_OFFSET = 12    # tối hơn hàng xóm chừng này thì tính là nét

# Làm mịn TRƯỚC khi khử xám, để viền nét bớt lồi lõm.
#
# Thứ tự: phóng to -> làm mịn -> khử xám. Làm mịn trên ảnh đã phóng thì mới
# xoá được cái gợn bị khuếch đại; làm trước khi phóng thì gợn vẫn còn nguyên.
# Khử xám sau cùng để ép lại thành nét đen dứt khoát, không bị mờ.
#
# 0 = tắt. Trên 3.5 thì chi tiết nhỏ bắt đầu dính vào nhau.
#
# HẠ 2.5 -> 1.0. Đây là một nửa nguyên nhân làm ảnh out vỡ nét.
# Cơ chế: làm mờ đẩy mực loang ra ngoài, rồi khử xám ở mức 170 BẮT LẠI toàn
# bộ phần loang đó thành đen tuyền. Hai bước cộng lại = một phép giãn nét
# trá hình. Bán kính càng lớn nét càng phình.
SMOOTH_RADIUS = 1.0

# Nối khe hở trên nét bằng phép đóng hình thái (giãn rồi co).
#
# HẠ 9 -> 3. Đây là nửa còn lại.
#
# Tôi đặt 9 vì đo được số mảnh rời giảm từ 83 xuống 42. Con số đó đúng, nhưng
# tôi CHỈ ĐO MỘT PHÍA. Phép đóng 9px lấp mọi khe trắng hẹp hơn 9px — mà tâm
# bông hồng, đường xoắn, nụ hoa nhỏ đều có khe trắng cỡ đó. Chúng bị bít
# thành mảng đen đặc. Bao nhìn ra ngay, còn chỉ số của tôi thì không, vì tôi
# chưa bao giờ đo phần MỰC PHÌNH RA.
#
# Đo lại trên 4 ảnh thật, so với ảnh gốc đã phóng to:
#
#   làm mịn / khử xám / nối khe |  phình nét   còn xám   mảnh rời
#   2.5 / 170 / 9  (cũ)         |    +38.1%     5.01%       12
#   1.0 / 170 / 3  (mới)        |    +21.3%     3.92%       15
#   0   / 170 / 1               |    +18.0%     3.43%       16
#
# Cấu hình cũ phình gần gấp đôi mà còn xám NHIỀU HƠN — nó thua ở cả hai cột
# nó lẽ ra phải thắng. Đổi lại chỉ được 3 mảnh rời, quá đắt.
CLOSE_GAPS = 3

# Làm DÀY nét lên (chỉ giãn, không co lại).
#
# Đây là chỗ duy nhất chắc chắn ăn. Đo trên ảnh thật: bào mòn nét 1 pixel là
# nét biến mất gần hết (điểm 0.00-0.04), tức nét chỉ dày 1-2 px ở khổ in —
# in ra sẽ mảnh như sợi tóc. Prompt có ghi "thick bold outlines" nhưng Flux
# schnell 4 bước vẽ sao thì ra vậy, chữ trong prompt không cãi lại được.
#
# Phép giãn thì không phụ thuộc model: nét bao nhiêu cũng dày thêm đúng
# ngần ấy pixel.
#
# Mặc định TẮT. Khâu làm mịn + khử xám ở trên đã làm dày nét sẵn (+21%).
# Bật thêm cái này nữa thì chi tiết nhỏ bắt đầu bít lại — đúng lỗi vừa sửa.
# Vẫn giữ làm nút vặn: sách cho bé 3 tuổi ít chi tiết có thể đặt 3.
LINE_THICKEN = 0

# Trần cho phép nét phình ra sau xử lý, so với ảnh gốc đã phóng to.
#
# Có con số này vì lỗi "ảnh raw đẹp mà ảnh out vỡ nét" trước đây KHÔNG có
# chỉ số nào bắt được — tôi chỉ đo mảnh rời và độ xám, cả hai đều nói tốt
# lên trong khi tranh thì hỏng đi. Giờ mỗi lần chỉnh ba tham số trên, kiểm
# thử đối chiếu lại với ngưỡng này.
INK_GROWTH_MAX = 0.28

# Bìa thì NGƯỢC HẲN trang ruột: ruột phải trắng, bìa phải rực.
# Đo 4 bìa đã sinh (độ bão hoà trung bình / tỉ lệ diện tích gần như không màu):
#     manmat 202 · 0.7%      <- đúng thứ cần
#     thu-hoa 115 · 33.7%
#     chihuahua 83 · 71.7%
#     ngay-hoi-bien 27 · 92.1%   <- nền trắng xoá, lên kệ là chìm nghỉm
# Cắt ở 90 và 55%: đủ để bắt hai bìa nhạt mà không đụng hai bìa đạt.
# SIẾT LẠI theo cuốn sách mẫu Bao đưa, thay vì theo bìa tự sinh của mình.
# Lấy bìa mình làm chuẩn thì chỉ chuẩn hoá được cái mức đang có; lấy sách
# thương mại làm chuẩn thì mới biết còn cách đích bao xa.
#
#     sách mẫu Hawaii     bão hoà 131.9   nhạt 15.9%   <- ĐÍCH
#     manmat              202    0.5%
#     thu-hoa             115   32.2%
#     chihuahua            83   69.1%
#     bìa penguin          24   87.0%     <- prompt cũ của tôi đẻ ra
COVER_SAT_MIN = 100.0
COVER_PALE_MAX = 0.35

# Bìa phải trông như TRANG TÔ MÀU ĐÃ ĐƯỢC TÔ — nét đen giữ nguyên, chỉ khác
# là bên trong đổ màu. Khách nhìn bìa là biết bên trong tô ra thành cái gì.
# Tỉ lệ pixel nét đen trên 4 bìa cũ:
#     thu-hoa 14.2%   <- đúng thứ cần
#     manmat 7.3% · ngay-hoi-bien 5.5%
#     chihuahua 1.8%  <- gần như không có nét, nhìn không ra sách tô màu
COVER_OUTLINE_MIN = 0.04

# Ô mã vạch trên BÌA SAU. Lulu in mã vạch ISBN vào góc dưới bên phải bìa sau,
# và vùng đó phải sáng màu, không có hình. Trước đây bìa sau chỉ là một mảng
# màu trơn nên chuyện này không thành vấn đề; giờ bìa sau có ảnh thì phải
# chừa chỗ, nếu không mã vạch đè lên hình và máy quét đọc không ra.
BARCODE_W_IN = 2.0
BARCODE_H_IN = 1.2
BARCODE_MARGIN_IN = 0.25

# VIỀN ĐEN quanh trang ruột.
#
# Đừng nhầm với "no frame, no border" trong prompt ảnh. Hai thứ khác hẳn:
#   · prompt cấm Flux TỰ vẽ khung trang trí — khung đó lệch lạc, toàn nét
#     mảnh, và mỗi trang một kiểu
#   · cái này là khung do studio vẽ, thẳng thớm, giống hệt nhau ở mọi trang
#
# Vẽ đúng trên đường bao vùng vẽ an toàn, nới ra một chút để không chạm hình.
# Vùng vẽ đã cách mép xén 0.5 in nên khung không bao giờ bị xén mất.
#
PAGE_BORDER_PX = 8         # 0 = tắt hẳn

# Khung ôm sát HÌNH THẬT, không phải ôm cái hộp cố định.
#
# Hình được thu vào hộp vùng vẽ theo tỉ lệ gốc nên gần như luôn hụt một chiều
# vài pixel. Vẽ khung ở mép hộp thì hở ra một khe, còn vẽ ở mép hình thì khung
# ăn sát nét vẽ — đúng như sách tô màu thật.
#
# 0.02 in = 6 px: đủ để nét vẽ không dính vào khung, mà mắt vẫn thấy là sát.
PAGE_BORDER_INSET_IN = 0.02

# 0 = góc vuông. Bo góc nhìn mềm hơn nhưng làm khung tách khỏi hình, mà hình
# thì góc vuông.
PAGE_BORDER_RADIUS_PX = 0

# Ngưỡng cảnh báo tự động (Phase 2 sẽ dùng để lọc trước khi mắt người nhìn)
INK_RATIO_MIN = 0.005  # dưới 0.5% -> trang gần như trắng
INK_RATIO_MAX = 0.40   # trên 40%  -> trang đen kịt
THIN_LINE_MAX = 0.55   # tỉ lệ nét biến mất sau khi bào mòn 1px

# Trang ruột phải TRẮNG HOÀN TOÀN để trẻ tô.
# Bìa thì ngược lại — bìa phải có màu, nên không áp ngưỡng này cho bìa.
#
# HAI ngưỡng cho HAI kiểu hỏng ngược nhau. Cả hai con số dưới đây đo từ 20
# ảnh thật trong library/, không phải đoán:
#
#   mảng màu đậm  má hồng nhân vật, vật được tô sẵn.
#                 ĐẬM mà HẸP — chỉ 0.4% diện tích.
#                 ảnh bẩn 0.37-21%  |  ảnh sạch <= 0.15%   -> cắt ở 0.2%
#                 Ngưỡng cũ là 1%, tức là lọt hết má hồng.
#
#   ám màu        cả trang phủ một lớp sắc nâu/xanh nhạt.
#                 NHẠT mà RỘNG — lệch kênh chỉ 8-30.
#                 ảnh bẩn 8.1 và 82  |  ảnh sạch <= 2.6    -> cắt ở 4.0
#                 Bản cũ chỉ đếm lệch > 30 nên đo ra ĐÚNG 0.00% và báo sạch.
COLOUR_RATIO_MAX = 0.002
COLOUR_TINT_MAX = 4.0


# --------------------------------------------------------------------------
# Ảnh xem trước cho web
# --------------------------------------------------------------------------

PREVIEW_PAGES = 3        # số trang mẫu phát công khai
PREVIEW_WEB_WIDTH = 1000  # px
WATERMARK_TEXT = "PREVIEW"


# --------------------------------------------------------------------------
# Đường dẫn và biến môi trường
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    comfyui_url: str
    workflow: Path
    workflow_map: Path
    cover_workflow: Path
    cover_workflow_map: Path
    library: Path
    steps: int | None
    guidance: float | None
    timeout: int


def _opt_int(key: str) -> int | None:
    v = os.environ.get(key, "").strip()
    return int(v) if v else None


def _opt_float(key: str) -> float | None:
    v = os.environ.get(key, "").strip()
    return float(v) if v else None


def load_settings() -> Settings:
    def _path(key: str, default: str) -> Path:
        p = Path(_env(key, default))
        return p if p.is_absolute() else ROOT / p

    return Settings(
        comfyui_url=_env("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/"),
        workflow=_path("STUDIO_WORKFLOW", "workflows/flux_lineart.api.json"),
        workflow_map=_path("STUDIO_WORKFLOW_MAP", "workflows/flux_lineart.map.json"),
        cover_workflow=_path(
            "STUDIO_COVER_WORKFLOW", "workflows/flux_cover.api.json"),
        cover_workflow_map=_path(
            "STUDIO_COVER_WORKFLOW_MAP", "workflows/flux_cover.map.json"),
        library=_path("STUDIO_LIBRARY", "library"),
        # Để TRỐNG trong .env thì dùng nguyên giá trị của workflow.
        #
        # Cần vậy vì mỗi model một kiểu: schnell chạy 4 bước CFG 1, còn SDXL
        # cần 28 bước CFG 7. Nhét một con số cố định vào .env là đổi workflow
        # xong lại quên sửa, rồi chạy SDXL với 4 bước ra ảnh nhiễu.
        steps=_opt_int("STUDIO_STEPS"),
        guidance=_opt_float("STUDIO_GUIDANCE"),
        timeout=int(_env("STUDIO_TIMEOUT", "600")),
    )


# --------------------------------------------------------------------------
# Bố cục thư mục một cuốn sách
# --------------------------------------------------------------------------
#   library/<slug>/
#       book.json          thông tin cuốn sách
#       raw/               ảnh vừa sinh, CHƯA duyệt
#           001.png
#           001.json       prompt, seed, tham số -> để sinh lại y hệt
#       approved/          ảnh đã qua mắt người
#       out/               interior.pdf, preview.pdf, web/*.webp


def book_dir(settings: Settings, slug: str) -> Path:
    return settings.library / slug


def raw_dir(settings: Settings, slug: str) -> Path:
    return book_dir(settings, slug) / "raw"


def approved_dir(settings: Settings, slug: str) -> Path:
    return book_dir(settings, slug) / "approved"


def out_dir(settings: Settings, slug: str) -> Path:
    return book_dir(settings, slug) / "out"
