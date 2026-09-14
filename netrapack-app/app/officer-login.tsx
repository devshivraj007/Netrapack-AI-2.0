import { useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Pressable,
} from "react-native";
import { useRouter } from "expo-router";
import { Header } from "../src/components/Header";
import { Button } from "../src/components/Button";
import { colors, font, radius, spacing } from "../src/theme";
import { login } from "../src/session";

export default function OfficerLogin() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [userFocused, setUserFocused] = useState(false);
  const [passFocused, setPassFocused] = useState(false);

  // Subtle shake animation on failed login
  const shakeAnim = useRef(new Animated.Value(0)).current;
  function shake() {
    Animated.sequence([
      Animated.timing(shakeAnim, { toValue: 8, duration: 60, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: -8, duration: 60, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: 6, duration: 50, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: -6, duration: 50, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: 0, duration: 40, useNativeDriver: true }),
    ]).start();
  }

  async function onLogin() {
    setBusy(true);
    setError(null);
    const res = await login(username, password);
    setBusy(false);
    if (res.ok) {
      router.replace("/");
    } else {
      setError(res.error ?? "Login failed.");
      shake();
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="Officer Login" />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={0}
      >
        <ScrollView
          contentContainerStyle={styles.body}
          keyboardShouldPersistTaps="handled"
        >
          {/* Page header card */}
          <View style={styles.headerCard}>
            <View style={styles.headerCardLeft}>
              <View style={styles.lockIcon}>
                <Text style={styles.lockIconText}>🔐</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.title}>Authorised Officer Access</Text>
                <Text style={styles.sub}>
                  Section 36 notices and category confirmation require officer
                  credentials.
                </Text>
              </View>
            </View>
          </View>

          {/* Login form */}
          <Animated.View
            style={[styles.formCard, { transform: [{ translateX: shakeAnim }] }]}
          >
            {/* Username */}
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>Username</Text>
              <TextInput
                value={username}
                onChangeText={setUsername}
                autoCapitalize="none"
                autoCorrect={false}
                placeholder="Enter officer username"
                placeholderTextColor={colors.textMuted}
                style={[styles.input, userFocused && styles.inputFocused]}
                onFocus={() => setUserFocused(true)}
                onBlur={() => setUserFocused(false)}
                returnKeyType="next"
              />
            </View>

            {/* Password */}
            <View style={styles.fieldGroup}>
              <Text style={styles.label}>Password</Text>
              <TextInput
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                placeholder="Enter password"
                placeholderTextColor={colors.textMuted}
                style={[styles.input, passFocused && styles.inputFocused]}
                onFocus={() => setPassFocused(true)}
                onBlur={() => setPassFocused(false)}
                returnKeyType="done"
                onSubmitEditing={onLogin}
              />
            </View>

            {/* Error */}
            {error ? (
              <View style={styles.errorBanner}>
                <Text style={styles.errorIcon}>⚠</Text>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}

            <Button label="LOG IN" onPress={onLogin} loading={busy} />
          </Animated.View>

          {/* Demo credentials notice */}
          <View style={styles.demoBanner}>
            <View style={styles.demoBannerBar} />
            <View style={{ flex: 1 }}>
              <Text style={styles.demoTitle}>Demo Credentials</Text>
              <Text style={styles.demoText}>officer / netra123</Text>
              <Text style={styles.demoText}>admin / admin123</Text>
            </View>
          </View>

          {/* Cancel link */}
          <Pressable onPress={() => router.back()} style={styles.cancelLink}>
            <Text style={styles.cancelText}>← Back to Home</Text>
          </Pressable>

        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: spacing.lg, gap: spacing.lg, paddingBottom: spacing.xxl },

  // Page header card
  headerCard: {
    backgroundColor: colors.navy,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  headerCardLeft: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.md,
  },
  lockIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: "rgba(255,255,255,0.12)",
    alignItems: "center",
    justifyContent: "center",
  },
  lockIconText: { fontSize: 22 },
  title: {
    fontSize: font.h3,
    fontWeight: "800",
    color: colors.white,
    marginBottom: 4,
  },
  sub: {
    fontSize: font.small,
    color: "rgba(255,255,255,0.65)",
    lineHeight: 18,
  },

  // Form card
  formCard: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  fieldGroup: { gap: spacing.xs },
  label: {
    fontSize: font.label,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: 0.3,
  },
  input: {
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 13,
    fontSize: font.body,
    color: colors.text,
    backgroundColor: colors.bg,
  },
  inputFocused: {
    borderColor: colors.teal,
    backgroundColor: colors.white,
  },

  // Error banner
  errorBanner: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    backgroundColor: "#FBE9E7",
    borderWidth: 1,
    borderColor: colors.red,
    borderRadius: radius.sm,
    padding: spacing.md,
  },
  errorIcon: { fontSize: 14, color: colors.red },
  errorText: {
    flex: 1,
    color: colors.red,
    fontWeight: "700",
    fontSize: font.small,
    lineHeight: 18,
  },

  // Demo credentials
  demoBanner: {
    flexDirection: "row",
    gap: spacing.md,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.md,
  },
  demoBannerBar: {
    width: 4,
    borderRadius: 2,
    backgroundColor: colors.teal,
  },
  demoTitle: {
    fontSize: font.label,
    fontWeight: "800",
    color: colors.text,
    marginBottom: 4,
  },
  demoText: {
    fontSize: font.small,
    color: colors.textMuted,
    fontFamily: Platform.OS === "ios" ? "Courier" : "monospace",
  },

  // Cancel
  cancelLink: { alignSelf: "center", paddingVertical: spacing.sm },
  cancelText: {
    color: colors.navy,
    fontWeight: "700",
    fontSize: font.body,
  },
});
