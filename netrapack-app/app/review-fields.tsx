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

  useEffect(() => {
    if (!verdict) {
      router.replace("/");
      return;
    }
    // Populate form with the initial raw inputs that were just extracted by the AI
    const p = verdict.parsed_fields || {};
    setFields({
      mrp_declaration: p.mrp_declaration?.raw_input || "",
      net_quantity_declaration: p.net_quantity_declaration?.raw_input || "",
      unit_sale_price_declaration: p.unit_sale_price_declaration?.raw_input || "",
      manufacturing_date_declaration: p.manufacturing_date_declaration?.raw_input || "",
      expiry_date_declaration: p.expiry_date_declaration?.raw_input || "",
      fssai_license_number: p.fssai_license_number?.raw_input || "",
      manufacturer_name_address: p.manufacturer_name_address?.raw_input || "",
      country_of_origin_declaration: p.country_of_origin_declaration?.raw_input || "",
      consumer_care_details: p.consumer_care_details?.raw_input || "",
    });
  }, [verdict]);

  async function submit() {
    if (!verdict) return;
    setBusy(true);
    setError(null);
    try {
      // Re-evaluate using the edited text fields
      const updatedVerdict = await processTextScan({
        scan_id: verdict.scan_id,
        ...fields,
      });
      // Keep the original metadata (like AI source and timings) but update the rule results
      if (verdict.ai_recognition) updatedVerdict.ai_recognition = verdict.ai_recognition;
      if (verdict.metadata) updatedVerdict.metadata = verdict.metadata;
      
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
