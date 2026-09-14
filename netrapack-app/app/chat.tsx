import { useState, useRef, useEffect } from "react";
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

type Msg = { role: "user" | "bot"; text: string; time: string };

const GENERAL_SUGGESTIONS = [
  "What are Rule 6 mandatory declarations?",
  "What is the penalty under Section 36?",
  "When is Unit Sale Price (USP) mandatory?",
  "What are the rules for Dual MRP?",
  "How to lodge an NCH consumer grievance?",
];

function cleanChatMessage(raw: string): string {
  if (!raw) return "";
  return raw
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/\*{1,3}(.*?)\*{1,3}/g, "$1")
    .replace(/_{1,3}(.*?)_{1,3}/g, "$1")
    .replace(/`{1,3}(.*?)`{1,3}/g, "$1")
    .replace(/[*#]/g, "")
    .replace(/^[ \t]*>[ \t]*/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export default function Chat() {
  const params = useLocalSearchParams<{ scanId?: string }>();
  const lastVerdict = getLastVerdict();
  const [activeScanId, setActiveScanId] = useState<string>(
    params.scanId || lastVerdict?.scan_id || ""
  );

  const scrollRef = useRef<ScrollView>(null);

  const nowTime = () =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const initialGreeting = activeScanId
    ? `Welcome to NetraPack AI Assistant. I am loaded with the inspection data for scan #${activeScanId}. Ask me about this product's violations, statutory exemptions, or legal metrology requirements.`
    : "Welcome to NetraPack's Legal Metrology AI Assistant. Ask me any question about the Legal Metrology Act, 2009, LMPC Rules, 2011, packaging compliance, or consumer grievance procedures.";

  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "bot",
      text: initialGreeting,
      time: nowTime(),
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [messages, busy]);

  const hasViolations =
    activeScanId &&
    lastVerdict?.scan_id === activeScanId &&
    (lastVerdict?.violations?.length ?? 0) > 0;

  const currentSuggestions = activeScanId
    ? hasViolations
      ? [
          "Why did this scan fail compliance?",
          "Explain the Rule 6 violations",
          "What is the penalty under Section 36?",
          "How can the manufacturer rectify this?",
        ]
      : [
          "Is this product fully compliant?",
          "Explain the Unit Sale Price rule",
          "What are the mandatory label declarations?",
        ]
    : GENERAL_SUGGESTIONS;

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;

    const time = nowTime();
    setMessages((m) => [...m, { role: "user", text: q, time }]);
    setInput("");
    setBusy(true);

    try {
      const res = await chatQuery(activeScanId || undefined, q);
      setMessages((m) => [
        ...m,
        { role: "bot", text: res.answer, time: nowTime() },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "bot",
          text:
            e instanceof Error
              ? e.message
              : "Sorry, I could not process your query at this time.",
          time: nowTime(),
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  function clearChat() {
    setMessages([
      {
        role: "bot",
        text: activeScanId
          ? `Chat cleared. Ready for questions about scan #${activeScanId}.`
          : "Chat cleared. Ready for general Legal Metrology questions.",
        time: nowTime(),
      },
    ]);
  }

  function toggleMode() {
    if (activeScanId) {
      setActiveScanId("");
      setMessages((m) => [
        ...m,
        {
          role: "bot",
          text: "Switched to General Legal Metrology Mode. You can ask any question regarding statutory packaging standards.",
          time: nowTime(),
        },
      ]);
    } else if (lastVerdict?.scan_id) {
      setActiveScanId(lastVerdict.scan_id);
      setMessages((m) => [
        ...m,
        {
          role: "bot",
          text: `Switched back to scan context #${lastVerdict.scan_id}.`,
          time: nowTime(),
        },
      ]);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="AI Legal Assistant" />

      {/* Mode / Context Header Bar */}
      <View style={styles.contextBar}>
        <View style={styles.contextBadge}>
          <Text style={styles.contextDot}>●</Text>
          <Text style={styles.contextText}>
            {activeScanId
              ? `Scan: #${activeScanId.slice(0, 14)}${
                  activeScanId.length > 14 ? "…" : ""
                }`
              : "General Statutory Advisor"}
          </Text>
        </View>

        <View style={styles.contextActions}>
          {lastVerdict?.scan_id ? (
            <Pressable style={styles.actionPill} onPress={toggleMode}>
              <Text style={styles.actionPillText}>
                {activeScanId ? "Switch to General" : "Load Last Scan"}
              </Text>
            </Pressable>
          ) : null}
          <Pressable style={styles.actionPill} onPress={clearChat}>
            <Text style={styles.actionPillText}>Clear</Text>
          </Pressable>
        </View>
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.body}
          showsVerticalScrollIndicator={false}
        >
          {messages.map((m, i) => (
            <View
              key={i}
              style={[
                styles.messageContainer,
                m.role === "user" ? styles.userContainer : styles.botContainer,
              ]}
            >
              <Text style={styles.senderLabel}>
                {m.role === "user" ? "You" : "🏛️ DCA Legal Metrology Assistant"}
              </Text>
              <View
                style={[
                  styles.bubble,
                  m.role === "user" ? styles.userBubble : styles.botBubble,
                ]}
              >
                <Text
                  style={m.role === "user" ? styles.userText : styles.botText}
                >
                  {cleanChatMessage(m.text)}
                </Text>
                <Text
                  style={[
                    styles.timeText,
                    m.role === "user" ? styles.userTime : styles.botTime,
                  ]}
                >
                  {m.time}
                </Text>
              </View>
            </View>
          ))}

          {busy ? (
            <View style={[styles.messageContainer, styles.botContainer]}>
              <Text style={styles.senderLabel}>
                🏛️ DCA Legal Metrology Assistant
              </Text>
              <View style={[styles.bubble, styles.botBubble, styles.loadingBubble]}>
                <ActivityIndicator size="small" color={colors.navy} />
                <Text style={styles.loadingText}>
                  Analyzing statutory framework…
                </Text>
              </View>
            </View>
          ) : null}

          {/* Suggested queries */}
          <View style={styles.suggestionsContainer}>
            <Text style={styles.suggestionTitle}>SUGGESTED QUESTIONS</Text>
            <View style={styles.suggestions}>
              {currentSuggestions.map((s) => (
                <Pressable
                  key={s}
                  style={({ pressed }) => [
                    styles.chip,
                    pressed && styles.chipPressed,
                  ]}
                  onPress={() => send(s)}
                  disabled={busy}
                >
                  <Text style={styles.chipText}>{s}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        </ScrollView>

        {/* Input Bar */}
        <View style={styles.inputRow}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder={
              activeScanId
                ? "Ask about this product's compliance…"
                : "Ask about Legal Metrology rules…"
            }
            placeholderTextColor={colors.textMuted}
            style={styles.input}
            onSubmitEditing={() => send(input)}
            returnKeyType="send"
          />
          <Pressable
            style={({ pressed }) => [
              styles.sendBtn,
              (!input.trim() || busy) && styles.sendBtnDisabled,
              pressed && styles.sendBtnPressed,
            ]}
            onPress={() => send(input)}
            disabled={!input.trim() || busy}
          >
            <Text style={styles.sendText}>SEND</Text>
          </Pressable>
        </View>

        <Text style={styles.disclaimer}>
          AI Guidance for statutory compliance under LMPC Rules, 2011. Does not
          substitute for formal judicial orders.
        </Text>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  contextBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#F1F5F9",
    borderBottomWidth: 1,
    borderBottomColor: "#E2E8F0",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
  },
  contextBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  contextDot: {
    color: "#059669",
    fontSize: 10,
  },
  contextText: {
    fontSize: 11.5,
    fontWeight: "700",
    color: "#1E293B",
  },
  contextActions: {
    flexDirection: "row",
    gap: spacing.xs,
  },
  actionPill: {
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#CBD5E1",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  actionPillText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#334155",
  },

  body: {
    padding: spacing.md,
    gap: spacing.md,
    paddingBottom: spacing.lg,
  },

  messageContainer: {
    maxWidth: "88%",
    gap: 3,
  },
  userContainer: {
    alignSelf: "flex-end",
    alignItems: "flex-end",
  },
  botContainer: {
    alignSelf: "flex-start",
    alignItems: "flex-start",
  },
  senderLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: "#64748B",
    paddingHorizontal: 4,
  },

  bubble: {
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    borderWidth: 1,
  },
  userBubble: {
    backgroundColor: colors.navy,
    borderColor: colors.navyDark,
    borderBottomRightRadius: 2,
  },
  botBubble: {
    backgroundColor: "#FFFFFF",
    borderColor: "#CBD5E1",
    borderWidth: 1.2,
    borderBottomLeftRadius: 2,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },
  loadingBubble: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.md,
  },
  loadingText: {
    fontSize: font.small,
    color: "#475569",
    fontWeight: "500",
    fontStyle: "italic",
  },

  userText: {
    color: "#FFFFFF",
    fontSize: 13.5,
    fontWeight: "600",
    lineHeight: 20,
  },
  botText: {
    color: "#000000",
    fontSize: 13.5,
    fontWeight: "600",
    lineHeight: 21,
    letterSpacing: 0.1,
  },

  timeText: {
    fontSize: 9,
    marginTop: 4,
    alignSelf: "flex-end",
  },
  userTime: {
    color: "rgba(255,255,255,0.7)",
  },
  botTime: {
    color: "#64748B",
    fontWeight: "600",
  },

  suggestionsContainer: {
    marginTop: spacing.sm,
    gap: spacing.xs,
  },
  suggestionTitle: {
    fontSize: 10,
    fontWeight: "800",
    color: "#64748B",
    letterSpacing: 0.5,
    paddingHorizontal: 2,
  },
  suggestions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs + 2,
  },
  chip: {
    backgroundColor: "#EFF6FF",
    borderColor: "#BFDBFE",
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: spacing.xs + 2,
  },
  chipPressed: {
    backgroundColor: "#DBEAFE",
  },
  chipText: {
    color: "#1D4ED8",
    fontWeight: "700",
    fontSize: 11,
  },

  inputRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
    paddingBottom: 2,
    alignItems: "center",
    backgroundColor: colors.bg,
  },
  input: {
    flex: 1,
    borderWidth: 1.2,
    borderColor: "#CBD5E1",
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: Platform.OS === "ios" ? 11 : 9,
    fontSize: font.body,
    color: "#0F172A",
    backgroundColor: "#FFFFFF",
  },
  sendBtn: {
    backgroundColor: colors.navy,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md + 2,
    paddingVertical: Platform.OS === "ios" ? 11 : 10,
    justifyContent: "center",
    alignItems: "center",
  },
  sendBtnDisabled: {
    opacity: 0.45,
  },
  sendBtnPressed: {
    opacity: 0.85,
  },
  sendText: {
    color: "#FFFFFF",
    fontWeight: "800",
    fontSize: font.small + 1,
    letterSpacing: 0.5,
  },

  disclaimer: {
    fontSize: 9.5,
    color: "#94A3B8",
    textAlign: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
  },
});
