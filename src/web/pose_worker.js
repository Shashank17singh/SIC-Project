/*
 * Runs pose detection off the main thread, so a slow device updates the
 * skeleton less often but never stalls the video.
 * A classic worker, because MediaPipe's loader calls importScripts, which
 * module workers do not allow. The library itself loads by dynamic import.
 */
let landmarker = null;

async function init({ visionUrl, modelUrl, minConfidence }) {
  const { FilesetResolver, PoseLandmarker } = await import(`${visionUrl}/vision_bundle.mjs`);

  const vision = await FilesetResolver.forVisionTasks(`${visionUrl}/wasm`);
  const create = (delegate) =>
    PoseLandmarker.createFromOptions(vision, {
      baseOptions: { modelAssetPath: modelUrl, delegate },
      canvas: new OffscreenCanvas(1, 1),
      runningMode: "VIDEO",
      numPoses: 1,
      minPoseDetectionConfidence: minConfidence,
      minPosePresenceConfidence: minConfidence,
      minTrackingConfidence: minConfidence,
    });
  landmarker = await create("GPU").catch(() => create("CPU"));
  self.postMessage({ type: "ready", connections: PoseLandmarker.POSE_CONNECTIONS });
}

function detect({ bitmap, timestamp }) {
  const landmarks = landmarker.detectForVideo(bitmap, timestamp).landmarks[0];
  bitmap.close();
  self.postMessage({ type: "result", landmarks });
}

self.onmessage = async ({ data }) => {
  try {
    if (data.type === "init") await init(data);
    else detect(data);
  } catch (error) {
    self.postMessage({ type: "error", message: String(error) });
  }
};
