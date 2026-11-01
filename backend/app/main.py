import threading
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .cache import ResponseCache
from .config import get_settings
from .history import History
from .meta_client import MetaAPIError, MetaClient
from . import price_lists
from .pipeline import InvalidImage, analyze, analyze_room, apply_edits, change_language, finish_reasoning
from .pricing import load_prices, save_prices
from pydantic import BaseModel, Field

from .schemas import AREA_WORK, ALL_WORK, AnalysisOptions, AnalysisResult, Edits, HistoryEntry, PriceTable, RoomResult, RoomType

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_ROOM_PHOTOS = 6

settings = get_settings()
client = None if settings.mock else MetaClient(settings, ResponseCache(settings.cache_dir))
history = History(settings.data_dir / "history.db")
price_lists.ensure_live(settings)

_writing = threading.Lock()

app = FastAPI(title="Mimaar AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _model_source() -> str:
    return "local model" if settings.backend == "local" else "Meta Model API"


def _options(scale_element, scale_height_m, language, currency, finish, scope) -> AnalysisOptions:
    return AnalysisOptions(
        scale_element=scale_element,
        scale_height_m=scale_height_m,
        language=language,
        currency=currency,
        finish=finish,
        scope=_parse_scope(scope),
    )


def _parse_scope(scope: str | None) -> list[str]:
    """Comma-separated work items to price; omitted means everything."""
    if scope is None:
        return list(ALL_WORK)
    items = [s.strip() for s in scope.split(",") if s.strip()]
    unknown = [s for s in items if s not in ALL_WORK]
    if unknown:
        raise HTTPException(422, f"Unknown work items: {', '.join(unknown)}.")
    if not items:
        raise HTTPException(400, "Choose at least one item of work to price.")
    return items


async def _read(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"{file.filename or 'Photo'} is larger than 15 MB.")
    return data


def _writer_status() -> str:
    """Whether the report writer can answer: ready, loading (local model still starting), offline,
    api (Meta Model API, not checked) or off (mock mode)."""
    if settings.mock:
        return "off"
    if settings.backend != "local":
        return "api"
    import httpx

    try:
        res = httpx.get(settings.base_url.removesuffix("/v1") + "/health", timeout=1.5)
    except httpx.HTTPError:
        return "offline"
    return "ready" if res.status_code == 200 else "loading"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "mock" if settings.mock else "live",
        "backend": settings.backend,
        "perceiver": settings.perceiver,
        "reasoner": settings.reasoner,
        "writer": _writer_status(),
    }


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_photo(
    file: UploadFile = File(...),
    scale_element: Literal["door", "window"] | None = Form(None),
    scale_height_m: float | None = Form(None, gt=0, le=20),
    language: Literal["en", "ur", "ar"] = Form("en"),
    currency: str | None = Form(None),
    finish: Literal["basic", "standard", "premium"] = Form("standard"),
    scope: str | None = Form(None),
    role: Literal["floor", "ceiling", "wall"] | None = Form(None),
    wall_width_m: float | None = Form(None, gt=0, le=50),
    ceiling_height_m: float | None = Form(None, gt=0, le=10),
    estimate: bool = Form(False),
    defer_reasoning: bool = Form(False),
) -> AnalysisResult:
    options = _options(scale_element, scale_height_m, language, currency, finish, scope)
    options.wall_width_m, options.ceiling_height_m, options.estimate = wall_width_m, ceiling_height_m, estimate
    data = await _read(file)
    try:
        result = analyze(data, settings, client, options, file.filename or "", role, defer=defer_reasoning)
    except InvalidImage as exc:
        raise HTTPException(400, str(exc)) from exc
    except MetaAPIError as exc:
        raise HTTPException(502, f"The {_model_source()} call failed: {exc}") from exc
    history.add(result)
    return result


@app.post("/api/analyze-room", response_model=RoomResult)
async def analyze_room_photos(
    files: list[UploadFile] = File(...),
    scale_element: Literal["door", "window"] | None = Form(None),
    scale_height_m: float | None = Form(None, gt=0, le=20),
    language: Literal["en", "ur", "ar"] = Form("en"),
    currency: str | None = Form(None),
    finish: Literal["basic", "standard", "premium"] = Form("standard"),
    scope: str | None = Form(None),
    roles: str | None = Form(None, description="Comma-separated floor/ceiling/wall, one per file"),
    room_length_m: float | None = Form(None, gt=0, le=100),
    room_width_m: float | None = Form(None, gt=0, le=100),
    ceiling_height_m: float | None = Form(None, gt=0, le=10),
    estimate: bool = Form(False),
    room_type: RoomType | None = Form(None),
    room_floor_area_m2: float | None = Form(None, gt=0, le=2000),
    room_perimeter_m: float | None = Form(None, gt=0, le=400),
    defer_reasoning: bool = Form(False),
) -> RoomResult:
    if not 1 <= len(files) <= MAX_ROOM_PHOTOS:
        raise HTTPException(400, f"A room needs 1 to {MAX_ROOM_PHOTOS} photos.")
    role_list: list[str | None] = [None] * len(files)
    if roles is not None:
        role_list = [r.strip() for r in roles.split(",")]
        if len(role_list) != len(files) or any(r not in ("floor", "ceiling", "wall") for r in role_list):
            raise HTTPException(422, "roles must list floor, ceiling or wall once per photo.")
    options = _options(scale_element, scale_height_m, language, currency, finish, scope)
    options.room_length_m, options.room_width_m = room_length_m, room_width_m
    options.ceiling_height_m, options.estimate, options.room_type = ceiling_height_m, estimate, room_type
    options.room_floor_area_m2, options.room_perimeter_m = room_floor_area_m2, room_perimeter_m
    photos = [(await _read(f), f.filename or "", role) for f, role in zip(files, role_list)]
    try:
        result = analyze_room(photos, settings, client, options, defer=defer_reasoning)
    except InvalidImage as exc:
        raise HTTPException(400, str(exc)) from exc
    except MetaAPIError as exc:
        raise HTTPException(502, f"The {_model_source()} call failed: {exc}") from exc
    history.add(result)
    return result


@app.post("/api/language/{entry_id}", response_model=AnalysisResult | RoomResult)
def relanguage(entry_id: str, language: Literal["en", "ur", "ar"] = Form(...)) -> AnalysisResult | RoomResult:
    """Same analysis, report in another language. Instant; call /api/reason/{id} after it for the
    Muse model's write-up."""
    result = history.get(entry_id)
    if result is None:
        raise HTTPException(404, "Not found.")
    if result.report.language != language:
        result = change_language(result, language)
        history.update(result)
    return result


@app.post("/api/reason/{entry_id}", response_model=AnalysisResult | RoomResult)
def write_report(entry_id: str, retry: bool = False) -> AnalysisResult | RoomResult:
    """Second half of a deferred analysis: the Muse model writes the report. A plain `def`, so the
    minutes a local model can take run in a worker thread instead of blocking other requests.
    `retry` tries again after a failed write-up."""
    result = history.get(entry_id)
    if result is None:
        raise HTTPException(404, "Not found.")
    if retry and result.reasoning == "failed" and client is not None:
        result.reasoning = "pending"
        result.warnings = [w for w in result.warnings if "could not write the report" not in w and "measurement-only" not in w]
        history.update(result)
    if result.reasoning != "pending" or client is None:
        return result
    try:
        # One write-up at a time: a local model splits its speed across parallel requests.
        with _writing:
            result = history.get(entry_id) or result  # another request may have finished it
            if result.reasoning == "pending":
                result = finish_reasoning(result, settings, client)
    except MetaAPIError as exc:
        result.reasoning = "failed"
        result.warnings.append(f"The {_model_source()} could not write the report: {exc}")
    history.update(result)
    return result


@app.post("/api/edit/{entry_id}", response_model=AnalysisResult | RoomResult)
def edit_result(entry_id: str, edits: Edits) -> AnalysisResult | RoomResult:
    """Apply the user's corrections (tapped-away detections, changed counts or areas) and re-price
    with the current price list. Sending empty edits undoes them all."""
    result = history.get(entry_id)
    if result is None or result.measurements is None:
        raise HTTPException(404, "Not found.")
    result = apply_edits(result, edits, settings)
    history.update(result)
    return result


@app.get("/api/prices", response_model=PriceTable)
def get_prices() -> PriceTable:
    return load_prices(settings.prices_path)


@app.put("/api/prices", response_model=PriceTable)
def put_prices(table: PriceTable) -> PriceTable:
    """Save the price table: edited in the app, or imported from a vendor's price file."""
    if not table.tables:
        raise HTTPException(422, "The price table has no currencies.")
    for currency, items in table.tables.items():
        if not items:
            raise HTTPException(422, f"{currency}: no rates.")
        for name, item in items.items():
            if item.low > item.high:
                raise HTTPException(422, f"{currency} {name}: low is above high.")
            expected = "m2" if name in AREA_WORK else "each"
            if item.unit != expected:
                raise HTTPException(422, f"{currency} {name}: unit must be {expected}.")
    if table.default_currency not in table.tables:
        raise HTTPException(422, "default_currency must be one of the tables.")
    table.sample = False  # saved from the editor or imported: these are now the user's own rates
    return price_lists.remember(settings, table)


class PriceListInfo(BaseModel):
    id: str
    name: str
    currencies: list[str]
    active: bool
    logo: str | None = None


@app.get("/api/price-lists", response_model=list[PriceListInfo])
def get_price_lists() -> list[PriceListInfo]:
    active = price_lists.adopt(settings).list_id
    return [
        PriceListInfo(
            id=t.list_id,
            name=t.vendor.name if t.vendor else ("Mimaar default rates" if t.list_id == price_lists.DEFAULT_ID else "My rates"),
            currencies=list(t.tables),
            active=t.list_id == active,
            logo=t.vendor.logo if t.vendor else None,
        )
        for t in price_lists.saved(settings)
    ]


@app.post("/api/price-lists/{list_id}/activate", response_model=PriceTable)
def activate_price_list(list_id: str) -> PriceTable:
    table = price_lists.activate(settings, list_id)
    if table is None:
        raise HTTPException(404, "No such price list.")
    return table


@app.delete("/api/price-lists/{list_id}")
def delete_price_list(list_id: str) -> dict[str, bool]:
    if not price_lists.forget(settings, list_id):
        raise HTTPException(404, "No such price list, or it can't be deleted.")
    return {"deleted": True}


@app.get("/api/history", response_model=list[HistoryEntry])
def list_history() -> list[HistoryEntry]:
    return history.list()


@app.get("/api/history/{entry_id}", response_model=AnalysisResult | RoomResult)
def get_history(entry_id: str) -> AnalysisResult | RoomResult:
    result = history.get(entry_id)
    if result is None:
        raise HTTPException(404, "Not found.")
    return result


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=120)


@app.patch("/api/history/{entry_id}")
def rename_history(entry_id: str, body: Rename) -> dict[str, bool]:
    if not history.rename(entry_id, body.title.strip()):
        raise HTTPException(404, "Not found.")
    return {"renamed": True}


@app.delete("/api/history")
def clear_history() -> dict[str, int]:
    return {"deleted": history.clear()}


@app.delete("/api/history/{entry_id}")
def delete_history(entry_id: str) -> dict[str, bool]:
    if not history.delete(entry_id):
        raise HTTPException(404, "Not found.")
    return {"deleted": True}


@app.get("/api/samples")
def list_samples() -> list[str]:
    if not settings.samples_dir.exists():
        return []
    return sorted(p.name for p in settings.samples_dir.glob("*.jpg"))


@app.get("/api/samples/{name}")
def get_sample(name: str) -> FileResponse:
    path = (settings.samples_dir / name).resolve()
    if path.parent != settings.samples_dir.resolve() or not path.is_file():
        raise HTTPException(404, "Not found.")
    return FileResponse(path, media_type="image/jpeg")
