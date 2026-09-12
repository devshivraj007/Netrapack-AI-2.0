import { Pressable, Text, StyleSheet, ActivityIndicator, View } from "react-native";
import { colors, font, radius, spacing } from "../theme";

type Variant = "primary" | "secondary" | "danger" | "outline";

export function Button({
  label,
  onPress,
  variant = "primary",
  loading = false,
  disabled = false,
}: {
  label: string;
  onPress?: () => void;
  variant?: Variant;
  loading?: boolean;
  disabled?: boolean;
}) {
  const v = VARIANTS[variant];
  const isDisabled = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        { backgroundColor: v.bg, borderColor: v.border },
        pressed && !isDisabled ? { opacity: 0.85 } : null,
        isDisabled ? { opacity: 0.5 } : null,
      ]}
    >
      <View style={styles.inner}>
        {loading ? <ActivityIndicator color={v.fg} /> : null}
        <Text style={[styles.label, { color: v.fg }]}>{label}</Text>
      </View>
    </Pressable>
  );
}

const VARIANTS: Record<Variant, { bg: string; fg: string; border: string }> = {
  primary: { bg: colors.navy, fg: colors.white, border: colors.navy },
  secondary: { bg: colors.saffron, fg: colors.white, border: colors.saffron },
  danger: { bg: colors.red, fg: colors.white, border: colors.red },
  outline: { bg: colors.white, fg: colors.navy, border: colors.navy },
};

const styles = StyleSheet.create({
  base: {
    minHeight: 54, // large, confident tap target
    borderRadius: radius.md, // minimally rounded, not pill
    borderWidth: 1.5,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  inner: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  label: { fontSize: font.body, fontWeight: "800", letterSpacing: 0.3 },
});
