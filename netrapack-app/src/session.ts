/**
 * Simple in-memory session for officer/admin auth.
 *
 * CHECKPOINT 3: login() calls the real backend /auth/login endpoint and stores
 * the returned signed token + role. The rest of the app reads token/role from
 * here, so screens didn't need to change when we swapped out the CP1 hardcoded
 * check. The token is attached as `Authorization: Bearer <token>` on the
 * officer/admin API calls (see api.ts confirmCategory/generateNotice).
 */

import { loginRequest } from "./api";

export type Role = "officer" | "admin" | null;

type SessionState = {
  role: Role;
  token: string | null;
  userId: string | null;
};

const state: SessionState = { role: null, token: null, userId: null };
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

export const session = {
  get(): SessionState {
    return { ...state };
  },
  isOfficer(): boolean {
    return state.role === "officer" || state.role === "admin";
  },
  subscribe(fn: () => void): () => void {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
  setSession(role: Role, token: string | null, userId: string | null) {
    state.role = role;
    state.token = token;
    state.userId = userId;
    emit();
  },
  logout() {
    state.role = null;
    state.token = null;
    state.userId = null;
    emit();
  },
};

/**
 * CP3 real login: authenticates against the backend /auth/login endpoint and
 * stores the returned signed token + role. Returns { ok: true } on success.
 *
 * Seeded demo credentials (server-side, PBKDF2-hashed):
 *   officer / netra123  -> role "officer"
 *   admin   / admin123  -> role "admin"
 */
export async function login(
  username: string,
  password: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await loginRequest(username.trim(), password);
    const role: Role = res.role === "admin" ? "admin" : "officer";
    session.setSession(role, res.token, res.username);
    return { ok: true };
  } catch (e) {
    const msg =
      e instanceof Error ? e.message : "Login failed. Please try again.";
    return { ok: false, error: msg };
  }
}
