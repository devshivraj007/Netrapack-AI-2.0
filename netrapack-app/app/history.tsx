import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Header } from "../src/components/Header";
import { Button } from "../src/components/Button";
import { colors, font, radius, spacing, statusStyle } from "../src/theme";
import { session } from "../src/session";
import { searchReports, type ReportRow } from "../src/api";

const STATUS_FILTERS: { label: string; value?: string }[] = [
  { label: "All", value: undefined },
  { label: "Compliant", value: "fully_compliant" },
  { label: "Non-compliant", value: "non_compliant" },
  { label: "Needs review", value: "needs_manual_review" },
];

export default function History() {
  const router = useRouter();
  const [, force] = useState(0);
  useEffect(() => session.subscribe(() => force((n) => n + 1)), []);
  const isOfficer = session.isOfficer();

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [rows, setRows] = useState<ReportRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  async function runSearch(nextStatus?: string) {
    setBusy(true);
    setError(null);
    setSearched(true);
    try {
      const res = await searchReports(
        { q: query.trim() || undefined, status: nextStatus, limit: 50 },
        session.get().token ?? undefined,
      );
      setRows(res.reports);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
      setRows([]);
    } finally {
      setBusy(false);
    }
  }

  // Officer gate: this endpoint is protected, so require login.
  if (!isOfficer) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <Header subtitle="Scan Records" />
        <View style={styles.center}>
          <Text style={styles.muted}>
            Searching scan records requires an authorised officer login.
          </Text>
          <Button label="OFFICER LOGIN" onPress={() => router.push("/officer-login")} />
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="Scan Records" />
      <View style={styles.searchBar}>
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search by product or scan ID…"
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          onSubmitEditing={() => runSearch(status)}
          returnKeyType="search"
        />
        <Pressable style={styles.searchBtn} onPress={() => runSearch(status)}>
          <Text style={styles.searchBtnText}>GO</Text>
        </Pressable>
      </View>

      {/* Status filter chips (lavender = active) */}
      <View style={styles.filters}>
        {STATUS_FILTERS.map((f) => {
          const active = status === f.value;
          return (
            <Pressable
              key={f.label}
              style={[styles.chip, active ? styles.chipActive : null]}
              onPress={() => {
                setStatus(f.value);
                runSearch(f.value);
              }}
            >
              <Text style={[styles.chipText, active ? styles.chipTextActive : null]}>
                {f.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <ScrollView contentContainerStyle={styles.body}>
        {busy ? <ActivityIndicator color={colors.navy} style={{ marginTop: spacing.lg }} /> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {!busy && searched && rows.length === 0 && !error ? (
          <Text style={styles.muted}>No matching records found.</Text>
        ) : null}

        {rows.map((r) => {
          const st = statusStyle(r.overall_status);
          return (
            <View key={`${r.scan_id}-${r.created_at}`} style={styles.card}>
              <View style={styles.cardHead}>
                <Text style={styles.cardId} numberOfLines={1}>{r.scan_id}</Text>
                <View style={[styles.statusTag, { backgroundColor: st.bg }]}>
                  <Text style={styles.statusTagText}>{st.label}</Text>
                </View>
              </View>
              <Text style={styles.cardMeta}>
                {(r.ai_category || "general").toUpperCase()} · {r.rules_passed ?? 0}/{r.rules_checked ?? 0} checks
              </Text>
              {r.created_at ? <Text style={styles.cardDate}>{r.created_at}</Text> : null}
              {r.investigation_status ? (
                <Text style={styles.cardInv}>Investigation: {r.investigation_status}</Text>
              ) : null}
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.lg, padding: spacing.xl },
  muted: { color: colors.textMuted, fontSize: font.body, textAlign: "center", lineHeight: 22 },
  searchBar: { flexDirection: "row", gap: spacing.sm, padding: spacing.lg, paddingBottom: spacing.sm },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.md,
    fontSize: font.body,
    color: colors.text,
    backgroundColor: colors.white,
  },
  searchBtn: {
    backgroundColor: colors.navy,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.lg,
    justifyContent: "center",
  },
  searchBtnText: { color: colors.white, fontWeight: "800", fontSize: font.label },
  filters: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, paddingHorizontal: spacing.lg, paddingBottom: spacing.sm },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    backgroundColor: colors.card,
  },
  chipActive: { backgroundColor: colors.lavender, borderColor: colors.lavenderBorder },
  chipText: { color: colors.textMuted, fontWeight: "700", fontSize: font.small },
  chipTextActive: { color: colors.navy },
  body: { padding: spacing.lg, gap: spacing.md, paddingBottom: spacing.xxl },
  card: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  cardHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  cardId: { flex: 1, fontSize: font.body, fontWeight: "800", color: colors.navy },
  statusTag: { borderRadius: radius.sm, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  statusTagText: { color: colors.white, fontWeight: "800", fontSize: 10, letterSpacing: 0.5 },
  cardMeta: { fontSize: font.small, color: colors.text, fontWeight: "600", marginTop: spacing.xs },
  cardDate: { fontSize: font.small, color: colors.textMuted, marginTop: 2 },
  cardInv: { fontSize: font.small, color: colors.tealDark, fontWeight: "700", marginTop: 2 },
  error: {
    color: colors.red,
    backgroundColor: colors.redSoft,
    borderColor: colors.red,
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: spacing.md,
    fontSize: font.small,
    fontWeight: "600",
  },
});
