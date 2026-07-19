<div align="center">

# 🏋️ AI-Based Physiotherapy Posture Checker

**Real-time exercise form feedback using pose estimation — counts reps, flags shallow reps, and calls out common form errors as they happen**

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Pose-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![OpenCV](https://img.shields.io/badge/OpenCV-Video-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)

</div>

---

## 📖 Overview

Points a browser webcam at MediaPipe's pose-landmark model, converts the
landmarks into joint angles (knee, hip, elbow, shoulder), and runs each
angle stream through a small per-exercise rule set: a 2-state machine for
rep counting (squat, bicep curl) and a hold-timer for isometric holds
(plank), plus threshold-based form checks (leaning too far forward,
elbow swinging away from the torso, hips sagging).

No exercise-classification model, no dataset to collect or label — the
"AI" here is pose estimation; everything downstream of the landmarks is
interpretable geometry, which also means every piece of feedback is
explainable (you can point at the exact angle and threshold that fired).

---



### 🏃 Computer Vision Pipeline

`mermaid
graph TD
    subgraph "Streamlit Frontend"
    A[Browser Webcam] -->|streamlit-webrtc| B(Video Frame)
    H[Live Feedback Overlay] --> A
    end
    
    subgraph "Pose Estimation Engine"
    B --> C{MediaPipe Pose Model}
    C -->|33 Body Landmarks| D[Joint Angle Calculator]
    D --> E(Knee, Hip, Elbow, Shoulder Angles)
    end
    
    subgraph "Rules Engine"
    E --> F{Finite State Machine}
    F -->|Depth Check| G[Rep Counter]
    F -->|Threshold Check| I[Form Error Detection]
    G --> H
    I --> H
    end
    
    classDef io fill:#f9f0ff,stroke:#8a2be2,stroke-width:2px,color:#000;
    classDef core fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#000;
    classDef logic fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#000;
    
    class A,H,B io;
    class C,D,E core;
    class F,G,I logic;
`

## ✨ Features

| | |
|---|---|
| 🎯 **Rep Counting** | 2-state machine per exercise, driven by one primary joint angle (e.g. knee angle for squats) |
| 📏 **Shallow-Rep Detection** | Tracks the minimum angle reached during the "down" phase — flags reps that didn't reach full depth |
| ⚠️ **Live Form Feedback** | Threshold-based checks per exercise (forward lean, elbow swing, sagging hips), shown as on-screen overlay + sidebar warnings |
| ⏱️ **Hold Timer** | Plank uses a body-line-angle hold timer instead of rep counting |
| 🌐 **Browser Webcam, No Server Camera** | `streamlit-webrtc` streams frames from the browser's `getUserMedia`, so it deploys on Streamlit Community Cloud without needing a camera on the server |
| 🧪 **Testable Core Logic** | Angle math and rep/hold state machines are pure functions with no MediaPipe or webcam dependency — unit tested in isolation |

---

## 🛠️ Tech Stack

**Language** — Python 3.x
**Pose Estimation** — MediaPipe Pose (legacy `solutions` API, pinned to `0.10.14`)
**Video** — OpenCV (frame processing) · `streamlit-webrtc` + `av` (browser webcam → server frames)
**Frontend** — Streamlit
**Testing** — pytest

---

## 🧠 Architecture Overview

```
Browser webcam (getUserMedia)
   │  streamlit-webrtc (WebRTC)
   ▼
PostureVideoProcessor.recv()  (app.py)
   │
   ▼
ExerciseAnalyzer.process()  (src/analyzer.py)
   │  1. pose_utils.py      → MediaPipe landmark extraction + angle geometry
   │  2. exercise_rules.py  → declarative per-exercise spec (angles, thresholds, rep stages)
   │  3. rep_counter.py     → RepCounterState (squat/curl) or HoldTimerState (plank)
   ▼
Annotated frame + feedback list + rep count / hold time
   ▼
Streamlit sidebar (live stats) + on-frame overlay
```

**Design choices:**
- **Declarative exercise specs, not per-exercise branching code.** Adding a
  new exercise means adding one `ExerciseSpec` to `exercise_rules.py` — the
  analyzer's control flow doesn't change.
- **Rule-based, not a learned classifier.** Transparent, zero training
  cost, tunable by eye from a few test videos. The trade-off is manual
  threshold tuning per exercise/body type — see Limitations.
- **Analyzer has zero UI dependency.** `ExerciseAnalyzer.process()` takes a
  raw frame and returns a plain dataclass — it doesn't know Streamlit or
  WebRTC exist, so the angle/rep-counting logic is unit tested directly.

---

## ⚙️ Setup and Installation

### 1. Clone the repository

```bash
git clone https://github.com/Shashank17singh/posture-checker.git
cd posture-checker
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run the app

```bash
streamlit run app.py
```

Open the URL Streamlit prints, click **Start** on the video panel, allow
camera access, and pick an exercise from the sidebar.

### 4. Run the tests

```bash
pytest tests/ -v
```

---

## 🎥 Usage Tips

- Stand **side-on** to the camera (sagittal view) — the joint angles this
  app checks (knee, hip, elbow) are only meaningful from a side angle, not
  face-on.
- Make sure your full body (or full arm, for curls) is in frame — the app
  will tell you when a needed landmark isn't visible enough rather than
  silently guessing.
- Good, consistent lighting matters more than camera resolution for
  MediaPipe's detection confidence.

---

## ⚠️ Limitations

- **2D angles only.** MediaPipe Pose here runs on a single RGB frame with
  no depth sensor, so angles are computed in the image plane. A camera
  angle that isn't roughly perpendicular to the plane of motion will
  distort the numbers — this is the single biggest source of false
  feedback.
- **Thresholds are hand-tuned, not personalized.** The same "too shallow"
  or "leaning too far" cutoffs apply to everyone; a rigorous version would
  calibrate per-user from a short warm-up set or use range-of-motion
  history.
- **Not a medical device.** This flags form patterns against fixed
  geometric rules — it does not diagnose injury risk and isn't a
  substitute for in-person physiotherapist supervision.
- **Single person, single exercise at a time.** No multi-person tracking
  or automatic exercise detection (the user selects the exercise from a
  dropdown).

---

## 🔭 Future Work

- Automatic exercise recognition (classify which exercise is being
  performed instead of a manual dropdown).
- Per-user threshold calibration from a short calibration set.
- Session history / progress tracking across workouts (ties into the
  "Stroke Rehabilitation Progress Tracker" idea from the same project
  list this was picked from).
- Swap the 2-state rep counter for a learned temporal segmentation model
  once there's a labeled rep dataset to justify it.

---

## 📄 License

MIT
