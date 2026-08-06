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
    steps: int
    guidance: float


class ImageProvider(ABC):
    """
    Phase 1 chỉ có ComfyUI. Lớp trừu tượng này để sau muốn đổi sang fal.ai
    hay Replicate thì chỉ thêm một file, không phải sửa lệnh generate.
    """

    name: str = "base"

    @abstractmethod
    def healthcheck(self) -> str:
        """Ném lỗi nếu không kết nối được. Trả về mô tả ngắn khi thành công."""

    @abstractmethod
    def generate(self, req: GenRequest) -> bytes:
        """Trả về nội dung file ảnh dạng bytes (PNG)."""


class ProviderError(RuntimeError):
    pass
