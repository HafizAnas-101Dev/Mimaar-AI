"""Phase 0 feasibility probe.

Lists models, runs SAM 3.1 and Muse Spark on one photo, and saves the raw responses
to fixtures/ so perceive.py can be checked against the real output shape.

    python -m scripts.probe_api path/to/photo.jpg
"""
import io
import json
import sys
from pathlib import Path

import httpx
from PIL import Image

from app.cache import ResponseCache
from app.config import BACKEND_DIR, get_settings
from app.meta_client import MetaClient, image_data_url
from app.perceive import parse_sam_response


def main(photo: Path) -> None:
    settings = get_settings()
    if not settings.api_key:
        sys.exit("Set MODEL_API_KEY in backend/.env first.")
    fixtures = BACKEND_DIR / "fixtures"
    fixtures.mkdir(exist_ok=True)

    models = httpx.get(
        f"{settings.base_url}/models", headers={"Authorization": f"Bearer {settings.api_key}"}, timeout=30
    ).json()
    ids = [m.get("id") for m in models.get("data", [])]
    print("Models:", ids)
    for wanted in (settings.sam_model, settings.muse_model):
        print(f"  {wanted}: {'available' if wanted in ids else 'MISSING'}")

    img = Image.open(photo).convert("RGB")
    img.thumbnail((settings.max_image_side, settings.max_image_side))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()

    client = MetaClient(settings, ResponseCache(settings.cache_dir))
    for phrase in ("wall", "floor", "door", "crack in wall"):
        raw = client.segment(png, phrase)
        out = fixtures / f"sam_{phrase.replace(' ', '_')}.json"
        out.write_text(json.dumps(raw, indent=2)[:2_000_000], encoding="utf-8")
        found = parse_sam_response(raw, phrase, *img.size)
        print(f"SAM '{phrase}': parsed {len(found)} detection(s); raw saved to {out.name}")

    text = client.chat(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": 'Describe this site photo as JSON: {"scene": "...", "elements": [...]}'},
                    {"type": "image_url", "image_url": {"url": image_data_url(png)}},
                ],
            }
        ]
    )
    (fixtures / "muse_probe.txt").write_text(text, encoding="utf-8")
    print("Muse reply:", text[:500])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
