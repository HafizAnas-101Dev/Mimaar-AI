# Mimaar AI

AI site analyzer for construction and real estate. Upload one site photo, or several photos of
the same room. You get a segmented overlay and a rough quantity, cost and defect report in
English, Urdu or Arabic.

Built for the Meta Global AI Developer Hackathon. *Mimaar* is Arabic and Urdu for "architect" or "builder".

## Quick start (Windows)

```powershell
.\start.ps1 -Mock   # any laptop: demo geometry and template reports, no GPU, models or key
.\start.ps1         # full app on Meta's open weights (after the one-time setup below)
```

The script installs dependencies on first run, starts the servers and opens http://localhost:5173.
In the app choose **A whole room → Or try an example room** for a complete six-photo room.

## How it works

```mermaid
flowchart LR
    A[Site photo(s)] --> B[Perceive<br/>SAM 3 masks<br/>or Muse boxes]
    B --> C[Measure<br/>counts, areas,<br/>m² from a known door height]
    C --> D[Price<br/>editable SAR / PKR / USD table<br/>× finish level]
    C --> E[Reason<br/>Muse Glimmer / Muse Spark:<br/>photo + measurements → strict JSON report]
    D --> E
    E --> F[Present<br/>mask layers, quantities, defects,<br/>confidence + trace, PDF]
```

1. **Perceive.** Element and defect detection. `PERCEIVER=sam_local` runs SAM 3 masks on this PC, `sam` uses SAM 3.1 over the Meta Model API, `muse` uses grounding boxes from the reasoning model, and `mock` uses synthetic geometry.
2. **Measure.** Code turns masks into counts and pixel areas. With a known door or window height it also gives square metres. Doors and windows are cut out of wall area.
3. **Price.** Code computes the cost range from the active price list: the built-in defaults in [backend/data/default-prices.json](backend/data/default-prices.json), or a vendor's file imported in the app. Totals are rounded like estimates and split into labour and materials when the list gives labour shares.
4. **Reason.** Muse Glimmer (local) or Muse Spark (API) reads the photo plus the measurements and writes the report in the chosen language. Code then overwrites every number, so the model can't change counts, areas, costs or the disclaimer. Invalid output gets one repair retry, then a measurement-only fallback.
5. **Present.** The overlay has a layer per element type that you can toggle. The report shows confidence labels and a "Why this?" trace per finding. Past analyses are kept in local history. You can also export to PDF or copy the JSON.

Every report is an estimate, not an engineering or safety assessment.

### Meta models used

Mimaar runs on Meta's **open-weight models on your own PC** (the default for this submission, since
the Meta Model API is not available in our region), or on the Meta Model API with a key.

| Model | Where it runs | Role |
|---|---|---|
| **SAM 3** (`facebook/sam3`) | This PC, via transformers | Pixel masks for walls, floor, ceiling, openings, fixtures, defects and furniture, in about a second |
| **Muse Glimmer 30B** (`unsloth/Muse-Glimmer-30B-GGUF`, 4-bit, with its DFlash draft model) | This PC, via llama.cpp | Reads the photos and measurements, judges the defects, writes the report in English, Urdu or Arabic |
| `muse-spark-1.3` | Meta Model API | Same role as Glimmer, when an API key is available |
| `sam-3.1` | Meta Model API | Same role as SAM 3 (`PERCEIVER=sam`) |

## Features

- Single-photo analysis, or a combined room report from 2–6 photos in labelled slots (floor, ceiling, walls 1–4)
- Four example rooms (living room, bedroom, sitting room, empty room), six photos each, one click to load
- Phone photos in any common format, including iPhone HEIC; photos that aren't of a room are refused with a clear message
- Instant report: outlines, m², defects and cost appear in seconds (SAM 3 + code); the Muse model's written report replaces the summary when it is ready
- No tape measure needed: a standard door, a typical room size and ceiling height fill the gaps, flagged as estimates with a wider range
- Walls from room size × ceiling height, so furniture in the photo does not change the wall area; a warning when furniture hides a wall
- Rooms that aren't rectangles: enter the floor area and total wall length instead
- Wardrobe and cabinet doors, window panes and edge slivers of neighbouring walls are not counted; split or duplicate defect patches are merged
- Room defects name their photo ("Wall 2 · upper right of the photo")
- Toggleable mask layers per element type
- Quantities with m² (when a scale reference is given), confidence labels, per-finding evidence trace
- Defects with severity, location and reason
- Work-scope picker before analysis: choose which finishing work and repairs (crack, damp, peeling paint) to price; replacing doors, windows and lights is opt-in; everything detected is still reported
- Cost range by currency (SAR, PKR, USD) and finish level (basic, standard, premium), with line items
- In-app price table editor with saved price lists to switch between, plus vendor price files: a contractor imports their own rates, logo and contact details, and every report and PDF says "Quote prepared with rates from …" (template and two sample vendors in [docs/price-tables](docs/price-tables))
- Report language: English, Urdu, Arabic (right-to-left layout); an open report can be rewritten in another language without analysing again
- Correct the AI: tap a wrong door, window or defect on the photo to remove it, change counts with − and +, type in an area, or add a missed item; the cost recalculates and every edit can be undone
- Click a defect to jump to it on its photo; retry a failed write-up; a status light shows whether the AI writer is ready
- Quotation-ready PDF: quote number, validity date, labour and materials split, vendor branding and terms
- Phone friendly: a camera button in each photo slot, tips for each shot, remembered settings, undo after clearing
- History of past analyses (SQLite) with rename, search, filters and clear-all; export to PDF (print), copy JSON
- Synthetic sample photos, mock mode with no API key, cached model responses

## Run locally

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
cp .env.example .env                                      # add MODEL_API_KEY for live mode
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Frontend (Node 18+):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Run on open weights (no API key)

Tested on Windows 11 with an RTX 5060 (8 GB) and 32 GB RAM. About 26 GB of downloads (Glimmer
15.9 GB, its vision part 2.1 GB and draft model 1.6 GB, SAM 3 3.4 GB, llama.cpp and PyTorch), kept
in `backend/models/` and the virtualenv (ignored by git).

```bash
cd backend
.venv/Scripts/python -m scripts.setup_local_models          # Muse Glimmer 4-bit + llama.cpp CUDA build
.venv/Scripts/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130
.venv/Scripts/python -m pip install "transformers>=5" accelerate huggingface_hub
```

SAM 3 is gated: request access at https://huggingface.co/facebook/sam3, put a read token in
`backend/.env` as `HF_TOKEN=`, then run `python -m scripts.setup_local_models --sam`.

Set `MODEL_BACKEND=local` in `backend/.env` (and `PERCEIVER=sam_local` once SAM 3 is downloaded),
start the model server, then the backend:

```bash
models/llama.cpp/llama-server.exe -m models/glimmer/Muse-Glimmer-30B-UD-Q4_K_XL.gguf --mmproj models/glimmer/mmproj-Muse-Glimmer-30B-Q8_0.gguf --alias muse-glimmer-30b --port 8080 -c 16384 --fit on --fit-target 3600 --parallel 1 -md models/glimmer/dflash-kquant.gguf --spec-type draft-dflash --spec-draft-n-max 8
```

What makes it usable on an 8 GB GPU, measured on the sample photos:

| Step | Time |
|---|---|
| SAM 3, all 10 concepts on one photo | about 1 s (first run loads the model: +8 s) |
| Instant report (single wall / 4-photo room) | 3 s / 9 s |
| Muse Glimmer write-up, English single wall | about 50 s |
| Muse Glimmer write-up, Arabic or Urdu, or a 4-photo room | 75–110 s |

- The report is returned at once (`defer_reasoning`), and `POST /api/reason/{id}` has Glimmer write
  it; the page swaps the text in when it arrives.
- The answer is pre-filled with `{`, which makes Glimmer skip its hidden thinking (4× fewer tokens).
- Glimmer writes only the scene, defects and a 2–3 sentence summary; code fills in every number.
- SAM 3 sits in system memory and moves onto the GPU only while it runs, leaving the GPU to Glimmer.
- The DFlash draft model roughly doubles Glimmer's writing speed in English (less in Arabic and Urdu).

### Modes

| `.env` | Behaviour |
|---|---|
| no `MODEL_API_KEY` | Mock mode: synthetic geometry and a measurement-only report. No model calls. |
| key + `PERCEIVER=muse` (default) | Muse Spark does perception (boxes) and reasoning. |
| key + `PERCEIVER=sam` | SAM 3.1 masks + Muse Spark reasoning. |
| `MODEL_BACKEND=local` + `PERCEIVER=muse` | Muse Glimmer on this PC does perception (boxes) and reasoning. No key, no cloud. |
| `MODEL_BACKEND=local` + `PERCEIVER=sam_local` | SAM 3 masks + Muse Glimmer reasoning, all on this PC. |

## Accuracy

**Real photos.** Tested on 3 real Pakistani property-listing photos of finished rooms (not
included in this repository, for copyright reasons), with SAM 3 and Muse Glimmer running locally:

| | Detected correctly |
|---|---|
| Doors | 4 of 4 |
| Windows | 4 of 4 |
| Floors and ceilings | 6 of 6 |
| Walls | 6 of 8 visible walls (one corner seen as a single wall; one wall almost entirely covered by its door) |
| False defects on these clean rooms | 0 |
| Instant report (outlines, m², cost) | 2–4 seconds per photo |

Overall 20 of 22 items correct. Wall counts don't change the price when the room size (or an
estimate) is used, because walls are then priced from the room's perimeter. These photos also
drove fixes for edge slivers, two-tone door panels, window panes taken for doors, open double
doors, and the next room seen through a doorway.

*Square metres are not yet checked against a tape measure: listing photos come without
measurements.*

**Tests** (`python -m pytest`, 84 tests): measurement and pricing rules, the code-owns-the-numbers
contract, deferred reports, room combination, defect merging, wardrobe, window and doorway
filtering, edits and undo, price lists, language changes, HEIC upload and refusal of non-room
photos.

## Built during the hackathon

Everything in this repository was written during the Meta Global AI Developer Hackathon
(building period Oct 27 – Nov 4, 2026); the first commit is from Oct 27. Nothing was carried over
from an earlier product. That includes the SAM 3 + Muse Glimmer pipeline, measurement, pricing,
the bilingual report, the web app, the sample rooms and every test.

## Credits and licences

| Component | Source | Licence |
|---|---|---|
| SAM 3 | Meta, [`facebook/sam3`](https://huggingface.co/facebook/sam3) | SAM License (accepted on Hugging Face) |
| Muse Glimmer 30B | Meta open weights, [`meta-models/Muse-Glimmer-30B`](https://huggingface.co/meta-models/Muse-Glimmer-30B); 4-bit GGUF and DFlash draft model by [Unsloth](https://huggingface.co/unsloth/Muse-Glimmer-30B-GGUF) | Apache-2.0 |
| llama.cpp | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT |
| Sample room photos | Generated for this project; no real people or addresses | — |
| Mimaar AI code | This repository | [MIT](LICENSE) |

Model weights are downloaded by `scripts/setup_local_models.py`, not stored in this repository.

## Scripts (run from `backend/`)

| Command | Purpose |
|---|---|
| `python -m scripts.probe_api photo.jpg` | Phase 0: list models, save raw SAM/Muse responses to `fixtures/` |
| `python -m scripts.evaluate photos/ --labels labels.json --runs 3 --scale door:2.1` | Phase 7: JSON validity, consistency, defect precision/recall, latency → `eval/results/` |
| `python -m scripts.make_samples` | Regenerate the synthetic sample photos |
| `python -m scripts.add_vendor_logo file.json logo.png` | Embed a vendor's logo in their price file |
| `python -m scripts.setup_local_models [--sam]` | Download Muse Glimmer, llama.cpp and (optionally) SAM 3 into `models/` |
| `python -m pytest` | Backend tests |

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Mode, backend (meta/local), perceiver and report model |
| POST | `/api/analyze` | One photo (multipart `file` + options) |
| POST | `/api/analyze-room` | 2–6 photos (`files`) combined into one report |
| POST | `/api/reason/{id}` | Have the Muse model write the report of a result returned with `defer_reasoning=true` |
| GET/PUT | `/api/prices` | Read or replace the price table |
| GET/DELETE | `/api/history[/{id}]` | Past analyses |
| GET | `/api/samples[/{name}]` | Sample photos |

Options: `scale_element` (`door`/`window`), `scale_height_m`, `language` (`en`/`ur`/`ar`),
`currency`, `finish` (`basic`/`standard`/`premium`), `scope`, `room_length_m`, `room_width_m`,
`ceiling_height_m`, `wall_width_m` (single wall), `estimate` + `room_type` (no measurements),
`defer_reasoning` (return the instant report, write it afterwards).

## Limitations

- Areas from photos are rough: perspective distorts them, and front-on photos work best.
- Square metres need a scale reference. With Muse perception, areas come from boxes, not masks.
- Room reports add doors and windows across photos. Overlapping photos can double count them.
- Prices are placeholders. Replace them with local rates before relying on them.
- The SAM 3.1 response format is unpublished. The parser accepts PNG, RLE, polygon and box encodings until access confirms the real one.

## Data

Use only your own, stock or consented photos. Blur faces and licence plates. Do not upload
client data. Photos sent in live mode go to the Meta Model API.

See [docs/AUDIENCE.md](docs/AUDIENCE.md) (target audience and consumer story),
[docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md), [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)
and [docs/SUBMISSION.md](docs/SUBMISSION.md).
