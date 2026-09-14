import { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Alert,
  Linking,
  Platform,
  Pressable,
  Share,
} from "react-native";
import { useRouter } from "expo-router";
import { Header } from "../src/components/Header";
import { Button } from "../src/components/Button";
import { colors, font, radius, spacing, statusStyle } from "../src/theme";
import { getLastVerdict } from "../src/verdictStore";
import { session } from "../src/session";
import { confirmCategory, generateNotice, type VisionExtraction } from "../src/api";
import { API_BASE_URL } from "../src/config";

const NCH_HELPLINE = "1800-11-4000";
// e-Jagriti was merged into the main NCH consumer complaint portal.
const EJAGRITI_URL = "https://consumerhelpline.gov.in/";

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
  const [noticeInfo, setNoticeInfo] = useState<{ filename: string; hash: string } | null>(null);
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
  const unclearFields: string[] = ve.unclear_fields || [];
  const isUnclear = (fieldKey: string, ruleKey?: string) => {
    return (
      unclearFields.includes(fieldKey) ||
      (ruleKey ? unclearFields.includes(ruleKey) : false) ||
      Boolean(verdict.parsed_fields?.[ruleKey || fieldKey]?.parsed?.needs_verification)
    );
  };
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
          productBarcode: verdict!.barcode_verification?.scanned_barcode ?? undefined,
        },
        session.get().token ?? undefined,
      );
      setNoticeInfo({ filename: res.file_name, hash: res.evidence_sha256 });
    } catch (e) {
      Alert.alert("Notice failed", e instanceof Error ? e.message : "Error");
    } finally {
      setWorking(false);
    }
  }

  async function shareSummary() {
    if (!verdict) return;
    const vioList = verdict.violations.length > 0
      ? verdict.violations.map((v, i) => `${i + 1}. [${v.field}] ${v.description} (${v.rule_citation})`).join("\n")
      : "No violations detected. Product is fully compliant.";
    const text = [
      "NETRAPACK STATUTORY COMPLIANCE INSPECTION SUMMARY",
      "Department of Consumer Affairs, Government of India",
      "--------------------------------------------------",
      `Scan ID: ${verdict.scan_id}`,
      `Status: ${verdict.overall_status.toUpperCase()}`,
      `Rules Passed: ${verdict.rules_passed} / ${verdict.rules_checked}`,
      `Barcode: ${verdict.barcode_verification?.scanned_barcode || "N/A"}`,
      `GS1 Origin: ${verdict.barcode_verification?.gs1_country || "N/A"}`,
      "",
      "VIOLATIONS / FINDINGS:",
      vioList,
      "",
      `Evidence SHA-256: ${verdict.metadata?.image_hash || "Secured in custody record"}`,
      `Verified via NetraPack AI Inspection Portal`,
    ].join("\n");

    try {
      await Share.share({ message: text, title: `NetraPack Compliance Report #${verdict.scan_id}` });
    } catch {
      // dismissed
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

        {/* PDF Compliance Report Download Card */}
        <View style={styles.downloadCard}>
          <Text style={styles.downloadTitle}>STATUTORY COMPLIANCE REPORT</Text>
          <Text style={styles.downloadSub}>
            Official Legal Metrology inspection record with evidence hash &amp; violation breakdown.
          </Text>
          <Button
            label="📄  DOWNLOAD COMPLIANCE REPORT (PDF)"
            onPress={() =>
              openExternal(
                `${API_BASE_URL}/scan/${verdict.scan_id}/report-pdf`,
                "Download Compliance Report"
              )
            }
          />
          <View style={styles.downloadCardBtnRow}>
            <View style={{ flex: 1 }}>
              <Button
                label="✏️  EDIT FIELDS"
                variant="outline"
                onPress={() => router.push("/review-fields")}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Button
                label="📋  SHARE REPORT"
                variant="outline"
                onPress={shareSummary}
              />
            </View>
          </View>
        </View>

        {/* Ask AI Assistant Callout */}
        <Pressable
          style={styles.askAiCard}
          onPress={() =>
            router.push({ pathname: "/chat", params: { scanId: verdict.scan_id } })
          }
        >
          <View style={{ flex: 1 }}>
            <Text style={styles.askAiTitle}>💬 Ask DCA AI Assistant</Text>
            <Text style={styles.askAiSub}>
              Questions about Rule 6 violations, USP calculations, or Section 36 penalties?
            </Text>
          </View>
          <View style={styles.askAiPill}>
            <Text style={styles.askAiPillText}>ASK AI →</Text>
          </View>
        </Pressable>

        {/* Official report container */}
        <View style={styles.report}>
          <Text style={styles.reportTitle}>EXTRACTED DECLARATIONS</Text>

          {unclearFields.length > 0 ? (
            <View style={styles.unclearNotice}>
              <Text style={styles.unclearNoticeIcon}>ℹ️</Text>
              <Text style={styles.unclearNoticeText}>
                Autonomous inspection complete. Fields marked "Verify Manually" were extracted from faint or stamped print and are flagged for physical pack reference.
              </Text>
            </View>
          ) : null}

          <Field
            label="Maximum Retail Price (MRP)"
            value={money(ve.mrp) || (verdict.parsed_fields?.mrp?.raw_input ? String(verdict.parsed_fields.mrp.raw_input) : undefined)}
            needsVerification={isUnclear("mrp")}
          />
          {verdict.parsed_fields?.mrp?.parsed?.tax_included_declared ? (
            <View style={styles.taxPillOk}>
              <Text style={styles.taxPillOkText}>✓ Statutory text '(incl. of all taxes)' verified (Rule 6(1)(e))</Text>
            </View>
          ) : verdict.parsed_fields?.mrp?.parsed?.tax_included_declared === false ? (
            <View style={styles.taxPillWarn}>
              <Text style={styles.taxPillWarnText}>⚠️ Advisory: Statutory '(incl. of all taxes)' not detected (Rule 6(1)(e))</Text>
            </View>
          ) : null}
          {ve.mrp_is_ambiguous ? (
            <Text style={styles.ambiguous}>
              Multiple prices detected — flagged for manual review.
            </Text>
          ) : null}
          <Field
            label="Net Quantity"
            value={ve.net_quantity || (verdict.parsed_fields?.net_quantity?.raw_input ? String(verdict.parsed_fields.net_quantity.raw_input) : undefined)}
            needsVerification={isUnclear("net_quantity")}
          />
          <Field
            label="Unit Sale Price"
            value={ve.unit_sale_price != null ? `Rs ${ve.unit_sale_price}` : (verdict.parsed_fields?.unit_sale_price?.raw_input ? String(verdict.parsed_fields.unit_sale_price.raw_input) : undefined)}
            needsVerification={isUnclear("unit_sale_price")}
          />
          <Field
            label="Mfg / Packed Date"
            value={ve.mfd_pkd_date || (verdict.parsed_fields?.manufacturing_date?.raw_input ? String(verdict.parsed_fields.manufacturing_date.raw_input) : undefined)}
            needsVerification={isUnclear("mfd_pkd_date", "manufacturing_date")}
          />
          <Field
            label="Expiry / Best Before"
            value={ve.expiry_date || (verdict.parsed_fields?.expiry_date?.raw_input ? String(verdict.parsed_fields.expiry_date.raw_input) : undefined)}
            needsVerification={isUnclear("expiry_date")}
          />
          <Field
            label="FSSAI Licence No."
            value={ve.fssai_license_number || (verdict.parsed_fields?.fssai_license?.raw_input ? String(verdict.parsed_fields.fssai_license.raw_input) : undefined)}
            needsVerification={isUnclear("fssai_license_number", "fssai_license")}
          />
          <Field
            label="Country of Origin"
            value={ve.country_of_origin || (verdict.parsed_fields?.country_of_origin?.raw_input ? String(verdict.parsed_fields.country_of_origin.raw_input) : undefined)}
            needsVerification={isUnclear("country_of_origin")}
          />
          <Field
            label="Manufacturer"
            value={ve.manufacturer_details || (verdict.parsed_fields?.manufacturer_name_address?.raw_input ? String(verdict.parsed_fields.manufacturer_name_address.raw_input) : undefined)}
            needsVerification={isUnclear("manufacturer_details", "manufacturer_name_address")}
          />
          <Field
            label="Consumer Care Contact"
            value={ve.consumer_care_details || (verdict.parsed_fields?.consumer_care?.raw_input ? String(verdict.parsed_fields.consumer_care.raw_input) : undefined)}
            needsVerification={isUnclear("consumer_care_details", "consumer_care")}
          />
        </View>

        {/* Registry & GS1 Cross-Check */}
        {verdict.barcode_verification?.scanned_barcode ? (
          <View style={styles.registryWrap}>
            <Text style={styles.reportTitle}>BARCODE &amp; GS1 REGISTRY CHECK</Text>
            <Text style={styles.registrySub}>
              Barcode: <Text style={{ fontWeight: "800", fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace" }}>{verdict.barcode_verification.scanned_barcode}</Text>
              {verdict.barcode_verification.product_name ? ` • ${verdict.barcode_verification.product_name}` : ""}
            </Text>

            {verdict.barcode_verification.gs1_country ? (
              <View style={styles.gs1Row}>
                <Text style={styles.gs1Text}>
                  GS1 Prefix {verdict.barcode_verification.gs1_prefix || ""}:{" "}
                  <Text style={{ fontWeight: "800", color: colors.navyDark }}>{verdict.barcode_verification.gs1_country}</Text>
                </Text>
                {verdict.barcode_verification.origin_matches_barcode === false ? (
                  <View style={styles.gs1MismatchBadge}>
                    <Text style={styles.gs1MismatchText}>⚠️ ORIGIN MISMATCH</Text>
                  </View>
                ) : verdict.barcode_verification.origin_matches_barcode === true ? (
                  <View style={styles.gs1MatchBadge}>
                    <Text style={styles.gs1MatchText}>✓ MATCHES ORIGIN</Text>
                  </View>
                ) : null}
              </View>
            ) : null}

            {verdict.barcode_verification.matched && verdict.barcode_verification.comparisons ? (
              verdict.barcode_verification.comparisons.map((c, i) => {
                if (c.status === "not_available") return null;
                const isMatch = c.status === "agree";
                return (
                  <View key={i} style={styles.registryRow}>
                    <Text style={styles.registryIcon}>{isMatch ? "✅" : "❌"}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.registryLabel, !isMatch && { color: colors.red }]}>
                        {c.field.toUpperCase().replace(/_/g, " ")}
                      </Text>
                      <Text style={styles.registryValue}>
                        {isMatch
                          ? `Matches registry: ${c.reference}`
                          : `MISMATCH! Printed '${c.declared}' but registry expects '${c.reference}'`}
                      </Text>
                    </View>
                  </View>
                );
              })
            ) : null}
          </View>
        ) : null}

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
            {confirmedCategory ? "Officer-confirmed" : "Autonomous AI-verified"}
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
              label="FILE COMPLAINT ONLINE (NCH Portal)"
              variant="outline"
              onPress={() => openExternal(EJAGRITI_URL, "NCH Complaint Portal")}
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
                {noticeInfo ? (
                  <View style={styles.noticeCard}>
                    <Text style={styles.noticeText}>
                      ✓ Notice generated successfully
                    </Text>
                    <Text style={styles.noticeHash}>
                      Evidence Hash: {noticeInfo.hash.slice(0, 16)}…
                    </Text>
                    <Button 
                      label="📄  DOWNLOAD / OPEN PDF" 
                      onPress={() => openExternal(`${API_BASE_URL}/officer/notice/${noticeInfo.filename}`, "Download PDF")} 
                    />
                  </View>
                ) : null}
              </View>
            ) : null}
          </View>
        ) : null}

        <Button label="SCAN ANOTHER" variant="outline" onPress={() => router.replace("/scan")} />
      </ScrollView>
    </View>
  );
}

function Field({
  label,
  value,
  needsVerification = false,
}: {
  label: string;
  value?: string | null;
  needsVerification?: boolean;
}) {
  const shown = value && String(value).trim() ? String(value) : "Not declared";
  const missing = !(value && String(value).trim());
  return (
    <View style={styles.field}>
      <View style={styles.fieldHeaderRow}>
        <Text style={styles.fieldLabel}>{label}</Text>
        {needsVerification && !missing ? (
          <View style={styles.verifyBadge}>
            <Text style={styles.verifyBadgeText}>⚠️ Verify Manually</Text>
          </View>
        ) : null}
      </View>
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
  field: {
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 2,
  },
  fieldHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  verifyBadge: {
    backgroundColor: "#FEF3C7",
    borderWidth: 1,
    borderColor: "#FCD34D",
    borderRadius: radius.sm,
    paddingHorizontal: spacing.xs,
    paddingVertical: 1,
  },
  verifyBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#92400E",
  },
  unclearNotice: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: "#FFFBEB",
    borderWidth: 1,
    borderColor: "#FDE68A",
    borderRadius: radius.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  unclearNoticeIcon: { fontSize: 16 },
  unclearNoticeText: {
    flex: 1,
    fontSize: font.small,
    color: "#92400E",
    lineHeight: 17,
  },
  fieldLabel: {
    fontSize: font.small,
    fontWeight: "600",
    color: colors.textMuted,
  },
  fieldValue: { fontSize: font.h3, color: colors.text, fontWeight: "700", marginTop: 2 },
  fieldMissing: { color: colors.textMuted, fontStyle: "italic", fontWeight: "600" },
  ambiguous: { color: colors.amber, fontSize: font.small, fontWeight: "700", marginTop: spacing.xs },

  registryWrap: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: colors.navyDark,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  registrySub: {
    fontSize: font.small,
    color: colors.textMuted,
    lineHeight: 18,
    marginBottom: spacing.xs,
  },
  registryRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: colors.bg,
    padding: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  registryIcon: { fontSize: 18, marginRight: spacing.sm, marginTop: 2 },
  registryLabel: { fontSize: font.label, fontWeight: "800", color: colors.navy },
  registryValue: { fontSize: font.body, color: colors.text, marginTop: 2 },

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
  noticeCard: {
    backgroundColor: colors.tealSoft,
    borderColor: colors.teal,
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: spacing.md,
    gap: spacing.sm,
  },
  noticeText: {
    color: colors.tealDark,
    fontSize: font.body,
    fontWeight: "800",
  },
  noticeHash: {
    color: colors.textMuted,
    fontSize: font.small,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  downloadCard: {
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: colors.navyDark,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  downloadTitle: {
    fontSize: font.label,
    fontWeight: "900",
    color: colors.navyDark,
    letterSpacing: 0.5,
  },
  downloadSub: {
    fontSize: font.small,
    color: colors.textMuted,
    lineHeight: 18,
  },
  downloadCardBtnRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: 2,
  },
  askAiCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F0FDF4",
    borderWidth: 1.5,
    borderColor: "#86EFAC",
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.03,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  askAiTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: "#166534",
  },
  askAiSub: {
    fontSize: 10.5,
    color: "#15803D",
    marginTop: 2,
    lineHeight: 15,
  },
  askAiPill: {
    backgroundColor: "#166534",
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radius.sm,
  },
  askAiPillText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0.5,
  },
  taxPillOk: {
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 3,
    marginBottom: 4,
  },
  taxPillOkText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#047857",
  },
  taxPillWarn: {
    backgroundColor: "#FFFBEB",
    borderWidth: 1,
    borderColor: "#FDE68A",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 3,
    marginBottom: 4,
  },
  taxPillWarnText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#B45309",
  },
  gs1Row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginVertical: 4,
  },
  gs1Text: {
    fontSize: 11,
    color: "#475569",
    flex: 1,
  },
  gs1MatchBadge: {
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  gs1MatchText: {
    fontSize: 9.5,
    fontWeight: "800",
    color: "#059669",
  },
  gs1MismatchBadge: {
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  gs1MismatchText: {
    fontSize: 9.5,
    fontWeight: "900",
    color: "#DC2626",
  },
});
