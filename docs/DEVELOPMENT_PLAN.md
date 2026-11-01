# Mimaar AI — Development Plan

Mimaar AI turns a construction site photo into a segmented overlay plus a structured
quantity, cost and defect report. It chains **SAM 3.1** (perception) into **Muse Spark**
(reasoning) through the Meta Model API, built for the Meta Global AI Developer Hackathon.

This plan is ordered by phase, not by date. Each phase has a goal, the work, and an
acceptance check that must pass before moving on. If time runs short, use the cut order
at the end.

## Guiding principles

- **Chain, not two calls.** SAM output is measured by code and fed into Muse Spark as
  structured input. This is the "beyond a basic integration" story (25% of judging).
- **Demo first.** Every phase leaves the app in a demoable state. Cache every model
  response so the demo never depends on a live API call.
- **Honest numbers.** Areas are pixel proxies until the user gives a scale reference.
  Every finding carries a confidence and a reason. Always show the disclaimer.
- **Mock mode.** The whole pipeline runs without an API key using fixture responses, so
  frontend and tests never block on credits or API access.

## Architecture

```
 Browser (React + Vite)
   │  upload photo, scale ref, finish type, language
   ▼
 FastAPI backend ──► cache (SQLite / files, keyed by image hash + params)
   │
   ├─ 1. Perceive  sam-3.1 via POST /v1/responses, one noun-phrase prompt per element type
   ├─ 2. Measure   masks → pixel areas, counts, bboxes; apply metres-per-pixel if given
   ├─ 3. Reason    muse-spark-1.3: image + measurement JSON + price table → strict JSON report
   └─ 4. Present   overlay PNG / mask polygons + validated report JSON
```

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TypeScript |
| Backend | FastAPI, Pydantic v2, Python 3.11+ |
| Model access | OpenAI SDK pointed at `https://api.meta.ai/v1`, key in `MODEL_API_KEY` |
| Perception | `sam-3.1` |
| Reasoning | `muse-spark-1.3` (fallback `muse-spark-1.2`) |
| Imaging | Pillow + NumPy (mask decoding, overlay rendering) |
| Storage | Local file cache + SQLite for history |
| Tests | pytest (backend), Vitest (frontend, light) |

### Repository layout

```
backend/
  app/
    main.py          FastAPI app and routes
    config.py        settings (env vars, mock mode)
    schemas.py       Pydantic report + measurement models
    meta_client.py   thin wrapper over the Meta Model API
    perceive.py      SAM 3.1 calls and mask parsing
    measure.py       masks → measurements
    reason.py        Muse Spark prompt + JSON validation + retry
    overlay.py       render coloured mask overlay
    pricing.py       editable regional price table
    cache.py         response cache
    pipeline.py      orchestrates the four stages
  data/default-prices.json   (live rates and saved price lists: .data/)
  fixtures/          mock SAM / Muse responses and sample photos
  tests/
frontend/
  src/ (Upload, Analysis viewer, Report)
docs/
  DEVELOPMENT_PLAN.md
```

## Status

| Phase | State |
|---|---|
| 0 Access and feasibility | Open: needs an API key. `scripts/probe_api.py` is ready. |
| 1 Backend and perception | Built. Perception is pluggable: `mock`, `muse` (Muse Spark grounding boxes) and `sam` (slot ready, waiting on SAM 3.1 access) |
| 2 Measurement | Built and unit tested |
| 3 Reasoning and report | Built: strict validation, repair retry, fallback, code-owned numbers |
| 4 Frontend | Built |
| 5 Trust and robustness | Built: confidence labels, per-finding trace, error messages, price editor (SAR/PKR/USD), finish levels |
| 6 Stretch | Built: Urdu/Arabic with RTL, PDF export (print), multi-photo rooms, history |
| 7 Evaluation | Tooling built (`scripts/evaluate.py`); needs real photos and labels |
| 8 Demo and submission | Drafts in `DEMO_SCRIPT.md` and `SUBMISSION.md`; video not recorded yet |

**Remaining work:** SAM 3.1 integration once access arrives (confirm the response format with
`probe_api.py`, then tighten `parse_sam_response`), a live run with a key, evaluation on real
photos, real price rates, and the demo video.

## Phases

### Phase 0 — Access and feasibility gate
**Goal:** prove the two models can do the job before building on assumptions.

- Confirm Meta Model API access from the build location; claim credits; read the Credit
  Terms and data terms.
- `GET /v1/models` to confirm `sam-3.1` and `muse-spark-1.3` are available.
- Call `sam-3.1` on one photo with prompts like `"wall"`, `"floor"`, `"door"`, `"crack"`.
  Record the **exact** response shape (mask encoding, boxes, scores) into
  `backend/fixtures/` — the public docs do not publish an output schema.
- Call `muse-spark-1.3` with an image and ask for JSON; check how reliably it follows a schema.
- Run both on ~10 real photos (own, stock or consented only).

**Acceptance:** masks are usable for at least walls, floors and openings, and Muse
returns parseable JSON. If not, decide: narrow element types, or fall back to
open-weights models (record the trade-off for the judging story).

### Phase 1 — Backend skeleton and perception
**Goal:** a photo returns a visible overlay.

- FastAPI app with `/health`, `/analyze` (multipart upload) and static overlay output.
- `meta_client.py`, `perceive.py` with mask parsing written against the Phase 0 fixtures.
- Image resizing before upload (save credits), response cache keyed by image hash.
- `overlay.py` draws colour-coded masks per element type.
- Mock mode returns fixture masks so everything works without a key.

**Acceptance:** `POST /analyze` with a sample photo returns an overlay image with
masks drawn, both live and in mock mode.

### Phase 2 — Measurement
**Goal:** turn masks into trustworthy numbers.

- Per element type: instance count, pixel area, share of image, bounding boxes.
- Scale reference: user gives one known dimension (e.g. door height in metres) →
  metres-per-pixel → area in m². Without it, report proportions only.
- Unit tests on synthetic masks with known areas.

**Acceptance:** numbers match a hand check on 3 photos; tests pass.

### Phase 3 — Reasoning and report
**Goal:** a strict, validated JSON report.

- Pydantic report schema (scene, scale, elements, defects, cost estimate, summary,
  disclaimer).
- Prompt template: the image + measurement JSON + price table; "use supplied numbers,
  do not invent measurements, never claim structural safety".
- Validate output; on failure, one repair retry with the validation error, then a
  safe fallback report.
- Cost range computed in code from the price table where possible; Muse explains
  assumptions and adjusts for finish type.

**Acceptance:** JSON validates on 20 consecutive runs; defects carry severity,
confidence and a `why`.

### Phase 4 — Frontend, end to end
**Goal:** the full user flow in the browser.

- Upload screen: drop zone, sample photos, scale reference, finish type, language.
- Analysis screen: photo with toggleable mask layers per element type, hover details.
- Report screen: quantities table, defects with severity, cost range, summary,
  disclaimer, copy/export JSON.
- Progress states for each pipeline stage.

**Acceptance:** upload → overlay → report works in the browser in under a minute.

### Phase 5 — Trust and robustness
**Goal:** failures are graceful and every finding is explainable.

- Confidence labels and a per-finding trace (which mask, which numbers, why).
- Clear error messages for: bad file, API down, rate limit, invalid model output.
- Editable price table (currency field: SAR / PKR / USD).
- Timeouts and retries on API calls.

**Acceptance:** each failure path shows a clear message, not a crash.

### Phase 6 — Stretch
Only if Phases 0–5 are solid.

- Urdu and Arabic report output (Muse writes the summary in the chosen language; RTL UI).
- PDF export.
- Multi-photo rooms.
- History of past analyses (SQLite).

**Acceptance:** each stretch item works fully or is cut.

### Phase 7 — Evaluation and hardening
- Run on 20–30 photos across at least 3 scene types; record segmentation quality,
  defect hits/misses/false positives, and JSON validity.
- Compare cost estimates against a manual takeoff on 5 rooms.
- Fix bugs; freeze features.

**Acceptance:** no open critical bugs; one-slide evaluation result ready.

### Phase 8 — Demo and submission
- Pre-cache the demo photos so the live demo is instant.
- README: what it does, architecture diagram, Meta models used, limitations.
- 2–3 minute demo video with voiceover + backup recording.
- Submission text checked against judging weights (Impact 30, Meta tooling 25, Demo 25,
  Technical 20). Submit with buffer before the deadline.

## Cut order if time runs short

1. PDF export and multi-photo rooms
2. Urdu / Arabic output
3. History screen
4. Cost estimate detail (keep a single range)

**Never cut:** the overlay, the structured report, confidence labels, the disclaimer,
and a clean demo.

## Known unknowns (resolve in Phase 0)

- Exact `sam-3.1` response format (mask encoding, scores) — docs give no schema.
- Whether Muse Spark supports a structured-output / JSON-schema parameter, or only prompting.
- API availability from Pakistan / Saudi Arabia.
- Which currency the default price table should use.

## Data and safety rules

- Only own, stock or consented photos; blur faces and plates; no client data.
- Nothing confidential in the submission (Meta receives a perpetual licence).
- Every report says: estimate only, not an engineering or safety assessment.
