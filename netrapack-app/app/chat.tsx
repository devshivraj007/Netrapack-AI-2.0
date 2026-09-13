import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  Pressable,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Header } from "../src/components/Header";
import { colors, font, radius, spacing } from "../src/theme";
import { chatQuery } from "../src/api";
import { getLastVerdict } from "../src/verdictStore";

type Msg = { role: "user" | "bot"; text: string };

const SUGGESTIONS = [
  "Why is this non-compliant?",
  "What is MRP declaration?",
  "Which rule was violated?",
];

export default function Chat() {
  const params = useLocalSearchParams<{ scanId?: string }>();
  const scanId = params.scanId || getLastVerdict()?.scan_id || "";

  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "bot",
      text:
        "Ask me about this scan's compliance or Legal Metrology rules in general. " +
        "I explain findings in plain language.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    if (!scanId) {
      setMessages((m) => [...m, { role: "bot", text: "No scan is loaded. Scan a product first, then ask about it." }]);
      return;
    }
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const res = await chatQuery(scanId, q);
      setMessages((m) => [...m, { role: "bot", text: res.answer }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "bot", text: e instanceof Error ? e.message : "Sorry, I couldn't answer that." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="Compliance Assistant" />
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={styles.body}>
          {messages.map((m, i) => (
            <View
              key={i}
              style={[
                styles.bubble,
                m.role === "user" ? styles.userBubble : styles.botBubble,
              ]}
            >
              <Text style={m.role === "user" ? styles.userText : styles.botText}>
                {m.text}
              </Text>
            </View>
          ))}
          {busy ? (
            <View style={[styles.bubble, styles.botBubble]}>
              <ActivityIndicator color={colors.navy} />
            </View>
          ) : null}

          {/* Suggested questions */}
          <View style={styles.suggestions}>
            {SUGGESTIONS.map((s) => (
              <Pressable key={s} style={styles.chip} onPress={() => send(s)} disabled={busy}>
                <Text style={styles.chipText}>{s}</Text>
              </Pressable>
            ))}
          </View>
        </ScrollView>

        <View style={styles.inputRow}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Ask a question…"
            placeholderTextColor={colors.textMuted}
            style={styles.input}
            onSubmitEditing={() => send(input)}
            returnKeyType="send"
          />
          <Pressable
            style={[styles.sendBtn, busy ? { opacity: 0.5 } : null]}
            onPress={() => send(input)}
            disabled={busy}
          >
            <Text style={styles.sendText}>SEND</Text>
          </Pressable>
        </View>

        <Text style={styles.disclaimer}>
          Informational only — not legal advice. Verify against the official
          Legal Metrology rules.
        </Text>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: spacing.lg, gap: spacing.sm, paddingBottom: spacing.lg },
  bubble: {
    maxWidth: "88%",
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: colors.lavender,
    borderColor: colors.lavenderBorder,
  },
  botBubble: {
    alignSelf: "flex-start",
    backgroundColor: colors.card,
    borderColor: colors.border,
  },
  userText: { color: colors.navy, fontSize: font.body, fontWeight: "600", lineHeight: 21 },
  botText: { color: colors.text, fontSize: font.body, lineHeight: 21 },
  suggestions: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.sm },
  chip: {
    backgroundColor: colors.tealSoft,
    borderColor: colors.teal,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  chipText: { color: colors.tealDark, fontWeight: "700", fontSize: font.small },
  inputRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    alignItems: "center",
  },
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
  sendBtn: {
    backgroundColor: colors.navy,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  sendText: { color: colors.white, fontWeight: "800", fontSize: font.label },
  disclaimer: {
    fontSize: font.small,
    color: colors.textMuted,
    textAlign: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    fontStyle: "italic",
  },
});
