"""
AI Physiotherapy Posture Checker — Streamlit front end.

Uses streamlit-webrtc so the webcam runs in the *browser* (getUserMedia)
and frames are streamed to this server over WebRTC — this is what makes it
deployable on Streamlit Community Cloud, where the server itself has no
camera and cv2.VideoCapture(0) would fail.
"""

import av
import streamlit as st
from streamlit_webrtc import RTCConfiguration, VideoProcessorBase, webrtc_streamer

from src.analyzer import ExerciseAnalyzer
from src.exercise_rules import EXERCISES

st.set_page_config(page_title="AI Physiotherapy Posture Checker", page_icon="🏋️", layout="wide")

RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

EXERCISE_LABELS = {
    "squat": "Squat",
    "bicep_curl": "Bicep Curl",
    "plank": "Plank (hold)",
}


class PostureVideoProcessor(VideoProcessorBase):
    """Bridges streamlit-webrtc's frame callback to our ExerciseAnalyzer.

    st.session_state isn't safely writable from inside the WebRTC callback
    thread, so results are stashed on `self` and read back on the main
    thread via `st.session_state.processor` on each Streamlit rerun.
    """

    def __init__(self) -> None:
        self.exercise_key = "squat"
        self.side = "LEFT"
        self.analyzer = ExerciseAnalyzer(self.exercise_key, self.side)
        self.last_feedback: list[str] = []
        self.last_rep_count: int | None = None
        self.last_hold_seconds: float | None = None
        self.last_rep_shallow: bool = False

    def set_exercise(self, exercise_key: str, side: str) -> None:
        if exercise_key != self.exercise_key or side != self.side:
            self.analyzer.close()
            self.exercise_key = exercise_key
            self.side = side
            self.analyzer = ExerciseAnalyzer(exercise_key, side)

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        result = self.analyzer.process(img)

        self.last_feedback = result.feedback
        self.last_rep_count = result.rep_count
        self.last_hold_seconds = result.hold_seconds
        self.last_rep_shallow = result.last_rep_shallow

        return av.VideoFrame.from_ndarray(result.annotated_frame, format="bgr24")


def main() -> None:
    st.title("🏋️ AI-Based Physiotherapy Posture Checker")
    st.caption(
        "Real-time pose estimation (MediaPipe) checks exercise form and counts reps — "
        "runs entirely in your browser + this session, no video is stored."
    )

    with st.sidebar:
        st.header("Settings")
        exercise_key = st.selectbox(
            "Exercise",
            options=list(EXERCISE_LABELS.keys()),
            format_func=lambda k: EXERCISE_LABELS[k],
        )
        side = st.radio("Which side is facing the camera?", options=["LEFT", "RIGHT"], horizontal=True)
        st.divider()
        st.markdown(
            "**Camera tip:** stand side-on to the camera (sagittal view) so the "
            "knee/hip/elbow angles used for form-checking are clearly visible."
        )
        st.markdown(
            "**Disclaimer:** this is a form-feedback demo, not a medical device. "
            "It does not diagnose injuries or replace guidance from a physiotherapist."
        )

    col_video, col_stats = st.columns([2, 1])

    with col_video:
        ctx = webrtc_streamer(
            key="posture-checker",
            video_processor_factory=PostureVideoProcessor,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"video": True, "audio": False},
        )

    with col_stats:
        st.subheader("Live stats")
        stats_placeholder = st.empty()
        feedback_placeholder = st.empty()

        if ctx.video_processor:
            ctx.video_processor.set_exercise(exercise_key, side)

            vp = ctx.video_processor
            if vp.last_rep_count is not None:
                stats_placeholder.metric("Reps", vp.last_rep_count)
                if vp.last_rep_shallow:
                    st.warning("Last rep was shallow — try to go deeper.")
            elif vp.last_hold_seconds is not None:
                stats_placeholder.metric("Hold time", f"{vp.last_hold_seconds:0.1f}s")

            if vp.last_feedback:
                feedback_placeholder.error("\n".join(f"⚠️ {m}" for m in vp.last_feedback))
            else:
                feedback_placeholder.success("✅ Form looks good")
        else:
            st.info("Click **Start** on the video panel to begin.")


if __name__ == "__main__":
    main()
