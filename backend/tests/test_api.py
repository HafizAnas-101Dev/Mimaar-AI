import io

from fastapi.testclient import TestClient
from PIL import Image

from app import main


def _photo(color=(200, 190, 170)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color).save(buf, format="JPEG")
    return buf.getvalue()


def test_analyze_in_mock_mode_and_saves_history(api_settings):
    api = TestClient(main.app)
    res = api.post(
        "/api/analyze",
        files={"file": ("room.jpg", _photo(), "image/jpeg")},
        data={"scale_element": "door", "scale_height_m": "2.1", "currency": "PKR", "finish": "premium"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "mock" and body["perceiver"] == "mock"
    report = body["report"]
    assert report["scale"]["method"] == "user_reference"
    assert report["cost_estimate"]["currency"] == "PKR"
    assert report["cost_estimate"]["finish"] == "premium"
    assert report["elements"][0]["confidence_label"] in ("high", "medium", "low")
    assert report["elements"][0]["evidence"]["rule"]
    assert {layer["type"] for layer in body["layers"]} >= {"wall", "floor", "door"}

    [entry] = api.get("/api/history").json()
    assert entry["id"] == body["id"] and entry["title"] == "room.jpg"
    assert api.get(f"/api/history/{body['id']}").json()["report"] == report
    assert api.delete(f"/api/history/{body['id']}").status_code == 200
    assert api.get(f"/api/history/{body['id']}").status_code == 404


def test_analyze_room_combines_photos(api_settings):
    api = TestClient(main.app)
    res = api.post(
        "/api/analyze-room",
        files=[("files", ("a.jpg", _photo(), "image/jpeg")), ("files", ("b.jpg", _photo((180, 180, 180)), "image/jpeg"))],
        data={"scale_element": "door", "scale_height_m": "2.1", "language": "ar"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["photos"]) == 2
    doors = next(e for e in body["report"]["elements"] if e["type"] == "door")
    assert doors["count"] == 2
    assert body["report"]["language"] == "ar"
    assert {d["evidence"]["photo"] for d in body["report"]["defects"]} == {0, 1}
    assert api.get("/api/history").json()[0]["kind"] == "room"


def test_room_photo_limits(api_settings):
    api = TestClient(main.app)
    one = api.post("/api/analyze-room", files=[("files", ("a.jpg", _photo(), "image/jpeg"))])
    assert one.status_code == 200
    seven = [("files", (f"{i}.jpg", _photo(), "image/jpeg")) for i in range(7)]
    assert api.post("/api/analyze-room", files=seven).status_code == 400


def test_room_roles_and_room_size(api_settings):
    api = TestClient(main.app)
    files = [("files", (f"{n}.jpg", _photo(), "image/jpeg")) for n in ("floor", "ceiling", "wall1", "wall2")]
    res = api.post(
        "/api/analyze-room",
        files=files,
        data={"roles": "floor,ceiling,wall,wall", "scale_element": "door", "scale_height_m": "2.1",
              "room_length_m": "5", "room_width_m": "4"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [p["role"] for p in body["photos"]] == ["floor", "ceiling", "wall", "wall"]
    # Each photo only contributes its own surface.
    assert {l["type"] for l in body["photos"][0]["layers"]} - {"crack", "damp", "peeling"} == {"floor"}
    elements = {e["type"]: e for e in body["report"]["elements"]}
    assert elements["floor"]["area_m2"] == 20.0 and elements["ceiling"]["area_m2"] == 20.0
    assert elements["floor"]["evidence"]["area_basis"] == "dimensions"
    assert elements["door"]["count"] == 2  # one door in each wall photo
    assert elements["wall"]["area_m2"] is not None  # wall photos were scaled by the door


def test_room_roles_validation(api_settings):
    api = TestClient(main.app)
    files = [("files", ("a.jpg", _photo(), "image/jpeg")), ("files", ("b.jpg", _photo(), "image/jpeg"))]
    assert api.post("/api/analyze-room", files=files, data={"roles": "floor"}).status_code == 422
    assert api.post("/api/analyze-room", files=files, data={"roles": "floor,roof"}).status_code == 422


def test_single_wall_photo_keeps_only_wall_surfaces(api_settings):
    res = TestClient(main.app).post(
        "/api/analyze", files={"file": ("w.jpg", _photo(), "image/jpeg")},
        data={"role": "wall", "scale_element": "door", "scale_height_m": "2.1"},
    )
    body = res.json()
    assert body["role"] == "wall"
    assert {e["type"] for e in body["report"]["elements"]} == {"wall", "door", "window"}


def test_rejects_non_image(api_settings):
    res = TestClient(main.app).post("/api/analyze", files={"file": ("x.txt", b"hello", "text/plain")})
    assert res.status_code == 400


def test_price_table_round_trip_and_validation(api_settings):
    api = TestClient(main.app)
    table = api.get("/api/prices").json()
    assert set(table["tables"]) >= {"SAR", "PKR", "USD"}

    table["tables"]["SAR"]["wall"]["high"] = 99
    assert api.put("/api/prices", json=table).status_code == 200
    assert api.get("/api/prices").json()["tables"]["SAR"]["wall"]["high"] == 99

    table["tables"]["SAR"]["wall"]["low"] = 500
    assert api.put("/api/prices", json=table).status_code == 422


def test_samples_listed_and_served(api_settings):
    api = TestClient(main.app)
    names = api.get("/api/samples").json()
    assert names
    assert api.get(f"/api/samples/{names[0]}").headers["content-type"] == "image/jpeg"
    assert api.get("/api/samples/..%2Fdata%2Fprices.json").status_code == 404


def test_scope_limits_the_estimate(api_settings):
    api = TestClient(main.app)
    data = {"scale_element": "door", "scale_height_m": "2.1"}
    full = api.post("/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}, data=data).json()
    floor_only = api.post(
        "/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}, data={**data, "scope": "floor,damp"}
    ).json()
    cost = floor_only["report"]["cost_estimate"]
    assert cost["scope"] == ["floor", "damp"]
    assert [line["item"] for line in cost["lines"]] == ["Floor tiling", "Damp treatment"]
    assert cost["high"] < full["report"]["cost_estimate"]["high"]
    # Quantities still cover everything detected, not just the priced work.
    assert len(floor_only["report"]["elements"]) == len(full["report"]["elements"])


def test_scope_validation(api_settings):
    api = TestClient(main.app)
    photo = {"file": ("a.jpg", _photo(), "image/jpeg")}
    assert api.post("/api/analyze", files=photo, data={"scope": "roof"}).status_code == 422
    assert api.post("/api/analyze", files=photo, data={"scope": " , "}).status_code == 400


def test_room_without_measurements_is_estimated(api_settings):
    api = TestClient(main.app)
    res = api.post(
        "/api/analyze-room",
        files=[("files", ("a.jpg", _photo(), "image/jpeg")), ("files", ("b.jpg", _photo(), "image/jpeg"))],
        data={"roles": "floor,wall", "estimate": "true", "room_type": "living"},
    )
    assert res.status_code == 200, res.text
    cost = res.json()["report"]["cost_estimate"]
    assert cost["estimated"] and cost["low"] is not None
    elements = {e["type"]: e for e in res.json()["report"]["elements"]}
    assert elements["floor"]["area_m2"] == 30.0
    assert elements["wall"]["evidence"]["estimated"]
    assert "perimeter" in elements["wall"]["evidence"]["rule"]


def test_wall_mode_with_wall_size(api_settings):
    api = TestClient(main.app)
    res = api.post(
        "/api/analyze",
        files={"file": ("w.jpg", _photo(), "image/jpeg")},
        data={"role": "wall", "wall_width_m": "4", "ceiling_height_m": "3", "scope": "wall"},
    )
    assert res.status_code == 200, res.text
    [line] = res.json()["report"]["cost_estimate"]["lines"]
    assert line["quantity"] == 12 - 1.85 - 1.5 and not line["estimated"]


def test_estimate_fields_validated(api_settings):
    api = TestClient(main.app)
    res = api.post(
        "/api/analyze-room",
        files=[("files", ("a.jpg", _photo(), "image/jpeg"))],
        data={"room_type": "castle"},
    )
    assert res.status_code == 422


def test_local_backend_needs_no_key(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("MODEL_BACKEND", "local")
    monkeypatch.setenv("MODEL_API_KEY", "")
    monkeypatch.setenv("MIMAAR_MOCK", "false")
    s = get_settings()
    assert not s.mock and s.base_url == "http://127.0.0.1:8080/v1" and s.reasoner == "Muse Glimmer"


def test_deferred_report_is_written_afterwards(api_settings, monkeypatch):
    """Instant code report first; the Muse model's text replaces it on /api/reason."""
    import json as _json

    from app.perceive import mock_detections

    class FakeMuse:
        settings = main.settings

        def chat(self, messages, **params):
            return _json.dumps({"scene": "interior", "defects": [], "summary": "Written by the model."})

    monkeypatch.setattr(main, "client", FakeMuse())
    monkeypatch.setattr(main, "settings", main.settings.__class__(**{**main.settings.__dict__, "mock": False, "perceiver": "muse"}))
    monkeypatch.setattr("app.pipeline.detect", lambda perceiver, client, png, w, h: mock_detections(w, h))
    api = TestClient(main.app)
    res = api.post("/api/analyze", files={"file": ("w.jpg", _photo(), "image/jpeg")}, data={"defer_reasoning": "true"})
    assert res.status_code == 200, res.text
    first = res.json()
    assert first["reasoning"] == "pending" and first["report"]["summary"] != "Written by the model."

    done = api.post(f"/api/reason/{first['id']}").json()
    assert done["reasoning"] == "done" and done["report"]["summary"] == "Written by the model."
    assert done["report"]["cost_estimate"] == first["report"]["cost_estimate"]
    assert api.get(f"/api/history/{first['id']}").json()["reasoning"] == "done"
    assert api.post("/api/reason/missing").status_code == 404


def test_room_counts_one_wall_per_wall_photo_or_four_with_a_room_size(api_settings):
    api = TestClient(main.app)
    files = [("files", (f"{i}.jpg", _photo(), "image/jpeg")) for i in range(3)]
    walls = lambda body: next(e for e in body["report"]["elements"] if e["type"] == "wall")["count"]
    two = api.post("/api/analyze-room", files=files, data={"roles": "floor,wall,wall"}).json()
    assert walls(two) == 2
    sized = api.post(
        "/api/analyze-room", files=files, data={"roles": "floor,wall,wall", "room_length_m": "4", "room_width_m": "3", "ceiling_height_m": "3"}
    ).json()
    assert walls(sized) == 4


def test_iphone_heic_photo_is_accepted(api_settings):
    import pillow_heif

    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (200, 190, 170)).save(buf, format="HEIF")
    res = TestClient(main.app).post("/api/analyze", files={"file": ("IMG_0001.HEIC", buf.getvalue(), "image/heic")})
    assert res.status_code == 200, res.text


def _live(monkeypatch, detections):
    """Run the API as if models were live, with fixed detections and a fake report writer."""
    import json as _json

    class FakeMuse:
        settings = main.settings

        def chat(self, messages, **params):
            return _json.dumps({"scene": "interior", "defects": {}, "summary": "ok"})

    monkeypatch.setattr(main, "client", FakeMuse())
    monkeypatch.setattr(main, "settings", main.settings.__class__(**{**main.settings.__dict__, "mock": False, "perceiver": "muse"}))
    monkeypatch.setattr("app.pipeline.detect", lambda perceiver, client, png, w, h: detections(w, h))
    return TestClient(main.app)


def test_photo_that_is_not_a_room_is_refused(api_settings, monkeypatch):
    api = _live(monkeypatch, lambda w, h: [])
    res = api.post("/api/analyze", files={"file": ("selfie.jpg", _photo(), "image/jpeg")})
    assert res.status_code == 400 and "doesn't look like" in res.json()["detail"]


def test_room_photo_in_the_wrong_slot_is_flagged(api_settings, monkeypatch):
    from app.perceive import mock_detections

    only_walls = lambda w, h: [d for d in mock_detections(w, h) if d.label in ("wall", "door")]
    api = _live(monkeypatch, only_walls)
    files = [("files", ("a.jpg", _photo(), "image/jpeg")), ("files", ("b.jpg", _photo(), "image/jpeg"))]
    res = api.post("/api/analyze-room", files=files, data={"roles": "floor,wall", "defer_reasoning": "true"})
    assert res.status_code == 200, res.text
    assert any("floor photo (a.jpg) shows no floor" in w for w in res.json()["warnings"])


def test_language_change_rewrites_without_reanalysing(api_settings):
    api = TestClient(main.app)
    files = [("files", ("a.jpg", _photo(), "image/jpeg")), ("files", ("b.jpg", _photo(), "image/jpeg"))]
    first = api.post("/api/analyze-room", files=files, data={"roles": "floor,wall"}).json()
    ar = api.post(f"/api/language/{first['id']}", data={"language": "ar"}).json()
    assert ar["id"] == first["id"] and ar["report"]["language"] == "ar"
    assert ar["report"]["cost_estimate"] == first["report"]["cost_estimate"]
    assert ar["report"]["elements"] == first["report"]["elements"]
    assert ar["report"]["summary"] != first["report"]["summary"]
    assert all(p["report"]["language"] == "ar" for p in ar["photos"])
    assert ar["reasoning"] == "none"  # mock mode: nothing for a model to write
    assert api.get(f"/api/history/{first['id']}").json()["report"]["language"] == "ar"


def test_sample_rates_are_flagged_until_the_user_saves_their_own(api_settings):
    api = TestClient(main.app)
    table = api.get("/api/prices").json()
    table["sample"] = True
    from app.pricing import save_prices
    from app.schemas import PriceTable

    save_prices(main.settings.prices_path, PriceTable.model_validate(table))
    first = api.post("/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}).json()
    assert first["report"]["cost_estimate"]["sample_rates"] is True
    assert api.put("/api/prices", json=table).json()["sample"] is False
    second = api.post("/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}).json()
    assert second["report"]["cost_estimate"]["sample_rates"] is False


def _vendor_table(api):
    table = api.get("/api/prices").json()
    table["vendor"] = {
        "name": "Test Finishing Co.",
        "city": "Riyadh",
        "phone": "+966 50 000 0000",
        "logo": "data:image/svg+xml;base64,PHN2Zy8+",
        "terms": "Labour and materials included.",
    }
    return table


def test_vendor_price_table_is_imported_and_shown_on_reports(api_settings):
    api = TestClient(main.app)
    saved = api.put("/api/prices", json=_vendor_table(api))
    assert saved.status_code == 200, saved.text
    report = api.post("/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}).json()["report"]
    vendor = report["cost_estimate"]["vendor"]
    assert vendor["name"] == "Test Finishing Co." and vendor["logo"].startswith("data:image/svg+xml")


def test_bad_vendor_files_are_refused_with_a_reason(api_settings):
    api = TestClient(main.app)
    bad_logo = _vendor_table(api)
    bad_logo["vendor"]["logo"] = "https://example.com/logo.png"
    assert api.put("/api/prices", json=bad_logo).status_code == 422
    wrong_unit = _vendor_table(api)
    wrong_unit["tables"]["SAR"]["wall"]["unit"] = "each"
    res = api.put("/api/prices", json=wrong_unit)
    assert res.status_code == 422 and "unit must be m2" in res.json()["detail"]
    no_name = _vendor_table(api)
    no_name["vendor"]["name"] = ""
    assert api.put("/api/prices", json=no_name).status_code == 422


def test_edits_change_counts_remove_defects_and_can_be_undone(api_settings):
    api = TestClient(main.app)
    first = api.post("/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}, data={"scale_element": "door", "scale_height_m": "2.1"}).json()
    report = first["report"]
    doors = next(e for e in report["elements"] if e["type"] == "door")
    crack = next(d for d in report["defects"] if d["kind"] == "crack")
    edits = {
        "counts": {"door": doors["count"] + 1},
        "removed": {"0": {"crack": [crack["evidence"]["boxes"][0]]}},
    }
    edited = api.post(f"/api/edit/{first['id']}", json=edits).json()
    new_door = next(e for e in edited["report"]["elements"] if e["type"] == "door")
    assert new_door["count"] == doors["count"] + 1 and new_door["edited"]
    assert not any(d["kind"] == "crack" for d in edited["report"]["defects"])
    assert edited["report"]["cost_estimate"]["assumptions"][0].startswith("Edited by you")
    assert edited["report"]["summary"] == report["summary"]  # the written text is kept

    undone = api.post(f"/api/edit/{first['id']}", json={}).json()
    assert [e["count"] for e in undone["report"]["elements"]] == [e["count"] for e in report["elements"]]
    assert len(undone["report"]["defects"]) == len(report["defects"])
    assert undone["report"]["cost_estimate"]["low"] == report["cost_estimate"]["low"]


def test_adding_a_missed_window_prices_it(api_settings):
    api = TestClient(main.app)
    first = api.post("/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}, data={"scope": "window"}).json()
    low = first["report"]["cost_estimate"]["low"] or 0
    edited = api.post(f"/api/edit/{first['id']}", json={"counts": {"window": 3}}).json()
    assert next(e for e in edited["report"]["elements"] if e["type"] == "window")["count"] == 3
    assert edited["report"]["cost_estimate"]["low"] > low


def test_price_lists_save_switch_and_delete(api_settings):
    api = TestClient(main.app)
    table = api.get("/api/prices").json()
    table["vendor"] = {"name": "List Test Co."}
    assert api.put("/api/prices", json=table).json()["list_id"] == "list-test-co"
    lists = {x["id"]: x for x in api.get("/api/price-lists").json()}
    assert lists["list-test-co"]["active"] and not lists["default"]["active"]
    assert api.post("/api/price-lists/default/activate").json()["list_id"] == "default"
    assert api.get("/api/prices").json().get("vendor") is None
    assert api.delete("/api/price-lists/list-test-co").json()["deleted"]
    assert api.delete("/api/price-lists/default").status_code == 404
    assert api.post("/api/price-lists/../activate").status_code == 404


def test_rename_and_clear_history(api_settings):
    api = TestClient(main.app)
    first = api.post("/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}).json()
    assert api.patch(f"/api/history/{first['id']}", json={"title": "Villa 12, master bedroom"}).status_code == 200
    assert api.get("/api/history").json()[0]["title"] == "Villa 12, master bedroom"
    assert api.delete("/api/history").json()["deleted"] == 1
    assert api.get("/api/history").json() == []


def test_failed_write_up_can_be_retried(api_settings, monkeypatch):
    import json as _json

    from app.perceive import mock_detections

    replies = iter(["not json", "still not json", _json.dumps({"scene": "interior", "defects": {}, "summary": "Second try."})])

    class FlakyMuse:
        settings = main.settings

        def chat(self, messages, **params):
            return next(replies)

    monkeypatch.setattr(main, "client", FlakyMuse())
    monkeypatch.setattr(main, "settings", main.settings.__class__(**{**main.settings.__dict__, "mock": False, "perceiver": "muse"}))
    monkeypatch.setattr("app.pipeline.detect", lambda perceiver, client, png, w, h: mock_detections(w, h))
    api = TestClient(main.app)
    first = api.post("/api/analyze", files={"file": ("a.jpg", _photo(), "image/jpeg")}, data={"defer_reasoning": "true"}).json()
    assert api.post(f"/api/reason/{first['id']}").json()["reasoning"] == "failed"
    again = api.post(f"/api/reason/{first['id']}?retry=true").json()
    assert again["reasoning"] == "done" and again["report"]["summary"] == "Second try."


def test_health_reports_the_writer(api_settings):
    assert TestClient(main.app).get("/api/health").json()["writer"] == "off"  # mock mode


def test_rates_from_before_saved_lists_are_adopted(api_settings):
    import json as _json

    table = _json.loads(main.settings.prices_path.read_text(encoding="utf-8"))
    table["vendor"] = {"name": "Old Import Co."}
    main.settings.prices_path.write_text(_json.dumps(table), encoding="utf-8")
    lists = {x["id"]: x for x in TestClient(main.app).get("/api/price-lists").json()}
    assert lists["old-import-co"]["active"] and not lists["default"]["active"]
