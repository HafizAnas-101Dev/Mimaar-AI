"""Download what Mimaar needs to run on Meta's open-weight models, on this PC.

    python -m scripts.setup_local_models            # Muse Glimmer + llama.cpp (Windows, CUDA)
    python -m scripts.setup_local_models --sam      # also fetch SAM 3 (needs HF_TOKEN with access)

Everything lands in backend/models/, which git ignores. Downloads resume if interrupted.
PyTorch and transformers for SAM 3 are installed separately; see README "Run on open weights".
"""
import argparse
import io
import os
import zipfile
from pathlib import Path

import httpx

from app.config import BACKEND_DIR

MODELS = BACKEND_DIR / "models"
GLIMMER_REPO = "https://huggingface.co/unsloth/Muse-Glimmer-30B-GGUF/resolve/main"
# Model, vision projector, and the DFlash draft model used for faster (speculative) decoding.
GLIMMER_FILES = ("Muse-Glimmer-30B-UD-Q4_K_XL.gguf", "mmproj-Muse-Glimmer-30B-Q8_0.gguf", "dflash-kquant.gguf")
LLAMA_BUILD = "b12029"
LLAMA_ZIPS = (f"llama-{LLAMA_BUILD}-bin-win-cuda-13.4-x64.zip", "cudart-llama-bin-win-cuda-13.4-x64.zip")


def download(url: str, dest: Path) -> None:
    """Stream to disk, resuming a partial file."""
    done = dest.stat().st_size if dest.exists() else 0
    headers = {"Range": f"bytes={done}-"} if done else {}
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60) as r:
        if r.status_code == 416:  # already complete
            return
        r.raise_for_status()
        mode = "ab" if r.status_code == 206 else "wb"
        total = done + int(r.headers.get("content-length", 0)) if mode == "ab" else int(r.headers.get("content-length", 0))
        with open(dest, mode) as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                done = f.tell()
                print(f"\r{dest.name}: {done / 1e9:.2f} / {total / 1e9:.2f} GB", end="", flush=True)
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sam", action="store_true", help="also download SAM 3 (gated; needs HF_TOKEN)")
    args = parser.parse_args()

    glimmer = MODELS / "glimmer"
    glimmer.mkdir(parents=True, exist_ok=True)
    for name in GLIMMER_FILES:
        download(f"{GLIMMER_REPO}/{name}", glimmer / name)

    llama = MODELS / "llama.cpp"
    if not (llama / "llama-server.exe").exists():
        llama.mkdir(parents=True, exist_ok=True)
        for name in LLAMA_ZIPS:
            data = httpx.get(
                f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_BUILD}/{name}",
                follow_redirects=True,
                timeout=600,
            ).content
            zipfile.ZipFile(io.BytesIO(data)).extractall(llama)
            print(f"unpacked {name}")

    if args.sam:
        if not os.getenv("HF_TOKEN"):
            raise SystemExit("Set HF_TOKEN in backend/.env after facebook/sam3 grants you access.")
        from huggingface_hub import snapshot_download

        snapshot_download("facebook/sam3", cache_dir=MODELS / "hf", allow_patterns=["*.json", "*.safetensors", "*.txt"])
        print("SAM 3 ready")


if __name__ == "__main__":
    main()
