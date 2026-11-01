# Submission draft

Draft text for the Cerebral Valley submission form. Check the published Official Rules for the
exact fields, and update the bracketed parts before submitting. Do not claim anything the
build does not do on the day.

## Project name

Mimaar AI

## One-liner

Phone photos of a room in; outlines, square metres, defects and a cost estimate out in seconds,
written up in English, Urdu or Arabic by Meta's Muse Glimmer, with Meta's SAM 3, running entirely on
a consumer PC.

## Problem

Getting a renovation or repair quote in Saudi Arabia and Pakistan means waiting for a contractor
to visit and measure by hand. Quotes are slow, vary from one person to the next, and are hard for
homeowners to check. Contractors spend unpaid hours measuring rooms for jobs they may not win.

## What it does

The customer chooses a whole room or a single wall, adds photos of the floor, ceiling and walls
(any phone photo, including iPhone HEIC), and either enters sizes or says they don't have any.
They tick the work they want priced: plaster and paint, tiling, ceiling, crack, damp and peeling
repairs; replacing doors, windows and lights is opt-in.

Mimaar outlines walls, floor, ceiling, doors, windows, fixtures, cracks, damp and peeling paint,
measures them, and shows the report within seconds: quantities in square metres, a defect list
with severity and location ("Wall 2 · upper right"), and a cost range in SAR, PKR or USD from an
editable price table. Muse Glimmer then writes the summary and judges each defect.

Without a tape measure it uses a standard door, typical room sizes and a typical ceiling height,
labels those figures as estimates and widens the range. With the room size and ceiling height,
wall areas come from the room's dimensions, so furniture in the photo doesn't change them; irregular
rooms can give their floor area and wall length. Wardrobe doors aren't counted as room doors, walls
hidden by furniture are flagged, and photos that aren't of a room are refused. Every number shows
how it was made, and the report exports to PDF. Contractors can import their own price file with
their rates, logo and contact details, so every report becomes a branded quote. It is decision support, not an engineering or
safety assessment.

## How we used Meta's models

The Meta Model API is not available in our region, so Mimaar runs entirely on **Meta's
open-weight models on a consumer PC** (RTX 5060 8 GB, 32 GB RAM), with no cloud and no API key.

- **SAM 3 (`facebook/sam3`)** segments walls, floor, ceiling, doors, windows, light fixtures,
  cracks, damp, peeling paint and furniture from text prompts, in about a second per photo.
  Code turns the masks into counts and square metres, and uses the furniture masks to warn when
  a wall is partly hidden.
- **Muse Glimmer 30B** (Meta open weights; 4-bit GGUF build by Unsloth, served with llama.cpp
  and its DFlash draft model) reads the photos and the measured results, keeps or drops each
  defect candidate, sets severity, and writes the report in English, Urdu or Arabic.
- The models work as a chain: SAM 3 masks → code measurement and pricing → Muse Glimmer report →
  code validation. Code owns every number, so the model cannot invent measurements or costs.
- To make a 30B model practical on an 8 GB GPU, the report is shown instantly from SAM 3 + code,
  and Glimmer's write-up replaces the summary when ready (about 50 s in English).
- The same code runs on Muse Spark and SAM 3.1 through the Meta Model API by changing one setting.

## Technical details

- FastAPI backend, React frontend, Pydantic schemas for the report contract; 84 backend tests.
- SAM 3 (transformers, bfloat16) segments ten concepts per photo in about a second on an 8 GB GPU,
  then moves off the GPU so Muse Glimmer can use it.
- Muse Glimmer 30B (4-bit GGUF, llama.cpp) with a DFlash draft model for speculative decoding.
  Its answer is pre-filled with `{` so it skips hidden reasoning, and it writes only defect verdicts
  and a short summary, which cut a single-wall write-up from 11 minutes to under a minute.
- The report is returned instantly from SAM 3 + code; the write-up arrives afterwards and replaces
  the summary (`/api/reason/{id}`). Changing language rewrites the text without analysing again.
- Code owns every number: model output is validated, numbers are overwritten from measurements,
  one repair retry, then a measurement-only fallback.
- Room logic: per-slot photo roles, one wall per wall photo, perimeter × ceiling height for walls,
  merging of split or duplicate defect masks, furniture masks for hidden walls and wardrobe doors.
- Real-world check: on 3 real Pakistani property-listing photos, every door, window, floor and ceiling was
  detected correctly (20 of 22 items overall; 6 of 8 walls), with no false defects, and the instant
  report took 2–4 seconds per photo. Square metres are not yet checked against a tape measure.

## Impact

A first quote in seconds instead of a site visit, consistent between people, readable by
non-engineers, in the region's languages, and private: photos never leave the device, and no cloud
or API costs per estimate.

## Limitations

Photo-measured areas are rough because of perspective; sizes or estimates are more reliable.
Prices are regional placeholders until replaced with local rates. Defects hidden behind furniture
can't be seen. The written summary takes about a minute on an 8 GB GPU (longer for Arabic and Urdu).
It is never a structural safety assessment.

## Links

- Repository: *[URL]*
- Demo video: *[URL]*

## Checklist before pressing submit

- [ ] Official Rules read; track and representative confirmed
- [ ] Work committed and the GitHub repository set to public
- [ ] Only own, stock, generated or consented photos in the video and repo
- [ ] Optional: add a tape-measured room to the accuracy line (square metres)
- [ ] Demo video under 3 minutes, unlisted or public on YouTube
- [ ] Bracketed placeholders above replaced with real facts
- [ ] Submitted with buffer before the deadline (Nov 4, 9:00 PM ET = Nov 5, 7:00 AM PKT)
