# Target audience, consumer and consumer story

Who Mimaar AI is for, who pays, and the story the demo tells. Anything marked
**hypothesis** is an assumption to test with real users, not a finding.

## Market

- **First markets:** Saudi Arabia and Pakistan. Both have large volumes of residential
  finishing and renovation work, priced through manual site surveys and takeoffs.
- **Languages:** Arabic (Saudi Arabia), Urdu and English (Pakistan). Many site teams and
  clients prefer reports in their own language, which is why the report is trilingual.
- **Work type:** interior finishing and renovation of villas, apartments and small
  commercial units. That's walls, floors, ceilings, openings and visible defects, not
  structural engineering.

## Target audience

| Segment | Role in the work | Pain today | What Mimaar gives them |
|---|---|---|---|
| **Primary: finishing contractors and site engineers** (small to mid-size firms) | Measure rooms and price finishing work before quoting | Every quote starts with a tape-measure survey and a spreadsheet; about an hour per room, done again for every bid | Quantities, flagged defects and a cost range from photos, on site, in under a minute |
| **Secondary: quantity surveyors and small developers** | Check or prepare first estimates across many units | First passes vary from person to person and start from zero each time | A consistent first pass with a trace for every number, to check instead of build |
| **Secondary: real-estate agents and property managers** | Describe a property's condition to buyers, tenants or owners | Asked about condition and repair costs, they can only guess | A plain-language condition summary with defects and a rough repair range |
| **Later: homeowners** | Plan renovations | Don't know what a fair quote looks like | A neutral first estimate to compare quotes against (**hypothesis**: needs a simpler flow) |

**Not for (anti-audience):** structural engineers, insurers or authorities who need a
certified assessment. Mimaar is decision support and says so on every report. It never
claims structural safety.

## Consumer vs. customer

- **Consumer (who uses it):** the site engineer or contractor holding the phone on site.
  They need speed, a result they can explain to a client, and their own language.
- **Customer (who pays):** the contracting firm or developer. They buy it for faster,
  more consistent quotes and less surveyor time per bid.
  - **Hypothesis:** a per-seat subscription for firms, or pay-per-report for occasional
    users such as agents.
- **Influencer:** the quantity surveyor. They will trust it only if every number can be
  traced, which is why each finding carries a "Why this?" trace and the numbers come from
  code, not the model.

## Primary persona

**The site engineer at a finishing contractor** (fictional, for design and demo purposes)

- Works for a 20 to 50-person finishing firm in Riyadh or Lahore. They visit several sites a
  week and turn each visit into a quote.
- **Goals:** quote quickly, avoid under-pricing, spot problems (cracks, damp) before they
  become disputes.
- **Frustrations:** repetitive measuring, a backlog waiting on the quantity surveyor, clients
  who want an answer the same day.
- **Context:** a smartphone on site, a laptop at the office, mixed Arabic/Urdu and English.
- **What success looks like:** a quote sent the same day, with numbers they can defend.

## Consumer story

**One villa, one afternoon.**

1. **The ask.** A finishing contractor in Riyadh has to quote a villa's interior by tomorrow
   morning.
2. **Before Mimaar.** An engineer spends about an hour per room with a tape and a
   spreadsheet, and the quantity surveyor checks it the next day.
3. **With Mimaar.** They photograph each room with a door in frame and give the door's
   height. They get:
   - quantities in square metres;
   - flagged defects with severity;
   - a cost range in SAR, in under a minute;
   - the summary in Arabic for the client.
4. **The outcome.** The quote goes out the same day, and the surveyor reviews a first pass,
   with a trace for every number, instead of starting from zero.

This is the story the demo video tells (see [DEMO_SCRIPT.md](DEMO_SCRIPT.md)); the site's
"Who it's for" and "Consumer story" sections show the same content in English, Arabic and Urdu.

## User stories

| As a… | I want to… | So that… | Feature |
|---|---|---|---|
| site engineer | photograph a room and get quantities | I can quote without a tape-measure survey | Upload, segmentation, measurement |
| site engineer | give one known dimension | areas come out in square metres, not guesses | Scale reference (door or window height) |
| contractor | see a cost range in my currency and finish level | the quote matches my market | Price table (SAR, PKR, USD), finish levels |
| contractor | combine several photos of one room | the whole room is priced once | Multi-photo room report |
| quantity surveyor | see where each number came from | I can check it instead of redoing it | Confidence labels, "Why this?" trace |
| agent | get a plain summary in Arabic or Urdu | I can share it with a buyer as is | Trilingual report, PDF export |
| any user | see clearly that it's an estimate | nobody relies on it as a safety assessment | Disclaimer on every report |

## Hypotheses to validate

1. Site engineers will photograph rooms in a usable way (front-on, door in frame) without
   training.
2. A rough range with visible assumptions is useful for a first quote even before accuracy
   is proven.
3. Firms will pay per seat; agents would rather pay per report.
4. Arabic and Urdu output measurably increases trust and sharing with clients.

How to test them: interviews with 5 to 10 contractors and surveyors in each market, plus
the evaluation in `backend/scripts/evaluate.py` comparing estimates against manual takeoffs.
