"""Stage 1: perception, normalised into Detection objects.

Interchangeable perceivers (PERCEIVER env var):
- mock: synthetic room geometry, no API calls.
- muse: grounding by the reasoning model (Muse Spark, or Muse Glimmer when local), which
        returns labelled boxes on a 0-1000 grid.
- sam:  SAM 3.1 masks over the Meta Model API. Its output schema is not published, so
        `parse_sam_response` walks the JSON and accepts the common encodings (base64 PNG,
        uncompressed RLE, polygons, boxes).
- sam_local: SAM 3 open weights run on this PC (see sam_local.py).
"""
import base64
import io
import json
from dataclasses import dataclass
from typing import Any, Iterator

import numpy as np
from PIL import Image, ImageDraw

# Noun phrase sent to SAM -> internal label
ELEMENT_PROMPTS: dict[str, str] = {
    "wall": "wall",
    "floor": "floor",
    "ceiling": "ceiling",
    "door": "door",
    "window": "window",
    "fixture": "light fixture",
}
DEFECT_PROMPTS: dict[str, str] = {
    "crack": "crack in wall",
    "damp": "damp stain",
    "peeling": "peeling paint",
}

# Never counted or priced. Used to tell how much of each wall is hidden, and to drop wardrobe and
# cabinet doors (and dresser mirrors) that SAM 3 also calls doors and windows.
FURNITURE_PROMPTS = ("furniture", "wardrobe")
# An opening lying at least this much inside furniture belongs to the furniture.
INSIDE_FURNITURE = 0.5
# SAM 3 (local) phrases and score floors, tuned on the sample photos: "crack" scores higher than
# "crack in wall", "water stain" finds damp that "damp stain" misses, and "peeling paint" fires
# weakly on cracks, so it needs a higher bar.
SAM3_PROMPTS: dict[str, str] = {**ELEMENT_PROMPTS, "crack": "crack", "damp": "water stain", "peeling": "peeling paint"}
SAM3_MIN_SCORE: dict[str, float] = {"damp": 0.3, "peeling": 0.5}
SAM3_DEFAULT_MIN = 0.4

MASK_KEYS = ("mask", "segmentation", "rle", "polygon", "polygons", "points")
BOX_KEYS = ("box", "bbox", "bounding_box")


@dataclass
class Detection:
    label: str
    score: float
    mask: np.ndarray  # bool, shape (height, width)
    source: str = "mock"
    hidden: float = 0.0  # share of the instance covered by furniture, as judged by the model

    @property
    def box(self) -> list[int]:
        ys, xs = np.nonzero(self.mask)
        if len(xs) == 0:
            return [0, 0, 0, 0]
        return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if any(k in node for k in MASK_KEYS + BOX_KEYS):
            yield node
            return
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, str) and node.lstrip().startswith(("{", "[")):
        # Geometry may arrive as JSON text inside an output_text block.
        try:
            yield from _walk(json.loads(node))
        except ValueError:
            return


def _scale_points(points: list[list[float]], width: int, height: int) -> list[tuple[float, float]]:
    flat = [v for p in points for v in p]
    normalised = flat and max(flat) <= 1.0
    return [(x * width, y * height) if normalised else (x, y) for x, y in points]


def decode_png_mask(data: str, width: int, height: int) -> np.ndarray:
    if data.startswith("data:"):
        data = data.split(",", 1)[1]
    img = Image.open(io.BytesIO(base64.b64decode(data))).convert("L")
    if img.size != (width, height):
        img = img.resize((width, height), Image.NEAREST)
    return np.array(img) > 127


def decode_rle(rle: dict[str, Any], width: int, height: int) -> np.ndarray:
    """Uncompressed COCO RLE: column-major run lengths starting with zeros."""
    counts = rle["counts"]
    if isinstance(counts, str):
        raise ValueError("Compressed RLE strings are not supported yet")
    h, w = rle.get("size", [height, width])
    flat = np.zeros(h * w, dtype=bool)
    pos, value = 0, False
    for run in counts:
        flat[pos : pos + run] = value
        pos += run
        value = not value
    mask = flat.reshape((w, h)).T
    if (w, h) != (width, height):
        mask = np.array(Image.fromarray(mask).resize((width, height), Image.NEAREST))
    return mask


def polygon_mask(points: list[list[float]], width: int, height: int) -> np.ndarray:
    img = Image.new("L", (width, height), 0)
    ImageDraw.Draw(img).polygon(_scale_points(points, width, height), fill=255)
    return np.array(img) > 0


def box_mask(box: list[float], width: int, height: int) -> np.ndarray:
    x0, y0, x1, y1 = box
    if max(box) <= 1.0:
        x0, x1, y0, y1 = x0 * width, x1 * width, y0 * height, y1 * height
    mask = np.zeros((height, width), dtype=bool)
    mask[int(y0) : int(y1), int(x0) : int(x1)] = True
    return mask


def _decode(item: dict[str, Any], width: int, height: int) -> np.ndarray | None:
    for key in MASK_KEYS:
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return decode_png_mask(value, width, height)
        if isinstance(value, dict) and "counts" in value:
            return decode_rle(value, width, height)
        if isinstance(value, list) and value:
            # One polygon [[x,y],...] or several [[[x,y],...], ...]
            polys = value if isinstance(value[0][0], list) else [value]
            mask = np.zeros((height, width), dtype=bool)
            for poly in polys:
                mask |= polygon_mask(poly, width, height)
            return mask
    for key in BOX_KEYS:
        if item.get(key):
            return box_mask(item[key], width, height)
    return None


def parse_sam_response(data: Any, label: str, width: int, height: int) -> list[Detection]:
    detections = []
    for item in _walk(data):
        mask = _decode(item, width, height)
        if mask is None or not mask.any():
            continue
        score = float(item.get("score", item.get("confidence", 0.5)))
        detections.append(Detection(label=label, score=score, mask=mask, source="sam-3.1"))
    return detections


def mark_hidden(detections: list[Detection], furniture: list[np.ndarray]) -> list[Detection]:
    """Share of each wall's extent that furniture covers. SAM traces walls around furniture, so
    the wall's bounding box stands in for the whole wall."""
    if not furniture:
        return detections
    cover = np.logical_or.reduce(furniture)
    for d in detections:
        if d.label == "wall":
            x0, y0, x1, y1 = d.box
            region = cover[y0 : y1 + 1, x0 : x1 + 1]
            if region.size:
                d.hidden = round(float(region.mean()), 2)
    return detections


def drop_furniture_openings(detections: list[Detection], furniture: list[np.ndarray]) -> list[Detection]:
    """A wardrobe's panels look like doors to SAM 3; a door or window inside furniture isn't one."""
    if not furniture:
        return detections
    cover = np.logical_or.reduce(furniture)
    return [
        d
        for d in detections
        if d.label not in ("door", "window") or (d.mask & cover).sum() < INSIDE_FURNITURE * d.mask.sum()
    ]


def perceive_with_sam_local(settings: Any, png_bytes: bytes) -> list[Detection]:
    from . import sam_local

    lowest = min(SAM3_DEFAULT_MIN, *SAM3_MIN_SCORE.values())
    found = sam_local.segment(settings, png_bytes, [*SAM3_PROMPTS.values(), *FURNITURE_PROMPTS], threshold=lowest)
    detections = [
        Detection(label, score, mask, source="sam-3")
        for label, phrase in SAM3_PROMPTS.items()
        for mask, score in found.get(phrase, [])
        if score >= SAM3_MIN_SCORE.get(label, SAM3_DEFAULT_MIN)
    ]
    furniture = [mask for phrase in FURNITURE_PROMPTS for mask, score in found.get(phrase, []) if score >= SAM3_DEFAULT_MIN]
    return mark_hidden(drop_furniture_openings(detections, furniture), furniture)


def mock_detections(width: int, height: int) -> list[Detection]:
    """Plausible room geometry for any photo, so the app runs without an API key."""

    def rect(x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
        return box_mask([x0, y0, x1, y1], width, height)

    wall = rect(0, 0.12, 1, 0.68)
    door = rect(0.12, 0.28, 0.27, 0.68)
    window = rect(0.55, 0.25, 0.82, 0.48)
    wall &= ~door & ~window
    crack = polygon_mask([[0.40, 0.20], [0.41, 0.20], [0.46, 0.45], [0.45, 0.45]], width, height)
    damp = polygon_mask([[0.85, 0.55], [0.95, 0.52], [0.98, 0.66], [0.86, 0.67]], width, height)
    return [
        Detection("ceiling", 0.88, rect(0, 0, 1, 0.12)),
        Detection("wall", 0.91, wall),
        Detection("floor", 0.93, rect(0, 0.68, 1, 1)),
        Detection("door", 0.86, door),
        Detection("window", 0.84, window),
        Detection("fixture", 0.62, rect(0.45, 0.02, 0.55, 0.08)),
        Detection("crack", 0.58, crack),
        Detection("damp", 0.49, damp),
    ]


def perceive_with_sam(client: Any, png_bytes: bytes, width: int, height: int) -> list[Detection]:
    detections: list[Detection] = []
    for label, phrase in {**ELEMENT_PROMPTS, **DEFECT_PROMPTS}.items():
        raw = client.segment(png_bytes, phrase)
        detections.extend(parse_sam_response(raw, label, width, height))
    return detections


GROUNDING_PROMPT = """Locate construction elements and visible defects in this site photo.
Return ONLY a JSON array. Each item: {"label": one of %s, "box": [x_min, y_min, x_max, y_max], "score": 0.0-1.0}.
Box coordinates are on a 0-1000 grid relative to the image width and height.
One item per visible instance (each door, each window). Doors are room doors only: never wardrobe,
cupboard or cabinet doors. Mirrors and pictures are not windows. Use one box per wall surface and draw it
over the whole wall, including parts behind furniture.
For each wall also give "hidden": 0.0-1.0, the share of that wall covered by furniture or objects.
Only report defects you can actually see; lower the score when unsure."""


def parse_grounding(data: Any, width: int, height: int) -> list[Detection]:
    """Muse Spark grounding output: labelled boxes on a 0-1000 grid."""
    items = data.get("detections", data.get("objects", [])) if isinstance(data, dict) else data
    allowed = set(ELEMENT_PROMPTS) | set(DEFECT_PROMPTS)
    detections = []
    for item in items if isinstance(items, list) else []:
        try:
            label = str(item["label"]).lower().strip()
            x0, y0, x1, y1 = (float(v) for v in item["box"])
        except (KeyError, TypeError, ValueError):
            continue
        if label not in allowed:
            continue
        x0, x1 = sorted((max(0.0, min(1000.0, x0)), max(0.0, min(1000.0, x1))))
        y0, y1 = sorted((max(0.0, min(1000.0, y0)), max(0.0, min(1000.0, y1))))
        mask = box_mask([x0 / 1000, y0 / 1000, x1 / 1000, y1 / 1000], width, height)
        if not mask.any():
            continue
        score = float(item.get("score", 0.5))
        try:
            hidden = max(0.0, min(1.0, float(item.get("hidden") or 0.0)))
        except (TypeError, ValueError):
            hidden = 0.0
        detections.append(Detection(label, max(0.0, min(1.0, score)), mask, "muse-grounding", hidden))
    return detections


def perceive_with_muse(client: Any, png_bytes: bytes, width: int, height: int, source: str = "muse-grounding") -> list[Detection]:
    from .meta_client import image_data_url
    from .reason import extract_json

    labels = ", ".join(f'"{label}"' for label in {**ELEMENT_PROMPTS, **DEFECT_PROMPTS})
    text = client.chat(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": GROUNDING_PROMPT % labels},
                    {"type": "image_url", "image_url": {"url": image_data_url(png_bytes)}},
                ],
            }
        ],
        prefill="[",
        temperature=0,
    )
    detections = parse_grounding(extract_json(text), width, height)
    for d in detections:
        d.source = source
    return detections


def merge_defects(detections: list[Detection], gap: float = 0.04) -> list[Detection]:
    """SAM can return one defect as several masks: duplicates, or a damp area split into many small
    patches. Patches of the same kind whose boxes come within `gap` (a share of the image size) of
    each other become one defect, so one damp wall is not priced as twelve treatments."""
    defects = sorted((d for d in detections if d.label in DEFECT_PROMPTS), key=lambda d: -d.score)
    if not defects:
        return detections
    height, width = defects[0].mask.shape
    pad_x, pad_y = gap * width, gap * height

    def near(a: list[int], b: list[int]) -> bool:
        return a[0] - pad_x <= b[2] and b[0] - pad_x <= a[2] and a[1] - pad_y <= b[3] and b[1] - pad_y <= a[3]

    groups: list[list[Detection]] = []
    for d in defects:
        joined = [g for g in groups if g[0].label == d.label and any(near(d.box, m.box) for m in g)]
        merged = [d] + [m for g in joined for m in g]
        groups = [g for g in groups if not any(g is j for j in joined)] + [merged]  # identity: masks can't be ==
    merged_defects = [
        Detection(g[0].label, max(m.score for m in g), np.logical_or.reduce([m.mask for m in g]), g[0].source)
        for g in groups
    ]
    return [d for d in detections if d.label not in DEFECT_PROMPTS] + merged_defects


# Elements thinner than this share of the image (or smaller in area) are edge slivers, not walls,
# doors or windows: a 3-pixel strip of the next wall at the photo's edge, for example.
MIN_ELEMENT_SIDE = 0.03
MIN_ELEMENT_AREA = 0.004
# A door or window lying this much inside a bigger one of the same kind is one of its panels.
PART_OF = 0.8


def drop_slivers_and_parts(detections: list[Detection]) -> list[Detection]:
    """SAM 3 also returns edge slivers of neighbouring walls, and the panels of a two-tone door as
    extra doors. Keep whole elements only; defects are handled by merge_defects."""
    kept: list[Detection] = []
    for d in sorted(detections, key=lambda d: -int(d.mask.sum())):
        if d.label not in ELEMENT_PROMPTS:
            kept.append(d)
            continue
        height, width = d.mask.shape
        x0, y0, x1, y1 = d.box
        area = int(d.mask.sum())
        if (x1 - x0 + 1) < MIN_ELEMENT_SIDE * width or (y1 - y0 + 1) < MIN_ELEMENT_SIDE * height:
            continue
        if area < MIN_ELEMENT_AREA * width * height:
            continue
        if any(k.label == d.label and (k.mask & d.mask).sum() >= PART_OF * area for k in kept):
            continue
        kept.append(d)
    return kept


# Open door leaves seen edge-on are narrow; two of them close together are one double doorway.
LEAF_MAX_WIDTH = 0.08
LEAF_MAX_GAP = 3.0  # times the wider leaf


def join_double_doors(detections: list[Detection]) -> list[Detection]:
    """An open double door shows as two narrow leaves with the doorway between them: one door."""
    doors = sorted((d for d in detections if d.label == "door"), key=lambda d: d.box[0])
    others = [d for d in detections if d.label != "door"]
    if len(doors) < 2:
        return detections
    width = doors[0].mask.shape[1]
    joined: list[Detection] = []
    for d in doors:
        prev = joined[-1] if joined else None
        if prev is not None:
            (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = prev.box, d.box
            widths = ax1 - ax0, bx1 - bx0
            overlap = min(ay1, by1) - max(ay0, by0)
            if (
                max(widths) < LEAF_MAX_WIDTH * width
                and 0 <= bx0 - ax1 <= LEAF_MAX_GAP * max(widths)
                and overlap >= 0.7 * min(ay1 - ay0, by1 - by0)
            ):
                joined[-1] = Detection("door", max(prev.score, d.score), prev.mask | d.mask, prev.source)
                continue
        joined.append(d)
    return others + joined


def drop_through_doorways(detections: list[Detection]) -> list[Detection]:
    """Through an open doorway the next room shows: its wall, floor or window is not this room's.
    The doorway is the door's box, widened by one door width each side (the opening sits beside an
    open leaf)."""
    regions = []
    for d in detections:
        if d.label == "door":
            x0, y0, x1, y1 = d.box
            w, h = x1 - x0, y1 - y0
            regions.append((x0 - w, y0 - 0.05 * h, x1 + w, y1 + 0.05 * h))

    def inside(box: list[int]) -> bool:
        x0, y0, x1, y1 = box
        return any(rx0 <= x0 and ry0 <= y0 and x1 <= rx1 and y1 <= ry1 for rx0, ry0, rx1, ry1 in regions)

    return [d for d in detections if d.label not in ("wall", "floor", "window") or not inside(d.box)]


def separate_openings(detections: list[Detection]) -> list[Detection]:
    """A sliding window's panes look like doors to SAM 3, and a door's glass panel like a window.
    A door lying mostly inside a window is a pane; a window lying mostly inside a door is its glass."""
    windows = [d.mask for d in detections if d.label == "window"]
    if windows:
        glass = np.logical_or.reduce(windows)
        detections = [d for d in detections if d.label != "door" or (d.mask & glass).sum() < INSIDE_FURNITURE * d.mask.sum()]
    doors = [d.mask for d in detections if d.label == "door"]
    if doors:
        leaf = np.logical_or.reduce(doors)
        detections = [d for d in detections if d.label != "window" or (d.mask & leaf).sum() < INSIDE_FURNITURE * d.mask.sum()]
    return detections


def refine(detections: list[Detection]) -> list[Detection]:
    """Drop edge slivers, door panels and window panes taken for doors, merge split or duplicate
    defects, and cut openings out of
    walls so wall area is not double counted with doors and windows."""
    detections = drop_slivers_and_parts(detections)
    detections = drop_through_doorways(join_double_doors(separate_openings(detections)))
    detections = merge_defects(detections)
    openings = [d.mask for d in detections if d.label in ("door", "window")]
    if not openings:
        return detections
    holes = np.logical_or.reduce(openings)
    refined = []
    for d in detections:
        if d.label == "wall":
            d = Detection(d.label, d.score, d.mask & ~holes, d.source, d.hidden)
        if d.mask.any():
            refined.append(d)
    return refined


def detect(perceiver: str, client: Any, png_bytes: bytes, width: int, height: int) -> list[Detection]:
    if perceiver == "mock" or client is None:
        return mock_detections(width, height)
    if perceiver == "sam":
        return refine(perceive_with_sam(client, png_bytes, width, height))
    if perceiver == "sam_local":
        return refine(perceive_with_sam_local(client.settings, png_bytes))
    local = getattr(getattr(client, "settings", None), "backend", "meta") == "local"
    return refine(perceive_with_muse(client, png_bytes, width, height, "glimmer-grounding" if local else "muse-grounding"))
