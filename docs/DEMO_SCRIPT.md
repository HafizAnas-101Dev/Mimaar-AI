# Demo script (3 minutes)

Judging weights to hit: Impact 30%, Use of Meta AI tooling 25%, Demo 25%, Technical depth 20%.
The video must show only what was built during the hackathon (everything in this repository).

## Before recording

- Start everything with `.\start.ps1` and wait until the Muse Glimmer window says the server is listening.
- Close GPU-heavy apps (browser tabs with video, Slack, game launchers): Glimmer writes faster with more GPU memory.
- Run each demo once beforehand. Model replies are cached, so the recorded run is instant and repeatable.
- If you have it, film one real room on a phone and measure one wall with a tape for the accuracy line.
- Browser at 100% zoom, 1440 px wide or more, so the overlay and report fit side by side.
- Record a backup take of the full flow.

## Script

| Time | Show | Say |
|---|---|---|
| 0:00–0:15 | A worn room (the living-room example), then the homepage | "Getting a renovation quote in Saudi Arabia or Pakistan means waiting for someone to visit and measure by hand. Mimaar gives a first quote from phone photos." |
| 0:15–0:40 | Analyse → **A whole room** → **Living room** example fills six slots; choose **I don't have measurements**, room type Living room | "I add a photo of the floor, the ceiling and each wall. No tape measure: Mimaar uses a standard door and typical room sizes, and says so." |
| 0:40–0:55 | Step 3: the work picker. Untick nothing, point at "Replace doors" being off | "The customer picks the work they want priced. Replacing doors or windows is opt-in, so the total isn't inflated." |
| 0:55–1:20 | Generate. The report appears in seconds; toggle wall, crack and damp layers on a wall photo | "Meta's SAM 3 outlines every wall, floor, opening, crack and damp patch, on this PC, in about a second. Code turns the outlines into square metres and prices them." |
| 1:20–1:45 | The writing panel ticks through its steps, then Muse Glimmer's summary fades in | "Meta's Muse Glimmer reads the photos and the numbers, decides which defects are real and how serious they are, and writes the summary. It runs locally: no cloud, no API key, the photos never leave the machine." |
| 1:45–2:05 | Open "Why this?" on Wall; point at the Estimated badge and the ≈ lines | "Every number comes from code, never from the model, and each one shows how it was made. Estimates are labelled and get a wider range." |
| 2:05–2:25 | Switch the site to Arabic, click **Write it in Arabic**; then Urdu | "The same report in Arabic or Urdu, in a few seconds, without analysing again." |
| 2:25–2:45 | Bedroom example: open a wall photo with a wardrobe; show the door count | "It knows a wardrobe door isn't a room door, and walls hidden behind furniture get a warning." |
| 2:45–3:00 | Export PDF; end on the homepage badge | "A full report in English, Arabic or Urdu, built on Meta SAM 3 and Muse Glimmer." Add the accuracy line if you measured a real room. |

## Talking points for technical depth

- **Two Meta models in a chain:** SAM 3 masks → code measurement and pricing → Muse Glimmer report → code validation.
- **Code owns every number:** the model only judges defects and writes the summary; counts, areas and costs are code.
- **Built for an 8 GB GPU:** instant report first, then the write-up; Glimmer's answer is pre-filled to skip hidden reasoning; it writes only short verdicts; a DFlash draft model speeds it up; SAM 3 leaves the GPU between runs.
- **Real-world details:** furniture-proof wall areas from room size, irregular rooms, wardrobe filtering, merged defect patches, iPhone HEIC photos, refusal of non-room photos.
- **Same code on the Meta Model API:** one setting switches to Muse Spark and SAM 3.1.
