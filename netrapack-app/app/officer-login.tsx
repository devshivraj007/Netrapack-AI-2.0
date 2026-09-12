import { useState } from "react";
import { View, Text, StyleSheet, TextInput, ScrollView } from "react-native";
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

  async function onLogin() {
    setBusy(true);
    setError(null);
    const res = await login(username, password);
    setBusy(false);
    if (res.ok) {
      router.replace("/");
    } else {
      setError(res.error ?? "Login failed.");
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="Officer Login" />
      <ScrollView contentContainerStyle={styles.body}>
        <Text style={styles.title}>Authorised Officer Access</Text>
        <Text style={styles.sub}>
          Officers can confirm the product category and generate Section 36
          notices. Public users can scan without logging in.
        </Text>

        <View style={styles.form}>
          <Text style={styles.label}>Username</Text>
          <TextInput
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            placeholder="officer"
            placeholderTextColor={colors.textMuted}
            style={styles.input}
          />
          <Text style={styles.label}>Password</Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="••••••••"
            placeholderTextColor={colors.textMuted}
            style={styles.input}
          />
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Button label="LOG IN" onPress={onLogin} loading={busy} />
          <Button label="CANCEL" variant="outline" onPress={() => router.back()} />
        </View>

        <View style={styles.demo}>
          <Text style={styles.demoText}>
            Demo credentials — officer / netra123  ·  admin / admin123
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: spacing.lg, gap: spacing.lg },
  title: { fontSize: font.h2, fontWeight: "800", color: colors.navy },
  sub: { fontSize: font.body, color: colors.textMuted, lineHeight: 22 },
  form: { gap: spacing.sm },
  label: { fontSize: font.label, fontWeight: "700", color: colors.text, marginTop: spacing.sm },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.md,
    fontSize: font.body,
    color: colors.text,
    backgroundColor: colors.white,
  },
  error: {
    color: colors.red,
    fontWeight: "700",
    fontSize: font.small,
    marginTop: spacing.xs,
  },
  demo: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.md,
    backgroundColor: colors.card,
  },
  demoText: { color: colors.textMuted, fontSize: font.small, textAlign: "center" },
});
