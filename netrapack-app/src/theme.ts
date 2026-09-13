/**
 * NetraPack design system — grounded in the official Government of India design
 * system (GIGW 3.0 via the DBIM ToolKit), as used by MeitY / national portals.
 *
 * Observed GIGW/DBIM patterns encoded here:
 *  - Deep navy/indigo header bar with a circular GOI-style emblem + white bold
 *    app name; minimal clutter.
 *  - Solid, bold status blocks: teal-toned for compliant, maroon/red for
 *    non-compliant, amber for needs-review — with a small breadcrumb-style
 *    label ABOVE the main status text.
 *  - White cards with a subtle border, small corner radius, a corner tag/badge,
 *    bold title + muted description, arranged on a light page.
 *  - Darker teal accent bar for secondary nav/tabs directly under the header.
 *  - Light lavender / pale-purple highlight for active/selected items.
 *  - Light page backgrounds everywhere; deep colors only in header/banners/accents.
 */

export const colors = {
  // Brand — GIGW deep indigo/navy
  navy: "#1A1464", // primary header / deep indigo
  navyDark: "#120E4A",
  indigo: "#1A1464",
  indigoSoft: "#E8E6F5",

  // Teal accent (secondary nav bar, compliant tone)
  teal: "#0E7C7B",
  tealDark: "#0A5F5E",
  tealSoft: "#E1F1F1",

  // Saffron accent — sparing (badges/active highlights only)
  saffron: "#FF8A00",
  saffronSoft: "#FFF1E0",

  // Lavender selection highlight (active/selected states)
  lavender: "#EDE9FB",
  lavenderBorder: "#C9BFF0",

  // Surfaces — light everywhere
  bg: "#F5F6FA",
  card: "#FFFFFF",
  border: "#DCE1EC",
  headerBorder: "#120E4A",

  // Text
  text: "#1B1B2F",
  textMuted: "#5A6B85",
  textOnNavy: "#FFFFFF",

  // Status (solid, bold — used on banners/badges)
  green: "#0E7C7B", // teal-toned "compliant"
  greenBg: "#0E7C7B",
  greenSoft: "#E1F1F1",
  red: "#8E1B2E", // maroon "non-compliant"
  redBg: "#8E1B2E",
  redSoft: "#F7E7EA",
  amber: "#B26A00",
  amberBg: "#C9820A",
  amberSoft: "#FBEFD8",
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
  // Small corner radius per GIGW cards — official, not playful.
  sm: 6,
  md: 8,
  lg: 12,
};

export const font = {
  // Larger-than-default for legibility.
  h1: 26,
  h2: 20,
  h3: 17,
  body: 16,
  label: 13,
  small: 12,
  statusBanner: 24,
  breadcrumb: 12,
};

/**
 * Map an overall_status string to its solid banner color, a big status label,
 * and a small breadcrumb-style label shown ABOVE it (GIGW status-block pattern).
 */
export function statusStyle(status?: string): {
  bg: string;
  soft: string;
  label: string;
  breadcrumb: string;
} {
  const s = (status || "").toLowerCase();
  if (s === "fully_compliant" || s === "compliant") {
    return {
      bg: colors.greenBg,
      soft: colors.greenSoft,
      label: "COMPLIANT",
      breadcrumb: "Compliance Check Result",
    };
  }
  if (s === "non_compliant") {
    return {
      bg: colors.redBg,
      soft: colors.redSoft,
      label: "NON-COMPLIANT",
      breadcrumb: "Compliance Check Result",
    };
  }
  return {
    bg: colors.amberBg,
    soft: colors.amberSoft,
    label: "NEEDS REVIEW",
    breadcrumb: "Compliance Check Result",
  };
}
