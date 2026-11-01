import json

import pytest

from app import main
from app.measure import measure
from app.perceive import mock_detections
from app.pricing import estimate_cost, load_prices
from app.reason import extract_json, fallback_report, reason


@pytest.fixture
def inputs():
    m = measure(mock_detections(640, 480), 640, 480, "door", 2.1)
    return m, estimate_cost(m, load_prices(main.settings.prices_path))


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def chat(self, messages, **params):
        self.calls += 1
        return self.replies.pop(0)


def test_extract_json_handles_fences_prose_and_arrays():
    assert extract_json('Here:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure {"a": {"b": 2}} done') == {"a": {"b": 2}}
    assert extract_json('[{"label": "door"}]') == [{"label": "door"}]


def test_model_cannot_change_numbers(inputs):
    m, cost = inputs
    raw = fallback_report(m, cost).model_dump()
    raw["cost_estimate"]["low"] = 1
    raw["elements"][0]["count"] = 99
    raw["disclaimer"] = "Totally safe"
    report, warnings = reason(FakeClient([json.dumps(raw)]), b"png", m, cost)
    assert report.cost_estimate.low == cost.low
    assert report.elements[0].count == m.elements[0].count
    assert "not an engineering" in report.disclaimer
    assert warnings == []


def test_evidence_is_attached_from_measurements(inputs):
    m, cost = inputs
    raw = fallback_report(m, cost).model_dump()
    raw["defects"].append(
        {"kind": "other", "candidate": None, "location": "x", "severity": "high", "confidence": 0.9, "why": "seen"}
    )
    report, _ = reason(FakeClient([json.dumps(raw)]), b"png", m, cost)
    wall = next(e for e in report.elements if e.type == "wall")
    assert wall.evidence.source == "mock" and "m²" in wall.evidence.rule
    assert report.defects[0].evidence.boxes
    unmeasured = report.defects[-1]
    assert unmeasured.evidence.source == "muse-spark"
    assert unmeasured.confidence == 0.5  # capped because nothing measured it
    assert unmeasured.confidence_label == "medium"


def test_invalid_output_retries_once_then_succeeds(inputs):
    m, cost = inputs
    good = json.dumps(fallback_report(m, cost).model_dump())
    client = FakeClient(['{"scene": "kitchen"}', good])
    report, warnings = reason(client, b"png", m, cost)
    assert client.calls == 2
    assert len(warnings) == 1
    assert report.scene == "interior"


def test_twice_invalid_output_falls_back(inputs):
    m, cost = inputs
    report, warnings = reason(FakeClient(["nope", "[1, 2]"]), b"png", m, cost)
    assert "measurement-only" in warnings[-1]
    assert report.elements


@pytest.mark.parametrize("lang, marker", [("ur", "دیوار"), ("ar", "جدار")])
def test_fallback_report_is_localised(inputs, lang, marker):
    m, cost = inputs
    report = fallback_report(m, cost, lang)
    assert marker in report.summary
    assert report.language == lang
    assert "Estimate only" not in report.disclaimer
    assert all(not d.location.isascii() for d in report.defects)


def test_short_reply_without_elements_or_cost_is_completed_by_code(inputs):
    m, cost = inputs
    reply = {"scene": "interior", "defects": [], "summary": "A room."}
    report, warnings = reason(FakeClient([json.dumps(reply)]), b"png", m, cost)
    assert [e.type for e in report.elements] == [e.type for e in m.elements]
    assert report.elements[0].area_m2 == m.elements[0].area_m2
    assert report.cost_estimate.low == cost.low
    assert warnings == []


def test_room_photos_go_to_the_model_together(inputs):
    from app.reason import build_messages

    m, cost = inputs
    messages = build_messages([b"a", b"b", b"c"], m, cost, "en")
    images = [part for part in messages[1]["content"] if part["type"] == "image_url"]
    assert len(images) == 3


def test_compact_verdicts_become_full_defects(inputs):
    m, cost = inputs
    assert len(m.defect_candidates) >= 2
    reply = {"scene": "interior", "defects": {"1": "high", "99": "low", "x": "low"}, "summary": "Short."}
    report, warnings = reason(FakeClient([json.dumps(reply)]), b"png", m, cost, "ur")
    [defect] = report.defects  # unknown candidates are ignored, unlisted ones dropped
    assert defect.candidate == 1 and defect.severity == "high" and defect.kind == m.defect_candidates[1].kind
    assert defect.location and defect.why  # written by code, in Urdu
    assert defect.evidence.source != "muse-spark"
    assert warnings == []


def test_payload_is_compact(inputs):
    from app.reason import build_messages

    m, cost = inputs
    text = build_messages(b"png", m, cost, "en")[1]["content"][0]["text"]
    assert "pixel_area" not in text and "assumptions" not in text
    assert '"n": 0' in text


def test_room_defects_name_their_photo():
    from app import i18n

    roles = ["floor", "ceiling", "wall", "wall"]
    assert i18n.location(0, 2, "en", 3, roles) == "Wall 2 · upper right of the photo"
    assert i18n.location(1, 1, "en", 0, roles).startswith("Floor · ")
    assert i18n.location(1, 1, "en", 1, ["floor", "wall"]).startswith("Wall · ")  # only one wall: no number
    assert i18n.location(1, 1, "ar", 3, roles).startswith("الجدار 2 · ")
    assert i18n.location(1, 1, "en", 1, None) == "middle centre of the photo (photo 2)"  # older results
