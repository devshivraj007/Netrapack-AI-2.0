import { useEffect, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Pressable,
  StatusBar,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors, font, radius, spacing } from "../src/theme";

export default function Welcome() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  // Fade-in animation for the content
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(30)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 700,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 700,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  return (
    <View style={[styles.root, { paddingTop: insets.top, paddingBottom: insets.bottom + spacing.xl }]}>
      <StatusBar barStyle="light-content" backgroundColor={colors.navy} />

      {/* Top watermark bar */}
      <View style={styles.topBar}>
        <View style={styles.sealOuter}>
          <View style={styles.sealMiddle}>
            <View style={styles.sealInner}>
              <Text style={styles.sealAcronym}>DCA</Text>
            </View>
          </View>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.deptHindi} numberOfLines={1}>उपभोक्ता मामले विभाग</Text>
          <Text style={styles.deptEng} numberOfLines={1}>DEPARTMENT OF CONSUMER AFFAIRS</Text>
        </View>
        <View style={styles.govBadge}>
          <Text style={styles.govBadgeText}>GoI</Text>
        </View>
      </View>

      {/* Animated main content */}
      <Animated.View
        style={[
          styles.content,
          { opacity: fadeAnim, transform: [{ translateY: slideAnim }] },
        ]}
      >
        {/* App identity block */}
        <View style={styles.identityBlock}>
          {/* Large circular badge */}
          <View style={styles.heroBadgeOuter}>
            <View style={styles.heroBadgeMiddle}>
              <View style={styles.heroBadgeInner}>
                <Text style={styles.heroBadgeText}>NP</Text>
              </View>
            </View>
          </View>
          <Text style={styles.appName}>NetraPack</Text>
          <Text style={styles.tagline}>
            Packaged Commodity Compliance{"\n"}Powered by Legal Metrology AI
          </Text>
        </View>

        {/* Feature highlights */}
        <View style={styles.features}>
          {[
            { icon: "📷", text: "Scan any product label with your camera" },
            { icon: "⚖️", text: "Instant Legal Metrology Rules 2011 check" },
            { icon: "📋", text: "Violation reports with legal citations" },
            { icon: "🏛️", text: "Officer tools for Section 36 notices" },
          ].map(({ icon, text }) => (
            <View key={text} style={styles.featureRow}>
              <Text style={styles.featureIcon}>{icon}</Text>
              <Text style={styles.featureText}>{text}</Text>
            </View>
          ))}
        </View>

        {/* CTA */}
        <Pressable
          style={({ pressed }) => [styles.ctaBtn, pressed && styles.ctaBtnPressed]}
          onPress={() => router.replace("/")}
        >
          <Text style={styles.ctaBtnText}>GET STARTED  →</Text>
        </Pressable>

        <Text style={styles.legalNote}>
          For authorised food safety and metrology officers, tap "Officer Login"
          from the home screen.
        </Text>
      </Animated.View>

      {/* Bottom attribution strip */}
      <View style={styles.bottomBar}>
        <Text style={styles.bottomText}>
          Ministry of Consumer Affairs, Food &amp; Public Distribution
        </Text>
        <Text style={styles.bottomText}>Government of India</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.navy,
    justifyContent: "space-between",
  },

  // Top bar — thin, spaced like a gov letterhead
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.12)",
  },

  // Concentric-ring seal (same as Header)
  sealOuter: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.saffron,
    alignItems: "center",
    justifyContent: "center",
  },
  sealMiddle: {
    width: 33,
    height: 33,
    borderRadius: 17,
    backgroundColor: colors.white,
    alignItems: "center",
    justifyContent: "center",
  },
  sealInner: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.navy,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.2)",
    alignItems: "center",
    justifyContent: "center",
  },
  sealAcronym: {
    color: colors.white,
    fontWeight: "900",
    fontSize: 9,
    letterSpacing: 0.5,
  },
  deptHindi: {
    color: "rgba(255,255,255,0.75)",
    fontSize: 10,
    fontWeight: "600",
  },
  deptEng: {
    color: colors.white,
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 0.4,
  },
  govBadge: {
    backgroundColor: colors.saffron,
    borderRadius: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  govBadgeText: {
    color: colors.white,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 0.5,
  },

  // Main animated content
  content: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
    gap: spacing.xl,
  },

  // Hero identity
  identityBlock: { alignItems: "center", gap: spacing.md },

  heroBadgeOuter: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.saffron,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.saffron,
    shadowOpacity: 0.5,
    shadowRadius: 20,
    elevation: 12,
  },
  heroBadgeMiddle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.white,
    alignItems: "center",
    justifyContent: "center",
  },
  heroBadgeInner: {
    width: 62,
    height: 62,
    borderRadius: 31,
    backgroundColor: colors.navy,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.saffron,
  },
  heroBadgeText: {
    color: colors.white,
    fontWeight: "900",
    fontSize: 22,
    letterSpacing: 1,
  },
  appName: {
    color: colors.white,
    fontSize: 36,
    fontWeight: "900",
    letterSpacing: 1,
    marginTop: spacing.sm,
  },
  tagline: {
    color: "rgba(255,255,255,0.65)",
    fontSize: font.body,
    textAlign: "center",
    lineHeight: 24,
  },

  // Feature list
  features: {
    width: "100%",
    gap: spacing.sm,
    backgroundColor: "rgba(255,255,255,0.07)",
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
  },
  featureRow: { flexDirection: "row", gap: spacing.md, alignItems: "center" },
  featureIcon: { fontSize: 18, width: 28, textAlign: "center" },
  featureText: {
    flex: 1,
    color: "rgba(255,255,255,0.85)",
    fontSize: font.small,
    lineHeight: 18,
    fontWeight: "500",
  },

  // CTA button
  ctaBtn: {
    width: "100%",
    backgroundColor: colors.saffron,
    borderRadius: radius.lg,
    paddingVertical: 16,
    alignItems: "center",
    shadowColor: colors.saffron,
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 8,
  },
  ctaBtnPressed: { opacity: 0.85, transform: [{ scale: 0.98 }] },
  ctaBtnText: {
    color: colors.white,
    fontSize: font.h3,
    fontWeight: "900",
    letterSpacing: 1,
  },

  legalNote: {
    color: "rgba(255,255,255,0.4)",
    fontSize: font.label,
    textAlign: "center",
    lineHeight: 18,
  },

  // Bottom attribution
  bottomBar: {
    alignItems: "center",
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: "rgba(255,255,255,0.08)",
    paddingBottom: spacing.sm,
  },
  bottomText: {
    color: "rgba(255,255,255,0.35)",
    fontSize: 10,
    letterSpacing: 0.3,
  },
});
