"""
AI Physiotherapy Posture Checker - Streamlit front end.
Uses streamlit-webrtc so the webcam runs in the *browser* (getUserMedia)
and frames are streamed to this server over WebRTC - this is what makes it
deployable on Streamlit Community Cloud, where the server itself has no
camera and cv2.VideoCapture(0) would fail.
"""
import av
import streamlit as st
from streamlit_webrtc import RTCConfiguration, VideoProcessorBase, webrtc_streamer
from src.analyzer import ExerciseAnalyzer
from src.exercise_rules import EXERCISES

st.set_page_config(page_title="AI Physiotherapy Posture Checker", layout="wide")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@300;400;500;600;700&family=Noto+Sans:wght@300;400;500;700&display=swap');

html, body, [class*="css"]  {
    font-family: 'Noto Sans', sans-serif !important;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Figtree', sans-serif !important;
    color: #0891B2 !important;
}

.stApp {
    background-color: #ECFEFF;
    color: #164E63;
}

[data-testid="stHeader"] {
    background-color: rgba(236,254,255,0.9) !important;
}

/* Neumorphism Buttons */
.stButton > button {
    background-color: #ECFEFF;
    color: #0891B2;
    font-family: 'Figtree', sans-serif;
    font-weight: 600;
    font-size: 1.1rem;
    border: none;
    border-radius: 12px;
    box-shadow: 6px 6px 12px #BFE1E3, -6px -6px 12px #FFFFFF;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    color: #059669;
    box-shadow: 4px 4px 8px #BFE1E3, -4px -4px 8px #FFFFFF;
}

.stButton > button:active {
    box-shadow: inset 6px 6px 12px #BFE1E3, inset -6px -6px 12px #FFFFFF;
    color: #059669;
}

/* Containers */
[data-testid="stExpander"], [data-testid="stVerticalBlock"] > div > div > div[data-testid="stContainer"] {
    background-color: #ECFEFF;
    border-radius: 16px;
    border: none;
    box-shadow: 6px 6px 12px #BFE1E3, -6px -6px 12px #FFFFFF;
    padding: 15px;
    margin-bottom: 20px;
}

/* Inputs */
.stSelectbox > div > div > div {
    background-color: #ECFEFF;
    border: none;
    border-radius: 8px;
    color: #164E63;
    box-shadow: inset 4px 4px 8px #BFE1E3, inset -4px -4px 8px #FFFFFF;
}
.stSelectbox > div > div > div:focus {
    box-shadow: inset 6px 6px 12px #BFE1E3, inset -6px -6px 12px #FFFFFF;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [
        {"urls": ["stun:stun.l.google.com:19302"]},
        {
            "urls": [
                "turn:openrelay.metered.ca:80",
                "turn:openrelay.metered.ca:443",
                "turn:openrelay.metered.ca:443?transport=tcp",
            ],
            "username": "openrelayproject",
            "credential": "openrelayproject",
        }
    ]}
)

EXERCISE_LABELS = {
    "squat": "Squat",
    "push_up": "Push-up",
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
        """Updates the current exercise and re-initializes the analyzer."""
        if exercise_key != self.exercise_key or side != self.side:
            self.analyzer.close()
            self.exercise_key = exercise_key
            self.side = side
            self.analyzer = ExerciseAnalyzer(exercise_key, side)

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """Processes each incoming video frame through the ExerciseAnalyzer."""
        try:
            img = frame.to_ndarray(format="bgr24")
            result = self.analyzer.process(img)
            self.last_feedback = result.feedback
            self.last_rep_count = result.rep_count
            self.last_hold_seconds = result.hold_seconds
            self.last_rep_shallow = result.last_rep_shallow
            return av.VideoFrame.from_ndarray(result.annotated_frame, format="bgr24")
        except Exception as e:
            print(f"Error in recv: {e}")
            return frame

def main() -> None:
    """Main application entry point for the Streamlit UI."""
    st.title("AI-Based Physiotherapy Posture Checker")
    st.caption(
        "Real-time pose estimation (MediaPipe) checks exercise form and counts reps - "
        "runs entirely in your browser + this session, no video is stored."
    )
    with st.sidebar:
        st.header("Settings")
        exercise_key = st.radio(
            "Exercise",
            options=list(EXERCISE_LABELS.keys()),
            format_func=lambda k: EXERCISE_LABELS[k],
        )
        side = st.radio(
            "Which side is facing the camera?",
            options=["LEFT", "RIGHT"],
            horizontal=True,
        )
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
            media_stream_constraints={
                "video": {
                    "facingMode": "user",
                    "width": {"ideal": 1280},
                    "height": {"ideal": 720},
                    "frameRate": {"ideal": 15, "max": 20},
                },
                "audio": False,
            },
            video_html_attrs={
                "style": {
                    "width": "100%",
                    "margin": "0 auto",
                    "border": "5px solid yellow",
                },
                "controls": True,
                "autoPlay": True,
                "playsinline": True,
            },
            async_processing=False,
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
                    st.warning("Last rep was shallow - try to go deeper.")
            elif vp.last_hold_seconds is not None:
                stats_placeholder.metric("Hold time", f"{vp.last_hold_seconds:0.1f}s")
            if vp.last_feedback:
                feedback_placeholder.error("\n".join(m for m in vp.last_feedback))
            else:
                feedback_placeholder.success("Form looks good")
        else:
            st.info("Click **Start** on the video panel to begin.")


if __name__ == "__main__":
    main()
