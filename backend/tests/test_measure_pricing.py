import numpy as np

from app.measure import STANDARD_DOOR_M, apply_dimensions, combine, filter_for_role, hidden_walls, measure
from app.perceive import Detection
from app.pricing import estimate_cost
from app.schemas import PriceTable

PRICES = PriceTable.model_validate(
    {
        "default_currency": "SAR",
        "finish_multipliers": {"basic": 0.5, "standard": 1.0, "premium": 2.0},
        "tables": {
            "SAR": {
                "wall": {"label": "Paint", "unit": "m2", "low": 10, "high": 20},
                "door": {"label": "Door", "unit": "each", "low": 100, "high": 200},
            },
            "PKR": {
                "wall": {"label": "Paint", "unit": "m2", "low": 1000, "high": 2000},
                "door": {"label": "Door", "unit": "each", "low": 10000, "high": 20000},
            },
        },
    }
)


def _rect(x0, y0, x1, y1, w=100, h=100):
    m = np.zeros((h, w), dtype=bool)
    m[y0:y1, x0:x1] = True
    return m


def _door_and_wall():
    # door box height 40 px; wall 2000 px
    return [Detection("door", 0.9, _rect(10, 20, 30, 61)), Detection("wall", 0.9, _rect(0, 0, 100, 20))]


def test_counts_and_union_area_without_scale():
    dets = [
        Detection("wall", 0.8, _rect(0, 0, 50, 50)),
        Detection("wall", 0.6, _rect(25, 0, 75, 50)),  # overlaps the first
        Detection("crack", 0.5, _rect(10, 10, 11, 30)),
    ]
    m = measure(dets, 100, 100)
    [wall] = m.elements
    assert wall.count == 2
    assert wall.pixel_area == 75 * 50
    assert wall.image_share == 0.375
    assert wall.area_m2 is None
    assert wall.mean_score == 0.7
    assert m.scale.method == "none"
    assert m.defect_candidates[0].kind == "crack"


def test_door_height_sets_scale_and_square_metres():
    m = measure(_door_and_wall(), 100, 100, scale_element="door", scale_height_m=2.0)
    assert m.scale.method == "user_reference"
    assert m.scale.metres_per_pixel == 0.05
    wall = next(e for e in m.elements if e.type == "wall")
    assert wall.area_m2 == 5.0  # 2000 * 0.05^2


def test_missing_reference_element_leaves_scale_unset():
    m = measure([Detection("wall", 0.9, _rect(0, 0, 10, 10))], 100, 100, "door", 2.0)
    assert m.scale.method == "none"


def test_cost_uses_area_when_scaled_and_count_for_each_items():
    cost = estimate_cost(measure(_door_and_wall(), 100, 100, "door", 2.0), PRICES)
    assert (cost.low, cost.high) == (5 * 10 + 100, 5 * 20 + 200)
    assert [line.item for line in cost.lines] == ["Paint", "Door"]


def test_cost_skips_area_items_without_scale_and_says_so():
    cost = estimate_cost(measure(_door_and_wall(), 100, 100), PRICES)
    assert (cost.low, cost.high) == (100, 200)
    assert any("No scale reference" in a for a in cost.assumptions)


def test_currency_and_finish_change_the_range():
    m = measure(_door_and_wall(), 100, 100, "door", 2.0)
    cost = estimate_cost(m, PRICES, currency="PKR", finish="premium")
    assert cost.currency == "PKR"
    assert (cost.low, cost.high) == ((5 * 1000 + 10000) * 2, (5 * 2000 + 20000) * 2)
    assert estimate_cost(m, PRICES, currency="EUR").currency == "SAR"  # unknown -> default


def test_combine_adds_walls_and_takes_max_floor():
    a = measure(_door_and_wall() + [Detection("floor", 0.9, _rect(0, 80, 100, 100))], 100, 100, "door", 2.0)
    b = measure(_door_and_wall() + [Detection("floor", 0.7, _rect(0, 70, 100, 100))], 100, 100, "door", 2.0)
    room = combine([a, b])
    by_type = {e.type: e for e in room.elements}
    assert by_type["wall"].area_m2 == 10.0
    assert by_type["door"].count == 2
    assert by_type["floor"].area_m2 == 7.5  # max of 5.0 and 7.5
    assert by_type["floor"].count == 1


def test_combine_drops_area_only_for_elements_seen_unscaled():
    a = measure(_door_and_wall(), 100, 100, "door", 2.0)
    b = measure([Detection("wall", 0.9, _rect(0, 0, 100, 20))], 100, 100, "door", 2.0)  # no door: unscaled
    room = combine([a, b])
    by_type = {e.type: e for e in room.elements}
    assert by_type["wall"].area_m2 is None  # one wall photo had no scale
    assert by_type["door"].area_m2 == 2.05  # 20 x 41 px at 0.05 m/px; only in the scaled photo
    assert room.scale.method == "user_reference"


def test_role_keeps_its_own_elements_and_all_defects():
    dets = _door_and_wall() + [Detection("floor", 0.9, _rect(0, 80, 100, 100)), Detection("damp", 0.5, _rect(5, 5, 9, 9))]
    assert {d.label for d in filter_for_role(dets, "floor")} == {"floor", "damp"}
    assert {d.label for d in filter_for_role(dets, "wall")} == {"wall", "door", "damp"}
    assert filter_for_role(dets, None) == dets


def test_room_size_sets_floor_and_ceiling_area():
    m = measure([Detection("floor", 0.9, _rect(0, 80, 100, 100)), Detection("ceiling", 0.9, _rect(0, 0, 100, 10))], 100, 100)
    apply_dimensions(m, 4.0, 3.5)
    assert {e.type: (e.area_m2, e.area_source) for e in m.elements} == {"floor": (14.0, "dimensions"), "ceiling": (14.0, "dimensions")}
    assert m.room_size_m == [4.0, 3.5]


REPAIR_PRICES = PriceTable.model_validate(
    {
        **PRICES.model_dump(),
        "tables": {
            "SAR": {
                **PRICES.model_dump()["tables"]["SAR"],
                "crack": {"label": "Crack repair", "unit": "each", "low": 50, "high": 100},
            }
        },
    }
)


def test_scope_prices_only_selected_work_and_lists_the_rest():
    m = measure(_door_and_wall(), 100, 100, "door", 2.0)
    cost = estimate_cost(m, PRICES, scope=["door"])
    assert [line.item for line in cost.lines] == ["Door"]
    assert (cost.low, cost.high) == (100, 200)
    assert cost.scope == ["door"]
    assert any("not selected" in a and "Paint" in a for a in cost.assumptions)


def test_repairs_are_priced_per_flagged_defect():
    dets = _door_and_wall() + [Detection("crack", 0.6, _rect(50, 0, 51, 10)), Detection("crack", 0.6, _rect(60, 0, 61, 10))]
    cost = estimate_cost(measure(dets, 100, 100, "door", 2.0), REPAIR_PRICES, scope=["crack"])
    [line] = cost.lines
    assert (line.item, line.quantity, line.low, line.high) == ("Crack repair", 2.0, 100, 200)
    assert any("per flagged defect" in a for a in cost.assumptions)


def test_selected_work_not_in_photo_gives_no_range():
    cost = estimate_cost(measure(_door_and_wall(), 100, 100, "door", 2.0), REPAIR_PRICES, scope=["crack"])
    assert cost.low is None and cost.lines == []
    assert any("Nothing from the selected work" in a for a in cost.assumptions)


def test_estimate_mode_assumes_a_standard_door():
    m = measure(_door_and_wall(), 100, 100, assume_door=True)
    assert m.scale.method == "assumed_door"
    assert m.scale.metres_per_pixel == STANDARD_DOOR_M / 40  # box height 40 px, as in the 2.0 m test above
    wall = next(e for e in m.elements if e.type == "wall")
    assert wall.area_m2 is not None and wall.estimated
    assert m.estimate_notes


def test_user_reference_beats_the_standard_door():
    m = measure(_door_and_wall(), 100, 100, "door", 2.0, assume_door=True)
    assert m.scale.method == "user_reference"
    assert not any(e.estimated for e in m.elements)


def test_walls_from_room_size_and_ceiling_height_ignore_the_photo():
    dets = _door_and_wall() + [Detection("floor", 0.9, _rect(0, 80, 100, 100))]
    m = apply_dimensions(measure(dets, 100, 100), 4.0, 3.0, 2.8)
    by = {e.type: e for e in m.elements}
    # perimeter 14 m x 2.8 m = 39.2, minus one standard door 1.85
    assert (by["wall"].area_m2, by["wall"].area_source, by["wall"].estimated) == (37.35, "dimensions", False)
    assert by["floor"].area_m2 == 12.0
    assert m.ceiling_height_m == 2.8


def test_single_wall_width_times_height():
    m = apply_dimensions(measure(_door_and_wall(), 100, 100), ceiling_m=3.0, wall_width_m=4.0)
    wall = next(e for e in m.elements if e.type == "wall")
    assert wall.area_m2 == 10.15  # 12 - 1.85


def test_room_type_and_typical_ceiling_fill_gaps_when_estimating():
    dets = _door_and_wall() + [Detection("floor", 0.9, _rect(0, 80, 100, 100))]
    m = apply_dimensions(measure(dets, 100, 100), room_type="bedroom", estimate=True)
    by = {e.type: e for e in m.elements}
    assert m.room_size_m == [3.5, 4.0] and m.ceiling_height_m == 3.0
    assert by["floor"].area_m2 == 14.0 and by["floor"].estimated
    assert by["wall"].area_m2 == 43.15 and by["wall"].estimated  # 15 x 3 - 1.85
    assert any("bedroom" in n for n in m.estimate_notes)


def test_presets_are_ignored_without_estimate_mode():
    m = apply_dimensions(measure(_door_and_wall(), 100, 100), room_type="bedroom")
    assert m.room_size_m is None
    assert next(e for e in m.elements if e.type == "wall").area_m2 is None


def test_estimated_quantities_widen_the_range():
    exact = estimate_cost(apply_dimensions(measure(_door_and_wall(), 100, 100), 4.0, 3.0, 3.0), PRICES, scope=["wall"])
    rough = estimate_cost(
        apply_dimensions(measure(_door_and_wall(), 100, 100), 4.0, 3.0, estimate=True), PRICES, scope=["wall"]
    )
    # Same wall area (ceiling defaults to 3.0 m), but the estimate is wider on both ends.
    assert exact.lines[0].quantity == rough.lines[0].quantity
    assert rough.estimated and not exact.estimated
    q = rough.lines[0].quantity
    assert (rough.lines[0].low, rough.lines[0].high) == (round(q * 10 * 0.8), round(q * 20 * 1.25))
    assert (exact.lines[0].low, exact.lines[0].high) == (round(q * 10), round(q * 20))
    assert any("Estimated sizes" in a for a in rough.assumptions)
    assert any("furniture" in a for a in exact.assumptions)


def test_furniture_share_flows_from_detection_to_warning():
    wall = Detection("wall", 0.9, _rect(0, 0, 100, 20), hidden=0.45)
    m = measure([wall], 100, 100)
    assert m.elements[0].hidden_share == 0.45
    assert hidden_walls(m) == 0.45
    assert hidden_walls(measure([Detection("wall", 0.9, _rect(0, 0, 100, 20), hidden=0.1)], 100, 100)) is None


def test_room_that_is_not_a_rectangle_uses_entered_area_and_wall_length():
    dets = _door_and_wall() + [Detection("floor", 0.9, _rect(0, 80, 100, 100))]
    m = apply_dimensions(measure(dets, 100, 100), ceiling_m=3.0, floor_area_m2=21.5, perimeter_m=20.0)
    by = {e.type: e for e in m.elements}
    assert by["floor"].area_m2 == 21.5
    assert by["wall"].area_m2 == 58.15  # 20 m x 3 m - one standard door
    assert by["wall"].count == 1  # not assumed to be four walls
    assert not by["wall"].estimated


def test_totals_are_rounded_like_estimates_and_split_into_labour_and_materials():
    from app.pricing import nice_round

    assert (nice_round(7625), nice_round(27917), nice_round(321), nice_round(47)) == (7600, 27900, 320, 47)
    table = PriceTable.model_validate({
        "default_currency": "SAR",
        "finish_multipliers": {"basic": 1, "standard": 1, "premium": 1},
        "tables": {"SAR": {
            "wall": {"label": "Paint", "unit": "m2", "low": 100, "high": 200, "labour_share": 0.6},
            "door": {"label": "Door", "unit": "each", "low": 1000, "high": 2000, "labour_share": 0.2},
        }},
    })
    cost = estimate_cost(measure(_door_and_wall(), 100, 100, "door", 2.0), table)  # 5 m2 wall, 1 door
    assert (cost.low, cost.high) == (1500, 3000)
    assert (cost.labour_low, cost.materials_low) == (500, 1000)  # 300 + 200 labour
    no_split = estimate_cost(measure(_door_and_wall(), 100, 100, "door", 2.0), PRICES)
    assert no_split.labour_low is None
