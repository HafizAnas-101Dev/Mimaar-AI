# Vendor price files

A price file holds one vendor's rates and details. Import it in Mimaar under **Price table →
Import**: the table switches to those rates at once, and every new report shows the vendor's name,
logo and contact details, on screen and in the PDF.

| File | What it is |
|---|---|
| `mimaar-price-table-template.json` | Blank template for a vendor to fill in (SAR, PKR and USD) |
| `sample-vendor-sahara-finish-riyadh-sar.json` | Sample vendor in Riyadh, rates in SAR |
| `sample-vendor-indus-build-lahore-pkr.json` | Sample vendor in Lahore, rates in PKR |
| `mimaar-default-rates.json` | Mimaar's built-in placeholder rates; import it to go back to them |

The two sample vendors are fictional companies made for testing; their rates are illustrative.

## For vendors: making your own file

Start from `mimaar-price-table-template.json`:

1. Fill in `vendor`: `name` is required; everything else is optional.
2. Keep the currencies you quote in and delete the others; set `default_currency` to one you kept.
3. For each item set `low` and `high` (low must not be above high). Wall, floor and ceiling are
   priced per m² (`"unit": "m2"`); doors, windows, lights and repairs per item (`"unit": "each"`).
   You can rename any `label`, for example "Gypsum plaster + 2 coats premium emulsion".
4. `finish_multipliers` scales your rates for basic, standard and premium finishes.
5. Add your logo (PNG, JPEG, WebP or SVG) from the `backend` folder:
   `python -m scripts.add_vendor_logo path/to/your-file.json path/to/logo.png`.
   The logo is embedded in the file, so the one file is all you share with customers.

Mimaar checks every file on import and says what to fix, for example a low rate above its high rate
or a wall priced per item instead of per m².
