import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Header } from "../src/components/Header";
import { Button } from "../src/components/Button";
import { colors, font, radius, spacing } from "../src/theme";
import { session } from "../src/session";

export default function Home() {
  const router = useRouter();
  const [, force] = useState(0);

  useEffect(() => session.subscribe(() => force((n) => n + 1)), []);
  const isOfficer = session.isOfficer();

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header />
      <ScrollView contentContainerStyle={styles.body}>
        <View style={styles.hero}>
          <Text style={styles.heroTitle}>
            Packaged Commodity Compliance
          </Text>
          <Text style={styles.heroSub}>
            Scan a product label to check its declarations under the Legal
            Metrology (Packaged Commodities) Rules, 2011.
          </Text>
        </View>

        <View style={{ gap: spacing.md }}>
          <Button
            label="SCAN PRODUCT"
            onPress={() => router.push("/scan")}
          />

          <Button
            label="ASK COMPLIANCE ASSISTANT"
            variant="outline"
            onPress={() => router.push("/chat")}
          />

          {isOfficer ? (
            <View style={styles.officerBadge}>
              <Text style={styles.officerBadgeText}>
                Officer mode active ({session.get().role?.toUpperCase()})
              </Text>
              <Pressable onPress={() => session.logout()}>
                <Text style={styles.logout}>Log out</Text>
              </Pressable>
            </View>
          ) : (
            <Pressable
              onPress={() => router.push("/officer-login")}
              style={styles.officerLink}
            >
              <Text style={styles.officerLinkText}>Officer Login →</Text>
            </Pressable>
          )}
        </View>

        <View style={styles.note}>
          <Text style={styles.noteText}>
            Consumer mode gives an AI-suggested reading. Official Section 36
            notices require an authorised officer to confirm the product
            category first.
          </Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: spacing.lg, gap: spacing.xl },
  hero: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  heroTitle: { fontSize: font.h1, fontWeight: "800", color: colors.navy },
  heroSub: { fontSize: font.body, color: colors.textMuted, lineHeight: 22 },
  officerLink: { alignSelf: "center", paddingVertical: spacing.sm },
  officerLinkText: { color: colors.navy, fontSize: font.body, fontWeight: "700" },
  officerBadge: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.lavender,
    borderColor: colors.lavenderBorder,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  officerBadgeText: { color: colors.navy, fontWeight: "700", fontSize: font.label },
  logout: { color: colors.red, fontWeight: "800", fontSize: font.label },
  note: {
    borderLeftWidth: 4,
    borderLeftColor: colors.teal,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    borderRadius: radius.sm,
  },
  noteText: { color: colors.textMuted, fontSize: font.small, lineHeight: 18 },
});
