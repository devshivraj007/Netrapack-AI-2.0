import { View, Text, StyleSheet, Image } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, font, spacing } from "../theme";

const EMBLEM_IMG = require("../../assets/images/emblem.png");

export function Header({ subtitle }: { subtitle?: string }) {
  const insets = useSafeAreaInsets();
  return (
    <View>
      {/* Deep indigo brand bar */}
      <View style={[styles.bar, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.row}>

          {/* Real GoI Emblem */}
          <View style={styles.sealOuter}>
            <Image source={EMBLEM_IMG} style={styles.sealImage} resizeMode="contain" />
          </View>

          {/* Bilingual department name + app sub-brand */}
          <View style={{ flex: 1, gap: 1 }}>
            <Text style={styles.hindiTitle} numberOfLines={1}>
              उपभोक्ता मामले विभाग
            </Text>
            <Text style={styles.engTitle} numberOfLines={1}>
              DEPARTMENT OF CONSUMER AFFAIRS
            </Text>
            <Text style={styles.appBrand}>NetraPack · Legal Metrology</Text>
          </View>

          {/* Small GoI tag */}
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

  // Geometric concentric-ring circular seal (outer gold → middle white → inner)
  sealOuter: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#ffffff",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    borderWidth: 1.5,
    borderColor: colors.saffron,
  },
  sealImage: {
    width: 36,
    height: 36,
  },

  // Bilingual department text
  hindiTitle: {
    color: "#E8E6F5",
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 0.2,
  },
  engTitle: {
    color: colors.white,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 0.5,
  },
  appBrand: {
    color: "#9B97C8",
    fontSize: 10,
    fontWeight: "500",
    marginTop: 2,
  },

  // Small "GoI" badge (right side)
  govTag: {
    backgroundColor: colors.saffron,
    borderRadius: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  govTagText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0.5,
  },

  // Teal secondary nav bar
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
