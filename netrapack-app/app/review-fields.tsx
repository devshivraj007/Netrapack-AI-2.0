import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Header } from "../src/components/Header";
import { Button } from "../src/components/Button";
import { colors, font, radius, spacing } from "../src/theme";
import { getLastVerdict, setLastVerdict } from "../src/verdictStore";
import { processTextScan } from "../src/api";

export default function ReviewFields() {
  const router = useRouter();
  const verdict = getLastVerdict();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [fields, setFields] = useState({
    mrp_declaration: "",
    net_quantity_declaration: "",
    unit_sale_price_declaration: "",
    manufacturing_date_declaration: "",
    expiry_date_declaration: "",
    fssai_license_number: "",
    manufacturer_name_address: "",
    country_of_origin_declaration: "",
    consumer_care_details: "",
  });

  function cleanVal(raw?: any): string {
    if (raw == null) return "";
    const s = String(raw).trim();
    if (/^(not\s*declared|none|null|undefined|unclear)$/i.test(s)) {
      return "";
    }
    return s;
  }

  useEffect(() => {
    if (!verdict) {
      router.replace("/");
      return;
    }
    const p = verdict.parsed_fields || {};
    const v = verdict.vision_extraction || {};
    setFields({
      mrp_declaration: cleanVal(p.mrp?.raw_input) || (v.mrp != null ? `₹${v.mrp}` : "") || cleanVal(p.mrp_declaration?.raw_input),
      net_quantity_declaration: cleanVal(p.net_quantity?.raw_input) || cleanVal(v.net_quantity) || cleanVal(p.net_quantity_declaration?.raw_input),
      unit_sale_price_declaration: cleanVal(p.unit_sale_price?.raw_input) || (v.unit_sale_price != null ? `₹${v.unit_sale_price}` : "") || cleanVal(p.unit_sale_price_declaration?.raw_input),
      manufacturing_date_declaration: cleanVal(p.manufacturing_date?.raw_input) || cleanVal(v.mfd_pkd_date) || cleanVal(p.manufacturing_date_declaration?.raw_input),
      expiry_date_declaration: cleanVal(p.expiry_date?.raw_input) || cleanVal(v.expiry_date) || cleanVal(p.expiry_date_declaration?.raw_input),
      fssai_license_number: cleanVal(p.fssai_license?.raw_input) || cleanVal(v.fssai_license_number) || cleanVal(p.fssai_license_number?.raw_input),
      manufacturer_name_address: cleanVal(p.manufacturer_name_address?.raw_input) || cleanVal(v.manufacturer_details) || cleanVal(p.manufacturer_details?.raw_input),
      country_of_origin_declaration: cleanVal(p.country_of_origin?.raw_input) || cleanVal(v.country_of_origin) || cleanVal(p.country_of_origin_declaration?.raw_input),
      consumer_care_details: cleanVal(p.consumer_care?.raw_input) || cleanVal(v.consumer_care_details) || cleanVal(p.consumer_care_details?.raw_input),
    });
  }, [verdict]);

  async function submit() {
    if (!verdict) return;
    setBusy(true);
    setError(null);
    try {
      const category = verdict.ai_recognition?.category || verdict.ai_recognition?.effective_category || undefined;
      const barcode = verdict.barcode_verification?.scanned_barcode || undefined;

      // Re-evaluate using the edited text fields
      const updatedVerdict = await processTextScan({
        scan_id: verdict.scan_id,
        barcode,
        product_category: category,
        ...fields,
      });

      // Keep the original metadata, recognition, and barcode verification
      if (verdict.ai_recognition) updatedVerdict.ai_recognition = verdict.ai_recognition;
      if (verdict.metadata) updatedVerdict.metadata = verdict.metadata;
      if (verdict.barcode_verification && !updatedVerdict.barcode_verification) {
        updatedVerdict.barcode_verification = verdict.barcode_verification;
      }
      if (verdict.readability && !updatedVerdict.readability) {
        updatedVerdict.readability = verdict.readability;
      }

      // CRITICAL: Ensure vision_extraction is populated with the updated fields so verdict screen displays them
      const numMrp = parseFloat(fields.mrp_declaration.replace(/[^0-9.]/g, ""));
      const numUsp = parseFloat(fields.unit_sale_price_declaration.replace(/[^0-9.]/g, ""));
      updatedVerdict.vision_extraction = {
        ...(updatedVerdict.vision_extraction || verdict.vision_extraction || {}),
        mrp: !isNaN(numMrp) ? numMrp : (verdict.vision_extraction?.mrp ?? null),
        net_quantity: fields.net_quantity_declaration.trim() || null,
        unit_sale_price: !isNaN(numUsp) ? numUsp : (verdict.vision_extraction?.unit_sale_price ?? null),
        mfd_pkd_date: fields.manufacturing_date_declaration.trim() || null,
        expiry_date: fields.expiry_date_declaration.trim() || null,
        fssai_license_number: fields.fssai_license_number.trim() || null,
        manufacturer_details: fields.manufacturer_name_address.trim() || null,
        country_of_origin: fields.country_of_origin_declaration.trim() || null,
        consumer_care_details: fields.consumer_care_details.trim() || null,
        unclear_fields: [], // Cleared because the user has reviewed & edited!
      };
      
      setLastVerdict(updatedVerdict);
      router.replace("/verdict");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to re-evaluate fields.");
      setBusy(false);
    }
  }

  if (!verdict) return null;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="Review Data" />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
          <View style={styles.infoCard}>
            <Text style={styles.infoTitle}>Verify Extracted Fields</Text>
            <Text style={styles.infoText}>
              The AI has read the label. Please quickly review the fields below and correct any misread text before generating the final compliance report.
            </Text>
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <View style={styles.form}>
            <FieldInput label="MRP (₹)" value={fields.mrp_declaration} onChange={(v) => setFields({ ...fields, mrp_declaration: v })} />
            <FieldInput label="Net Quantity" value={fields.net_quantity_declaration} onChange={(v) => setFields({ ...fields, net_quantity_declaration: v })} />
            <FieldInput label="Unit Sale Price (USP)" value={fields.unit_sale_price_declaration} onChange={(v) => setFields({ ...fields, unit_sale_price_declaration: v })} />
            <FieldInput label="Mfg / Pkd Date" value={fields.manufacturing_date_declaration} onChange={(v) => setFields({ ...fields, manufacturing_date_declaration: v })} />
            <FieldInput label="Expiry / Best Before" value={fields.expiry_date_declaration} onChange={(v) => setFields({ ...fields, expiry_date_declaration: v })} />
            <FieldInput label="Consumer Care Contact" value={fields.consumer_care_details} onChange={(v) => setFields({ ...fields, consumer_care_details: v })} />
            <FieldInput label="FSSAI License" value={fields.fssai_license_number} onChange={(v) => setFields({ ...fields, fssai_license_number: v })} />
            <FieldInput label="Country of Origin" value={fields.country_of_origin_declaration} onChange={(v) => setFields({ ...fields, country_of_origin_declaration: v })} />
            <FieldInput label="Manufacturer Details" value={fields.manufacturer_name_address} multiline onChange={(v) => setFields({ ...fields, manufacturer_name_address: v })} />
          </View>

          <View style={styles.actions}>
            <Button label="CONFIRM & EVALUATE" onPress={submit} loading={busy} />
            <View style={{ marginTop: spacing.sm }}>
              <Button label="CANCEL" variant="outline" onPress={() => router.back()} disabled={busy} />
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

function FieldInput({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
}) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={[styles.input, multiline && styles.inputMulti]}
        value={value}
        onChangeText={onChange}
        placeholder="Not declared"
        placeholderTextColor={colors.textMuted}
        multiline={multiline}
        autoCorrect={false}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },
  infoCard: {
    backgroundColor: colors.lavender,
    padding: spacing.md,
    borderRadius: radius.md,
    gap: spacing.xs,
  },
  infoTitle: { color: colors.navy, fontSize: font.h3, fontWeight: "800" },
  infoText: { color: colors.navy, fontSize: font.small, lineHeight: 18 },
  error: { color: colors.red, fontSize: font.small, fontWeight: "600" },
  form: { gap: spacing.md },
  fieldGroup: { gap: 4 },
  label: { fontSize: font.label, fontWeight: "700", color: colors.textMuted },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 10,
    fontSize: font.body,
    backgroundColor: colors.card,
    color: colors.text,
  },
  inputMulti: { height: 80, textAlignVertical: "top" },
  actions: { marginTop: spacing.md },
});
