"""Stage 2: turn masks into counts, areas and (with a scale reference) square metres."""
import numpy as np

from .perceive import DEFECT_PROMPTS, ELEMENT_PROMPTS, Detection
from .schemas import DefectCandidate, ElementMeasurement, Measurements, Scale

# Typical sizes, used only when the customer has no tape measure. Every use is labelled as an
# estimate in the report and widens the cost range.
STANDARD_DOOR_M = 2.05
TYPICAL_CEILING_M = 3.0
DOOR_AREA_M2 = 1.85  # 0.9 m x 2.05 m
WINDOW_AREA_M2 = 1.5
ROOM_PRESETS: dict[str, tuple[float, float]] = {
    "bedroom": (3.5, 4.0),
    "master_bedroom": (4.5, 5.0),
    "living": (5.0, 6.0),
    "kitchen": (3.0, 3.5),
    "bathroom": (2.0, 2.5),
}
# Share of a wall hidden by furniture above which the report warns.
HIDDEN_WARN = 0.3

# Surfaces seen from several angles of one room overlap, so take the largest view;
# walls differ per photo, so add them up.
MAX_ACROSS_PHOTOS = {"floor", "ceiling"}

# Elements each kind of photo is trusted for. A floor photo also shows wall edges, but those
# walls are measured from the wall photos, so counting them here would double them.
ROLE_ELEMENTS: dict[str, set[str]] = {
    "floor": {"floor"},
    "ceiling": {"ceiling", "fixture"},
    "wall": {"wall", "door", "window"},
}


def filter_for_role(detections: list[Detection], role: str | None) -> list[Detection]:
    """Keep the role's own elements plus every defect; no role keeps everything."""
    if role is None:
        return detections
    keep = ROLE_ELEMENTS[role]
    return [d for d in detections if d.label in keep or d.label in DEFECT_PROMPTS]


def metres_per_pixel(detections: list[Detection], element: str, height_m: float) -> float | None:
    """Scale from the tallest instance of a reference element, e.g. a door of known height."""
    heights = [d.box[3] - d.box[1] for d in detections if d.label == element]
    if not heights or max(heights) <= 0 or height_m <= 0:
        return None
    return height_m / max(heights)


def measure(
    detections: list[Detection],
    width: int,
    height: int,
    scale_element: str | None = None,
    scale_height_m: float | None = None,
    assume_door: bool = False,
) -> Measurements:
    """`assume_door` falls back to a standard door height when the user gave no reference."""
    total = width * height
    mpp = None
    scale = Scale()
    if scale_element and scale_height_m:
        mpp = metres_per_pixel(detections, scale_element, scale_height_m)
        if mpp:
            scale = Scale(method="user_reference", metres_per_pixel=mpp, reference=f"{scale_element} = {scale_height_m} m")
    elif assume_door:
        mpp = metres_per_pixel(detections, "door", STANDARD_DOOR_M)
        if mpp:
            scale = Scale(method="assumed_door", metres_per_pixel=mpp, reference=f"door ≈ {STANDARD_DOOR_M} m (standard)")
    assumed = scale.method == "assumed_door"

    elements = []
    for label in ELEMENT_PROMPTS:
        group = [d for d in detections if d.label == label]
        if not group:
            continue
        union = np.logical_or.reduce([d.mask for d in group])
        pixels = int(union.sum())
        elements.append(
            ElementMeasurement(
                type=label,
                count=len(group),
                pixel_area=pixels,
                image_share=round(pixels / total, 4),
                area_m2=round(pixels * mpp * mpp, 2) if mpp else None,
                area_source="scale" if mpp else None,
                estimated=bool(mpp) and assumed,
                hidden_share=round(max(d.hidden for d in group), 2) or None,
                mean_score=round(float(np.mean([d.score for d in group])), 3),
                boxes=[d.box for d in group],
                source=group[0].source,
            )
        )

    defects = [
        DefectCandidate(
            kind=d.label,
            pixel_area=int(d.mask.sum()),
            image_share=round(float(d.mask.sum()) / total, 5),
            score=round(d.score, 3),
            box=d.box,
            source=d.source,
        )
        for d in detections
        if d.label in DEFECT_PROMPTS
    ]
    return Measurements(
        image_width=width,
        image_height=height,
        scale=scale,
        elements=elements,
        defect_candidates=defects,
        estimate_notes=[f"Scale from a standard door height of {STANDARD_DOOR_M} m."] if assumed else [],
    )


def combine(photos: list[Measurements]) -> Measurements:
    """Merge per-photo measurements of one room, surface by surface.

    An element's area only adds up when every photo it appears in was scaled; otherwise that
    element falls back to proportions while other elements keep their square metres.
    """
    merged: dict[str, ElementMeasurement] = {}
    unscaled: set[str] = set()
    for m in photos:
        for e in m.elements:
            if e.area_m2 is None:
                unscaled.add(e.type)
            if e.type not in merged:
                merged[e.type] = e.model_copy(update={"boxes": []})
                continue
            current = merged[e.type]
            pick_max = e.type in MAX_ACROSS_PHOTOS
            current.count = max(current.count, e.count) if pick_max else current.count + e.count
            current.mean_score = round((current.mean_score + e.mean_score) / 2, 3)
            current.pixel_area = max(current.pixel_area, e.pixel_area) if pick_max else current.pixel_area + e.pixel_area
            current.image_share = max(current.image_share, e.image_share)
            current.estimated = current.estimated or e.estimated
            if e.hidden_share:
                current.hidden_share = max(current.hidden_share or 0.0, e.hidden_share)
            if e.area_m2 is not None and current.area_m2 is not None:
                current.area_m2 = round(max(current.area_m2, e.area_m2) if pick_max else current.area_m2 + e.area_m2, 2)
    for kind in unscaled:
        merged[kind].area_m2 = None
        merged[kind].area_source = None
        merged[kind].estimated = False

    defects = [d.model_copy(update={"photo": i}) for i, m in enumerate(photos) for d in m.defect_candidates]
    first = photos[0]
    scale = next(
        (m.scale for method in ("user_reference", "assumed_door") for m in photos if m.scale.method == method), Scale()
    )
    return Measurements(
        image_width=first.image_width,
        image_height=first.image_height,
        scale=scale,
        elements=list(merged.values()),
        defect_candidates=defects,
        estimate_notes=sorted({n for m in photos for n in m.estimate_notes}),
    )


def apply_dimensions(
    measurements: Measurements,
    length_m: float | None = None,
    width_m: float | None = None,
    ceiling_m: float | None = None,
    *,
    wall_width_m: float | None = None,
    room_type: str | None = None,
    estimate: bool = False,
    floor_area_m2: float | None = None,
    perimeter_m: float | None = None,
) -> Measurements:
    """Areas from sizes instead of pixels, so furniture and perspective stop mattering.

    Floor and ceiling = length x width. Walls = perimeter (or the single wall's width) x ceiling
    height, minus doors and windows. With `estimate`, a room type fills a missing room size and a
    typical ceiling height fills a missing height; those areas are flagged as estimated.
    A room that isn't a rectangle can give its floor area and total wall length instead.
    """
    notes: list[str] = []
    size_estimated = height_estimated = False
    if not (length_m and width_m) and estimate and room_type in ROOM_PRESETS:
        length_m, width_m = ROOM_PRESETS[room_type]
        size_estimated = True
        name = "living room" if room_type == "living" else room_type.replace("_", " ")
        notes.append(f"Typical {name} size of {length_m:g} m × {width_m:g} m.")
    span = perimeter_m or (2 * (length_m + width_m) if length_m and width_m else wall_width_m)
    floor_area = floor_area_m2 or (length_m * width_m if length_m and width_m else None)
    if not ceiling_m and estimate and span:
        ceiling_m = TYPICAL_CEILING_M
        height_estimated = True
        notes.append(f"Typical ceiling height of {TYPICAL_CEILING_M:g} m.")

    by_type = {e.type: e for e in measurements.elements}
    if floor_area:
        for kind in ("floor", "ceiling"):
            if kind in by_type:
                by_type[kind].area_m2 = round(floor_area, 2)
                by_type[kind].area_source = "dimensions"
                by_type[kind].estimated = size_estimated and not floor_area_m2
    if length_m and width_m:
        measurements.room_size_m = [length_m, width_m]
    measurements.floor_area_m2 = floor_area_m2
    measurements.perimeter_m = perimeter_m
    wall = by_type.get("wall")
    if wall and span and ceiling_m:
        # Openings use their measured area when there is one, otherwise a standard size.
        openings = sum(
            e.area_m2 if e.area_m2 is not None and not e.estimated else e.count * standard
            for e, standard in ((by_type.get("door"), DOOR_AREA_M2), (by_type.get("window"), WINDOW_AREA_M2))
            if e
        )
        wall.area_m2 = round(max(span * ceiling_m - openings, 0.0), 2)
        wall.area_source = "dimensions"
        if length_m and width_m and not perimeter_m:
            wall.count = 4  # the perimeter covers all four walls of a rectangular room
        wall.estimated = (size_estimated and not perimeter_m) or height_estimated
    measurements.ceiling_height_m = ceiling_m
    measurements.estimate_notes = sorted(set(measurements.estimate_notes) | set(notes))
    return measurements


def hidden_walls(measurements: Measurements) -> float | None:
    """Share of the most-covered wall when furniture hides enough of it to matter."""
    wall = next((e for e in measurements.elements if e.type == "wall"), None)
    if wall and wall.hidden_share and wall.hidden_share >= HIDDEN_WARN:
        return wall.hidden_share
    return None
