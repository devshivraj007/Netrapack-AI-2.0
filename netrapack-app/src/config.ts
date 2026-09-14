import Constants from "expo-constants";

/**
 * API base URL — SINGLE place to change for local network testing.
 *
 * Expo Go on a physical phone CANNOT reach "localhost" (that points at the
 * phone, not your PC). Set this to your PC's LAN IP, e.g.:
 *   http://192.168.1.5:8000/api/v1
 *
 * Priority:
 *   1. EXPO_PUBLIC_API_BASE_URL env var (if set), else
 *   2. expo.extra.apiBaseUrl in app.json, else
 *   3. the fallback below.
 *
 * Find your PC IP: run `ipconfig` (Windows) and use the IPv4 address on the
 * same Wi-Fi as your phone. Make sure the backend runs with
 *   uvicorn app.main:app --host 0.0.0.0 --port 8000
 * so it's reachable from the LAN.
 */
const FALLBACK = "http://10.86.20.33:8000/api/v1";

export const API_BASE_URL: string =
  process.env.EXPO_PUBLIC_API_BASE_URL ||
  (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl ||
  FALLBACK;
