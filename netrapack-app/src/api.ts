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

export type ScanVerdict = {
  scan_id: string;
  overall_status: string;
  rules_passed: number;
  rules_checked: number;
  violations: Violation[];
  vision_extraction?: VisionExtraction | null;
  readability?: ReadabilityInfo | null;
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
 * Authenticate against the backend and return a real session token.
 * Contract matches app/api/auth_routes.py: POST /auth/login {username, password}.
 */
export async function loginRequest(
  username: string,
  password: string,
): Promise<LoginResult> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
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
 * Upload a captured photo to the backend and return the verdict.
 * Matches the backend contract: multipart with scan_id (Form) + image (File).
 */
export async function processPhoto(
  photoUri: string,
  opts?: { scanId?: string; barcode?: string },
): Promise<ScanVerdict> {
  const scanId = opts?.scanId ?? newScanId();
  const form = new FormData();
  form.append("scan_id", scanId);
  if (opts?.barcode) form.append("barcode", opts.barcode);
  // React Native FormData file object.
  form.append("image", {
    uri: photoUri,
    name: "front.jpg",
    type: "image/jpeg",
  } as unknown as Blob);

  const res = await fetch(`${API_BASE_URL}/scan/process-photo`, {
    method: "POST",
    body: form,
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Scan failed (HTTP ${res.status})`);
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
  const res = await fetch(`${API_BASE_URL}/officer/confirm-category`, {
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
): Promise<{ status: string; file_name?: string; evidence_sha256?: string }> {
  const res = await fetch(`${API_BASE_URL}/officer/generate-notice`, {
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
  scanId: string,
  question: string,
): Promise<ChatAnswer> {
  const res = await fetch(`${API_BASE_URL}/chat/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ scan_id: scanId, question }),
  });
  if (res.status === 404) {
    throw new Error("This scan was not found on the server. Try scanning again.");
  }
  if (!res.ok) throw new Error(`Chat failed (HTTP ${res.status})`);
  return (await res.json()) as ChatAnswer;
}
