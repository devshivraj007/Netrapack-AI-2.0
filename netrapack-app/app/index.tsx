import { useEffect, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Pressable,
  StatusBar,
  Image,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { colors, font, radius, spacing } from "../src/theme";

const EMBLEM_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Emblem_of_India.svg/200px-Emblem_of_India.svg.png";

export default function Welcome() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(20)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 500,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 500,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor="#ffffff" />

      {/* Top Header */}
      <View style={styles.topHeader}>
        <View style={styles.headerLeft}>
          <Image 
            source={{ uri: EMBLEM_URL }} 
            style={[styles.headerEmblem, { tintColor: colors.navyDark }]} 
            resizeMode="contain" 
          />
          <View>
            <Text style={styles.headerTitle}>Department of Consumer Affairs</Text>
            <Text style={styles.headerSubtitle}>Ministry of Consumer Affairs, Food & Public Distribution</Text>
          </View>
        </View>
        <View style={styles.liveBadge}>
          <View style={styles.liveDot} />
          <Text style={styles.liveText}>LIVE</Text>
        </View>
      </View>

      <ScrollView 
        style={styles.scrollArea} 
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
        showsVerticalScrollIndicator={false}
      >
        <Animated.View style={{ opacity: fadeAnim, transform: [{ translateY: slideAnim }] }}>
          
          {/* Hero Banner */}
          <View style={styles.heroCard}>
            <View style={styles.heroBackgroundPattern} />
            
            <View style={styles.emblemCircle}>
              <Image 
                source={{ uri: EMBLEM_URL }} 
                style={[styles.heroEmblem, { tintColor: "#ffffff" }]} 
                resizeMode="contain" 
              />
            </View>

            <View style={styles.heroPill}>
              <MaterialCommunityIcons name="scale-balance" size={12} color="#FCEB8D" />
              <Text style={styles.heroPillText}>Legal Metrology Division</Text>
            </View>

            <View style={styles.heroTitleRow}>
              <Text style={styles.heroTitle}>NetraPack</Text>
              <MaterialCommunityIcons name="check-decagram-outline" size={22} color="#00E676" />
            </View>

            <Text style={styles.heroSubtitle}>Legal Metrology Compliance Portal</Text>
            <Text style={styles.heroDesc}>
              AI-Powered Statutory Verification under Legal Metrology Act, 2009
            </Text>
          </View>

          {/* Modules Header */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>STATUTORY MODULES</Text>
            <Text style={styles.sectionLink}>Rule 6 & Section 36</Text>
          </View>

          {/* Module Cards */}
          <View style={styles.modulesContainer}>
            
            {/* Card 1 */}
            <View style={styles.moduleCard}>
              <View style={[styles.moduleIconBg, { backgroundColor: "#E3F2FD" }]}>
                <MaterialCommunityIcons name="crop-free" size={24} color="#1976D2" />
              </View>
              <View style={styles.moduleContent}>
                <Text style={styles.moduleTitle}>Instant Statutory Verification</Text>
                <Text style={styles.moduleDesc}>Optical scan of MRP, Net Quantity, Dates & Manufacturer details.</Text>
              </View>
              <View style={[styles.moduleBadge, { backgroundColor: "#E8F5E9", borderColor: "#C8E6C9" }]}>
                <Text style={[styles.moduleBadgeText, { color: "#2E7D32" }]}>AI OCR</Text>
              </View>
            </View>

            {/* Card 2 */}
            <View style={styles.moduleCard}>
              <View style={[styles.moduleIconBg, { backgroundColor: "#FFF8E1" }]}>
                <MaterialCommunityIcons name="check-all" size={24} color="#F57C00" />
              </View>
              <View style={styles.moduleContent}>
                <Text style={styles.moduleTitle}>Rule 6 Declarations Checklist</Text>
                <Text style={styles.moduleDesc}>Automated mandatory compliance verification under Legal Metrology Act, 2009.</Text>
              </View>
              <View style={[styles.moduleBadge, { backgroundColor: "#E3F2FD", borderColor: "#BBDEFB" }]}>
                <Text style={[styles.moduleBadgeText, { color: "#1976D2" }]}>PCR 2011</Text>
              </View>
            </View>

            {/* Card 3 */}
            <View style={styles.moduleCard}>
              <View style={[styles.moduleIconBg, { backgroundColor: "#FFEBEE" }]}>
                <MaterialCommunityIcons name="gavel" size={24} color="#D32F2F" />
              </View>
              <View style={styles.moduleContent}>
                <Text style={styles.moduleTitle}>Grievance & Section 36 Notice</Text>
                <Text style={styles.moduleDesc}>1-tap infraction report dispatch to National Consumer Helpline & Legal Metrology Officers.</Text>
              </View>
              <View style={[styles.moduleBadge, { backgroundColor: "#FFEBEE", borderColor: "#FFCDD2" }]}>
                <Text style={[styles.moduleBadgeText, { color: "#C62828" }]}>NCH 1915</Text>
              </View>
            </View>

          </View>

          {/* Action Buttons */}
          <View style={styles.actionContainer}>
            <Pressable
              style={({ pressed }) => [styles.scanBtn, pressed && styles.btnPressed]}
              onPress={() => router.push("/scan")}
            >
              <MaterialCommunityIcons name="qrcode-scan" size={22} color="#ffffff" style={{ marginRight: 8 }} />
              <Text style={styles.scanBtnText}>Start Label Scan</Text>
              <MaterialCommunityIcons name="arrow-right" size={20} color="#ffffff" style={{ marginLeft: 6 }} />
            </Pressable>

            <Pressable
              style={({ pressed }) => [styles.officerBtn, pressed && styles.btnPressed]}
              onPress={() => router.push("/officer-login")}
            >
              <MaterialCommunityIcons name="shield-account-outline" size={20} color="#1976D2" style={{ marginRight: 8 }} />
              <Text style={styles.officerBtnText}>Officer Login with e-Pramaan SSO</Text>
            </Pressable>
          </View>

        </Animated.View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#F5F7FA",
  },
  
  /* Header */
  topHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#ffffff",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#E0E0E0",
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  headerEmblem: {
    width: 28,
    height: 40,
  },
  headerTitle: {
    fontSize: 12,
    fontWeight: "900",
    color: colors.navyDark,
  },
  headerSubtitle: {
    fontSize: 9,
    color: colors.textMuted,
    fontWeight: "500",
    marginTop: 2,
  },
  liveBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#E8F5E9",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#C8E6C9",
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#00E676",
    marginRight: 4,
  },
  liveText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#2E7D32",
    letterSpacing: 0.5,
  },

  /* Scroll Area */
  scrollArea: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    gap: 20,
  },

  /* Hero Banner */
  heroCard: {
    backgroundColor: "#1C315E",
    borderRadius: 16,
    padding: 24,
    alignItems: "center",
    overflow: "hidden",
    shadowColor: "#1C315E",
    shadowOpacity: 0.2,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  heroBackgroundPattern: {
    position: "absolute",
    top: -50,
    right: -50,
    width: 300,
    height: 300,
    borderRadius: 150,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.05)",
  },
  emblemCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#111D3B",
    borderWidth: 2,
    borderColor: "#FCEB8D",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  heroEmblem: {
    width: 34,
    height: 46,
  },
  heroPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(252, 235, 141, 0.15)",
    borderWidth: 1,
    borderColor: "#FCEB8D",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginBottom: 12,
  },
  heroPillText: {
    color: "#FCEB8D",
    fontSize: 10,
    fontWeight: "800",
    marginLeft: 6,
  },
  heroTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 4,
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: "900",
    color: "#ffffff",
    marginRight: 6,
    letterSpacing: 0.5,
  },
  heroSubtitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#ffffff",
    marginBottom: 12,
  },
  heroDesc: {
    fontSize: 11,
    color: "rgba(255,255,255,0.7)",
    textAlign: "center",
    paddingHorizontal: 10,
    lineHeight: 16,
  },

  /* Sections */
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 4,
    marginBottom: -8,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: "800",
    color: colors.navyDark,
    letterSpacing: 0.5,
  },
  sectionLink: {
    fontSize: 12,
    fontWeight: "700",
    color: "#1976D2",
  },

  /* Modules */
  modulesContainer: {
    gap: 12,
  },
  moduleCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ffffff",
    borderRadius: 12,
    padding: 16,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
    borderWidth: 1,
    borderColor: "#EAEAEA",
  },
  moduleIconBg: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 14,
  },
  moduleContent: {
    flex: 1,
    paddingRight: 8,
  },
  moduleTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: colors.navyDark,
    marginBottom: 4,
  },
  moduleDesc: {
    fontSize: 10,
    color: colors.textMuted,
    lineHeight: 14,
  },
  moduleBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
  },
  moduleBadgeText: {
    fontSize: 9,
    fontWeight: "900",
  },

  /* Actions */
  actionContainer: {
    gap: 12,
    marginTop: 8,
  },
  scanBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#D84315", // Deep orange
    paddingVertical: 16,
    borderRadius: 12,
    shadowColor: "#D84315",
    shadowOpacity: 0.3,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  scanBtnText: {
    fontSize: 16,
    fontWeight: "800",
    color: "#ffffff",
  },
  officerBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#ffffff",
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E0E0E0",
  },
  officerBtnText: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.navyDark,
  },
  btnPressed: {
    opacity: 0.8,
    transform: [{ scale: 0.98 }],
  },
});
