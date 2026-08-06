"""Kiểm tra môi trường trước khi chạy mẻ 40 ảnh."""

from __future__ import annotations

from .. import config
from ..providers import ProviderError, get_provider
from ..util import info


def register(subparsers) -> None:
    p = subparsers.add_parser(
        "doctor",
        help="Kiểm tra ComfyUI, workflow và thư viện phụ thuộc",
    )
    p.set_defaults(func=run)


def _check(label: str, fn) -> bool:
    try:
        detail = fn()
        info(f"  ✓ {label}" + (f" — {detail}" if detail else ""))
        return True
    except Exception as exc:  # noqa: BLE001 - doctor cốt để hiện lỗi
        info(f"  ✗ {label} — {exc}")
        return False


def run(args) -> int:
    settings = config.load_settings()
    ok = True

    info("Thư viện phụ thuộc")

    def _pillow():
        import PIL
        return f"Pillow {PIL.__version__}"

    def _reportlab():
        import reportlab
        return f"reportlab {reportlab.Version}"

    ok &= _check("Pillow", _pillow)
    ok &= _check("reportlab", _reportlab)

    info("")
    info("Cấu hình")
    info(f"  Thư viện sách : {settings.library}")
    info(f"  Workflow      : {settings.workflow}")
    info(f"  Map node      : {settings.workflow_map}")

    info("")
    info("Spec in ấn")
    info(f"  Khổ trim      : {config.TRIM_W_IN} x {config.TRIM_H_IN} in")
    info(f"  Khổ file PDF  : {config.PAGE_W_IN} x {config.PAGE_H_IN} in "
         f"(bleed {config.BLEED_IN} in)")
    info(f"  Vùng vẽ       : {config.ART_W_IN} x {config.ART_H_IN} in "
         f"(safety {config.SAFETY_IN}, gutter {config.GUTTER_IN})")
    info(f"  Pixel/trang   : {config.PAGE_W_PX} x {config.PAGE_H_PX} @ "
         f"{config.DPI} DPI")
    info(f"  Sinh ảnh ở    : {config.GEN_W} x {config.GEN_H} px")

    info("")
    info("Model workflow đang gọi")
    try:
        provider = get_provider(settings, "comfyui")
        for label, name in provider.models().items():
            info(f"  {label:<12}: {name}")
        info(f"  Tham số dùng: {', '.join(sorted(provider.supported_params))}")
    except Exception as exc:  # noqa: BLE001
        info(f"  ✗ Không đọc được workflow — {exc}")
        provider = None
        ok = False

    info("")
    info(f"ComfyUI ({settings.comfyui_url})")

    def _provider():
        if provider is None:
            raise RuntimeError("workflow lỗi, xem ở trên")
        return provider.healthcheck()

    if not _check("Kết nối + workflow hợp lệ", _provider):
        ok = False
        info("")
        info("  Gợi ý:")
        info("   · ComfyUI đã chạy chưa? Mặc định http://127.0.0.1:8188")
        info("   · Workflow phải export dạng API format")
        info("     (Settings → bật Dev mode → nút 'Save (API Format)')")
        info("   · Tên model trong workflow phải khớp file trong models/")

    info("")
    info("Tổng kết: " + ("sẵn sàng chạy" if ok else "còn lỗi, xem ở trên"))
    return 0 if ok else 1
