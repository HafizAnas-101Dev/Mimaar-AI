import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

# mock: synthetic geometry; muse: grounding boxes from the reasoning model; sam: SAM 3.1 over the
# Meta Model API; sam_local: SAM 3 open weights run in this process.
PERCEIVERS = ("mock", "muse", "sam", "sam_local")
BACKENDS = ("meta", "local")


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    sam_model: str
    muse_model: str
    mock: bool  # True when no model can be called at all
    perceiver: str  # mock | muse | sam | sam_local
    max_image_side: int
    cache_dir: Path
    data_dir: Path
    prices_path: Path
    samples_dir: Path
    backend: str = "meta"  # meta: Meta Model API; local: open weights served on this PC
    local_sam_model: str = "facebook/sam3"
    models_dir: Path = BACKEND_DIR / "models"
    local_reasoning: str = "none"  # Muse Glimmer reasoning strength: none | low | medium | high
    timeout_s: float = 90.0

    @property
    def reasoner(self) -> str:
        """Human-readable name of the model that writes the report."""
        return "Muse Glimmer" if self.backend == "local" else "Muse Spark"


def get_settings() -> Settings:
    backend = os.getenv("MODEL_BACKEND", "meta").lower()
    if backend not in BACKENDS:
        raise ValueError(f"MODEL_BACKEND must be one of {BACKENDS}")
    local = backend == "local"
    api_key = os.getenv("MODEL_API_KEY", "").strip()
    # The local server needs no key; the Meta Model API does.
    mock = os.getenv("MIMAAR_MOCK", "false").lower() == "true" or (not local and not api_key)
    perceiver = os.getenv("PERCEIVER", "muse").lower()
    if perceiver not in PERCEIVERS:
        raise ValueError(f"PERCEIVER must be one of {PERCEIVERS}")
    data_dir = Path(os.getenv("MIMAAR_DATA_DIR", BACKEND_DIR / ".data"))
    if local:
        base_url = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:8080/v1")
        muse_model = os.getenv("LOCAL_LLM_MODEL", "muse-glimmer-30b")
    else:
        base_url = os.getenv("META_BASE_URL", "https://api.meta.ai/v1")
        muse_model = os.getenv("MUSE_MODEL", "muse-spark-1.3")
    return Settings(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        sam_model=os.getenv("SAM_MODEL", "sam-3.1"),
        muse_model=muse_model,
        mock=mock,
        perceiver="mock" if mock else perceiver,
        max_image_side=int(os.getenv("MAX_IMAGE_SIDE", "1280")),
        cache_dir=Path(os.getenv("MIMAAR_CACHE_DIR", BACKEND_DIR / ".cache")),
        data_dir=data_dir,
        # The live, user-chosen rates; private, so imported vendor files never end up in git.
        prices_path=Path(os.getenv("MIMAAR_PRICES", data_dir / "prices.json")),
        samples_dir=BACKEND_DIR / "samples",
        backend=backend,
        local_sam_model=os.getenv("LOCAL_SAM_MODEL", "facebook/sam3"),
        local_reasoning=os.getenv("LOCAL_REASONING", "none"),
        # A 30B model on a consumer GPU can take minutes per report.
        timeout_s=float(os.getenv("MODEL_TIMEOUT_S", "900" if local else "90")),
    )
