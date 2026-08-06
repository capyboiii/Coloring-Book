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


def get_provider(settings: Settings, name: str = "comfyui", *,
                 cover: bool = False) -> ImageProvider:
    """cover=True dùng workflow sinh ảnh màu thay vì workflow line art."""
    if name == "comfyui":
        return ComfyUIProvider(
            base_url=settings.comfyui_url,
            workflow_path=(
                settings.cover_workflow if cover else settings.workflow),
            map_path=(
                settings.cover_workflow_map if cover else settings.workflow_map),
            timeout=settings.timeout,
        )
    raise ProviderError(
        f"Chưa hỗ trợ provider '{name}'. Phase 1 chỉ có 'comfyui'."
    )
