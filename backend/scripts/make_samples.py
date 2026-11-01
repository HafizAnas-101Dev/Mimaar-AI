"""Draw synthetic room photos for demos and smoke tests (no real site or client data).

    python -m scripts.make_samples
"""
import random

from PIL import Image, ImageDraw, ImageFilter

from app.config import BACKEND_DIR

W, H = 1200, 800


def _room(seed: int, wall: tuple, floor: tuple, defects: bool) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (W, H), wall)
    d = ImageDraw.Draw(img)
    # Ceiling band and floor in simple one-point perspective
    d.polygon([(0, 0), (W, 0), (W - 160, 90), (160, 90)], fill=tuple(min(255, c + 18) for c in wall))
    d.polygon([(160, 560), (W - 160, 560), (W, H), (0, H)], fill=floor)
    for x in range(160, W - 160, 110):  # tile joints
        d.line([(x, 560), (x + (x - W / 2) * 0.35, H)], fill=tuple(c - 25 for c in floor), width=2)
    d.line([(160, 90), (160, 560)], fill=tuple(c - 30 for c in wall), width=3)
    d.line([(W - 160, 90), (W - 160, 560)], fill=tuple(c - 30 for c in wall), width=3)
    # Door, window and a ceiling light
    d.rectangle([250, 250, 400, 560], fill=(120, 80, 52), outline=(70, 45, 30), width=4)
    d.ellipse([375, 400, 387, 412], fill=(210, 180, 90))
    d.rectangle([650, 200, 930, 380], fill=(160, 200, 225), outline=(240, 240, 240), width=10)
    d.line([(790, 200), (790, 380)], fill=(240, 240, 240), width=6)
    d.ellipse([560, 25, 640, 60], fill=(250, 240, 200))
    if defects:
        x, y = 520, 130
        for _ in range(9):  # crack
            nx, ny = x + rng.randint(-12, 14), y + rng.randint(18, 30)
            d.line([(x, y), (nx, ny)], fill=(90, 85, 80), width=3)
            x, y = nx, ny
        stain = Image.new("L", (W, H), 0)
        ImageDraw.Draw(stain).ellipse([960, 380, 1080, 540], fill=150)
        stain = stain.filter(ImageFilter.GaussianBlur(25))
        img.paste((150, 140, 110), mask=stain)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def main() -> None:
    out = BACKEND_DIR / "samples"
    out.mkdir(exist_ok=True)
    samples = {
        "villa-room-clean.jpg": _room(1, (236, 228, 214), (196, 180, 150), defects=False),
        "villa-room-defects.jpg": _room(2, (226, 222, 210), (170, 160, 150), defects=True),
        "apartment-room.jpg": _room(3, (214, 224, 230), (150, 120, 95), defects=True),
    }
    for name, img in samples.items():
        img.save(out / name, quality=88)
        print("wrote", out / name)


if __name__ == "__main__":
    main()
