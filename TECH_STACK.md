# NetraPack — Technology Stack

> Legal Metrology compliance system for the Smart India Hackathon (PS SIH26034).
> NetraPack scans a packaged product's label, checks it against India's Legal
> Metrology (Packaged Commodities) Rules, and lets a field officer confirm the
> product category and issue a statutory notice — all from a phone.

This document explains **every technology** in the project and, more importantly,
**why it was chosen** over the alternatives. The guiding principle throughout is:
a demo-ready, low-footprint, auditable system that a single team can run on a
laptop and a phone without cloud infrastructure, while still being production-credible.

---

## At a glance

| Layer | Technology | Role |
|-------|-----------|------|
| Mobile app | React Native via **Expo (SDK 52)** + **expo-router** + **TypeScript** | Citizen/officer-facing scan → verdict → notice flow |
| API | **FastAPI** + **Uvicorn** (ASGI) | REST endpoints for scan, auth, admin, reports |
| Data validation | **Pydantic v2** | Typed request/response contracts |
| Database | **SQLite** (WAL mode, append-only via triggers) | Scans, reports, users, chain-of-custody evidence |
| Auth | **Python standard library** (PBKDF2-HMAC-SHA256 + HMAC-signed tokens) | Officer/Admin roles, no external auth service |
| Label reading (primary) | **Google Gemini** / **Ollama** vision models | Structured field extraction from photos |
| Label reading (fallback) | **Tesseract OCR** (`pytesseract`) + **OpenCV** + **Pillow** | Offline/edge extraction when no vision model |
| Legal PDF | **ReportLab** | Section 36 notice generation |
| HTTP client | **httpx** | Calls to Gemini/Ollama |
| Tests | **pytest** | Deterministic backend test suite |

---

## Backend

### FastAPI (web framework)
**What it does:** Serves every REST endpoint — `/scan/process-photo`, `/auth/login`,
`/admin/reports`, `/reports/{id}/export`, `/officer/*`.

**Why we chose it:**
- **Automatic, interactive API docs.** FastAPI generates a live Swagger UI at `/docs`
  from the code itself. During a hackathon demo this is invaluable — judges can see
  and try every endpoint without us building a separate API console. It was also our
  fastest connectivity test on the phone (open `/docs` in the phone browser).
- **First-class Pydantic integration.** Request bodies and responses are declared as
  typed models; FastAPI validates and documents them automatically. Fewer bugs, less
  boilerplate.
- **Async-native (ASGI).** Photo uploads and outbound AI calls are I/O-bound; an async
  framework handles them without blocking the whole server.
- **Small and Pythonic.** The whole backend runs from one `uvicorn app.main:app`
  command — no heavyweight application server to configure.

**Alternatives considered:** Flask (no built-in validation or async, would need extra
libraries for the same result); Django (batteries-included but far too heavy for a
focused API — its ORM/admin/templating add weight we don't need).

### Uvicorn (ASGI server)
The lightning-fast ASGI server that actually runs FastAPI. We bind it to
`--host 0.0.0.0` so the phone can reach it over the LAN during testing. It's the
reference server the FastAPI docs recommend, needs zero config, and supports hot
reload during development.

### Pydantic v2 (data modeling & validation)
**What it does:** Defines the shape of every payload — e.g. `ScanVerdict`,
`ReadabilityInfo`, `LoginRequest`. Invalid input is rejected before it reaches our logic.

**Why:** It turns our API contract into **typed Python classes** that are validated at
runtime and documented automatically. v2's Rust-based core is fast, and it pairs
natively with FastAPI so there's a single source of truth for the data model. This is
what lets the mobile app and backend agree on field names without guesswork.

### SQLite (database)
**What it does:** Stores scans, detected violations, the officer/admin user table, and
the chain-of-custody evidence (image hashes + paths).

**Why it's the right choice here — not just the convenient one:**
- **Zero setup, zero server.** It's a single file (`data/netrapack.db`) built into
  Python's standard library. No Postgres/MySQL to install, no connection strings, no
  container. A judge can clone and run instantly. For a field-deployable compliance
  tool that may run **offline at the edge** (a market inspection with no connectivity),
  an embedded database is genuinely the correct architecture, not a shortcut.
- **Append-only integrity for legal evidence.** Compliance records must be tamper-evident.
  We enforce this two ways: the repository layer only exposes insert/select for
  scans/reports, and **SQLite triggers raise on any UPDATE or DELETE** against those
  tables — so even a stray query cannot mutate an evidence record. That's a real
  audit-grade guarantee.
- **WAL mode + busy timeout.** We enable Write-Ahead Logging so reads don't block writes,
  which keeps the API responsive during concurrent scans.

**Alternatives considered:** PostgreSQL (excellent, but requires a running server and
setup that defeats the "run anywhere, even offline" goal); a cloud database (adds a
network dependency and cost, wrong for an edge/field tool). SQLite's file-based model is
a natural fit for a portable, offline-capable evidence store, and it can be migrated to
Postgres later with minimal code change because access is isolated in a thin repository
layer.

### Authentication — Python standard library (no external auth library)
**What it does:** Officer and Admin login with hashed passwords and signed session tokens.
- `app/auth/security.py` — **PBKDF2-HMAC-SHA256** password hashing (salted, iterated) and
  **HMAC-signed tokens** (`payload.signature`, 12-hour expiry).
- `app/auth/deps.py` — FastAPI dependencies `require_officer` / `require_admin` that gate
  the protected endpoints.

**Why we did it with the standard library instead of a JWT/auth package:**
- **Minimal footprint, zero new dependencies.** `hashlib` and `hmac` ship with Python.
  For a hackathon build, every dependency is a risk (version conflicts, install failures
  on a fresh machine). This keeps the attack surface and the install list small.
- **It's real, not hardcoded.** PBKDF2 is an industry-standard, deliberately slow hashing
  scheme that resists brute-force; the tokens are cryptographically signed so they can't
  be forged. This satisfies the "secure authentication with roles" requirement honestly.
- **Transparent and auditable.** For a compliance system, being able to point to exactly
  how a credential is hashed and a token is signed — with no black-box library — is a plus.

**Honest note:** for a large production system a vetted library (e.g. PyJWT + passlib)
or an identity provider would be preferable for features like key rotation and refresh
tokens. Our approach is intentionally scoped to "simple but real," which is what the
problem statement asked for.

### Label reading — a layered (fallback) strategy
Reading a real product label from a phone photo is the hard part. We use a **tiered
approach** so the system degrades gracefully instead of failing:

1. **Vision AI (primary): Google Gemini, then Ollama.**
   - **Gemini** (cloud) is tried first for the best structured extraction — it reads MRP,
     net quantity, dates, FSSAI number, manufacturer, country of origin directly from the
     image and returns them as JSON. Modern vision-language models handle messy real-world
     labels (curved surfaces, mixed fonts, glare) far better than classic OCR.
   - **Ollama** (local model) is the offline/edge alternative — the same job runs on a
     local model with no internet, which matters for a field-inspection tool.
2. **Tesseract OCR (fallback).** When no vision model is available, we fall back to
   **Tesseract** (`pytesseract`) with an **OpenCV** pre-processing pipeline (glare
   detection, deskew, adaptive thresholding, spatial word grouping). This guarantees the
   app still produces *something* usable with zero AI dependency.

**Why this design:** No single reader is reliable on all packages, and the deployment
environment ranges from a good office network to an offline market stall. The tiered
strategy means **online → best accuracy (Gemini), offline → still works (Ollama/Tesseract)**.
It's also honest about uncertainty — ambiguous prices are flagged for manual review rather
than guessed.

- **OpenCV (`opencv-python-headless`)** — image pre-processing (glare/deskew) that makes
  OCR far more accurate. The `headless` build omits GUI code we don't need on a server.
- **Pillow** — image decoding/handling.
- **NumPy** — the array backbone OpenCV and the readability check operate on.

### Readability / font-size check (advisory)
An OpenCV + Tesseract routine (`app/ocr/readability.py`) estimates whether declaration
text is large enough to be legible under LMPC Rule 9. It is **explicitly advisory**: a
photo has no physical scale, so we report a proportional estimate (text height vs frame)
and flag "possibly too small" for manual verification rather than fabricating a precise
millimetre measurement. Being honest about this limitation is a deliberate design choice
for a legal tool. It is folded into the main scan verdict so it can't be missed in the demo.

### ReportLab (PDF generation)
**What it does:** Generates the **Section 36 legal notice PDF** an officer issues to a
non-compliant establishment, including the evidence hash for chain-of-custody.

**Why:** ReportLab is the mature, pure-Python standard for programmatic PDF creation. It
needs no external binary (unlike wkhtmltopdf/headless-Chrome approaches), so it runs
anywhere the backend runs, and gives us precise control over an official document layout.

### httpx (HTTP client)
Used to call the Gemini and Ollama APIs. Chosen over `requests` because it supports async
(matching FastAPI), has clean timeout controls, and is actively maintained. Per-call
timeouts let a slow cloud response fail fast and fall back to the next tier.

### pytest (testing)
The backend ships a deterministic test suite (`tests/`) covering auth + roles, search,
CSV export, the officer gate + PDF, the admin state machine, chain-of-custody hashing, and
the readability integration. AI-dependent paths are asserted on structure/fallback behaviour
so tests are fast and require no live model or network. pytest was chosen for its concise
assert-based style and rich fixtures.

### python-dotenv & python-multipart
- **python-dotenv** loads secrets (the Gemini API key) from a gitignored `.env` file, so
  credentials never enter the codebase or the repo.
- **python-multipart** lets FastAPI accept the multipart photo uploads from the app.

---

## Mobile app

### Expo (React Native, SDK 52)
**What it does:** The phone app — Home → Scan → Verdict → Officer login → Confirm category
→ Generate notice.

**Why Expo over bare React Native:**
- **Instant on-device testing with no native build.** With **Expo Go**, we scan a QR code
  and the app runs on a real phone in seconds — no Android Studio, no Xcode, no APK build.
  For a hackathon this collapses the iteration loop from minutes to seconds.
- **Managed native modules.** `expo-camera` (label capture), `expo-image-picker` (gallery
  fallback), and `expo-asset`/`expo-font` are pre-wired and version-matched by the SDK, so
  we don't hand-configure native code.
- **One codebase, both platforms.** The same code targets Android and iOS.

**Why React Native at all (vs native Android/iOS or a web app):** field officers and the
public use phones; a camera-first, installable app is the right form factor. React Native
gives us native camera performance with a single JavaScript/TypeScript codebase, which one
small team can build and maintain quickly.

### expo-router (navigation)
File-based routing (each screen is a file in `app/`). It's the modern Expo-native
navigation approach — no manual navigator wiring — which keeps the screen structure obvious
and matches how the SDK is designed to be used.

### TypeScript
The app is written in TypeScript so the API response shapes (`ScanVerdict`,
`ReadabilityInfo`, etc.) are typed end-to-end. This catches field-name mismatches between
app and backend at edit time rather than at runtime on the phone — critical when the two
were built in parallel.

### Configurable API base URL
The backend address lives in one place (`app.json` → `extra.apiBaseUrl`, with a
`src/config.ts` fallback), so pointing the app at a different machine/network is a
one-line change. This is why we could move quickly between Wi-Fi and PC-hotspot networks
during testing.

---

## How the pieces fit together

```
 Phone (Expo / React Native / TypeScript)
        │  multipart photo  ──────────────►  FastAPI  /scan/process-photo
        │                                       │
        │                                       ├─► Gemini / Ollama (vision extraction)  ── primary
        │                                       │      └─ fallback: Tesseract + OpenCV    ── offline
        │                                       ├─► Rule engine (LMPC checks)
        │                                       ├─► Readability advisory (OpenCV/Tesseract)
        │                                       └─► SQLite (append-only scan + evidence)
        │  ◄──────────────  JSON verdict (status, extracted fields, violations, readability)
        │
        │  Officer login (PBKDF2 + signed token) ──► require_officer / require_admin gates
        │  Confirm category ──► Generate Section 36 notice (ReportLab PDF)
        │  Admin search / CSV export ──► SQLite queries
```

---

## Design principles behind the stack

1. **Runs anywhere, including offline.** SQLite + Tesseract/Ollama fallback mean the core
   flow works with no cloud and no internet — the reality of a field inspection.
2. **Minimal dependencies.** Standard-library auth, embedded database, pure-Python PDF. Fewer
   moving parts = fewer install failures and a smaller security surface.
3. **Honest about uncertainty.** Ambiguous prices and un-scalable font measurements are
   flagged for manual review, not faked — appropriate for a system that can trigger legal
   action.
4. **Auditable and tamper-evident.** Append-only evidence tables enforced by database triggers,
   image hashing for chain-of-custody, transparent crypto.
5. **Fast to demo, credible in production.** Every choice optimizes for "clone and run in
   minutes" while keeping a clean path to scale (swap SQLite→Postgres, self-hosted vision
   model, etc.) because concerns are cleanly separated.
