/**
 * NetraPack design system — modeled on official Indian government citizen apps
 * (DigiLocker / UMANG / Aarogya Setu), NOT a generic startup template.
 *
 * Principles encoded here:
 *  - Navy blue primary; saffron/orange as a SPARING accent (badges/active states).
 *  - Bold, solid status colors (green/red/amber) for immediate legibility.
 *  - Rectangular / minimally-rounded buttons, solid navy fill for primary.
 *  - Larger-than-default type for key info (MRP, status, violations).
 *  - No purple gradients, glassmorphism, pastels, or playful icons.
 */

export const colors = {
  // Brand
  navy: "#0B2F6B", // primary
  navyDark: "#082352",
  saffron: "#FF8A00", // accent — use sparingly
  saffronSoft: "#FFF1E0",

  // Surfaces
  bg: "#F4F6FA",
  card: "#FFFFFF",
  border: "#D5DBE6",
  headerBorder: "#C9D2E0",

  // Text
  text: "#14213D",
  textMuted: "#5A6B85",
  textOnNavy: "#FFFFFF",

  // Status (solid, bold — used on banners/badges)
  green: "#1B7F3B",
  greenBg: "#1B7F3B",
  red: "#B3261E",
  redBg: "#B3261E",
  amber: "#B26A00",
  amberBg: "#C9820A",
  white: "#FFFFFF",
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const radius = {
  // Minimally rounded — official, not playful.
  sm: 4,
  md: 6,
  lg: 8,
};

export const font = {
  // Larger-than-default for legibility.
  h1: 26,
  h2: 20,
  h3: 17,
  body: 16,
  label: 13,
  small: 12,
  statusBanner: 22,
};

/** Map an overall_status string to its solid banner color + label. */
export function statusStyle(status?: string): {
  bg: string;
  label: string;
} {
  const s = (status || "").toLowerCase();
  if (s === "fully_compliant" || s === "compliant") {
    return { bg: colors.greenBg, label: "COMPLIANT" };
  }
  if (s === "non_compliant") {
    return { bg: colors.redBg, label: "NON-COMPLIANT" };
  }
  // needs_manual_review or anything else
  return { bg: colors.amberBg, label: "NEEDS REVIEW" };
}
