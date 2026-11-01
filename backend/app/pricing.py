"""Cost range computed in code from an editable price table, not by the model."""
import json
from collections import Counter
from pathlib import Path

from .schemas import ALL_WORK, CostEstimate, CostLine, Finish, Measurements, PriceTable


# Quantities that rest on typical sizes get a wider range: -20% on the low end, +25% on the high.
ESTIMATE_LOW, ESTIMATE_HIGH = 0.8, 1.25


def nice_round(value: float) -> float:
    """Totals are estimates, so show them as such: nearest 100 from 1,000, nearest 10 below."""
    step = 100 if value >= 1000 else 10 if value >= 100 else 1
    return float(round(value / step) * step)


def load_prices(path: Path) -> PriceTable:
    return PriceTable.model_validate_json(path.read_text(encoding="utf-8"))


def save_prices(path: Path, table: PriceTable) -> None:
    path.write_text(json.dumps(table.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def estimate_cost(
    measurements: Measurements,
    prices: PriceTable,
    currency: str | None = None,
    finish: Finish = "standard",
    scope: list[str] | None = None,
) -> CostEstimate:
    """Price only the work items the customer selected; everything detected is still reported."""
    currency = currency if currency in prices.tables else prices.default_currency
    table = prices.tables[currency]
    multiplier = prices.finish_multipliers.get(finish, 1.0)
    wanted = [item for item in ALL_WORK if scope is None or item in scope]

    # (work item, quantity in the item's unit or None when it needs a scale reference, estimated, edited)
    candidates: list[tuple[str, float | None, bool, bool]] = []
    for element in measurements.elements:
        rate = table.get(element.type)
        if rate and element.count > 0:
            if rate.unit == "each":
                candidates.append((element.type, float(element.count), False, element.edited))
            else:
                estimated = element.estimated and element.area_m2 is not None and not element.edited
                candidates.append((element.type, element.area_m2, estimated, element.edited))
    # Repairs are priced per flagged defect.
    for kind, count in Counter(d.kind for d in measurements.defect_candidates).items():
        if kind in table:
            candidates.append((kind, float(count), False, False))

    lines: list[CostLine] = []
    skipped = []
    for item, quantity, estimated, edited in candidates:
        if item not in wanted:
            continue
        rate = table[item]
        if quantity is None:
            skipped.append(item)
            continue
        low, high = (ESTIMATE_LOW, ESTIMATE_HIGH) if estimated else (1.0, 1.0)
        lines.append(
            CostLine(
                item=rate.label,
                quantity=quantity,
                unit=rate.unit,
                low=round(quantity * rate.low * multiplier * low),
                high=round(quantity * rate.high * multiplier * high),
                estimated=estimated,
                labour_share=rate.labour_share,
                edited=edited,
            )
        )

    assumptions = [f"{line.item}: {line.quantity:g} {line.unit}" for line in lines]
    detected = {item for item, *_ in candidates}
    not_selected = [table[item].label for item in ALL_WORK if item in detected and item not in wanted]
    if not_selected:
        assumptions.append(f"Detected but not included (not selected): {', '.join(not_selected)}.")
    if any(item in wanted for item in ("crack", "damp", "peeling")):
        assumptions.append("Repairs are priced per flagged defect, before any on-site inspection.")
    if finish != "standard":
        assumptions.append(f"{finish.title()} finish: rates multiplied by {multiplier:g}.")
    if skipped:
        assumptions.append(
            f"No scale reference, so area-priced items were left out: {', '.join(skipped)}. "
            "Enter a known dimension, or choose \"I don't have measurements\" to estimate them."
        )
    estimated = any(line.estimated for line in lines)
    if estimated:
        assumptions.append(
            "Estimated sizes, not measured: " + " ".join(measurements.estimate_notes)
            + " Their range is widened (-20% / +25%). Measure for an exact quote."
        )
    base = {"currency": currency, "finish": finish, "scope": wanted, "sample_rates": prices.sample, "vendor": prices.vendor}
    if not lines:
        assumptions.append("Nothing from the selected work was found in the photo." if wanted else "No work was selected.")
        return CostEstimate(**base, assumptions=assumptions)
    wall = next((e for e in measurements.elements if e.type == "wall"), None)
    if wall and wall.area_source == "dimensions" and measurements.ceiling_height_m:
        assumptions.append(
            f"Wall area = wall length × {measurements.ceiling_height_m:g} m ceiling height, minus doors and windows; "
            "furniture in the photo does not change it."
        )
    if not all(e.area_source == "dimensions" for e in measurements.elements if e.area_m2 is not None):
        assumptions.append("Photo-measured areas cover visible surfaces only; perspective makes them rough.")
    if prices.note:
        assumptions.append(prices.note)
    split = {}
    if all(line.labour_share is not None for line in lines):
        labour_low = sum(line.low * line.labour_share for line in lines)
        labour_high = sum(line.high * line.labour_share for line in lines)
        split = {
            "labour_low": nice_round(labour_low),
            "labour_high": nice_round(labour_high),
            "materials_low": nice_round(sum(line.low for line in lines) - labour_low),
            "materials_high": nice_round(sum(line.high for line in lines) - labour_high),
        }
        assumptions.append("Labour and materials are split by the vendor's labour share for each item.")
    return CostEstimate(
        **base,
        **split,
        low=nice_round(sum(line.low for line in lines)),
        high=nice_round(sum(line.high for line in lines)),
        estimated=estimated,
        lines=lines,
        assumptions=assumptions,
    )
