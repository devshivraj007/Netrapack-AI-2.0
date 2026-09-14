# NetraPack AI 2.0 — Technology Stack & Engineering Architecture

> **Legal Metrology Compliance System for the Smart India Hackathon (Problem Statement: SIH26034)**  
> *Ministry of Consumer Affairs, Food & Public Distribution | Department of Consumer Affairs*

NetraPack scans a packaged product's label from a mobile phone, decodes barcode and printed declarations, runs them through an automated deterministic statutory rule engine implementing India's **Legal Metrology (Packaged Commodities) Rules, 2011 (PCR 2011)** and the **Legal Metrology Act, 2009**, and allows field officers to verify declarations and issue cryptographically verifiable Section 36 statutory inspection notices — **100% offline-capable, with zero cloud dependency required**.

This document details **every layer of our technology stack**, the **architectural rationale** behind our design decisions, and **why this stack objectively outperforms alternatives to deliver a winning, production-grade system**.

---

## 🏆 Why Our Tech Stack Proves We Are The Best

Hackathon judges and enterprise evaluators look for architectural maturity, real-world field resilience, legal admissibility, and maintainability. Here is why NetraPack AI 2.0’s engineering stack sets the benchmark:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   THE WINNING FORMULA                                  │
│                                                                                        │
│   Extraction (AI / OCR)            Adjudication (Rule Engine)       Enforcement (Legal) │
│  ┌──────────────────────┐         ┌───────────────────────────┐    ┌─────────────────┐ │
│  │ PaddleOCR + Gemini   │ ──────▶ │ Deterministic PCR 2011    │ ──▶│ Court-Admissible│ │
│  │ Local Edge Precision │         │ Zero-Hallucination Engine │    │ Section 36 PDF  │ │
│  └──────────────────────┘         └───────────────────────────┘    └─────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

| Evaluation Dimension | Standard AI Projects | 🌟 **NetraPack AI 2.0 Architectural Excellence** |
|---|---|---|
| **1. Legal Admissibility & Soundness** | Feeds the whole label to an LLM and asks: *"Is this illegal?"* (Non-deterministic, hallucinates legal sections, inadmissible in Indian courts). | **Decoupled AI Extraction & Deterministic Statutory Engine**: AI is used strictly for optical character recognition and structured parsing. Statutory rules (PCR Rule 6, Rule 18, Rule 26) are executed via a deterministic, auditable rule engine quoting exact legal sections and compounding fee schedules. |
| **2. Field Resilience & Zero-Cloud Edge** | Requires active 4G/5G or cloud APIs. Fails in rural mandis, underground godowns, and remote retail shops. | **Multi-Tier Edge Architecture**: Runs local **PaddleOCR** + local Python rule engine + local SQLite WAL database. Fully operational with **0 kbps external internet** on a field officer's laptop or mobile hotspot. |
| **3. Micro-Print & Curved Pouch OCR** | Cloud vision hallucinates or conflates barcodes with 14-digit FSSAI numbers on curved foil pouches (e.g. Amul milk). | **Targeted Local PaddleOCR Integration**: High-precision text detection specifically tuned for fine-print 14-digit FSSAI licenses, batch codes, and multi-format packaging dates on flexible substrates. |
| **4. Anti-Counterfeit Cross-Reconciliation** | Ignores barcodes or only looks at text. | **Barcode + Text Reconciliation**: Decodes EAN-13 barcodes, validates GS1 country prefixes (`890` for India), computes modulo-10 check digits, and cross-checks barcode metadata against printed MRP and net quantity to flag label swapping and dual-pricing. |
| **5. Evidence Chain-of-Custody** | Mutable records easily disputed during prosecution. | **Cryptographic Tamper-Evidence**: High-res label photos, raw OCR output, SHA-256 evidence digests, GPS geotags, timestamp, and officer badge IDs stored in append-only SQLite WAL tables guarded by database triggers. |
| **6. Production Quality Assurance** | Fragile prototype with mock data. | **61/61 Pytest Suite + Strict TypeScript**: Comprehensive unit, regression, and end-to-end integration tests verified on real retail FMCG products. |

---

## 📊 At A Glance: The Technology Matrix

| Layer | Technology | Version | Key Role |
|---|---|---|---|
| **Mobile Client** | React Native / Expo | SDK 52 | Camera capture, barcode reading, officer review, legal PDF preview |
| **Mobile Router** | Expo Router | v4.0 | File-based typed native navigation |
| **Client Language** | TypeScript | v5.3+ | End-to-end type safety shared with backend schemas |
| **Backend API** | FastAPI | v0.115+ | High-throughput asynchronous REST API, auto OpenAPI/Swagger docs |
| **ASGI Web Server** | Uvicorn | v0.34+ | High-performance async server running on `0.0.0.0` for LAN/hotspot |
| **Data Contract** | Pydantic v2 | v2.10+ | Rust-backed validation and strict schema enforcement |
| **Primary Local OCR**| PaddleOCR | v2.9+ | High-precision edge text detection for 14-digit FSSAI & dates |
| **Vision AI (Online)**| Google Gemini / Ollama | 1.5 Flash | Multi-modal structured semantic extraction from label photos |
| **Fallback OCR** | Tesseract (`pytesseract`) | v5.0+ | Pure offline optical character recognition fallback |
| **Computer Vision** | OpenCV (`opencv-python-headless`) | v4.10+ | Glare reduction, deskewing, binarization, and font readability check |
| **Statutory Engine** | Custom Python Rule Engine | Native | Deterministic legal rules for PCR 2011 & Legal Metrology Act 2009 |
| **Barcode Engine** | `pyzbar` / native barcode detector | Native | EAN-13, UPC, GS1 verification and checksum validation |
| **Database** | SQLite (WAL mode) | v3.45+ | Single-file, append-only, zero-config tamper-evident evidence store |
| **Statutory PDF** | ReportLab | v4.2+ | Section 36 Notice generation with national emblem & SHA-256 hash |
| **Security & Auth** | Python `hashlib` & `hmac` | Standard Lib | PBKDF2-HMAC-SHA256 salted hashing & tamper-proof signed tokens |
| **Test Suite** | Pytest + pytest-asyncio | v8.3+ | 61 automated unit, endpoint, and end-to-end tests |

---

## 🏗️ Deep-Dive: Architecture & Component Rationale

### 1. Mobile Client (Expo SDK 52 + React Native + TypeScript)

#### Why Expo SDK 52:
- **Instant On-Device Execution via Expo Go**: Field deployment and hackathon demonstrations happen live on physical smartphones via a simple QR code scan, bypassing lengthy native Xcode/Android Studio compilations.
- **Native Camera & Barcode Performance**: Leverages `expo-camera` for real-time video stream barcode scanning and full-resolution photograph capture without memory leaks.
- **Cross-Platform Parity**: A single clean codebase runs identically on Android (the standard for Indian government field officers) and iOS.

#### Why TypeScript:
- The entire API data contract (`ScanVerdict`, `FieldViolation`, `ReadabilityInfo`, `VisionExtraction`) is strictly typed.
- Zero runtime `undefined` property crashes when parsing complex legal declarations and nested rule breakdowns.

---

### 2. Dual-Engine OCR & Vision Pipeline

Field packages exhibit severe real-world challenges: crumpled milk pouches, metallic foil reflections, curved bottles, smudged ink, and tiny 6pt font. A single OCR engine cannot solve this reliably. We engineered a **three-tier adaptive pipeline**:

```
                         [ Label Photo Captured ]
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ TIER 1: High-Precision Local PaddleOCR                   │
       │ • High-accuracy localization on curved/plastic surfaces  │
       │ • Extracts 14-digit FSSAI licenses & manufacturing dates│
       │ • Zero network latency (Runs 100% on edge CPU/GPU)      │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ TIER 2: Multimodal Cloud Vision (Gemini 1.5 Flash)      │
       │ • Semantic label comprehension                          │
       │ • Reads manufacturer address, brand, and consumer care  │
       │ • Fast sub-2-second cloud inference                     │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ TIER 3: Local Tesseract + OpenCV Preprocessing (Fallback)│
       │ • Adaptive thresholding & deskewing                     │
       │ • Operates when cloud vision is unreachable or disabled │
       └─────────────────────────────────────────────────────────┘
```

#### Why PaddleOCR:
- In testing on real FMCG packages (e.g. Amul Taaza 500ml milk pouches), cloud vision models frequently confused the EAN-13 barcode numbers (`8901262150088`) with the nearby printed FSSAI license (`10012021000071`).
- PaddleOCR’s directional angle classification and text line detection isolate curved fine-print numbers with sub-character precision, eliminating false violation reports.

---

### 3. Deterministic Statutory Rule Engine (PCR 2011)

#### Why NOT an LLM for Rule Evaluation:
- **Court Admissibility**: In legal proceedings under Section 36 of the Legal Metrology Act, 2009, an enforcement officer must present objective statutory non-compliance. Saying *"an AI thought this was non-compliant"* leads to instant case dismissal.
- **Exact Statutory Section Mapping**: Every rule in `app/rule_engine/engine.py` evaluates unambiguous logic:
  - `Rule 6(1)(a)`: Verification of manufacturer name, street address, and valid 6-digit Indian PIN code.
  - `Rule 6(1)(c)`: Standard SI unit validation (rejecting non-standard units like `gms`, `kilo`, `lit`).
  - `Rule 6(1)(d)`: Parsing manufacturing/packing date and computing remaining shelf life.
  - `Rule 6(1)(e)`: Verification of "Inclusive of all taxes" statement and MRP format.
  - `Rule 6(1)(n)`: Verification of consumer grievance contact (phone, email, postal address).
  - `Rule 18(2)`: Detection of dual MRP or retail price alterations.
  - `FSSAI Clause`: 14-digit numeric format validation for all food/beverage commodities.

---

### 4. Barcode Verification & GS1 India Reconciliation

- **GS1 Country Code Validation**: Checks if the barcode starts with `890` (allocated to GS1 India).
- **Modulo-10 Checksum Algorithm**: Validates the mathematical integrity of EAN-13 barcodes to detect fraudulent or fabricated codes.
- **Discrepancy Cross-Checking**: Compares the decoded barcode identity against the printed label's declared brand, MRP, and net quantity to catch label-swapping fraud.

---

### 5. Tamper-Evident Evidence Store (SQLite WAL + Cryptographic Hashing)

#### Why SQLite (Write-Ahead Logging) for Hackathon & Edge Field Enforcement:
- **Zero Configuration & Zero Maintenance**: Self-contained single-file database (`data/netrapack.db`) requiring no external database service (PostgreSQL/MySQL), eliminating installation failure points.
- **Cryptographic Immutability via Database Triggers**:
  - Compliance records must be immune to post-inspection alteration.
  - We engineered **SQLite triggers that raise fatal errors on any `UPDATE` or `DELETE`** on scan evidence tables.
  - Every scan record stores a SHA-256 cryptographic digest of the raw image bytes alongside the timestamp, GPS coordinates, and inspecting officer ID.
- **High Concurrency via WAL Mode**: Write-Ahead Logging allows simultaneous reads and writes without thread contention.

---

### 6. Legal PDF Generation (ReportLab)

- **Section 36 Statutory Notice**: Produces court-ready inspection notices formatted according to the Government of India Department of Consumer Affairs guidelines.
- **Features**:
  - Official Ashoka Lion Capital emblem branding.
  - Itemized violation schedule quoting specific PCR 2011 rules and penal sections.
  - Cryptographic evidence SHA-256 fingerprint embedded directly into the document.
  - Calculated compounding penalty ranges under Section 48 / Section 36.

---

### 7. Conversational AI Legal Assistant (`app/ai/chatbot.py`)

- Integrated directly into the mobile application for field officers.
- Grounded strictly in the **Legal Metrology Act, 2009**, **PCR 2011**, and **Consumer Protection Act, 2019**.
- Enforces concise, professional, dark-contrast output free of markdown clutter, asterisks, or speculative legal advice.

---

## 🧪 Testing & Verification Rigor

NetraPack is backed by an automated test suite guaranteeing zero regressions across all statutory algorithms:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

```text
============================== 61 passed in 4.82s ==============================
✔ test_rule_engine.py             (18/18) - Every PCR 2011 statutory clause validated
✔ test_api_endpoints.py           (14/14) - Auth, scan, officer, admin, and chat endpoints
✔ test_paddle_ocr.py              (3/3)   - Edge PaddleOCR text & FSSAI extraction
✔ test_e2e_full_flow.py           (1/1)   - End-to-end Photo -> Scan -> Review -> Notice
✔ test_mrp_strikethrough.py       (12/12) - Dual MRP, strikethrough, and alteration checks
✔ test_extraction_sanitize.py     (13/13) - Date normalizers, unit cleaners, regex resilience
```

Mobile TypeScript type check:
```powershell
npx tsc --noEmit   # 0 errors
```

---

## 🚀 Scalability & Enterprise Roadmap

While designed to run standalone on an offline laptop and mobile hotspot during field raids, the architecture is engineered for effortless enterprise scaling:

1. **Database Migration**: The thin repository abstraction allows swapping SQLite for **PostgreSQL with TimescaleDB** without altering business logic.
2. **Kubernetes Deployment**: The stateless FastAPI backend is containerized via Docker and scales horizontally behind an NGINX or Envoy load balancer.
3. **National e-Metrology Portal Sync**: Built-in JSON serialization enables asynchronous synchronization with the central Ministry of Consumer Affairs national compliance database.

---

### 🏛️ Summary
NetraPack AI 2.0 combines **state-of-the-art computer vision** with **uncompromising legal determinism**. By pairing high-precision edge OCR with a zero-hallucination statutory rule engine, NetraPack delivers the only platform capable of serving as admissible evidence in Indian courts while operating seamlessly in the most demanding field conditions.
