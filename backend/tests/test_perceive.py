import base64
import io
import json

import numpy as np
from PIL import Image

from app.perceive import decode_rle, mock_detections, parse_sam_response


def _png_b64(mask: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray((mask * 255).astype(np.uint8)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_parses_base64_png_masks_nested_anywhere():
    mask = np.zeros((40, 60), dtype=bool)
    mask[10:20, 5:25] = True
    raw = {"output": [{"content": [{"objects": [{"mask": _png_b64(mask), "score": 0.9}]}]}]}
    [det] = parse_sam_response(raw, "wall", 60, 40)
    assert det.score == 0.9
    assert det.mask.sum() == 200
    assert det.box == [5, 10, 24, 19]


def test_parses_normalised_polygon_and_box():
    raw = {
        "results": [
            {"polygon": [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]], "confidence": 0.7},
            {"bbox": [50, 50, 100, 100]},
        ]
    }
    dets = parse_sam_response(raw, "door", 100, 100)
    assert len(dets) == 2
    assert 2400 < dets[0].mask.sum() <= 2601
    assert dets[1].mask.sum() == 2500
    assert dets[1].score == 0.5


def test_parses_geometry_embedded_as_json_text():
    text = json.dumps([{"box": [0, 0, 10, 10], "score": 0.8}])
    raw = {"output": [{"content": [{"type": "output_text", "text": text}]}]}
    [det] = parse_sam_response(raw, "window", 20, 20)
    assert det.mask.sum() == 100


def test_uncompressed_rle_is_column_major():
    # 2x3 image (h=2, w=3): column-major runs -> 2 zeros, 2 ones, 2 zeros
    mask = decode_rle({"counts": [2, 2, 2], "size": [2, 3]}, 3, 2)
    assert mask.tolist() == [[False, True, False], [False, True, False]]


def test_empty_masks_are_dropped():
    raw = {"objects": [{"bbox": [0, 0, 0, 0]}]}
    assert parse_sam_response(raw, "wall", 10, 10) == []


def test_mock_detections_cover_every_element_and_defects():
    labels = {d.label for d in mock_detections(320, 240)}
    assert {"wall", "floor", "ceiling", "door", "window", "crack"} <= labels


def test_muse_grounding_boxes_on_1000_grid():
    from app.perceive import parse_grounding

    data = [
        {"label": "Door", "box": [100, 200, 300, 900], "score": 0.8},
        {"label": "sofa", "box": [0, 0, 10, 10]},  # unknown label dropped
        {"label": "wall", "box": "bad"},  # malformed dropped
        {"label": "window", "box": [600, 100, 500, 300], "score": 3},  # swapped corners, clamped score
    ]
    door, window = parse_grounding(data, 200, 100)
    assert door.label == "door" and door.source == "muse-grounding"
    assert door.box == [20, 20, 59, 89]
    assert window.score == 1.0 and window.mask.sum() > 0


def test_refine_cuts_openings_out_of_walls():
    from app.perceive import Detection, box_mask, refine

    wall = Detection("wall", 0.9, box_mask([0, 0, 100, 100], 100, 100))
    door = Detection("door", 0.9, box_mask([10, 10, 30, 60], 100, 100))
    refined = refine([wall, door])
    assert refined[0].mask.sum() == 10000 - 1000


def test_grounding_reads_furniture_cover_and_refine_keeps_it():
    from app.perceive import parse_grounding, refine

    data = [
        {"label": "wall", "box": [0, 0, 1000, 600], "score": 0.9, "hidden": 0.4},
        {"label": "door", "box": [100, 200, 300, 600], "score": 0.8, "hidden": "n/a"},
    ]
    wall, door = parse_grounding(data, 200, 100)
    assert (wall.hidden, door.hidden) == (0.4, 0.0)
    assert next(d for d in refine([wall, door]) if d.label == "wall").hidden == 0.4


def test_furniture_cover_is_measured_inside_each_wall():
    from app.perceive import Detection, mark_hidden

    wall_mask = np.zeros((100, 100), dtype=bool)
    wall_mask[0:50, 0:100] = True
    wall_mask[30:50, 0:50] = False  # SAM traces the wall around the sofa
    sofa = np.zeros((100, 100), dtype=bool)
    sofa[30:50, 0:50] = True
    [wall] = mark_hidden([Detection("wall", 0.9, wall_mask)], [sofa])
    assert wall.hidden == 0.2  # 1000 of the wall box's 5000 pixels


def test_local_sam_routes_through_its_perceiver(monkeypatch):
    from types import SimpleNamespace

    from app import perceive, sam_local

    door = np.zeros((40, 60), dtype=bool)
    door[10:40, 5:20] = True
    sofa = np.zeros((40, 60), dtype=bool)
    sofa[25:40, 30:60] = True
    wall = np.zeros((40, 60), dtype=bool)
    wall[0:40, :] = True
    found = {"wall": [(wall, 0.9)], "door": [(door, 0.8)], "furniture": [(sofa, 0.7)]}
    weak = np.zeros((40, 60), dtype=bool)
    weak[0:3, 0:3] = True
    found["peeling paint"] = [(weak, 0.45)]  # below the peeling bar
    found["water stain"] = [(weak, 0.35)]  # above the damp bar
    monkeypatch.setattr(sam_local, "segment", lambda settings, png, phrases, threshold: found)
    client = SimpleNamespace(settings=SimpleNamespace(backend="local"))
    dets = perceive.detect("sam_local", client, b"", 60, 40)
    assert {d.label for d in dets} == {"wall", "door", "damp"}  # furniture is never an element
    assert all(d.source == "sam-3" for d in dets)
    assert next(d for d in dets if d.label == "wall").hidden > 0


def test_split_and_duplicate_defects_merge_but_distant_ones_stay():
    from app.perceive import Detection, refine

    def box(x0, y0, x1, y1):
        m = np.zeros((100, 100), dtype=bool)
        m[y0:y1, x0:x1] = True
        return m

    dets = [
        Detection("damp", 0.38, box(10, 10, 20, 20)),
        Detection("damp", 0.39, box(11, 11, 21, 21)),  # the same patch again
        Detection("damp", 0.30, box(22, 12, 30, 20)),  # an adjoining patch of the same stain
        Detection("damp", 0.35, box(70, 70, 80, 80)),  # a separate stain
        Detection("damp", 0.20, box(40, 70, 50, 80)),  # another separate stain, so groups get compared
        Detection("crack", 0.8, box(21, 10, 23, 30)),  # a crack beside the stain stays a crack
        Detection("wall", 0.9, box(0, 0, 100, 100)),
        Detection("wall", 0.8, box(0, 0, 100, 100)),  # an exact duplicate of the wall
    ]
    out = refine(dets)
    damp = sorted((d for d in out if d.label == "damp"), key=lambda d: d.score)
    assert [d.score for d in damp] == [0.2, 0.35, 0.39]
    assert damp[-1].mask.sum() > box(10, 10, 21, 21).sum()  # the merged stain covers all its patches
    assert sum(d.label == "crack" for d in out) == 1
    assert sum(d.label == "wall" for d in out) == 1


def test_wardrobe_doors_are_not_room_doors(monkeypatch):
    from types import SimpleNamespace

    from app import perceive, sam_local

    def box(x0, y0, x1, y1):
        m = np.zeros((100, 100), dtype=bool)
        m[y0:y1, x0:x1] = True
        return m

    found = {
        "wall": [(box(0, 0, 100, 80), 0.9)],
        "door": [
            (box(5, 10, 15, 75), 0.85),  # a wardrobe panel
            (box(15, 10, 25, 75), 0.84),  # the next panel
            (box(50, 20, 70, 75), 0.96),  # the real door
        ],
        "wardrobe": [(box(3, 8, 27, 78), 0.91)],
        "furniture": [(box(3, 8, 27, 78), 0.95)],
    }
    monkeypatch.setattr(sam_local, "segment", lambda settings, png, phrases, threshold: found)
    dets = perceive.detect("sam_local", SimpleNamespace(settings=SimpleNamespace(backend="local")), b"", 100, 100)
    doors = [d for d in dets if d.label == "door"]
    assert len(doors) == 1 and doors[0].score == 0.96


def test_edge_slivers_and_door_panels_are_not_extra_elements():
    from app.perceive import Detection, refine

    def box(x0, y0, x1, y1, w=600, h=800):
        m = np.zeros((h, w), dtype=bool)
        m[y0:y1, x0:x1] = True
        return m

    dets = [
        Detection("wall", 0.9, box(278, 281, 596, 556)),  # back wall
        Detection("wall", 0.9, box(2, 210, 273, 683)),  # left wall
        Detection("wall", 0.8, box(0, 2, 11, 799)),  # 11 px strip at the left edge
        Detection("wall", 0.7, box(596, 275, 599, 330)),  # 3 px strip at the right edge
        Detection("door", 0.9, box(247, 355, 277, 557)),  # back door
        Detection("door", 0.9, box(483, 334, 599, 638)),  # two-tone door, whole
        Detection("door", 0.8, box(525, 334, 599, 638)),  # its dark half
        Detection("door", 0.8, box(483, 336, 527, 630)),  # its light half
        Detection("window", 0.9, box(304, 317, 430, 474)),
        Detection("window", 0.9, box(13, 309, 150, 538)),
    ]
    out = refine(dets)
    count = lambda label: sum(d.label == label for d in out)
    assert (count("wall"), count("door"), count("window")) == (2, 2, 2)


def test_window_panes_are_not_doors_and_door_glass_is_not_a_window():
    from app.perceive import Detection, refine

    def box(x0, y0, x1, y1, w=600, h=700):
        m = np.zeros((h, w), dtype=bool)
        m[y0:y1, x0:x1] = True
        return m

    dets = [
        Detection("wall", 0.9, box(4, 104, 598, 437)),
        Detection("window", 0.9, box(329, 119, 596, 355)),  # sliding window
        Detection("door", 0.6, box(433, 142, 481, 324)),  # one of its panes
        Detection("door", 0.6, box(331, 152, 377, 315)),  # another pane
        Detection("door", 0.9, box(137, 172, 167, 391)),  # a real door leaf
        Detection("door", 0.9, box(500, 380, 560, 600)),  # a door with a glass panel...
        Detection("window", 0.7, box(515, 400, 545, 450)),  # ...that is not a window
    ]
    out = refine(dets)
    doors = sorted(d.box[0] for d in out if d.label == "door")
    windows = [d.box[0] for d in out if d.label == "window"]
    assert doors == [137, 500] and windows == [329]


def _box(x0, y0, x1, y1, w=600, h=800):
    m = np.zeros((h, w), dtype=bool)
    m[y0:y1, x0:x1] = True
    return m


def test_real_photo_double_door_and_room_beyond_it():
    """Boxes from a real listing photo: an open double door with the next room visible through it."""
    from app.perceive import Detection, refine

    dets = [
        Detection("wall", 0.9, _box(0, 204, 599, 544)),  # this room's walls
        Detection("wall", 0.8, _box(46, 272, 134, 465)),  # the next room's wall, through the doorway
        Detection("floor", 0.9, _box(0, 500, 599, 799)),
        Detection("floor", 0.7, _box(50, 470, 130, 490)),  # the next room's floor
        Detection("door", 0.9, _box(134, 278, 164, 496)),  # right leaf
        Detection("door", 0.9, _box(27, 262, 49, 522)),  # left leaf
        Detection("window", 0.9, _box(327, 225, 594, 460)),
    ]
    out = refine(dets)
    count = lambda label: sum(d.label == label for d in out)
    assert (count("wall"), count("floor"), count("door"), count("window")) == (1, 1, 1, 1)


def test_real_photo_wall_beside_an_open_door_is_the_next_room():
    from app.perceive import Detection, refine

    dets = [
        Detection("wall", 0.9, _box(0, 153, 239, 584)),
        Detection("wall", 0.9, _box(243, 230, 582, 541)),
        Detection("wall", 0.8, _box(560, 195, 599, 751)),
        Detection("wall", 0.7, _box(275, 315, 297, 486)),  # seen through the open door
        Detection("door", 0.9, _box(240, 314, 272, 499)),
        Detection("window", 0.9, _box(440, 306, 580, 457)),
    ]
    out = refine(dets)
    assert sum(d.label == "wall" for d in out) == 3


def test_two_separate_doors_stay_two():
    from app.perceive import Detection, refine

    dets = [Detection("door", 0.9, _box(247, 355, 277, 557)), Detection("door", 0.9, _box(483, 334, 599, 638))]
    assert sum(d.label == "door" for d in refine(dets)) == 2
