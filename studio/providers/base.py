"""Giao diện chung cho mọi nguồn sinh ảnh."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenRequest:
    prompt: str
    negative: str
    seed: int
    width: int
    height: int
    steps: int | None
    guidance: float | None
    # Để trống nghĩa là không dùng LoRA. Workflow nào có node LoraLoader thì
    # studio tự gỡ node đó ra và nối thẳng checkpoint vào sampler.
    lora: str | None = None
    lora_strength: float = 0.9


class ImageProvider(ABC):
    """
    Phase 1 chỉ có ComfyUI. Lớp trừu tượng này để sau muốn đổi sang fal.ai
    hay Replicate thì chỉ thêm một file, không phải sửa lệnh generate.
    """

    name: str = "base"

    #: Tham số mà provider này thực sự áp dụng được. Ví dụ FLUX.1-schnell
    #: không có guidance, nên 'guidance' sẽ vắng mặt và CLI biết mà bỏ qua
    #: thay vì in ra một con số không có tác dụng gì.
    supported_params: frozenset[str] = frozenset()

    @abstractmethod
    def healthcheck(self) -> str:
        """Ném lỗi nếu không kết nối được. Trả về mô tả ngắn khi thành công."""

    @abstractmethod
    def generate(self, req: GenRequest) -> bytes:
        """Trả về nội dung file ảnh dạng bytes (PNG)."""


class ProviderError(RuntimeError):
    pass
