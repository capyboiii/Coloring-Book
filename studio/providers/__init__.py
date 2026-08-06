"""Chọn nguồn sinh ảnh."""

from __future__ import annotations

from ..config import Settings
from .base import GenRequest, ImageProvider, ProviderError
from .comfyui import ComfyUIProvider

__all__ = [
    "GenRequest",
    "ImageProvider",
    "ProviderError",
    "ComfyUIProvider",
    "get_provider",
]


def get_provider(settings: Settings, name: str = "comfyui") -> ImageProvider:
    if name == "comfyui":
        return ComfyUIProvider(
            base_url=settings.comfyui_url,
            workflow_path=settings.workflow,
            map_path=settings.workflow_map,
            timeout=settings.timeout,
        )
    raise ProviderError(
        f"Chưa hỗ trợ provider '{name}'. Phase 1 chỉ có 'comfyui'."
    )
