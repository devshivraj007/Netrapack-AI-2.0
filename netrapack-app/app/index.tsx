import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  StatusBar,
  Image,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { colors, font, radius, spacing } from "../src/theme";
import { session } from "../src/session";

const EMBLEM_IMG = require("../assets/images/emblem.png");

export default function Home() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [, force] = useState(0);

  useEffect(() => {
    return session.subscribe(() => force((n) => n + 1));
  }, []);

  const isOfficer = session.isOfficer();
  const currentSession = session.get();

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <StatusBar barStyle="dark-content" backgroundColor="#ffffff" />

      {/* Top Header */}
      <View style={styles.topHeader}>
        <View style={styles.headerLeft}>
          <View style={styles.headerEmblemWrap}>
            <Image 
              source={EMBLEM_IMG} 
              style={styles.headerEmblem} 
              resizeMode="contain" 
            />
          </View>
          <View style={styles.headerTextCol}>
            <Text style={styles.headerTitle} numberOfLines={1}>
              Department of Consumer Affairs
            </Text>
            <Text style={styles.headerSubtitle} numberOfLines={1}>
              Ministry of Consumer Affairs, Food & Public Distribution
            </Text>
          </View>
        </View>
        <View style={styles.liveBadge}>
          <View style={styles.liveDot} />
          <Text style={styles.liveText}>LIVE</Text>
        </View>
      </View>

      <ScrollView 
        style={styles.scrollArea} 
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + 24 }]}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero Banner */}
        <View style={styles.heroCard}>
          <View style={styles.heroPattern1} />
          <View style={styles.heroPattern2} />

          {/* White Circular Emblem Ring */}
          <View style={styles.emblemCircle}>
            <Image 
              source={EMBLEM_IMG} 
              style={styles.heroEmblem} 
              resizeMode="contain" 
            />
          </View>

          {/* Legal Metrology Pill */}
          <View style={styles.heroPill}>
            <MaterialCommunityIcons name="scale-balance" size={13} color="#FCEB8D" />
            <Text style={styles.heroPillText}>Legal Metrology Division</Text>
          </View>

          {/* Title Row */}
          <View style={styles.heroTitleRow}>
            <Text style={styles.heroTitle}>NetraPack</Text>
            <MaterialCommunityIcons name="check-decagram" size={22} color="#00E676" />
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
          
          {/* Card 1: Instant Statutory Verification */}
          <View style={styles.moduleCard}>
            <View style={[styles.moduleIconBg, { backgroundColor: "#EFF6FF" }]}>
              <MaterialCommunityIcons name="crop-free" size={24} color="#2563EB" />
            </View>
            <View style={styles.moduleContent}>
              <Text style={styles.moduleTitle}>Instant Statutory Verification</Text>
              <Text style={styles.moduleDesc}>
                Optical scan of MRP, Net Quantity, Dates & Manufacturer details.
              </Text>
            </View>
            <View style={[styles.moduleBadge, { backgroundColor: "#ECFDF5", borderColor: "#A7F3D0" }]}>
              <Text style={[styles.moduleBadgeText, { color: "#059669" }]}>AI OCR</Text>
            </View>
          </View>

          {/* Card 2: Rule 6 Declarations Checklist */}
          <View style={styles.moduleCard}>
            <View style={[styles.moduleIconBg, { backgroundColor: "#FFFBEB" }]}>
              <MaterialCommunityIcons name="check-all" size={24} color="#D97706" />
            </View>
            <View style={styles.moduleContent}>
              <Text style={styles.moduleTitle}>Rule 6 Declarations Checklist</Text>
              <Text style={styles.moduleDesc}>
                Automated mandatory compliance verification under Legal Metrology Act, 2009.
              </Text>
            </View>
            <View style={[styles.moduleBadge, { backgroundColor: "#EFF6FF", borderColor: "#BFDBFE" }]}>
              <Text style={[styles.moduleBadgeText, { color: "#2563EB" }]}>PCR 2011</Text>
            </View>
          </View>

          {/* Card 3: Grievance & Section 36 Notice */}
          <View style={styles.moduleCard}>
            <View style={[styles.moduleIconBg, { backgroundColor: "#FEF2F2" }]}>
              <MaterialCommunityIcons name="gavel" size={24} color="#DC2626" />
            </View>
            <View style={styles.moduleContent}>
              <Text style={styles.moduleTitle}>Grievance & Section 36 Notice</Text>
              <Text style={styles.moduleDesc}>
                1-tap infraction report dispatch to National Consumer Helpline & Legal Metrology Officers.
              </Text>
            </View>
            <View style={[styles.moduleBadge, { backgroundColor: "#FEF2F2", borderColor: "#FECACA" }]}>
              <Text style={[styles.moduleBadgeText, { color: "#DC2626" }]}>NCH 1915</Text>
            </View>
          </View>

        </View>

        {/* Action Buttons */}
        <View style={styles.actionContainer}>
          {/* Primary Scan Button */}
          <Pressable
            style={({ pressed }) => [styles.scanBtn, pressed && styles.btnPressed]}
            onPress={() => router.push("/scan")}
          >
            <MaterialCommunityIcons name="qrcode-scan" size={20} color="#ffffff" style={{ marginRight: 8 }} />
            <Text style={styles.scanBtnText}>Start Label Scan</Text>
            <MaterialCommunityIcons name="arrow-right" size={18} color="#ffffff" style={{ marginLeft: 6 }} />
          </Pressable>

          {/* Officer Status / Login Button */}
          {isOfficer ? (
            <View style={styles.officerActiveCard}>
              <View style={styles.officerInfoRow}>
                <MaterialCommunityIcons name="shield-check" size={20} color="#059669" />
                <View style={{ flex: 1, marginLeft: 8 }}>
                  <Text style={styles.officerName}>
                    Officer Active: {currentSession.userId ?? "officer"}
                  </Text>
                  <Text style={styles.officerRole}>
                    e-Pramaan SSO Authenticated ({currentSession.role?.toUpperCase()})
                  </Text>
                </View>
                <Pressable onPress={() => session.logout()} style={styles.logoutBtn}>
                  <Text style={styles.logoutText}>Log out</Text>
                </Pressable>
              </View>
              <Pressable
                style={({ pressed }) => [styles.historyBtn, pressed && styles.btnPressed]}
                onPress={() => router.push("/history")}
              >
                <MaterialCommunityIcons name="file-search-outline" size={18} color="#1D4ED8" style={{ marginRight: 6 }} />
                <Text style={styles.historyBtnText}>Search Scan Records & Notices</Text>
              </Pressable>
            </View>
          ) : (
            <Pressable
              style={({ pressed }) => [styles.officerBtn, pressed && styles.btnPressed]}
              onPress={() => router.push("/officer-login")}
            >
              <MaterialCommunityIcons name="shield-account-outline" size={20} color="#1D4ED8" style={{ marginRight: 8 }} />
              <Text style={styles.officerBtnText}>Officer Login with e-Pramaan SSO</Text>
            </Pressable>
          )}
        </View>

      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#F4F6F9",
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
    borderBottomColor: "#E2E8F0",
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
    marginRight: 8,
  },
  headerEmblemWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#0F2137",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  headerEmblem: {
    width: 32,
    height: 32,
  },
  headerTextCol: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 12.5,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.2,
  },
  headerSubtitle: {
    fontSize: 9.5,
    color: "#64748B",
    fontWeight: "500",
    marginTop: 1.5,
  },
  liveBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ECFDF5",
    paddingHorizontal: 8,
    paddingVertical: 3.5,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#10B981",
    marginRight: 4,
  },
  liveText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#059669",
    letterSpacing: 0.5,
  },

  /* Scroll Area */
  scrollArea: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    gap: 16,
  },

  /* Hero Banner */
  heroCard: {
    backgroundColor: "#102A4E",
    borderRadius: 18,
    paddingVertical: 22,
    paddingHorizontal: 18,
    alignItems: "center",
    overflow: "hidden",
    shadowColor: "#102A4E",
    shadowOpacity: 0.25,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
    position: "relative",
  },
  heroPattern1: {
    position: "absolute",
    top: -40,
    right: -40,
    width: 220,
    height: 220,
    borderRadius: 110,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.06)",
  },
  heroPattern2: {
    position: "absolute",
    top: -10,
    right: -10,
    width: 160,
    height: 160,
    borderRadius: 80,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.04)",
  },
  emblemCircle: {
    width: 74,
    height: 74,
    borderRadius: 37,
    backgroundColor: "#0F2137",
    borderWidth: 2.5,
    borderColor: "#ffffff",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    marginBottom: 12,
    shadowColor: "#000",
    shadowOpacity: 0.3,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
  heroEmblem: {
    width: 66,
    height: 66,
  },
  heroPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(252, 235, 141, 0.12)",
    borderWidth: 1,
    borderColor: "#E5C158",
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 16,
    marginBottom: 10,
  },
  heroPillText: {
    color: "#FCEB8D",
    fontSize: 10.5,
    fontWeight: "700",
    marginLeft: 6,
  },
  heroTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  heroTitle: {
    fontSize: 26,
    fontWeight: "900",
    color: "#ffffff",
    marginRight: 6,
    letterSpacing: 0.5,
  },
  heroSubtitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#93C5FD",
    marginBottom: 6,
  },
  heroDesc: {
    fontSize: 11,
    color: "#CBD5E1",
    textAlign: "center",
    paddingHorizontal: 8,
    lineHeight: 16,
  },

  /* Sections */
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 2,
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: 11.5,
    fontWeight: "800",
    color: "#334155",
    letterSpacing: 0.5,
  },
  sectionLink: {
    fontSize: 11.5,
    fontWeight: "700",
    color: "#2563EB",
  },

  /* Modules */
  modulesContainer: {
    gap: 10,
  },
  moduleCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#ffffff",
    borderRadius: 12,
    padding: 14,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
    borderWidth: 1,
    borderColor: "#EAEAEA",
  },
  moduleIconBg: {
    width: 42,
    height: 42,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  moduleContent: {
    flex: 1,
    paddingRight: 8,
  },
  moduleTitle: {
    fontSize: 13,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 3,
  },
  moduleDesc: {
    fontSize: 10.5,
    color: "#64748B",
    lineHeight: 15,
  },
  moduleBadge: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
  },
  moduleBadgeText: {
    fontSize: 9.5,
    fontWeight: "800",
  },

  /* Actions */
  actionContainer: {
    gap: 10,
    marginTop: 4,
  },
  scanBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#D84315", // Rich deep orange matching user design
    paddingVertical: 15,
    borderRadius: 12,
    shadowColor: "#D84315",
    shadowOpacity: 0.35,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
  },
  scanBtnText: {
    fontSize: 15.5,
    fontWeight: "800",
    color: "#ffffff",
  },
  officerBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#ffffff",
    paddingVertical: 13,
    borderRadius: 12,
    borderWidth: 1.2,
    borderColor: "#CBD5E1",
    shadowColor: "#000",
    shadowOpacity: 0.03,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  officerBtnText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#1E3A5F",
  },

  /* Officer active card */
  officerActiveCard: {
    backgroundColor: "#EFF6FF",
    borderWidth: 1.2,
    borderColor: "#BFDBFE",
    borderRadius: 12,
    padding: 12,
    gap: 10,
  },
  officerInfoRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  officerName: {
    fontSize: 12.5,
    fontWeight: "800",
    color: "#1E3A5F",
  },
  officerRole: {
    fontSize: 10,
    color: "#2563EB",
    fontWeight: "600",
    marginTop: 1,
  },
  logoutBtn: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  logoutText: {
    color: "#DC2626",
    fontSize: 11,
    fontWeight: "800",
  },
  historyBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#ffffff",
    paddingVertical: 9,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#93C5FD",
  },
  historyBtnText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#1D4ED8",
  },

  btnPressed: {
    opacity: 0.85,
    transform: [{ scale: 0.985 }],
  },
});
