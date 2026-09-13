import { useEffect, useRef, useState } from "react";
import { View, Text, StyleSheet, ActivityIndicator, Pressable } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import * as ImageManipulator from "expo-image-manipulator";
import { useRouter } from "expo-router";
import { Header } from "../src/components/Header";
import { Button } from "../src/components/Button";
import { colors, font, radius, spacing } from "../src/theme";
import { processPhoto } from "../src/api";
import { setLastVerdict } from "../src/verdictStore";

// Staged progress messages so the wait feels responsive even if it takes a few
// seconds. We advance them on a timer while the request is in flight.
const PROGRESS_STAGES = [
  "Preparing image…",
  "Reading label…",
  "Checking compliance…",
  "Almost done…",
];

/**
 * Downscale a captured/picked image to ~1024px on the longest side and
 * re-compress before upload. Big phone photos (3-4000px, several MB) are slow to
 * send over the LAN and slow for the model; this cuts upload + processing time
 * significantly. Falls back to the original URI if manipulation fails.
 */
async function downscale(uri: string): Promise<string> {
  try {
    const result = await ImageManipulator.manipulateAsync(
      uri,
      [{ resize: { width: 1024 } }],
      { compress: 0.7, format: ImageManipulator.SaveFormat.JPEG },
    );
    return result.uri;
  } catch {
    return uri;
  }
}

export default function Scan() {
  const router = useRouter();
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stageIndex, setStageIndex] = useState(0);

  // Advance the progress message every ~1.5s while busy.
  useEffect(() => {
    if (!busy) return;
    const id = setInterval(() => {
      setStageIndex((i) => Math.min(i + 1, PROGRESS_STAGES.length - 1));
    }, 1500);
    return () => clearInterval(id);
  }, [busy]);

  async function submit(uri: string) {
    setBusy(true);
    setError(null);
    setStageIndex(0);
    try {
      const smaller = await downscale(uri);
      const verdict = await processPhoto(smaller);
      setLastVerdict(verdict);
      router.replace("/verdict");
    } catch (e) {
      setError(
        (e instanceof Error ? e.message : "Scan failed") +
          ". Check the API address in src/config.ts and that the backend is running on your PC's LAN IP.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function capture() {
    if (!cameraRef.current) return;
    const photo = await cameraRef.current.takePictureAsync({ quality: 0.7 });
    if (photo?.uri) await submit(photo.uri);
  }

  async function pickFromLibrary() {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.7,
    });
    if (!res.canceled && res.assets[0]?.uri) await submit(res.assets[0].uri);
  }

  if (busy) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <Header subtitle="Scanning" />
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.navy} />
          <Text style={styles.busyText}>{PROGRESS_STAGES[stageIndex]}</Text>
          <Text style={styles.busyHint}>
            Reading the printed declarations and checking Legal Metrology
            compliance.
          </Text>
        </View>
      </View>
    );
  }

  if (!permission) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <Header subtitle="Scan" />
        <View style={styles.center}>
          <ActivityIndicator color={colors.navy} />
        </View>
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <Header subtitle="Scan" />
        <View style={styles.body}>
          <Text style={styles.info}>
            Camera access is needed to scan a product label.
          </Text>
          <Button label="GRANT CAMERA ACCESS" onPress={requestPermission} />
          <Button label="CHOOSE FROM GALLERY" variant="outline" onPress={pickFromLibrary} />
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="Scan" />
      <View style={styles.body}>
        <View style={styles.cameraWrap}>
          <CameraView ref={cameraRef} style={styles.camera} facing="back" />
          <View style={styles.frameHint} pointerEvents="none">
            <Text style={styles.frameHintText}>
              Align the label inside the frame
            </Text>
          </View>
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Button label="CAPTURE & ANALYSE" onPress={capture} />
        <Pressable onPress={pickFromLibrary}>
          <Text style={styles.gallery}>Or choose a photo from gallery</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { flex: 1, padding: spacing.lg, gap: spacing.md },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, gap: spacing.md },
  busyText: { fontSize: font.h3, fontWeight: "700", color: colors.navy },
  busyHint: { fontSize: font.small, color: colors.textMuted, textAlign: "center" },
  cameraWrap: {
    flex: 1,
    borderRadius: radius.lg,
    overflow: "hidden",
    borderWidth: 2,
    borderColor: colors.navy,
  },
  camera: { flex: 1 },
  frameHint: {
    position: "absolute",
    bottom: spacing.md,
    alignSelf: "center",
    backgroundColor: "rgba(11,47,107,0.85)",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
  },
  frameHintText: { color: colors.white, fontWeight: "700", fontSize: font.small },
  info: { fontSize: font.body, color: colors.text, lineHeight: 22 },
  gallery: { color: colors.navy, textAlign: "center", fontWeight: "700", fontSize: font.label },
  error: {
    color: colors.red,
    backgroundColor: "#FBE9E7",
    borderColor: colors.red,
    borderWidth: 1,
    borderRadius: radius.sm,
    padding: spacing.md,
    fontSize: font.small,
    fontWeight: "600",
  },
});
