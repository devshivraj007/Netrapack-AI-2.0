# NetraPack Backend (Day 1)

Smart India Hackathon 2026 — PS SIH26034.

Day 1 scope: **rule-engine logic only**. No OCR/photos, no barcode lookup,
no reference database, no Officer Mode, no frontend. Those arrive on later days.

## What this does

Exposes one endpoint that runs a Legal Metrology compliance rule engine over
pre-extracted (typed-out) label text and returns a compliance verdict.

`POST /api/v1/scan/process`

Input: scan ID, optional barcode, and text fields for MRP, net quantity,
manufacturing date, expiry date, unit sale price, manufacturer name/address,
country of origin, consumer care, and FSSAI licence number.

Output: overall status, rules passed / rules checked, a list of violations
(each with an exact rule citation + plain description), and the parsed version
of every field.

## Folder structure

```
netrapack-backend/
├── app/
│   ├── main.py                 # FastAPI app + /health
│   ├── api/
│   │   └── scan_routes.py      # POST /api/v1/scan/process
│   ├── rule_engine/
│   │   ├── parsers.py          # price/quantity/date/contact/FSSAI parsers
│   │   └── engine.py           # the 9 compliance checks + verdict assembly
│   └── schemas/
│       └── scan.py             # request + response Pydantic models
├── tests/
│   └── sample_inputs.py        # 5 sample label scenarios
├── run_samples.py              # runs all 5 samples through the engine
├── requirements.txt
├── .env.example
└── README.md
```

## Run it

```powershell
# from the netrapack-backend directory
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# run the API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# open the interactive docs
# http://127.0.0.1:8000/docs
```

## Try the 5 sample scenarios

```powershell
.\.venv\Scripts\python.exe run_samples.py
```

## Rules implemented today

| Check | Behaviour |
|-------|-----------|
| MRP | One price → auto-resolve. Multiple prices → manual review (shows candidates). |
| Net quantity | Handles `200g`, `3 x 50g` (=150g), `100g + 20g extra` (total 120g / paid 100g). |
| Mfg / expiry date | Month+Year only (`03/2026` or `MAR 2026`); day never required. |
| Unit sale price | Exemptions checked FIRST (1kg/1L/1unit/1m, MRP ≤ ₹35, ≤10g/10ml). Then math verified against **paid** quantity. |
| Country of origin | Explicit phrase only ("Made in …"). No barcode guessing → manual review if absent. |
| Manufacturer | Presence check (deep parsing is Day 2). |
| Consumer care | Requires a phone or email pattern. |
| FSSAI | Requires a 14-digit number; "FSSAI" without one → invalid. |
```
