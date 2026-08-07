"""
Nói chuyện với ComfyUI đang chạy local qua HTTP.

Luồng:
  1. POST /prompt      đẩy workflow vào hàng đợi -> nhận prompt_id
  2. GET  /history/id  hỏi lại tới khi có kết quả
  3. GET  /view        tải file ảnh về

Dùng polling thay vì websocket: ít phụ thuộc hơn, và với tác vụ chạy hàng
loạt thì độ trễ vài giây không quan trọng.

Workflow phải là bản export dạng **API format** (Settings -> bật Dev mode ->
nút "Save (API Format)"), không phải file .json kéo thả thông thường.
"""

from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path

import requests

from .base import GenRequest, ImageProvider, ProviderError


class ComfyUIProvider(ImageProvider):
    name = "comfyui"

    def __init__(
        self,
        base_url: str,
        workflow_path: Path,
        map_path: Path,
        timeout: int = 600,
        poll_interval: float = 1.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.client_id = str(uuid.uuid4())

        if not workflow_path.exists():
            raise ProviderError(f"Không tìm thấy workflow: {workflow_path}")
        if not map_path.exists():
            raise ProviderError(f"Không tìm thấy file map node: {map_path}")

        self.workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        raw_map = json.loads(map_path.read_text(encoding="utf-8"))
        # Khoá bắt đầu bằng '_' là ghi chú cho người đọc, bỏ qua
        self.node_map = {
            k: v for k, v in raw_map.items() if not k.startswith("_")
        }
        self._validate_map()
        self.supported_params = frozenset(self.node_map)

    # ---------------------------------------------------------------- setup

    def models(self) -> dict[str, str]:
        """Model nào đang được workflow tham chiếu — để doctor in ra."""
        fields = {
            "unet_name": "UNET",
            "vae_name": "VAE",
            "clip_name1": "CLIP 1",
            "clip_name2": "CLIP 2",
            "ckpt_name": "Checkpoint",
        }
        found: dict[str, str] = {}
        for node in self.workflow.values():
            for field, label in fields.items():
                value = node.get("inputs", {}).get(field)
                if isinstance(value, str):
                    found[label] = value
        return found

    def _validate_map(self) -> None:
        """Bắt lỗi map sai node NGAY, thay vì để chạy 40 ảnh xong mới biết."""
        required = ["prompt", "seed", "width", "height"]
        for key in required:
            if key not in self.node_map:
                raise ProviderError(f"File map thiếu khoá bắt buộc '{key}'")

        for key, ref in self.node_map.items():
            node_id = str(ref["node"])
            field = ref["field"]
            if node_id not in self.workflow:
                raise ProviderError(
                    f"Map trỏ tới node '{node_id}' (cho '{key}') "
                    f"nhưng workflow không có node đó"
                )
            if field not in self.workflow[node_id].get("inputs", {}):
                raise ProviderError(
                    f"Node '{node_id}' không có input '{field}' (cho '{key}')"
                )

    # ---------------------------------------------------------------- public

    def healthcheck(self) -> str:
        try:
            r = requests.get(f"{self.base_url}/system_stats", timeout=10)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise ProviderError(
                f"Không kết nối được ComfyUI tại {self.base_url}. "
                f"ComfyUI đã chạy chưa? Chi tiết: {exc}"
            ) from exc

        stats = r.json()
        devices = stats.get("devices") or []
        if devices:
            d = devices[0]
            vram_gb = d.get("vram_total", 0) / (1024**3)
            return f"{d.get('name', 'không rõ GPU')} · VRAM {vram_gb:.1f} GB"
        return "đã kết nối (không đọc được thông tin GPU)"

    def generate(self, req: GenRequest) -> bytes:
        workflow = self._patch(req)
        prompt_id = self._queue(workflow)
        outputs = self._wait(prompt_id)
        return self._download_first_image(outputs)

    # --------------------------------------------------------------- private

    def _patch(self, req: GenRequest) -> dict:
        """Ghi tham số vào bản sao workflow theo file map."""
        wf = copy.deepcopy(self.workflow)
        values = {
            "prompt": req.prompt,
            "negative": req.negative,
            "seed": req.seed,
            "width": req.width,
            "height": req.height,
            "steps": req.steps,
            "guidance": req.guidance,
        }
        for key, ref in self.node_map.items():
            # None nghĩa là "giữ nguyên giá trị trong workflow". Cần vậy vì
            # mỗi model một kiểu: schnell 4 bước CFG 1, SDXL 28 bước CFG 7.
            if key not in values or values[key] is None:
                continue
            wf[str(ref["node"])]["inputs"][ref["field"]] = values[key]
        return wf

    def _queue(self, workflow: dict) -> str:
        payload = {"prompt": workflow, "client_id": self.client_id}
        try:
            r = requests.post(f"{self.base_url}/prompt", json=payload, timeout=30)
        except requests.RequestException as exc:
            raise ProviderError(f"Không đẩy được job sang ComfyUI: {exc}") from exc

        if r.status_code != 200:
            # ComfyUI trả lỗi validate rất chi tiết, in nguyên văn ra cho dễ sửa
            raise ProviderError(
                f"ComfyUI từ chối workflow (HTTP {r.status_code}):\n{r.text[:2000]}"
            )

        prompt_id = r.json().get("prompt_id")
        if not prompt_id:
            raise ProviderError(f"ComfyUI không trả prompt_id: {r.text[:500]}")
        return prompt_id

    def _wait(self, prompt_id: str) -> dict:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            try:
                r = requests.get(
                    f"{self.base_url}/history/{prompt_id}", timeout=30
                )
                r.raise_for_status()
                history = r.json()
            except requests.RequestException:
                # ComfyUI bận nặng có thể lỡ nhịp, thử lại thay vì bỏ cuộc
                time.sleep(self.poll_interval)
                continue

            entry = history.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ProviderError(
                        f"ComfyUI chạy lỗi: "
                        f"{json.dumps(status, ensure_ascii=False)[:1000]}"
                    )
                if entry.get("outputs"):
                    return entry["outputs"]

            time.sleep(self.poll_interval)

        raise ProviderError(
            f"Quá {self.timeout}s vẫn chưa xong. Tăng STUDIO_TIMEOUT nếu GPU chậm."
        )

    def _download_first_image(self, outputs: dict) -> bytes:
        for node_output in outputs.values():
            for image in node_output.get("images", []):
                params = {
                    "filename": image["filename"],
                    "subfolder": image.get("subfolder", ""),
                    "type": image.get("type", "output"),
                }
                r = requests.get(
                    f"{self.base_url}/view", params=params, timeout=120
                )
                r.raise_for_status()
                return r.content

        raise ProviderError(
            "Workflow chạy xong nhưng không có ảnh nào ở output. "
            "Workflow đã có node SaveImage chưa?"
        )
