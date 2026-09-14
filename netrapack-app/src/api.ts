import { API_BASE_URL } from "./config";

/** Shape of the backend scan verdict (only the fields the app uses). */
export type Violation = {
  field?: string;
  rule_citation?: string;
  description?: string;
};

export type VisionExtraction = {
  mrp?: number | null;
  mrp_all_prices?: number[];
  mrp_is_ambiguous?: boolean;
  net_quantity?: string | null;
  unit_sale_price?: number | null;
  mfd_pkd_date?: string | null;
  expiry_date?: string | null;
  fssai_license_number?: string | null;
  manufacturer_details?: string | null;
  country_of_origin?: string | null;
  consumer_care_details?: string | null;
  unclear_fields?: string[];
};

export type ReadabilityInfo = {
  assessed: boolean;
  approximate?: boolean;
  median_char_px?: number;
  image_height_px?: number;
  char_height_fraction?: number;
  likely_too_small?: boolean;
  note?: string;
};

export type FieldComparison = {
  field: string;
  reference?: string | null;
  declared?: string | null;
  status: "agree" | "mismatch" | "not_available";
};

export type BarcodeVerification = {
  scanned_barcode?: string | null;
  matched: boolean;
  product_code?: string | null;
  product_name?: string | null;
  comparisons: FieldComparison[];
  note?: string | null;
  gs1_prefix?: string | null;
  gs1_country?: string | null;
  origin_matches_barcode?: boolean | null;
};

export type ScanVerdict = {
  scan_id: string;
  overall_status: string;
  rules_passed: number;
  rules_checked: number;
  violations: Violation[];
  parsed_fields?: Record<string, any>;
  vision_extraction?: VisionExtraction | null;
  readability?: ReadabilityInfo | null;
  barcode_verification?: BarcodeVerification | null;
  ai_recognition?: {
    category?: string;
    effective_category?: string;
    confidence?: number;
    confirmation_status?: string;
  } | null;
  metadata?: {
    processing_ms?: number;
    ai_model_used?: string | null;
    ai_level?: string;
    connectivity_state?: string;
    extraction_source?: string;
    online_offline?: string;
    image_hash?: string | null;
  } | null;
};

function newScanId(): string {
  return `app-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
}

/** Backend login response (POST /auth/login). */
export type LoginResult = {
  token: string;
  role: string;
  username: string;
  display_name?: string | null;
};

/**
 * Safe fetch wrapper that intercepts React Native "Network request failed"
 * and produces an actionable error message with IP and Hotspot guidance.
 */
async function safeFetch(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (
      msg.includes("Network request failed") ||
      msg.includes("Failed to fetch") ||
      msg.includes("NetworkError")
    ) {
      throw new Error(
        `Cannot reach backend server at:\n${API_BASE_URL}\n\nPlease check:\n1. Mobile Hotspot 'LAPTOP-9DFJJCB4 6739' is active on PC.\n2. Your phone is connected to this Hotspot.\n3. Backend is running on port 8000.`,
      );
    }
    throw err;
  }
}

/**
 * Authenticate against the backend and return a real session token.
 * Contract matches app/api/auth_routes.py: POST /auth/login {username, password}.
 */
export async function loginRequest(
  username: string,
  password: string,
): Promise<LoginResult> {
  const res = await safeFetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ username, password }),
  });
  if (res.status === 401) {
    throw new Error("Invalid username or password.");
  }
  if (!res.ok) {
    throw new Error(`Login failed (HTTP ${res.status})`);
  }
  return (await res.json()) as LoginResult;
}

/**
 * Upload 1–4 captured photos to the backend and return one merged verdict.
 * Matches the backend contract: multipart with scan_id (Form) + images[] (Files).
 */
export async function processPhotos(
  photoUris: string[],
  opts?: { scanId?: string; barcode?: string },
): Promise<ScanVerdict> {
  const scanId = opts?.scanId ?? newScanId();
  const form = new FormData();
  form.append("scan_id", scanId);
  if (opts?.barcode) form.append("barcode", opts.barcode);
  // React Native FormData accepts multiple values for the same key.
  for (let i = 0; i < Math.min(photoUris.length, 4); i++) {
    form.append("images", {
      uri: photoUris[i],
      name: `photo_${i}.jpg`,
      type: "image/jpeg",
    } as unknown as Blob);
  }

  const res = await safeFetch(`${API_BASE_URL}/scan/process-photo`, {
    method: "POST",
    body: form,
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Scan failed (HTTP ${res.status})`);
  }
  return (await res.json()) as ScanVerdict;
}

/**
 * Convenience wrapper: upload a single photo (backward compat).
 * @deprecated prefer processPhotos([uri])
 */
export async function processPhoto(
  photoUri: string,
  opts?: { scanId?: string; barcode?: string },
): Promise<ScanVerdict> {
  return processPhotos([photoUri], opts);
}

/**
 * Send typed/edited text fields to the rule engine.
 * Matches the backend contract: POST /scan/process
 */
export async function processTextScan(req: {
  scan_id: string;
  barcode?: string;
  product_category?: string;
  mrp_declaration?: string;
  net_quantity_declaration?: string;
  unit_sale_price_declaration?: string;
  manufacturing_date_declaration?: string;
  expiry_date_declaration?: string;
  fssai_license_number?: string;
  manufacturer_name_address?: string;
  country_of_origin_declaration?: string;
  consumer_care_details?: string;
}): Promise<ScanVerdict> {
  const res = await safeFetch(`${API_BASE_URL}/scan/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Text scan processing failed (HTTP ${res.status})`);
  }
  return (await res.json()) as ScanVerdict;
}

/** Officer: confirm/override the AI-suggested category. */
export async function confirmCategory(
  scanId: string,
  confirmedCategory: string,
  inspectorId: string,
  token?: string,
): Promise<{ status: string; confirmed_category: string }> {
  const res = await safeFetch(`${API_BASE_URL}/officer/confirm-category`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      scan_id: scanId,
      confirmed_category: confirmedCategory,
      inspector_id: inspectorId,
    }),
  });
  if (!res.ok) throw new Error(`Confirm failed (HTTP ${res.status})`);
  return await res.json();
}

/** Officer: generate the Section 36 notice PDF (returns server-side file info). */
export async function generateNotice(
  scanId: string,
  info: {
    shopName: string;
    inspectorId: string;
    gpsCoordinates: string;
    productBarcode?: string;
  },
  token?: string,
): Promise<{ status: string; file_name: string; evidence_sha256: string }> {
  const res = await safeFetch(`${API_BASE_URL}/officer/generate-notice`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      scan_id: scanId,
      shop_name: info.shopName,
      inspector_id: info.inspectorId,
      gps_coordinates: info.gpsCoordinates,
      product_barcode: info.productBarcode,
    }),
  });
  if (res.status === 403) {
    throw new Error("Category must be confirmed before generating a notice.");
  }
  if (!res.ok) throw new Error(`Notice generation failed (HTTP ${res.status})`);
  return await res.json();
}

/** Chatbot answer about a specific scan (POST /chat/query). */
export type ChatAnswer = {
  scan_id: string;
  question: string;
  answer: string;
  ai_source: string;
  ai_level: string;
  model?: string | null;
};

/**
 * Ask a plain-language question about a scan's compliance.
 * Contract matches app/api/chat_routes.py: POST /chat/query {scan_id, question}.
 */
export async function chatQuery(
  scanId: string | undefined,
  question: string,
): Promise<ChatAnswer> {
  const sid = (scanId || "general").trim();
  const res = await safeFetch(`${API_BASE_URL}/chat/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ scan_id: sid, question }),
  });
  if (res.status === 404) {
    throw new Error("This scan was not found on the server. Try scanning again.");
  }
  if (!res.ok) throw new Error(`Chat failed (HTTP ${res.status})`);
  return (await res.json()) as ChatAnswer;
}

/** A scan/report summary row from the search endpoint. */
export type ReportRow = {
  scan_id: string;
  created_at?: string;
  overall_status?: string;
  rules_passed?: number;
  rules_checked?: number;
  ai_category?: string | null;
  investigation_status?: string | null;
};

/**
 * Search/filter scans & reports (officer-only). Wraps GET /admin/reports.
 * Contract: query params q | status | scan_id | product_name | date_from/to,
 * response { count, reports: [...] }. Requires a Bearer token (officer/admin).
 */
export async function searchReports(
  opts: { q?: string; status?: string; limit?: number },
  token?: string,
): Promise<{ count: number; reports: ReportRow[] }> {
  const params = new URLSearchParams();
  if (opts.q) params.set("q", opts.q);
  if (opts.status) params.set("status", opts.status);
  params.set("limit", String(opts.limit ?? 50));

  const res = await safeFetch(`${API_BASE_URL}/admin/reports?${params.toString()}`, {
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (res.status === 401 || res.status === 403) {
    throw new Error("Officer login required to search records.");
  }
  if (!res.ok) throw new Error(`Search failed (HTTP ${res.status})`);
  return (await res.json()) as { count: number; reports: ReportRow[] };
}
