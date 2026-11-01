"""Phase 7 evaluation: run the pipeline over a folder of photos and score it.

    python -m scripts.evaluate photos/ --labels photos/labels.json --runs 3 --no-cache --scale door:2.1

labels.json (optional), keyed by file name:
    {"room1.jpg": {"elements": {"door": 1, "window": 2}, "defects": ["crack", "damp"]}}

Writes eval/results/<timestamp>/results.json and results.md (one-slide summary).
"""
import argparse
import json
import statistics
import tempfile
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.cache import ResponseCache
from app.config import BACKEND_DIR, get_settings
from app.meta_client import MetaClient
from app.pipeline import analyze
from app.schemas import AnalysisOptions

PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def defect_scores(predicted: list[str], expected: list[str]) -> tuple[int, int, int]:
    p, e = Counter(predicted), Counter(expected)
    tp = sum((p & e).values())
    return tp, sum(p.values()) - tp, sum(e.values()) - tp


def run(args: argparse.Namespace) -> dict:
    settings = get_settings()
    photos = sorted(p for p in Path(args.photos).iterdir() if p.suffix.lower() in PHOTO_TYPES)
    if not photos:
        raise SystemExit(f"No photos in {args.photos}")
    labels = json.loads(Path(args.labels).read_text(encoding="utf-8")) if args.labels else {}
    scale_element, scale_height = (args.scale.split(":") + [None])[:2] if args.scale else (None, None)
    options = AnalysisOptions(
        scale_element=scale_element, scale_height_m=float(scale_height) if scale_height else None, language=args.language
    )
    tmp = Path(tempfile.mkdtemp(prefix="mimaar-eval-"))

    rows = []
    for photo in photos:
        data = photo.read_bytes()
        runs = []
        for i in range(args.runs):
            client = None
            if not settings.mock:
                cache_dir = tmp / f"{photo.stem}-{i}" if args.no_cache else settings.cache_dir
                client = MetaClient(settings, ResponseCache(cache_dir))
            start = time.perf_counter()
            result = analyze(data, settings, client, options, photo.name)
            runs.append((time.perf_counter() - start, result))

        counts = [tuple(sorted((e.type, e.count) for e in r.report.elements)) for _, r in runs]
        invalid = sum(any("failed validation" in w for w in r.warnings) for _, r in runs)
        fallback = sum(any("measurement-only" in w for w in r.warnings) for _, r in runs)
        last = runs[-1][1].report
        row = {
            "photo": photo.name,
            "mode": runs[-1][1].mode,
            "perceiver": runs[-1][1].perceiver,
            "seconds_mean": round(statistics.mean(t for t, _ in runs), 2),
            "invalid_outputs": invalid,
            "fallbacks": fallback,
            "consistent_counts": len(set(counts)) == 1,
            "elements": {e.type: e.count for e in last.elements},
            "defects": [d.kind for d in last.defects],
            "cost": [last.cost_estimate.low, last.cost_estimate.high, last.cost_estimate.currency],
        }
        label = labels.get(photo.name)
        if label:
            tp, fp, fn = defect_scores(row["defects"], label.get("defects", []))
            row["defect_tp_fp_fn"] = [tp, fp, fn]
            expected = label.get("elements", {})
            row["element_count_matches"] = sum(row["elements"].get(k) == v for k, v in expected.items())
            row["element_count_total"] = len(expected)
        rows.append(row)
        print(f"{photo.name}: {row['seconds_mean']}s, invalid={invalid}, consistent={row['consistent_counts']}")

    total_runs = len(rows) * args.runs
    tp = sum(r.get("defect_tp_fp_fn", [0, 0, 0])[0] for r in rows)
    fp = sum(r.get("defect_tp_fp_fn", [0, 0, 0])[1] for r in rows)
    fn = sum(r.get("defect_tp_fp_fn", [0, 0, 0])[2] for r in rows)
    matched = sum(r.get("element_count_matches", 0) for r in rows)
    expected = sum(r.get("element_count_total", 0) for r in rows)
    summary = {
        "photos": len(rows),
        "runs_per_photo": args.runs,
        "json_valid_rate": round(1 - sum(r["invalid_outputs"] for r in rows) / total_runs, 3),
        "fallback_rate": round(sum(r["fallbacks"] for r in rows) / total_runs, 3),
        "count_consistency_rate": round(sum(r["consistent_counts"] for r in rows) / len(rows), 3),
        "mean_seconds": round(statistics.mean(r["seconds_mean"] for r in rows), 2),
        "defect_precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "defect_recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "element_count_accuracy": round(matched / expected, 3) if expected else None,
    }
    return {"summary": summary, "rows": rows}


def to_markdown(results: dict) -> str:
    s = results["summary"]
    lines = [
        "# Mimaar AI evaluation",
        "",
        f"{s['photos']} photos x {s['runs_per_photo']} runs.",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    lines += [f"| {k.replace('_', ' ')} | {v if v is not None else 'n/a (no labels)'} |" for k, v in s.items()]
    lines += ["", "| Photo | Seconds | Invalid | Consistent | Defects | Cost |", "|---|---|---|---|---|---|"]
    for r in results["rows"]:
        cost = f"{r['cost'][0]}–{r['cost'][1]} {r['cost'][2]}" if r["cost"][0] is not None else "n/a"
        lines.append(
            f"| {r['photo']} | {r['seconds_mean']} | {r['invalid_outputs']} | {r['consistent_counts']} | "
            f"{', '.join(r['defects']) or '—'} | {cost} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photos")
    parser.add_argument("--labels")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--no-cache", action="store_true", help="fresh model calls per run (costs credits)")
    parser.add_argument("--scale", help="reference element and height, e.g. door:2.1")
    parser.add_argument("--language", default="en", choices=["en", "ur", "ar"])
    args = parser.parse_args()

    results = run(args)
    out = BACKEND_DIR.parent / "eval" / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "results.md").write_text(to_markdown(results), encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))
    print("Saved to", out)


if __name__ == "__main__":
    main()
