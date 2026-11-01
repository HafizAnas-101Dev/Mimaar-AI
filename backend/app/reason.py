"""Stage 3: Muse Spark reads the photo plus measurements and writes a strict JSON report."""
import json
import re
from typing import Any

from pydantic import ValidationError

from . import i18n
from .meta_client import image_data_url
from .schemas import (
    CostEstimate,
    Evidence,
    Measurements,
    Report,
    ReportDefect,
    ReportElement,
)

SYSTEM_PROMPT = """You are a construction site assistant. You receive site photo(s) and JSON with the elements code measured, numbered defect candidates and the cost range.
Return ONLY JSON matching the schema.
"defects": for each candidate you can actually see, its number mapped to a severity; leave out the rest.
"summary": 2-3 sentences in the requested language: what the space is, the main defects, the cost range.
Numbers come from code; never change them. Never claim structural safety."""

# The model owns only judgements and the summary. Elements, costs, and each defect's location and
# reason come from code, so a local model writing a few tokens a second only writes a few dozen.
SCHEMA_HINT = {
    "scene": "interior | exterior | unknown",
    "defects": {"<candidate number>": "low | medium | high"},
    "summary": "2-3 sentences",
}


def build_messages(
    png_bytes: bytes | list[bytes], measurements: Measurements, cost: CostEstimate, language: str
) -> list[dict[str, Any]]:
    """One photo, or every photo of a room in order. The data is kept small: reading it is slow too."""
    images = png_bytes if isinstance(png_bytes, list) else [png_bytes]
    w, h = measurements.image_width, measurements.image_height
    payload = {
        "elements": [{"type": e.type, "count": e.count, "m2": e.area_m2} for e in measurements.elements],
        "defect_candidates": [
            {"n": i, "kind": d.kind, "where": i18n.location(*_grid(d.box, w, h), "en", d.photo, measurements.photo_roles), "score": d.score}
            for i, d in enumerate(measurements.defect_candidates)
        ],
        "cost": {"currency": cost.currency, "low": cost.low, "high": cost.high, "estimated": cost.estimated},
        "language": i18n.LANGUAGE_NAMES.get(language, "English"),
        "schema": SCHEMA_HINT,
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": json.dumps(payload, ensure_ascii=False)},
                *({"type": "image_url", "image_url": {"url": image_data_url(png)}} for png in images),
            ],
        },
    ]


def extract_json(text: str) -> Any:
    """Parse a JSON object or array from model text, tolerating code fences and prose."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("No JSON in model output")
    start = min(starts)
    end = text.rfind("}" if text[start] == "{" else "]")
    if end == -1:
        raise ValueError("Unterminated JSON in model output")
    return json.loads(text[start : end + 1])


def _grid(box: list[int], width: int, height: int) -> tuple[int, int]:
    cx = (box[0] + box[2]) / 2 / width
    cy = (box[1] + box[3]) / 2 / height
    col = 0 if cx < 0.33 else 2 if cx > 0.66 else 1
    row = 0 if cy < 0.33 else 2 if cy > 0.66 else 1
    return row, col


def attach_evidence(report: Report, measurements: Measurements) -> Report:
    """Fill each finding's trace from the measurements, never from the model."""
    by_type = {e.type: e for e in measurements.elements}
    for element in report.elements:
        m = by_type.get(element.type)
        if m:
            rule = "union of detected masks"
            height = measurements.ceiling_height_m
            if m.area_source == "dimensions" and m.type == "wall" and height:
                if measurements.perimeter_m:
                    rule += f"; m² = wall length {measurements.perimeter_m:g} m × height {height:g} m − doors and windows"
                elif measurements.room_size_m:
                    length, width = measurements.room_size_m
                    rule += f"; m² = perimeter 2 × ({length:g} + {width:g}) m × height {height:g} m − doors and windows"
                else:
                    rule += f"; m² = wall width × height {height:g} m − doors and windows"
            elif m.area_source == "dimensions" and measurements.floor_area_m2:
                rule += f"; m² = floor area entered, {measurements.floor_area_m2:g} m²"
            elif m.area_source == "dimensions" and measurements.room_size_m:
                length, width = measurements.room_size_m
                rule += f"; m² = room size {length:g} m × {width:g} m"
            elif m.area_m2 is not None and measurements.scale.metres_per_pixel:
                rule += f"; m² = pixels × ({measurements.scale.metres_per_pixel:.5f} m/px)²"
            if m.estimated:
                rule += " (estimated: " + " ".join(measurements.estimate_notes) + ")"
            element.evidence = Evidence(
                source=m.source,
                detector_score=m.mean_score,
                image_share=m.image_share,
                boxes=m.boxes,
                area_basis=m.area_source,
                estimated=m.estimated,
                rule=rule,
            )
    candidates = measurements.defect_candidates
    for defect in report.defects:
        if defect.candidate is not None and 0 <= defect.candidate < len(candidates):
            c = candidates[defect.candidate]
            defect.evidence = Evidence(
                source=c.source,
                detector_score=c.score,
                image_share=c.image_share,
                boxes=[c.box],
                photo=c.photo,
                rule="severity from the visible extent of the flagged region",
            )
        else:
            defect.candidate = None
            defect.confidence = min(defect.confidence, 0.5)
            defect.evidence = Evidence(
                source="muse-spark", detector_score=0.0, image_share=0.0, rule="seen by the reasoning model only; not measured"
            )
    return report


def fallback_report(measurements: Measurements, cost: CostEstimate, language: str = "en", photos: int = 1) -> Report:
    """Deterministic report from measurements alone; used in mock mode and when Muse fails."""
    w, h = measurements.image_width, measurements.image_height
    defects = []
    for i, d in enumerate(measurements.defect_candidates):
        severity = "high" if d.image_share > 0.02 else "medium" if d.image_share > 0.004 else "low"
        row, col = _grid(d.box, w, h)
        defects.append(
            ReportDefect(
                kind=d.kind,
                candidate=i,
                location=i18n.location(row, col, language, d.photo, measurements.photo_roles),
                severity=severity,
                confidence=d.score,
                why=i18n.defect_why(d.kind, d.image_share, language),
            )
        )
    elements = [
        ReportElement(type=e.type, count=e.count, area_m2=e.area_m2, confidence=e.mean_score)
        for e in measurements.elements
    ]
    parts = i18n.element_parts([(e.type, e.count) for e in elements], language)
    money = (cost.low, cost.high, cost.currency) if cost.low is not None else None
    report = Report(
        scene="interior" if any(e.type in ("ceiling", "floor") for e in elements) else "unknown",
        scale=measurements.scale,
        elements=elements,
        defects=defects,
        cost_estimate=cost,
        summary=i18n.summary(parts, len(defects), money, photos, language),
        language=language,
        disclaimer=i18n.DISCLAIMERS[language],
    )
    return attach_evidence(report, measurements)


def _defects_from_verdicts(raw: dict[str, Any], measurements: Measurements, language: str) -> None:
    """Turn {"<candidate>": "severity"} into full defects, with location and reason written by code."""
    verdicts = raw.get("defects")
    if not isinstance(verdicts, dict):
        return  # already a list of full defects (older replies, or the Meta API)
    template = {d.candidate: d for d in fallback_report(measurements, CostEstimate(currency=""), language).defects}
    defects = []
    for key, severity in verdicts.items():
        try:
            d = template[int(key)]
        except (KeyError, ValueError, TypeError):
            continue
        defect = d.model_dump(exclude={"confidence_label", "evidence"})
        if severity in ("low", "medium", "high"):
            defect["severity"] = severity
        defects.append(defect)
    raw["defects"] = defects


def _with_code_numbers(raw: dict[str, Any], measurements: Measurements, cost: CostEstimate, language: str) -> dict[str, Any]:
    """Overwrite every number the model must not own before validation."""
    raw = dict(raw)
    _defects_from_verdicts(raw, measurements, language)
    raw["scale"] = measurements.scale.model_dump()
    raw["cost_estimate"] = {**cost.model_dump(), "assumptions": cost.assumptions + [
        a for a in (raw.get("cost_estimate") or {}).get("assumptions", []) if isinstance(a, str) and a not in cost.assumptions
    ]}
    raw["language"] = language
    raw["disclaimer"] = i18n.DISCLAIMERS[language]
    # Elements always mirror the measurements; a model-given confidence is kept when it sends one.
    given = {e.get("type"): e for e in raw.get("elements") or [] if isinstance(e, dict)}
    raw["elements"] = [
        {
            "type": m.type,
            "count": m.count,
            "area_m2": m.area_m2,
            "confidence": given.get(m.type, {}).get("confidence", m.mean_score),
        }
        for m in measurements.elements
    ]
    return raw


def reason(
    client: Any,
    png_bytes: bytes | list[bytes],
    measurements: Measurements,
    cost: CostEstimate,
    language: str = "en",
    photos: int = 1,
) -> tuple[Report, list[str]]:
    """Ask the Muse model for the report; one repair retry, then a safe fallback."""
    messages = build_messages(png_bytes, measurements, cost, language)
    warnings: list[str] = []
    for _ in range(2):
        text = client.chat(messages, prefill="{", temperature=0.2)
        try:
            raw = extract_json(text)
            if not isinstance(raw, dict):
                raise ValueError("Expected a JSON object")
            report = Report.model_validate(_with_code_numbers(raw, measurements, cost, language))
        except (ValueError, ValidationError) as exc:
            warnings.append(f"Model output failed validation: {str(exc)[:200]}")
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"That was invalid: {str(exc)[:500]}. Return only corrected JSON."},
            ]
            continue
        return attach_evidence(report, measurements), warnings
    warnings.append("Used a measurement-only report because the model output was invalid twice.")
    return fallback_report(measurements, cost, language, photos=photos), warnings
