import shutil
from dataclasses import replace

import pytest

from app import main
from app.config import BACKEND_DIR
from app.history import History

DEFAULT_RATES = BACKEND_DIR.parent / "docs" / "price-tables" / "mimaar-default-rates.json"


@pytest.fixture
def api_settings(tmp_path, monkeypatch):
    """Mock-mode settings with prices and history in a temp dir, so tests never touch real data.
    Prices start from the shipped defaults, not whatever vendor file is imported in the app."""
    prices = tmp_path / "prices.json"
    shutil.copy(DEFAULT_RATES, prices)
    settings = replace(main.settings, mock=True, perceiver="mock", data_dir=tmp_path, prices_path=prices)
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "client", None)
    monkeypatch.setattr(main, "history", History(tmp_path / "history.db"))
    return settings
