/*
 * Runs the camera in the browser. The <video> element shows it directly, so
 * nothing is compressed or sent to a server. Frames go to pose_worker.js for
 * detection, and the skeleton is drawn on a canvas above the video.
 */
const VISION_VERSION = "1.2.0";
const VISION_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VISION_VERSION}`;
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task";
const CAMERA = { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } };
const MIN_CONFIDENCE = 0.6;
// The model works on a small image, so detection does not need the full 720p frame.
const DETECT_WIDTH = 640;

const { exercises, sides, specs } = window.POSTURE_CONFIG;
const page = {
  frame: document.getElementById("frame"),
  video: document.getElementById("video"),
  canvas: document.getElementById("overlay"),
  start: document.getElementById("start"),
  status: document.getElementById("status"),
  metricLabel: document.getElementById("metric-label"),
  metric: document.getElementById("metric"),
  overlayMetric: document.getElementById("overlay-metric"),
  overlayFeedback: document.getElementById("overlay-feedback"),
  shallow: document.getElementById("shallow"),
  feedback: document.getElementById("feedback"),
  angles: document.getElementById("angles"),
  exercise: document.getElementById("exercise"),
  side: document.getElementById("side"),
};

const state = { worker: null, connections: [], stream: null, analyzer: null, exercise: Object.keys(exercises)[0], side: sides[0] };
const context = page.canvas.getContext("2d");
let running = false;
let detecting = false;
let lastVideoTime = -1;

function setStatus(message, isError = false) {
  page.status.textContent = message;
  page.status.dataset.error = String(isError);
}

function cameraMessage(error) {
  if (error.name === "NotAllowedError" || error.name === "SecurityError") {
    return "Camera access is blocked. Allow it in your browser's site settings, then press Start.";
  }
  if (error.name === "NotFoundError" || error.name === "OverconstrainedError") {
    return "No camera was found. Connect one, then press Start.";
  }
  return "The camera could not start. It may be in use by another app.";
}

function onWorkerMessage({ data }) {
  if (data.type === "error") {
    fail();
    return;
  }
  detecting = false;
  if (!running) return;
  setStatus("");
  drawSkeleton(data.landmarks);
  const { videoWidth, videoHeight } = page.video;
  render(state.analyzer.process(data.landmarks, videoWidth / videoHeight, performance.now() / 1000));
}

function loadWorker() {
  if (state.worker) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const source = new Blob([window.POSE_WORKER_SOURCE], { type: "text/javascript" });
    const worker = new Worker(URL.createObjectURL(source));
    worker.onerror = reject;
    worker.onmessage = ({ data }) => {
      if (data.type !== "ready") {
        reject(new Error(data.message));
        return;
      }
      state.worker = worker;
      state.connections = data.connections;
      worker.onmessage = onWorkerMessage;
      resolve();
    };
    worker.postMessage({ type: "init", visionUrl: VISION_URL, modelUrl: MODEL_URL, minConfidence: MIN_CONFIDENCE });
  });
}

function resetAnalyzer() {
  state.analyzer = new window.FormLogic.FormAnalyzer(specs[state.exercise][state.side]);
  render({ poseDetected: true, angles: {}, feedback: [], repCount: 0, lastRepShallow: false });
}

function sizeCanvas() {
  const { width, height } = page.frame.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  page.canvas.width = Math.round(width * scale);
  page.canvas.height = Math.round(height * scale);
}

function drawSkeleton(landmarks) {
  const { width, height } = page.canvas;
  context.clearRect(0, 0, width, height);
  if (!landmarks) return;
  const shown = (point) => (point.visibility ?? 0) >= 0.5;
  const scale = width / 640;

  context.lineWidth = Math.max(2, 2 * scale);
  context.strokeStyle = "#7CFC9A";
  context.beginPath();
  for (const { start, end } of state.connections) {
    const a = landmarks[start];
    const b = landmarks[end];
    if (!shown(a) || !shown(b)) continue;
    context.moveTo(a.x * width, a.y * height);
    context.lineTo(b.x * width, b.y * height);
  }
  context.stroke();

  context.fillStyle = "#FFFFFF";
  for (const point of landmarks.filter(shown)) {
    context.beginPath();
    context.arc(point.x * width, point.y * height, Math.max(3, 2.5 * scale), 0, Math.PI * 2);
    context.fill();
  }
}

function render(result) {
  const isHold = result.holdSeconds !== undefined;
  const value = isHold ? `${result.holdSeconds.toFixed(1)}s` : String(result.repCount ?? state.analyzer.reps.repCount);
  page.metricLabel.textContent = isHold ? "Hold time" : "Reps";
  page.metric.textContent = value;
  page.overlayMetric.textContent = `${isHold ? "Hold" : "Reps"}: ${value}`;
  page.shallow.hidden = !result.lastRepShallow;

  const messages = result.poseDetected ? result.feedback : ["No person detected"];
  page.overlayFeedback.replaceChildren(...messages.slice(0, 2).map((text) => Object.assign(document.createElement("p"), { textContent: text })));
  page.feedback.textContent = messages.length ? messages.join("\n") : "Form looks good";
  page.feedback.dataset.good = String(messages.length === 0);
  page.angles.replaceChildren(
    ...Object.entries(result.angles).map(([name, angle]) =>
      Object.assign(document.createElement("li"), { textContent: `${name.replaceAll("_", " ")}: ${Math.round(angle)}°` }),
    ),
  );
}

async function sendFrame() {
  if (!running) return;
  requestAnimationFrame(sendFrame);
  const { video } = page;
  if (detecting || video.readyState < 2 || video.currentTime === lastVideoTime) return;
  detecting = true;
  lastVideoTime = video.currentTime;
  const resizeHeight = Math.round((DETECT_WIDTH * video.videoHeight) / video.videoWidth);
  const bitmap = await createImageBitmap(video, { resizeWidth: DETECT_WIDTH, resizeHeight });
  state.worker.postMessage({ type: "detect", bitmap, timestamp: Math.round(performance.now()) }, [bitmap]);
}

function fail() {
  stop();
  setStatus("The pose model could not load. Check your connection, then press Start.", true);
}

function stop() {
  running = false;
  state.stream?.getTracks().forEach((track) => track.stop());
  state.stream = null;
  page.video.srcObject = null;
  context.clearRect(0, 0, page.canvas.width, page.canvas.height);
  page.frame.dataset.live = "false";
  page.start.textContent = "Start";
  setStatus("");
}

async function start() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("This browser cannot open a camera here. The page must be on HTTPS.", true);
    return;
  }
  page.start.disabled = true;
  try {
    setStatus("Starting camera");
    state.stream = await navigator.mediaDevices.getUserMedia({ video: CAMERA, audio: false });
    page.video.srcObject = state.stream;
    await page.video.play();
    page.frame.style.aspectRatio = `${page.video.videoWidth} / ${page.video.videoHeight}`;
    page.frame.dataset.live = "true";
    sizeCanvas();
    page.start.textContent = "Stop";

    setStatus("Loading the pose model. The first start takes a little longer.");
    await loadWorker();
    // The first detection compiles the model, so the message stays up until its result arrives.
    running = true;
    detecting = false;
    lastVideoTime = -1;
    resetAnalyzer();
    sendFrame();
  } catch (error) {
    if (error instanceof DOMException && !state.stream) {
      stop();
      setStatus(cameraMessage(error), true);
    } else {
      fail();
    }
  } finally {
    page.start.disabled = false;
  }
}

function addChoices(container, name, options, selected, onChange) {
  for (const [value, label] of options) {
    const input = Object.assign(document.createElement("input"), { type: "radio", name, value, id: `${name}-${value}`, checked: value === selected });
    const text = Object.assign(document.createElement("label"), { htmlFor: input.id, textContent: label });
    input.addEventListener("change", () => onChange(value));
    container.append(input, text);
  }
}

// Streamlit does not pass its theme into an iframe, so the colours are read from the page around it.
function matchStreamlitTheme() {
  try {
    const app = window.parent.document.querySelector(".stApp");
    if (!app) return;
    const { color, backgroundColor } = window.parent.getComputedStyle(app);
    document.documentElement.style.setProperty("--text", color);
    document.documentElement.style.setProperty("--page", backgroundColor);
  } catch {
    // Without access to the parent page, the system colours in camera.css apply.
  }
}

addChoices(page.exercise, "exercise", Object.entries(exercises), state.exercise, (value) => {
  state.exercise = value;
  resetAnalyzer();
});
addChoices(page.side, "side", sides.map((side) => [side, side[0] + side.slice(1).toLowerCase()]), state.side, (value) => {
  state.side = value;
  resetAnalyzer();
});
page.start.addEventListener("click", () => (state.stream ? stop() : start()));
window.addEventListener("resize", () => state.stream && sizeCanvas());
window.addEventListener("pagehide", stop);
matchStreamlitTheme();
resetAnalyzer();
