# NetraPack AI 2.0

Legal Metrology compliance system for the Smart India Hackathon (PS SIH26034).

NetraPack scans a packaged product's label from a phone, reads the printed
declarations, checks them against India's Legal Metrology (Packaged Commodities)
Rules, 2011, and lets a field officer confirm the product category and issue a
statutory Section 36 notice — all offline-capable, no cloud infrastructure
required.

The repository has two apps:

| Folder | Stack | Role |
|--------|-------|------|
| `netrapack-backend/` | FastAPI + Python | Scan/auth/officer/admin/chat REST API, rule engine, OCR + AI extraction, SQLite evidence store, PDF notices |
| `netrapack-app/` | Expo (React Native, SDK 52) + TypeScript | Phone app: scan → verdict → officer confirm → notice |

See [`TECH_STACK.md`](./TECH_STACK.md) for the full technology rationale.

---

## How to run

### Prerequisites

- **Python 3.12–3.14** (the pinned dependencies ship prebuilt wheels for 3.14).
- **Node.js 18+** and **npm** (for the mobile app).
- **Expo Go** on a physical phone, or an Android/iOS emulator, to run the app.
- *(Optional)* **Tesseract OCR** binary — only needed for the offline OCR
  fallback path. *(Optional)* a **Gemini API key** or a local **Ollama** install
  for live AI label extraction. The system works without these (it degrades
  gracefully), but photo-scan label reading needs at least one of them.

### 1. Backend (FastAPI)

From the `netrapack-backend/` directory:

```powershell
# create and populate a virtual environment
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# (optional) configure secrets — copy the template and edit it
Copy-Item .env.example .env      # then add GEMINI_API_KEY, AUTH_SECRET, etc.

# run the API (use --host 0.0.0.0 so a phone on the same Wi-Fi can reach it)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On macOS/Linux use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

Verify it's up:

- Interactive API docs: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

The database (`data/netrapack.db`) is created and seeded automatically on first
startup — no migration step. Default demo logins (change via `.env`):

| Role | Username | Password |
|------|----------|----------|
| Officer | `officer` | `netra123` |
| Admin | `admin` | `admin123` |

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rule_engine.py tests/test_api_endpoints.py tests/test_cp2_backend.py tests/test_extraction_sanitize.py tests/test_mrp_strikethrough.py -q
```

### 2. Mobile app (Expo / React Native)

From the `netrapack-app/` directory:

```powershell
npm install

# point the app at your backend: set the PC's LAN IP (not localhost — a phone
# cannot reach your PC via localhost). Find it with `ipconfig` (Windows).
# Edit the fallback in src/config.ts OR set extra.apiBaseUrl in app.json, e.g.:
#   http://192.168.1.5:8000/api/v1

npm start
```

Then scan the QR code with **Expo Go** on your phone (make sure the phone and PC
are on the same Wi-Fi network). You can also press `a` for an Android emulator or
`i` for an iOS simulator.

Type-check the app without running it:

```powershell
npx tsc --noEmit
```

### Connectivity notes

- The backend must run with `--host 0.0.0.0` to be reachable from a phone over
  the LAN.
- The app's API base URL lives in one place — `src/config.ts` (with an
  `app.json` → `extra.apiBaseUrl` override, or the `EXPO_PUBLIC_API_BASE_URL`
  environment variable). It must end in `/api/v1`.

---

## Project layout

```
Netrapack-AI-2.0/
├── netrapack-backend/     # FastAPI backend (rule engine, OCR/AI, SQLite, PDF)
│   ├── app/               # application code (api, rule_engine, ocr, ai, db, ...)
│   ├── tests/             # pytest suite + diagnostic scripts
│   └── requirements.txt
├── netrapack-app/         # Expo mobile app
│   ├── app/               # expo-router screens (index, scan, verdict, ...)
│   └── src/               # api client, config, theme, shared components
├── TECH_STACK.md          # technology choices and rationale
└── README.md
```
