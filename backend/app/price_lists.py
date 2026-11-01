"""Saved price lists: the built-in default rates plus every vendor file imported or saved.

The active list is the live price file (settings.prices_path) that pricing reads; switching
copies a saved list over it. Saved lists sit in data_dir, which git ignores.
"""
import json
import re
from pathlib import Path

from .config import BACKEND_DIR, Settings
from .pricing import load_prices, save_prices
from .schemas import PriceTable

DEFAULT_ID = "default"
DEFAULT_PATH = BACKEND_DIR / "data" / "default-prices.json"


def _dir(settings: Settings) -> Path:
    path = settings.data_dir / "price-lists"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_id_for(table: PriceTable) -> str:
    name = table.vendor.name if table.vendor else "my-rates"
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "my-rates"


def saved(settings: Settings) -> list[PriceTable]:
    """The default list first, then saved lists by name."""
    tables = [load_prices(DEFAULT_PATH).model_copy(update={"list_id": DEFAULT_ID})]
    for path in sorted(_dir(settings).glob("*.json")):
        tables.append(load_prices(path).model_copy(update={"list_id": path.stem}))
    return tables


LEGACY_PATH = BACKEND_DIR / "data" / "prices.json"


def ensure_live(settings: Settings) -> None:
    """Create the live price file on first run: from the old location if a previous version used
    it (keeping the user's rates), otherwise from the defaults."""
    if settings.prices_path.exists():
        return
    settings.prices_path.parent.mkdir(parents=True, exist_ok=True)
    source = LEGACY_PATH if LEGACY_PATH.exists() else DEFAULT_PATH
    settings.prices_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    if source == LEGACY_PATH:
        LEGACY_PATH.unlink()


def adopt(settings: Settings) -> PriceTable:
    """The live table from before saved lists existed has no list id: give it one, saving it as a
    list unless it is just the default rates."""
    table = load_prices(settings.prices_path)
    if table.list_id:
        return table
    default = load_prices(DEFAULT_PATH)
    if table.vendor is None and table.tables == default.tables:
        table = table.model_copy(update={"list_id": DEFAULT_ID})
        save_prices(settings.prices_path, table)
        return table
    return remember(settings, table)


def remember(settings: Settings, table: PriceTable) -> PriceTable:
    """Save a list (new or edited) under its vendor's name and make it the active one."""
    table = table.model_copy(update={"list_id": table.list_id if table.list_id not in (None, DEFAULT_ID) else list_id_for(table)})
    save_prices(_dir(settings) / f"{table.list_id}.json", table)
    save_prices(settings.prices_path, table)
    return table


def activate(settings: Settings, list_id: str) -> PriceTable | None:
    if list_id == DEFAULT_ID:
        table = load_prices(DEFAULT_PATH).model_copy(update={"list_id": DEFAULT_ID})
    else:
        path = _dir(settings) / f"{list_id}.json"
        if not re.fullmatch(r"[a-z0-9-]+", list_id) or not path.exists():
            return None
        table = load_prices(path).model_copy(update={"list_id": list_id})
    save_prices(settings.prices_path, table)
    return table


def forget(settings: Settings, list_id: str) -> bool:
    path = _dir(settings) / f"{list_id}.json"
    if list_id == DEFAULT_ID or not re.fullmatch(r"[a-z0-9-]+", list_id) or not path.exists():
        return False
    path.unlink()
    return True
