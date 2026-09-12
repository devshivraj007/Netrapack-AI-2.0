import { View, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, font, spacing } from "../theme";

/**
 * Official government-style header: white background, app name + a small
 * circular emblem-style icon, thin bottom border (no floating shadow).
 */
export function Header({ subtitle }: { subtitle?: string }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.wrap, { paddingTop: insets.top + spacing.sm }]}>
      <View style={styles.row}>
        <View style={styles.emblem}>
          <Text style={styles.emblemText}>NP</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>NetraPack</Text>
          <Text style={styles.sub}>
            {subtitle ?? "Legal Metrology Compliance"}
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.headerBorder,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  emblem: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.navy,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.saffron,
  },
  emblemText: { color: colors.white, fontWeight: "800", fontSize: 15 },
  title: { color: colors.navy, fontSize: font.h2, fontWeight: "800" },
  sub: { color: colors.textMuted, fontSize: font.small, fontWeight: "600" },
});
