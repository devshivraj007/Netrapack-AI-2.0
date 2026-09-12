import type { ScanVerdict } from "./api";

/**
 * Tiny module-level holder for the most recent verdict, so the Scan screen can
 * hand it to the Verdict screen without serializing a large object through
 * navigation params.
 */
let lastVerdict: ScanVerdict | null = null;

export function setLastVerdict(v: ScanVerdict | null) {
  lastVerdict = v;
}

export function getLastVerdict(): ScanVerdict | null {
  return lastVerdict;
}
