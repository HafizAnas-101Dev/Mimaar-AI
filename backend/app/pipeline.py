"""Perceive -> Measure -> Reason -> Present."""
import base64
import io
import uuid
from typing import Any

from PIL import Image, ImageOps

try:  # iPhones save photos as HEIC by default
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - optional dependency
    pass

from .config import Settings
from .measure import apply_dimensions, combine, filter_for_role, hidden_walls, measure
from .overlay import render_layers, to_base64_png
from .perceive import detect
from .pricing import estimate_cost, load_prices
from .reason import fallback_report, reason
from .schemas import ReportDefect, ReportElement
from .schemas import AnalysisOptions, AnalysisResult, Edits, ElementMeasurement, Layer, Measurements, RoomResult

MOCK_WARNING = "Mock mode: geometry is synthetic. Set MODEL_API_KEY for real analysis."


class InvalidImage(ValueError):
    pass


def prepare_image(data: bytes, max_side: int) -> Image.Image:
    """Decode, fix EXIF rotation and shrink so we send fewer bytes to the API."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception as exc:  # Pillow raises several types for bad input
        raise InvalidImage("Could not read the image. Upload a JPEG, PNG, WebP or HEIC (iPhone) photo.") from exc
    img.thumbnail((max_side, max_side))
    return img


# A local model reads image tokens slowly. SAM 3 and the code already did the pixel work, so the
# report writer gets a smaller copy (same proportions, so box coordinates still line up).
# A room sends every photo at once, so each gets a smaller copy.
LOCAL_REASON_SIDE = 768
LOCAL_ROOM_REASON_SIDE = 512


def reasoning_image(png_bytes: bytes, settings: Settings, side: int = LOCAL_REASON_SIDE) -> bytes:
    if settings.backend != "local":
        return png_bytes
    img = Image.open(io.BytesIO(png_bytes))
    if max(img.size) <= side:
        return png_bytes
    img.thumbnail((side, side))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def furniture_warning(measurements: Measurements) -> list[str]:
    share = hidden_walls(measurements)
    if share is None:
        return []
    wall = next(e for e in measurements.elements if e.type == "wall")
    text = f"Furniture covers about {share:.0%} of a wall, so defects behind it can't be seen."
    if wall.area_source == "dimensions":
        return [text + " The wall area comes from the sizes, so furniture does not affect it."]
    return [text + " Its photo-based area may be off; enter the room or wall size and the ceiling height for exact walls."]


def analyze(
    data: bytes,
    settings: Settings,
    client: Any | None,
    options: AnalysisOptions,
    filename: str = "",
    role: str | None = None,
    room: bool = False,
    defer: bool = False,
) -> AnalysisResult:
    """`room` marks a photo that analyze_room combines; sizes and their warnings are applied there.
    `defer` returns the code-written report at once and leaves the model's writing to finish_reasoning."""
    img = prepare_image(data, settings.max_image_side)
    width, height = img.size
    png = io.BytesIO()
    img.save(png, format="PNG")
    png_bytes = png.getvalue()

    mock = settings.mock or client is None
    perceiver = "mock" if mock else settings.perceiver
    detections = filter_for_role(detect(perceiver, client, png_bytes, width, height), role)
    surfaces = {d.label for d in detections} & {"wall", "floor", "ceiling"}
    if not mock and not room and not surfaces:
        raise InvalidImage(
            "This doesn't look like a photo of a room or a wall: no wall, floor or ceiling was found. "
            "Upload a photo taken inside the space."
        )
    measurements = measure(
        detections, width, height, options.scale_element, options.scale_height_m, assume_door=options.estimate
    )
    if not room:
        apply_dimensions(
            measurements, ceiling_m=options.ceiling_height_m, wall_width_m=options.wall_width_m, estimate=options.estimate
        )
    cost = estimate_cost(measurements, load_prices(settings.prices_path), options.currency, options.finish, options.scope)

    warnings: list[str] = []
    reasoning = "none"
    if mock or room or defer:
        # A room's photos are reasoned over together in analyze_room, in a single model call.
        report = fallback_report(measurements, cost, options.language)
        if mock:
            warnings.append(MOCK_WARNING)
        elif defer and not room:
            reasoning = "pending"
    else:
        report, warnings = reason(client, reasoning_image(png_bytes, settings), measurements, cost, options.language)
        reasoning = _state(warnings)
    if not mock:
        if perceiver == "muse":
            warnings.append(f"Perception used {settings.reasoner} boxes (SAM not enabled), so areas are box-based and rough.")
    if not mock and room and role and role not in surfaces:
        warnings.append(f"The {role} photo ({filename or 'no name'}) shows no {role}. Check it is in the right slot.")
    if options.scale_element and measurements.scale.method == "none":
        warnings.append(f"No {options.scale_element} was found, so areas are shown as image proportions only.")
    if not room:
        warnings += furniture_warning(measurements)
        wall = next((e for e in measurements.elements if e.type == "wall"), None)
        if options.estimate and wall and wall.area_m2 is None:
            warnings.append("No door was found to estimate the scale. Enter the wall width for square metres.")
        if options.wall_width_m and not options.ceiling_height_m and not options.estimate:
            warnings.append("Add the ceiling height to turn the wall width into square metres.")

    return AnalysisResult(
        id=_new_id(),
        mode="mock" if mock else "live",
        perceiver=perceiver,
        filename=filename,
        role=role,
        options=options,
        report=report,
        measurements=measurements,
        image_png_base64=to_base64_png(img),
        layers=[Layer(**layer) for layer in render_layers(detections, width, height)],
        warnings=warnings,
        reasoning=reasoning,
    )


def _state(reason_warnings: list[str]) -> str:
    return "failed" if any("measurement-only" in w for w in reason_warnings) else "done"


def change_language(result: AnalysisResult | RoomResult, language: str) -> AnalysisResult | RoomResult:
    """Rewrite a result's report in another language without detecting or measuring again: the
    code-written text changes at once, and the Muse model's write-up is redone via finish_reasoning."""
    photos = len(result.photos) if isinstance(result, RoomResult) else 1
    result.options.language = language
    result.report = fallback_report(result.measurements, result.report.cost_estimate, language, photos=photos)
    result.reasoning = "pending" if result.mode == "live" else "none"
    for photo in result.photos if isinstance(result, RoomResult) else []:
        photo.options.language = language
        photo.report = fallback_report(photo.measurements, photo.report.cost_estimate, language)
    return result


def apply_edits(result: AnalysisResult | RoomResult, edits: Edits, settings: Settings) -> AnalysisResult | RoomResult:
    """Recompute counts, areas and cost from the original measurements plus the user's edits.
    The written summary stays; the report notes that quantities changed after it was written."""
    base = result.measurements
    measurements = base.model_copy(deep=True)
    removed_types: dict[str, int] = {}
    removed_boxes: set[tuple[int | None, tuple[int, ...]]] = set()
    single = not isinstance(result, RoomResult)
    for photo, kinds in edits.removed.items():
        index = None if single else int(photo)
        for kind, boxes in kinds.items():
            removed_types[kind] = removed_types.get(kind, 0) + len(boxes)
            removed_boxes |= {(index, tuple(b)) for b in boxes}

    notes = []
    by_type = {e.type: e for e in measurements.elements}
    for kind in set(edits.counts) | set(edits.areas) | (set(removed_types) & set(by_type)):
        element = by_type.get(kind)
        if element is None:  # an element the model missed, added by the user
            element = ElementMeasurement(type=kind, count=0, pixel_area=0, image_share=0.0, mean_score=1.0, source="user")
            measurements.elements.append(element)
            by_type[kind] = element
        before = element.count, element.area_m2
        element.count = max(0, edits.counts.get(kind, element.count - removed_types.get(kind, 0)))
        if kind in edits.areas:
            element.area_m2 = round(edits.areas[kind], 2)
        element.edited = True
        if before != (element.count, element.area_m2):
            notes.append(f"{kind} {before[0]} → {element.count}" if before[0] != element.count else f"{kind} area → {element.area_m2} m²")
    measurements.defect_candidates = [
        d for d in measurements.defect_candidates if (d.photo, tuple(d.box)) not in removed_boxes
    ]

    options = result.options
    cost = estimate_cost(measurements, load_prices(settings.prices_path), options.currency, options.finish, options.scope)
    if notes or removed_boxes:
        removed_defects = len(base.defect_candidates) - len(measurements.defect_candidates)
        if removed_defects:
            notes.append(f"{removed_defects} defect(s) removed")
        cost.assumptions.insert(0, "Edited by you: " + "; ".join(notes) + ".")
    report = result.report
    previous = result.edits
    edits.unedited_elements = previous.unedited_elements or [e.model_dump() for e in report.elements]
    edits.unedited_defects = previous.unedited_defects or [d.model_dump() for d in report.defects]
    kept = {(d.photo, tuple(d.box)) for d in measurements.defect_candidates}
    report.defects = [
        d for d in (ReportDefect.model_validate(x) for x in edits.unedited_defects)
        if d.evidence is None or not d.evidence.boxes or (d.evidence.photo, tuple(d.evidence.boxes[0])) in kept
    ]
    written = {e["type"]: ReportElement.model_validate(e) for e in edits.unedited_elements}
    report.elements = []
    for m in measurements.elements:
        element = written.get(m.type) or ReportElement(type=m.type, count=0, confidence=1.0)
        if m.type not in written and m.count == 0:
            continue  # added by the user, then set back to zero
        element.count, element.area_m2, element.edited = m.count, m.area_m2, m.edited
        report.elements.append(element)
    report.cost_estimate = cost
    result.edits = edits
    return result


def finish_reasoning(result: AnalysisResult | RoomResult, settings: Settings, client: Any) -> AnalysisResult | RoomResult:
    """Have the Muse model write the report of a result returned with `defer`."""
    if result.reasoning != "pending":
        return result
    language = result.options.language
    if isinstance(result, RoomResult):
        pngs = [reasoning_image(base64.b64decode(p.image_png_base64), settings, LOCAL_ROOM_REASON_SIDE) for p in result.photos]
        report, warnings = reason(client, pngs, result.measurements, result.report.cost_estimate, language, photos=len(pngs))
    else:
        png = reasoning_image(base64.b64decode(result.image_png_base64), settings)
        report, warnings = reason(client, png, result.measurements, result.report.cost_estimate, language)
    result.report = report
    result.reasoning = _state(warnings)
    result.warnings += [w for w in warnings if w not in result.warnings]
    return result


def analyze_room(
    photos: list[tuple[bytes, str, str | None]],
    settings: Settings,
    client: Any | None,
    options: AnalysisOptions,
    defer: bool = False,
) -> RoomResult:
    """Each photo is (bytes, filename, role). Floor and ceiling photos rarely show a door, so the
    door-height scale is only applied to wall photos; a room size, if given, sets their areas."""
    results = []
    for data, name, role in photos:
        photo_options = options
        if role in ("floor", "ceiling"):
            photo_options = options.model_copy(update={"scale_element": None, "scale_height_m": None})
        results.append(analyze(data, settings, client, photo_options, name, role, room=True))

    combined = combine([r.measurements for r in results])
    combined.photo_roles = [r.role for r in results]
    # Each wall photo shows one wall, but SAM also finds the neighbouring walls at its edges, so
    # adding up surfaces across photos overcounts (four corner shots gave eight walls).
    wall_photos = sum(1 for r in results if r.role == "wall" and any(e.type == "wall" for e in r.measurements.elements))
    wall = next((e for e in combined.elements if e.type == "wall"), None)
    if wall and wall_photos:
        wall.count = wall_photos
    measurements = apply_dimensions(
        combined,
        options.room_length_m,
        options.room_width_m,
        options.ceiling_height_m,
        room_type=options.room_type,
        estimate=options.estimate,
        floor_area_m2=options.room_floor_area_m2,
        perimeter_m=options.room_perimeter_m,
    )
    cost = estimate_cost(measurements, load_prices(settings.prices_path), options.currency, options.finish, options.scope)
    warnings = sorted({w for r in results for w in r.warnings})
    reasoning = "none"
    if results[0].mode == "mock" or defer:
        report = fallback_report(measurements, cost, options.language, photos=len(results))
        reasoning = "pending" if results[0].mode == "live" else "none"
    else:
        pngs = [reasoning_image(base64.b64decode(r.image_png_base64), settings, LOCAL_ROOM_REASON_SIDE) for r in results]
        report, reason_warnings = reason(client, pngs, measurements, cost, options.language, photos=len(results))
        warnings += reason_warnings
        reasoning = _state(reason_warnings)
    missing = sorted(e.type for e in measurements.elements if e.area_m2 is None and e.type in ("wall", "floor", "ceiling"))
    if missing:
        hints = []
        if {"floor", "ceiling"} & set(missing):
            hints.append("Add the room size, or pick a room type under \"I don't have measurements\".")
        if "wall" in missing:
            hints.append("Add the room size and ceiling height for walls.")
        warnings.append(f"No square metres for: {', '.join(missing)}. {' '.join(hints)}".strip())
    warnings += furniture_warning(measurements)
    if sum(1 for _, _, role in photos if role == "wall") > 1:
        warnings.append("Doors and windows are added across wall photos; drop duplicates if photos overlap.")
    return RoomResult(
        id=_new_id(),
        mode=results[0].mode,
        options=options,
        photos=results,
        report=report,
        warnings=warnings,
        reasoning=reasoning,
        measurements=measurements,
    )
