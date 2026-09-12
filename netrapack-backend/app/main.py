"""NetraPack backend FastAPI application entrypoint.

Smart India Hackathon 2026 - PS SIH26034.
Day 2: real OCR on photos, 3-level AI product recognition, SQLite storage.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

# Load .env before anything reads os.environ (Gemini key, Ollama timeout, etc.).
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.recognizer import detect_online
from app.api.admin_routes import router as admin_router
from app.api.auth_routes import router as auth_router
from app.api.chat_routes import router as chat_router
from app.api.officer_routes import router as officer_router
from app.api.reports_routes import router as reports_router
from app.api.scan_routes import router as scan_router
from app.db import repository
from app.ocr.reader import tesseract_available


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create schema and reseed the 21 products + rules on every startup.
    counts = repository.reseed()
    # Seed default Officer/Admin accounts (hashed passwords) if none exist.
    repository.seed_default_users()
    app.state.seed_counts = counts
    yield


app = FastAPI(
    title="NetraPack Backend",
    description="Legal Metrology compliance engine with OCR + AI recognition.",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS: allow the mobile app / admin panel on local dev origins. allow_origins=*
# covers Expo Go LAN IPs and local dashboards; credentials disabled since we use
# bearer tokens (not cookies).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(scan_router)
app.include_router(officer_router)
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(reports_router)


@app.get("/health", tags=["meta"], summary="Health check")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "netrapack-backend",
        "version": "0.2.0",
        "tesseract_available": tesseract_available(),
        "online": detect_online(),
        "seed_counts": getattr(app.state, "seed_counts", {}),
    }
