import { View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, font, spacing } from "../theme";

/**
 * Official GIGW/DBIM header: a deep indigo bar with a circular GOI-style emblem
 * and the app name in white bold text, plus a darker teal secondary-nav accent
 * bar directly below carrying the current section title.
 */
export function Header({ subtitle }: { subtitle?: string }) {
  const insets = useSafeAreaInsets();
  return (
    <View>
      {/* Deep indigo brand bar */}
      <View style={[styles.bar, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.row}>
          <View style={styles.emblem}>
            <Text style={styles.emblemText}>NP</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>NetraPack</Text>
            <Text style={styles.brandSub}>Legal Metrology Compliance</Text>
          </View>
          <View style={styles.govTag}>
            <Text style={styles.govTagText}>GoI</Text>
          </View>
        </View>
      </View>
      {/* Teal secondary-nav accent bar */}
      {subtitle ? (
        <View style={styles.subNav}>
          <Text style={styles.subNavText}>{subtitle.toUpperCase()}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.navy,
    borderBottomWidth: 2,
    borderBottomColor: colors.tealDark,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  emblem: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.white,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.saffron,
  },
  emblemText: { color: colors.navy, fontWeight: "900", fontSize: 15 },
  title: { color: colors.white, fontSize: font.h2, fontWeight: "900", letterSpacing: 0.3 },
  brandSub: { color: "#C7C3E8", fontSize: font.small, fontWeight: "600" },
  govTag: {
    backgroundColor: colors.saffron,
    borderRadius: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  govTagText: { color: colors.white, fontSize: 11, fontWeight: "900", letterSpacing: 0.5 },
  subNav: {
    backgroundColor: colors.teal,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  subNavText: {
    color: colors.white,
    fontSize: font.small,
    fontWeight: "800",
    letterSpacing: 1,
  },
});
