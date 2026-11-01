"""SAM 3 open weights, run in this process with Hugging Face transformers.

The model loads once, on first use, and waits in system memory. It moves onto the GPU only for
the second or so it runs, so the GPU stays free for Muse Glimmer writing the report; on an 8 GB
card the two do not fit together. It needs access to the gated facebook/sam3 repository: accept
the licence on Hugging Face and set HF_TOKEN.
"""
import io
import threading
from typing import Any

import numpy as np
from PIL import Image

from .config import Settings
from .meta_client import MetaAPIError

_lock = threading.Lock()
_loaded: dict[str, Any] = {}


class LocalSamError(MetaAPIError):
    """Reported to the user like any other failed model call."""


def _load(settings: Settings) -> tuple[Any, Any, str]:
    with _lock:
        if not _loaded:
            try:
                import torch
                from transformers import Sam3Model, Sam3Processor
            except ImportError as exc:
                raise LocalSamError("PyTorch and transformers are not installed; run scripts/setup_local_models.") from exc
            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if device == "cuda" else torch.float32
            cache = settings.models_dir / "hf"
            try:
                processor = Sam3Processor.from_pretrained(settings.local_sam_model, cache_dir=cache)
                model = Sam3Model.from_pretrained(settings.local_sam_model, cache_dir=cache, dtype=dtype).eval()
            except OSError as exc:
                raise LocalSamError(
                    f"Could not load {settings.local_sam_model}. Request access on Hugging Face and set HF_TOKEN in backend/.env."
                ) from exc
            _loaded.update(processor=processor, model=model, device=device, dtype=dtype)
        return _loaded["processor"], _loaded["model"], _loaded["device"]


def segment(settings: Settings, png_bytes: bytes, phrases: list[str], threshold: float = 0.4) -> dict[str, list[tuple[np.ndarray, float]]]:
    """Masks and scores for each text concept, at the image's own size."""
    import torch

    processor, model, device = _load(settings)
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    found: dict[str, list[tuple[np.ndarray, float]]] = {}
    with _lock, torch.inference_mode():
        model.to(device)
        try:
            _run(processor, model, device, image, phrases, threshold, found)
        finally:
            if device == "cuda":
                model.to("cpu")
                torch.cuda.empty_cache()
    return found


def _run(processor: Any, model: Any, device: str, image: Image.Image, phrases: list[str], threshold: float, found: dict) -> None:
    # The image is encoded once; each concept only runs the light prompt decoder.
    vision = processor(images=image, return_tensors="pt").to(device)
    embeds = model.get_vision_features(pixel_values=vision.pixel_values.to(_loaded["dtype"]))
    for phrase in phrases:
        text = processor(text=phrase, return_tensors="pt").to(device)
        outputs = model(vision_embeds=embeds, **text)
        result = processor.post_process_instance_segmentation(
            outputs, threshold=threshold, mask_threshold=0.5, target_sizes=vision.get("original_sizes").tolist()
        )[0]
        masks = result["masks"].cpu().numpy().astype(bool)
        scores = result["scores"].float().cpu().numpy()
        found[phrase] = [(m, float(s)) for m, s in zip(masks, scores) if m.any()]
