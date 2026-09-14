import { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Pressable,
  ScrollView,
  Image,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import * as ImageManipulator from "expo-image-manipulator";
import { useRouter } from "expo-router";
import { Header } from "../src/components/Header";
import { Button } from "../src/components/Button";
import { colors, font, radius, spacing } from "../src/theme";
import { processPhotos } from "../src/api";
import { setLastVerdict } from "../src/verdictStore";

const MAX_PHOTOS = 4;

// Staged progress messages so the wait feels responsive.
const PROGRESS_STAGES = [
  "Preparing images…",
  "Reading label panels…",
  "Checking compliance…",
  "Almost done…",
];

/**
 * Downscale a captured/picked image to ~1024px on the longest side and
 * re-compress before upload. Big phone photos (3-4000px, several MB) are slow to
 * send over the LAN and slow for the model.
 */
async function downscale(uri: string): Promise<string> {
  try {
    const result = await ImageManipulator.manipulateAsync(
      uri,
      [{ resize: { width: 1800 } }],
      { compress: 0.85, format: ImageManipulator.SaveFormat.JPEG },
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
  const [photos, setPhotos] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stageIndex, setStageIndex] = useState(0);
  const [showCamera, setShowCamera] = useState(false);
  const [barcode, setBarcode] = useState<string | null>(null);

  // Advance the progress message every ~1.5s while busy.
  useEffect(() => {
    if (!busy) return;
    const id = setInterval(() => {
      setStageIndex((i) => Math.min(i + 1, PROGRESS_STAGES.length - 1));
    }, 1500);
    return () => clearInterval(id);
  }, [busy]);

  async function submitAll() {
    if (photos.length === 0) return;
    setBusy(true);
    setError(null);
    setStageIndex(0);
    try {
      const scaled = await Promise.all(photos.map(downscale));
      const verdict = await processPhotos(scaled, {
        barcode: barcode || undefined,
      });
      setLastVerdict(verdict);
      router.replace("/review-fields");
    } catch (e) {
      setError(
        (e instanceof Error ? e.message : "Scan failed") +
          ". Check the API address in src/config.ts and that the backend is running on your PC's LAN IP.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function capturePhoto() {
    if (!cameraRef.current || photos.length >= MAX_PHOTOS) return;
    const photo = await cameraRef.current.takePictureAsync({ quality: 0.7 });
    if (photo?.uri) {
      setPhotos((prev) => [...prev, photo.uri]);
      setShowCamera(false);
    }
  }

  async function pickFromLibrary() {
    if (photos.length >= MAX_PHOTOS) return;
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.7,
      allowsMultipleSelection: true,
      selectionLimit: MAX_PHOTOS - photos.length,
    });
    if (!res.canceled) {
      const uris = res.assets.map((a) => a.uri);
      setPhotos((prev) => [...prev, ...uris].slice(0, MAX_PHOTOS));
    }
  }

  function removePhoto(index: number) {
    setPhotos((prev) => prev.filter((_, i) => i !== index));
  }

  // ── Busy/loading screen ────────────────────────────────────────────────────
  if (busy) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <Header subtitle="Scanning" />
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.navy} />
          <Text style={styles.busyText}>{PROGRESS_STAGES[stageIndex]}</Text>
          <Text style={styles.busyHint}>
            Analysing {photos.length} photo{photos.length !== 1 ? "s" : ""} —
            reading label declarations and checking Legal Metrology compliance.
          </Text>
        </View>
      </View>
    );
  }

  // ── Camera viewfinder overlay ──────────────────────────────────────────────
  if (showCamera) {
    if (!permission?.granted) {
      return (
        <View style={{ flex: 1, backgroundColor: colors.bg }}>
          <Header subtitle="Scan" />
          <View style={styles.body}>
            <Text style={styles.info}>Camera access is needed to scan a product label.</Text>
            <Button label="GRANT CAMERA ACCESS" onPress={requestPermission} />
            <Button
              label="CANCEL"
              variant="outline"
              onPress={() => setShowCamera(false)}
            />
          </View>
        </View>
      );
    }
    return (
      <View style={{ flex: 1, backgroundColor: "#000" }}>
        <CameraView
          ref={cameraRef}
          style={styles.fullCamera}
          facing="back"
          barcodeScannerSettings={{ barcodeTypes: ["ean13", "ean8", "qr", "upc_e", "upc_a"] }}
          onBarcodeScanned={(result) => setBarcode(result.data)}
        >
          <View style={styles.cameraTopBar}>
            <Pressable onPress={() => setShowCamera(false)} style={styles.camCancel}>
              <Text style={styles.camCancelText}>✕ Cancel</Text>
            </Pressable>
            <Text style={styles.cameraCounter}>
              Photo {photos.length + 1} of {MAX_PHOTOS}
            </Text>
          </View>
          <View style={styles.cameraHintWrap} pointerEvents="none">
            {barcode ? (
              <Text style={styles.barcodeDetected}>Barcode: {barcode}</Text>
            ) : null}
            <Text style={styles.cameraHint}>Align the label inside the frame</Text>
          </View>
          <View style={styles.captureRow}>
            <Pressable onPress={capturePhoto} style={styles.captureBtn}>
              <View style={styles.captureBtnInner} />
            </Pressable>
          </View>
        </CameraView>
      </View>
    );
  }

  // ── Main scan screen ───────────────────────────────────────────────────────
  const canAddMore = photos.length < MAX_PHOTOS;
  const canAnalyse = photos.length > 0;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <Header subtitle="Scan" />
      <ScrollView contentContainerStyle={styles.body}>

        {/* Instruction card */}
        <View style={styles.instructionCard}>
          <Text style={styles.instructionTitle}>
            Add 1–{MAX_PHOTOS} photos of the label
          </Text>
          <Text style={styles.instructionSub}>
            Capture each panel separately — front, back, side, or a barcode
            close-up. Add as many as you need, then tap Analyse.
          </Text>
        </View>

        {/* Thumbnail strip */}
        {photos.length > 0 ? (
          <View>
            <Text style={styles.sectionLabel}>
              CAPTURED PHOTOS ({photos.length}/{MAX_PHOTOS})
            </Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.thumbRow}>
                {photos.map((uri, i) => (
                  <View key={uri + i} style={styles.thumbWrap}>
                    <Image source={{ uri }} style={styles.thumb} />
                    <Pressable
                      onPress={() => removePhoto(i)}
                      style={styles.thumbRemove}
                    >
                      <Text style={styles.thumbRemoveText}>✕</Text>
                    </Pressable>
                    <Text style={styles.thumbLabel}>Photo {i + 1}</Text>
                  </View>
                ))}
              </View>
            </ScrollView>
          </View>
        ) : (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>📷</Text>
            <Text style={styles.emptyText}>No photos added yet</Text>
          </View>
        )}

        {/* Error message */}
        {error ? <Text style={styles.error}>{error}</Text> : null}

        {/* Barcode status in thumbnail view */}
        {photos.length > 0 && barcode ? (
          <View style={styles.barcodeCard}>
            <Text style={styles.barcodeIcon}>🏷️</Text>
            <View>
              <Text style={styles.barcodeLabel}>Barcode Detected</Text>
              <Text style={styles.barcodeValue}>{barcode}</Text>
            </View>
          </View>
        ) : null}

        {/* Add photo actions */}
        {canAddMore ? (
          <View style={styles.addRow}>
            <Button
              label={photos.length === 0 ? "📷  TAKE PHOTO" : "📷  ADD ANOTHER PHOTO"}
              onPress={() => setShowCamera(true)}
            />
            <Pressable onPress={pickFromLibrary} style={styles.galleryLink}>
              <Text style={styles.gallery}>Or choose from gallery</Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.limitBadge}>
            <Text style={styles.limitText}>Maximum {MAX_PHOTOS} photos reached</Text>
          </View>
        )}

        {/* Analyse button */}
        {canAnalyse ? (
          <Button
            label={`CAPTURE & ANALYSE  (${photos.length} photo${photos.length !== 1 ? "s" : ""})`}
            onPress={submitAll}
          />
        ) : null}

      </ScrollView>
    </View>
  );
}

const THUMB_SIZE = 100;

const styles = StyleSheet.create({
  body: { padding: spacing.lg, gap: spacing.lg },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
    gap: spacing.md,
  },
  busyText: { fontSize: font.h3, fontWeight: "700", color: colors.navy },
  busyHint: {
    fontSize: font.small,
    color: colors.textMuted,
    textAlign: "center",
    lineHeight: 18,
  },

  // Instruction card
  instructionCard: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  instructionTitle: {
    fontSize: font.h3,
    fontWeight: "800",
    color: colors.navy,
  },
  instructionSub: {
    fontSize: font.small,
    color: colors.textMuted,
    lineHeight: 18,
  },

  // Section label
  sectionLabel: {
    fontSize: font.label,
    fontWeight: "800",
    color: colors.textMuted,
    letterSpacing: 0.8,
    marginBottom: spacing.sm,
  },

  // Thumbnail strip
  thumbRow: {
    flexDirection: "row",
    gap: spacing.md,
    paddingBottom: spacing.sm,
  },
  thumbWrap: {
    alignItems: "center",
    gap: spacing.xs,
  },
  thumb: {
    width: THUMB_SIZE,
    height: THUMB_SIZE,
    borderRadius: radius.md,
    borderWidth: 2,
    borderColor: colors.teal,
  },
  thumbRemove: {
    position: "absolute",
    top: -6,
    right: -6,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.red,
    alignItems: "center",
    justifyContent: "center",
  },
  thumbRemoveText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: "900",
    lineHeight: 14,
  },
  thumbLabel: {
    fontSize: font.label,
    color: colors.textMuted,
    fontWeight: "600",
  },

  // Empty state
  emptyState: {
    alignItems: "center",
    paddingVertical: spacing.xl,
    gap: spacing.sm,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    borderStyle: "dashed",
  },
  emptyIcon: { fontSize: 40 },
  emptyText: { fontSize: font.body, color: colors.textMuted, fontWeight: "600" },

  // Add photo section
  addRow: { gap: spacing.sm },
  galleryLink: { alignSelf: "center" },
  gallery: {
    color: colors.navy,
    textAlign: "center",
    fontWeight: "700",
    fontSize: font.label,
  },

  limitBadge: {
    backgroundColor: colors.lavender,
    borderWidth: 1,
    borderColor: colors.lavenderBorder,
    borderRadius: radius.sm,
    padding: spacing.md,
    alignItems: "center",
  },
  limitText: { color: colors.navy, fontWeight: "700", fontSize: font.small },

  // Error
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
  info: { fontSize: font.body, color: colors.text, lineHeight: 22 },

  // Camera overlay
  fullCamera: { flex: 1 },
  cameraTopBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 56,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    backgroundColor: "rgba(0,0,0,0.4)",
  },
  camCancel: { padding: spacing.sm },
  camCancelText: { color: colors.white, fontWeight: "700", fontSize: font.body },
  cameraCounter: { color: colors.white, fontWeight: "700", fontSize: font.label },
  cameraHintWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "flex-end",
    paddingBottom: spacing.xl,
  },
  cameraHint: {
    color: colors.white,
    fontWeight: "700",
    fontSize: font.small,
    backgroundColor: "rgba(11,47,107,0.85)",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
    overflow: "hidden",
  },
  captureRow: {
    alignItems: "center",
    paddingBottom: 48,
  },
  captureBtn: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 4,
    borderColor: colors.white,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.15)",
  },
  captureBtnInner: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: colors.white,
  },

  // Barcode styles
  barcodeDetected: {
    color: colors.white,
    backgroundColor: colors.teal,
    fontWeight: "800",
    fontSize: font.small,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
    marginBottom: spacing.xs,
    overflow: "hidden",
  },
  barcodeCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.teal,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  barcodeIcon: { fontSize: 24 },
  barcodeLabel: { fontSize: font.label, fontWeight: "700", color: colors.tealDark },
  barcodeValue: { fontSize: font.body, fontWeight: "800", color: colors.text, marginTop: 2 },
});
