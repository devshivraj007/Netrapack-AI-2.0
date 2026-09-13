import { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Alert,
  Linking,
} from "react-native";
import { useRouter } from "expo-router";
import { Header } from "../src/components/Header";
import { Button } from "../src/components/Button";
import { colors, font, radius, spacing, statusStyle } from "../src/theme";
import { getLastVerdict } from "../src/verdictStore";
import { session } from "../src/session";
import { confirmCategory, generateNotice, type VisionExtraction } from "../src/api";

const NCH_HELPLINE = "1800-11-4000";
const EJAGRITI_URL = "https://e-jagriti.gov.in/";

/** Is this a food/beverage product (drives the Health tab visibility)? */
function isFoodCategory(cat?: string): boolean {
  const c = (cat || "").toLowerCase();
  return c.includes("food") || c.includes("beverage");
}

/** Derive a simple expiry status from the extracted expiry date string. */
function expiryStatus(expiry?: string | null): { label: string; tone: "ok" | "warn" | "unknown" } {
  if (!expiry || !String(expiry).trim()) {
    return { label: "Expiry / best-before not detected on the label", tone: "unknown" };
  }
  const now = new Date();
  const parsed = new Date(expiry);
  if (!isNaN(parsed.getTime())) {
    if (parsed.getTime() < now.getTime()) {
      return { label: `Expired (${expiry}) — do not consume`, tone: "warn" };
    }
    return { label: `Within date (best before ${expiry})`, tone: "ok" };
  }
  // Unparseable but present — show it as-is for the officer to read.
  return { label: `Best before: ${expiry}`, tone: "ok" };
}

const CATEGORIES = [
  "food_and_beverage",
  "personal_care",
  "household",
  "electronics",
  "pharmaceutical",
  "baby_care",
  "other",
];

export default function Verdict() {
  const router = useRouter();
  const verdict = getLastVerdict();
  const [, force] = useState(0);
  useEffect(() => session.subscribe(() => force((n) => n + 1)), []);

  const isOfficer = session.isOfficer();
  const [confirmedCategory, setConfirmedCategory] = useState<string | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [working, setWorking] = useState(false);
  const [noticeInfo, setNoticeInfo] = useState<string | null>(null);
  const [shopName, setShopName] = useState("");

  const st = useMemo(() => statusStyle(verdict?.overall_status), [verdict]);

  if (!verdict) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <Header subtitle="Verdict" />
        <View style={styles.center}>
          <Text style={styles.muted}>No scan result available.</Text>
          <Button label="SCAN A PRODUCT" onPress={() => router.replace("/scan")} />
        </View>
      </View>
    );
  }

  const ve: VisionExtraction = verdict.vision_extraction ?? {};
  const aiCategory =
    verdict.ai_recognition?.category ||
    verdict.ai_recognition?.effective_category ||
    "general";
  const showHealth = isFoodCategory(confirmedCategory ?? aiCategory);
  const hasViolations = verdict.violations.length > 0;
  const exp = expiryStatus(ve.expiry_date);

  async function openExternal(url: string, label: string) {
    try {
      const ok = await Linking.canOpenURL(url);
      if (ok) await Linking.openURL(url);
      else Alert.alert(label, `Could not open: ${url}`);
    } catch {
      Alert.alert(label, `Could not open: ${url}`);
    }
  }

  async function doConfirm(category: string) {
    setWorking(true);
    try {
      await confirmCategory(
        verdict!.scan_id,
        category,
        session.get().userId ?? "officer",
        session.get().token ?? undefined,
      );
      setConfirmedCategory(category);
      setChoosing(false);
      Alert.alert("Category confirmed", `Confirmed as: ${category}`);
    } catch (e) {
      Alert.alert("Confirm failed", e instanceof Error ? e.message : "Error");
    } finally {
      setWorking(false);
    }
  }

  async function doGenerateNotice() {
    setWorking(true);
    setNoticeInfo(null);
    try {
      const res = await generateNotice(
        verdict!.scan_id,
        {
          shopName: shopName.trim() || "Unspecified establishment",
          inspectorId: session.get().userId ?? "officer",
          gpsCoordinates: "0.0,0.0",
          productBarcode: undefined,
        },
        session.get().token ?? undefined,
      );
      setNoticeInfo(
        `Notice generated: ${res.file_name ?? "(saved on server)"}\nEvidence hash: ${
          (res.evidence_sha256 ?? "").slice(0, 16)
        }…`,
      );
    } catch (e) {
      Alert.alert("Notice failed", e instanceof Error ? e.message : "Error");
    } finally {
      setWorking(false);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="Compliance Verdict" />
      <ScrollView contentContainerStyle={styles.body}>
        {/* GIGW status block: small breadcrumb label above the big status */}
        <View style={[styles.banner, { backgroundColor: st.bg }]}>
          <Text style={styles.bannerCrumb}>{st.breadcrumb}</Text>
          <Text style={styles.bannerLabel}>{st.label}</Text>
          <Text style={styles.bannerSub}>
            {verdict.rules_passed}/{verdict.rules_checked} checks passed
          </Text>
        </View>

        {/* Official report container */}
        <View style={styles.report}>
          <Text style={styles.reportTitle}>EXTRACTED DECLARATIONS</Text>
          <Field label="Maximum Retail Price (MRP)" value={money(ve.mrp)} />
          {ve.mrp_is_ambiguous ? (
            <Text style={styles.ambiguous}>
              Multiple prices detected — flagged for manual review.
            </Text>
          ) : null}
          <Field label="Net Quantity" value={ve.net_quantity} />
          <Field label="Unit Sale Price" value={ve.unit_sale_price != null ? `Rs ${ve.unit_sale_price}` : undefined} />
          <Field label="Mfg / Packed Date" value={ve.mfd_pkd_date} />
          <Field label="Expiry / Best Before" value={ve.expiry_date} />
          <Field label="FSSAI Licence No." value={ve.fssai_license_number} />
          <Field label="Country of Origin" value={ve.country_of_origin} />
          <Field label="Manufacturer" value={ve.manufacturer_details} />
        </View>

        {/* Health / Nutrition tab — food & beverage only */}
        {showHealth ? (
          <View style={styles.healthWrap}>
            <View style={styles.healthHead}>
              <Text style={styles.reportTitle}>HEALTH & SAFETY</Text>
              <View style={styles.foodTag}>
                <Text style={styles.foodTagText}>FOOD / BEVERAGE</Text>
              </View>
            </View>

            {/* Expiry status */}
            <View style={styles.healthRow}>
              <Text style={styles.healthLabel}>Expiry status</Text>
              <Text
                style={[
                  styles.healthValue,
                  exp.tone === "warn" ? { color: colors.red } :
                  exp.tone === "ok" ? { color: colors.green } :
                  { color: colors.textMuted },
                ]}
              >
                {exp.label}
              </Text>
            </View>

            {/* FSSAI presence (food safety marker) */}
            <View style={styles.healthRow}>
              <Text style={styles.healthLabel}>FSSAI licence</Text>
              <Text
                style={[
                  styles.healthValue,
                  ve.fssai_license_number ? { color: colors.green } : { color: colors.red },
                ]}
              >
                {ve.fssai_license_number
                  ? `Declared: ${ve.fssai_license_number}`
                  : "Not declared — mandatory for food products (FSS Act 2006)"}
              </Text>
            </View>

            {/* Allergen / nutrition — honest scope note */}
            <Text style={styles.healthNote}>
              Nutrition table and allergen details are printed on the pack and
              should be read directly. Automated nutrition extraction is not yet
              available; this section reports the safety markers we can verify
              (expiry and FSSAI licensing).
            </Text>
          </View>
        ) : null}

        {/* Readability / font-size advisory (LMPC Rule 9 area) */}
        {verdict.readability ? (
          <View
            style={[
              styles.readWrap,
              verdict.readability.assessed && verdict.readability.likely_too_small
                ? styles.readWarn
                : styles.readInfo,
            ]}
          >
            <Text style={styles.reportTitle}>FONT-SIZE / READABILITY (ADVISORY)</Text>
            {verdict.readability.assessed ? (
              <>
                <Text
                  style={[
                    styles.readStatus,
                    verdict.readability.likely_too_small
                      ? { color: colors.amber }
                      : { color: colors.green },
                  ]}
                >
                  {verdict.readability.likely_too_small
                    ? "⚠ Text may be below the minimum legible size — verify manually"
                    : "✓ Declaration text appears adequately legible"}
                </Text>
                {verdict.readability.note ? (
                  <Text style={styles.readNote}>{verdict.readability.note}</Text>
                ) : null}
              </>
            ) : (
              <Text style={styles.readNote}>
                {verdict.readability.note ||
                  "Readability could not be assessed for this scan."}
              </Text>
            )}
            <Text style={styles.readDisclaimer}>
              Proportional estimate only — not a certified mm measurement of LMPC
              Rule 9 character height.
            </Text>
          </View>
        ) : null}

        {/* AI category (suggested / confirmed) */}
        <View style={styles.catRow}>
          <Text style={styles.catLabel}>Product category</Text>
          <View style={styles.catBadge}>
            <Text style={styles.catBadgeText}>
              {(confirmedCategory ?? aiCategory).toUpperCase()}
            </Text>
          </View>
          <Text style={styles.catStatus}>
            {confirmedCategory ? "Officer-confirmed" : "AI-suggested, not confirmed"}
          </Text>
        </View>

        {/* Violations — bordered official list */}
        <View style={styles.violWrap}>
          <Text style={styles.reportTitle}>STATUTORY VIOLATIONS</Text>
          {verdict.violations.length === 0 ? (
            <Text style={styles.noViol}>No violations recorded for this scan.</Text>
          ) : (
            verdict.violations.map((v, i) => (
              <View key={i} style={styles.violItem}>
                <Text style={styles.violField}>{(v.field ?? "").toUpperCase()}</Text>
                {v.rule_citation ? (
                  <Text style={styles.violCite}>{v.rule_citation}</Text>
                ) : null}
                {v.description ? (
                  <Text style={styles.violDesc}>{v.description}</Text>
                ) : null}
              </View>
            ))
          )}
        </View>

        {/* Consumer redressal actions — shown when a violation is found */}
        {hasViolations ? (
          <View style={styles.redressWrap}>
            <Text style={styles.reportTitle}>CONSUMER ACTIONS</Text>
            <Text style={styles.muted}>
              This product has compliance issues. You can report it:
            </Text>
            <Button
              label={`CALL NCH HELPLINE (${NCH_HELPLINE})`}
              variant="secondary"
              onPress={() => openExternal(`tel:${NCH_HELPLINE.replace(/-/g, "")}`, "National Consumer Helpline")}
            />
            <Button
              label="FILE COMPLAINT ON e-JAGRITI"
              variant="outline"
              onPress={() => openExternal(EJAGRITI_URL, "e-Jagriti")}
            />
          </View>
        ) : null}

        {/* Ask the compliance chatbot about this result */}
        <Button
          label="ASK ABOUT THIS RESULT"
          variant="outline"
          onPress={() =>
            router.push({ pathname: "/chat", params: { scanId: verdict!.scan_id } })
          }
        />

        {/* Officer actions */}
        {isOfficer ? (
          <View style={styles.officer}>
            <Text style={styles.reportTitle}>OFFICER ACTIONS</Text>
            {!confirmedCategory && !choosing ? (
              <View style={{ gap: spacing.sm }}>
                <Text style={styles.muted}>
                  Confirm the AI-suggested category "{aiCategory}" or change it.
                </Text>
                <Button
                  label={`CONFIRM: ${aiCategory.toUpperCase()}`}
                  onPress={() => doConfirm(aiCategory)}
                  loading={working}
                />
                <Button label="CHANGE CATEGORY" variant="outline" onPress={() => setChoosing(true)} />
              </View>
            ) : null}

            {choosing ? (
              <View style={{ gap: spacing.sm }}>
                <Text style={styles.muted}>Select the correct category:</Text>
                {CATEGORIES.map((c) => (
                  <Button key={c} label={c.toUpperCase()} variant="outline" onPress={() => doConfirm(c)} />
                ))}
              </View>
            ) : null}

            {confirmedCategory ? (
              <View style={{ gap: spacing.sm }}>
                <Text style={styles.confirmed}>
                  ✓ Category confirmed as {confirmedCategory.toUpperCase()}
                </Text>
                <Text style={styles.muted}>Establishment / shop name (for the notice):</Text>
                <TextInput
                  value={shopName}
                  onChangeText={setShopName}
                  placeholder="e.g. Sharma Kirana Store, MG Road"
                  placeholderTextColor={colors.textMuted}
                  style={styles.input}
                />
                <Button label="GENERATE SECTION 36 NOTICE" variant="danger" onPress={doGenerateNotice} loading={working} />
                {noticeInfo ? <Text style={styles.notice}>{noticeInfo}</Text> : null}
              </View>
            ) : null}
          </View>
        ) : null}

        <Button label="SCAN ANOTHER" variant="outline" onPress={() => router.replace("/scan")} />
      </ScrollView>
    </View>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  const shown = value && String(value).trim() ? String(value) : "Not declared";
  const missing = !(value && String(value).trim());
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <Text style={[styles.fieldValue, missing ? styles.fieldMissing : null]}>{shown}</Text>
    </View>
  );
}

function money(v?: number | null): string | undefined {
  return v != null ? `Rs ${v}` : undefined;
}

const styles = StyleSheet.create({
  body: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.lg, padding: spacing.xl },
  muted: { color: colors.textMuted, fontSize: font.body, lineHeight: 22 },

  banner: {
    borderRadius: radius.md,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
  },
  bannerCrumb: {
    color: colors.white,
    fontSize: font.breadcrumb,
    fontWeight: "700",
    letterSpacing: 0.5,
    opacity: 0.85,
    marginBottom: 2,
  },
  bannerLabel: { color: colors.white, fontSize: font.statusBanner, fontWeight: "900", letterSpacing: 0.5 },
  bannerSub: { color: colors.white, fontSize: font.label, fontWeight: "700", marginTop: 2, opacity: 0.95 },

  report: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: colors.navy,
    borderRadius: radius.md,
    padding: spacing.lg,
  },
  reportTitle: {
    fontSize: font.label,
    fontWeight: "900",
    color: colors.navy,
    letterSpacing: 1,
    marginBottom: spacing.md,
  },
  field: { paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  fieldLabel: { fontSize: font.small, color: colors.textMuted, fontWeight: "700", textTransform: "uppercase" },
  fieldValue: { fontSize: font.h3, color: colors.text, fontWeight: "700", marginTop: 2 },
  fieldMissing: { color: colors.textMuted, fontStyle: "italic", fontWeight: "600" },
  ambiguous: { color: colors.amber, fontSize: font.small, fontWeight: "700", marginTop: spacing.xs },

  healthWrap: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: colors.teal,
    borderRadius: radius.md,
    padding: spacing.lg,
  },
  healthHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  foodTag: {
    backgroundColor: colors.tealSoft,
    borderColor: colors.teal,
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  foodTagText: { color: colors.tealDark, fontWeight: "800", fontSize: 10, letterSpacing: 0.5 },
  healthRow: { paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  healthLabel: { fontSize: font.small, color: colors.textMuted, fontWeight: "700", textTransform: "uppercase" },
  healthValue: { fontSize: font.body, fontWeight: "700", marginTop: 2, lineHeight: 20 },
  healthNote: { fontSize: font.small, color: colors.textMuted, fontStyle: "italic", marginTop: spacing.sm, lineHeight: 16 },

  redressWrap: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: colors.red,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },

  readWrap: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderRadius: radius.md,
    padding: spacing.lg,
  },
  readInfo: { borderColor: colors.border },
  readWarn: { borderColor: colors.amber },
  readStatus: { fontSize: font.body, fontWeight: "800", marginBottom: spacing.xs },
  readNote: { fontSize: font.small, color: colors.text, lineHeight: 18 },
  readDisclaimer: {
    fontSize: font.small,
    color: colors.textMuted,
    fontStyle: "italic",
    marginTop: spacing.xs,
    lineHeight: 16,
  },

  catRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    flexWrap: "wrap",
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.md,
  },
  catLabel: { fontSize: font.small, color: colors.textMuted, fontWeight: "700" },
  catBadge: { backgroundColor: colors.lavender, borderColor: colors.lavenderBorder, borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  catBadgeText: { color: colors.navy, fontWeight: "800", fontSize: font.small },
  catStatus: { fontSize: font.small, color: colors.textMuted, fontStyle: "italic" },

  violWrap: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.lg,
  },
  noViol: { color: colors.green, fontWeight: "700", fontSize: font.body },
  violItem: {
    borderLeftWidth: 4,
    borderLeftColor: colors.red,
    backgroundColor: "#FBEeee",
    padding: spacing.md,
    borderRadius: radius.sm,
    marginBottom: spacing.sm,
  },
  violField: { fontSize: font.body, fontWeight: "900", color: colors.red },
  violCite: { fontSize: font.small, color: colors.navyDark, fontWeight: "700", marginTop: 2 },
  violDesc: { fontSize: font.label, color: colors.text, marginTop: spacing.xs, lineHeight: 18 },

  officer: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: colors.teal,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.md,
  },
  confirmed: { color: colors.green, fontWeight: "800", fontSize: font.body },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.md,
    fontSize: font.body,
    color: colors.text,
    backgroundColor: colors.white,
  },
  notice: {
    color: colors.tealDark,
    backgroundColor: colors.tealSoft,
    borderColor: colors.teal,
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: spacing.md,
    fontSize: font.small,
    fontWeight: "700",
  },
});
