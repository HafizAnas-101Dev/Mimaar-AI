"""Stage 4 helpers: one transparent PNG layer per element type for the overlay viewer."""
import base64
import io

import numpy as np
from PIL import Image

from .perceive import Detection

COLORS: dict[str, str] = {
    "wall": "#4C9AFF",
    "floor": "#36B37E",
    "ceiling": "#B38DF7",
    "door": "#FFAB00",
    "window": "#00B8D9",
    "fixture": "#F5CD47",
    "crack": "#FF5630",
    "damp": "#E2483D",
    "peeling": "#FF8B00",
}


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def to_base64_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def render_layers(detections: list[Detection], width: int, height: int, alpha: int = 110) -> list[dict[str, str]]:
    layers = []
    for label in dict.fromkeys(d.label for d in detections):
        mask = np.logical_or.reduce([d.mask for d in detections if d.label == label])
        color = COLORS.get(label, "#FFFFFF")
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        rgba[mask] = (*_hex_to_rgb(color), alpha)
        layers.append({"type": label, "color": color, "png_base64": to_base64_png(Image.fromarray(rgba, "RGBA"))})
    return layers
