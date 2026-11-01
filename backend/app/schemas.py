"""Pydantic models for measurements, prices and the report Muse Spark must return."""
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator

ElementType = Literal["wall", "floor", "ceiling", "door", "window", "fixture"]
DefectKind = Literal["crack", "damp", "peeling", "misalignment", "other"]
Severity = Literal["low", "medium", "high"]
Language = Literal["en", "ur", "ar"]
Finish = Literal["basic", "standard", "premium"]
RepairType = Literal["crack", "damp", "peeling"]
# Which surface a photo shows; only that surface's elements are counted from it (defects always are).
PhotoRole = Literal["floor", "ceiling", "wall"]
# Everything a customer can choose to have priced: finishing work per element, plus defect repairs.
WorkItem = Literal["wall", "floor", "ceiling", "door", "window", "fixture", "crack", "damp", "peeling"]
ALL_WORK: tuple[str, ...] = ("wall", "floor", "ceiling", "door", "window", "fixture", "crack", "damp", "peeling")
# Typical room sizes for customers without a tape measure; see measure.ROOM_PRESETS.
RoomType = Literal["bedroom", "master_bedroom", "living", "kitchen", "bathroom"]
AreaSource = Literal["scale", "dimensions"]

# Whether the Muse model has written this report: "none" (mock mode), "pending" (the instant
# code-written report is shown while the model writes), "done", or "failed" (code report kept).
ReasoningState = Literal["none", "pending", "done", "failed"]

DISCLAIMER = "Estimate only; not an engineering or safety assessment."


def confidence_label(value: float) -> Literal["high", "medium", "low"]:
    return "high" if value >= 0.75 else "medium" if value >= 0.5 else "low"


class Scale(BaseModel):
    method: Literal["user_reference", "assumed_door", "none"] = "none"
    metres_per_pixel: float | None = None
    reference: str | None = None


class ElementMeasurement(BaseModel):
    type: ElementType
    count: int
    pixel_area: int
    image_share: float = Field(description="Fraction of the image covered, 0 to 1")
    area_m2: float | None = None
    mean_score: float
    boxes: list[list[int]] = Field(default_factory=list)
    source: str = "mock"
    area_source: AreaSource | None = None
    estimated: bool = Field(False, description="Area rests on a typical size, not a measurement")
    hidden_share: float | None = Field(None, description="Largest share of one instance covered by furniture, 0 to 1")
    edited: bool = Field(False, description="Count or area changed by the user")


class DefectCandidate(BaseModel):
    kind: DefectKind
    pixel_area: int
    image_share: float
    score: float
    box: list[int]
    source: str = "mock"
    photo: int | None = None


class Measurements(BaseModel):
    image_width: int
    image_height: int
    scale: Scale
    elements: list[ElementMeasurement]
    defect_candidates: list[DefectCandidate]
    room_size_m: list[float] | None = Field(None, description="[length, width] entered or assumed")
    ceiling_height_m: float | None = None
    floor_area_m2: float | None = Field(None, description="Entered for a room that isn't a rectangle")
    perimeter_m: float | None = Field(None, description="Total wall length, entered for a room that isn't a rectangle")
    estimate_notes: list[str] = Field(default_factory=list, description="Typical sizes used in place of measurements")
    photo_roles: list[str | None] | None = Field(None, description="Room slot of each photo, so defects can name it")


class Evidence(BaseModel):
    """Decision trace: where a finding came from, so a user can check it."""

    source: str
    detector_score: float
    image_share: float
    boxes: list[list[int]] = Field(default_factory=list)
    photo: int | None = None
    area_basis: AreaSource | None = None
    estimated: bool = False
    rule: str


class ReportElement(BaseModel):
    type: ElementType
    count: int = Field(ge=0)
    area_m2: float | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: Evidence | None = None
    edited: bool = False

    @computed_field
    @property
    def confidence_label(self) -> str:
        return confidence_label(self.confidence)


class ReportDefect(BaseModel):
    kind: DefectKind
    location: str
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    why: str
    candidate: int | None = Field(None, description="Index into measurements.defect_candidates")
    evidence: Evidence | None = None

    @computed_field
    @property
    def confidence_label(self) -> str:
        return confidence_label(self.confidence)


# Work priced per square metre; everything else is priced per item.
AREA_WORK = ("wall", "floor", "ceiling")
# A vendor's logo travels inside the price file as a data URL, so the file is all a vendor shares.
MAX_LOGO_CHARS = 400_000


class Vendor(BaseModel):
    """Who the rates belong to. Shown on every report and PDF priced with them."""

    name: str = Field(min_length=1, max_length=120)
    tagline: str = Field("", max_length=160)
    logo: str | None = Field(None, description="data:image/png, jpeg, webp or svg+xml URL, up to ~300 KB")
    phone: str = Field("", max_length=60)
    email: str = Field("", max_length=120)
    website: str = Field("", max_length=200)
    address: str = Field("", max_length=240)
    city: str = Field("", max_length=80)
    valid_until: str = Field("", max_length=40, description="Until when the quoted rates hold, as written by the vendor")
    terms: str = Field("", max_length=600, description="e.g. what the rates include, VAT, payment terms")

    @field_validator("logo")
    @classmethod
    def _logo(cls, value: str | None) -> str | None:
        if not value:
            return None
        if not value.startswith(("data:image/png", "data:image/jpeg", "data:image/webp", "data:image/svg+xml")):
            raise ValueError("logo must be a PNG, JPEG, WebP or SVG image embedded as a data URL")
        if len(value) > MAX_LOGO_CHARS:
            raise ValueError("logo is too large; use an image under 300 KB")
        return value


class CostLine(BaseModel):
    item: str
    quantity: float
    unit: str
    low: float
    high: float
    estimated: bool = False
    labour_share: float | None = None
    edited: bool = Field(False, description="Quantity changed by the user")


class CostEstimate(BaseModel):
    currency: str
    finish: Finish = "standard"
    scope: list[str] = Field(default_factory=lambda: list(ALL_WORK), description="Work items the customer asked to price")
    low: float | None = None
    high: float | None = None
    estimated: bool = Field(False, description="Some quantities rest on typical sizes, so the range is wider")
    sample_rates: bool = Field(False, description="Priced with the shipped placeholder rates, not the user's own")
    labour_low: float | None = Field(None, description="Labour part of the total, when every line has a labour share")
    labour_high: float | None = None
    materials_low: float | None = None
    materials_high: float | None = None
    vendor: Vendor | None = Field(None, description="Whose rates priced this estimate")
    lines: list[CostLine] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class Report(BaseModel):
    scene: Literal["interior", "exterior", "unknown"]
    scale: Scale
    elements: list[ReportElement]
    defects: list[ReportDefect]
    cost_estimate: CostEstimate
    summary: str
    language: Language = "en"
    disclaimer: str = DISCLAIMER


class Edits(BaseModel):
    """Corrections the user made to a result. Every number is recomputed from the original
    measurements plus these, so edits can be changed or undone at any time."""

    counts: dict[ElementType, int] = Field(default_factory=dict, description="Count per element type, set by the user")
    areas: dict[ElementType, float] = Field(default_factory=dict, description="m² per element type, set by the user")
    removed: dict[str, dict[str, list[list[int]]]] = Field(
        default_factory=dict, description="Photo index -> element type or defect kind -> boxes tapped away on the overlay"
    )
    # The report as written before any edit, so edits can always be undone.
    unedited_elements: list[dict] | None = None
    unedited_defects: list[dict] | None = None


class Layer(BaseModel):
    type: str
    color: str
    png_base64: str


class AnalysisOptions(BaseModel):
    scale_element: Literal["door", "window"] | None = None
    scale_height_m: float | None = None
    language: Language = "en"
    currency: str | None = None
    finish: Finish = "standard"
    scope: list[WorkItem] = Field(default_factory=lambda: list(ALL_WORK), description="Work items to include in the cost")
    room_length_m: float | None = None
    room_width_m: float | None = None
    room_floor_area_m2: float | None = Field(None, description="Instead of length x width, for a room that isn't a rectangle")
    room_perimeter_m: float | None = Field(None, description="Total length of all walls, for a room that isn't a rectangle")
    ceiling_height_m: float | None = None
    wall_width_m: float | None = Field(None, description="Width of the single wall in wall mode")
    estimate: bool = Field(False, description="No tape measure: fill gaps with a standard door and typical sizes")
    room_type: RoomType | None = None


class AnalysisResult(BaseModel):
    id: str
    mode: Literal["live", "mock"]
    perceiver: str
    filename: str = ""
    role: PhotoRole | None = None
    options: AnalysisOptions
    report: Report
    measurements: Measurements
    image_png_base64: str
    layers: list[Layer]
    warnings: list[str] = Field(default_factory=list)
    reasoning: ReasoningState = "none"
    edits: Edits = Field(default_factory=Edits)


class RoomResult(BaseModel):
    """Several photos of one room combined into a single report."""

    id: str
    mode: Literal["live", "mock"]
    options: AnalysisOptions
    photos: list[AnalysisResult]
    report: Report
    warnings: list[str] = Field(default_factory=list)
    reasoning: ReasoningState = "none"
    measurements: Measurements | None = Field(None, description="Combined measurements, kept so the report can be written later")
    edits: Edits = Field(default_factory=Edits)


class PriceItem(BaseModel):
    label: str
    unit: Literal["m2", "each"]
    low: float = Field(ge=0)
    high: float = Field(ge=0)
    labour_share: float | None = Field(None, ge=0, le=1, description="Share of the rate that is labour; the rest is materials")


class PriceTable(BaseModel):
    default_currency: str
    note: str = ""
    vendor: Vendor | None = None
    list_id: str | None = Field(None, description="Which saved price list this is; set by the app")
    sample: bool = Field(False, description="True while these are the shipped placeholder rates")
    finish_multipliers: dict[Finish, float]
    tables: dict[str, dict[WorkItem, PriceItem]]


class HistoryEntry(BaseModel):
    id: str
    kind: Literal["photo", "room"]
    created_at: str
    title: str
    summary: str
    currency: str
    low: float | None
    high: float | None
