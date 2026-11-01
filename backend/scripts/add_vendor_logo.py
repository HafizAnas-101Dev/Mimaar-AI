"""Embed a vendor's logo in their Mimaar price file, so the one file is all they share.

    python -m scripts.add_vendor_logo path/to/price-file.json path/to/logo.png

PNG, JPEG and WebP logos are shrunk to 256 px and stored as PNG; SVG logos are stored as they are.
"""
import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

from app.schemas import MAX_LOGO_CHARS, PriceTable

LOGO_SIDE = 256


def logo_data_url(path: Path) -> str:
    if path.suffix.lower() == ".svg":
        return "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode()
    img = Image.open(path)
    img.thumbnail((LOGO_SIDE, LOGO_SIDE))
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main(price_file: Path, logo: Path) -> None:
    data = json.loads(price_file.read_text(encoding="utf-8"))
    url = logo_data_url(logo)
    if len(url) > MAX_LOGO_CHARS:
        sys.exit("The logo is too large even after shrinking; use a simpler image.")
    data.setdefault("vendor", {})["logo"] = url
    if not data["vendor"].get("name"):
        sys.exit("Fill in vendor.name in the price file first.")
    PriceTable.model_validate(data)  # same checks as Mimaar's import
    price_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Logo added to {price_file.name} ({len(url) // 1024} KB). Import it in Mimaar: Price table > Import.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
