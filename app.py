"""
Streamlit WebRTC application for real-time AI physiotherapy posture checking.
Captures video, runs MediaPipe pose estimation, and provides live feedback.
Architecture note: Relies on `streamlit-webrtc` to run a local frame processing loop. 
UI thread sync is done via the `VideoProcessorBase` instance properties.
"""
import av
import cv2
import streamlit as st
from streamlit_webrtc import RTCConfiguration, VideoProcessorBase, webrtc_streamer

from src.analyzer import ExerciseAnalyzer

st.set_page_config(page_title="AI Physiotherapy Posture Checker", layout="wide")
RTC_CONFIGURATION = RTCConfiguration(
    {
        "iceServers": [
            {"urls": ["stun:stun.l.google.com:19302"]},
            {
                "urls": [
                    "turn:openrelay.metered.ca:80",
                    "turn:openrelay.metered.ca:443",
                    "turn:openrelay.metered.ca:443?transport=tcp",
                ],
                "username": "openrelayproject",
                "credential": "openrelayproject",
            },
        ]
    }
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
            img = cv2.flip(img, 1)
            result = self.analyzer.process(img)
            self.last_feedback = result.feedback
            self.last_rep_count = result.rep_count
            self.last_hold_seconds = result.hold_seconds
            self.last_rep_shallow = result.last_rep_shallow
            return av.VideoFrame.from_ndarray(result.annotated_frame, format="bgr24")
        except Exception as e:  # noqa: BLE001
            print(f"Error in recv: {e}")
            err_img = frame.to_ndarray(format="bgr24")
            cv2.putText(
                err_img, str(e), (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2
            )
            return av.VideoFrame.from_ndarray(err_img, format="bgr24")


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
                    "width": {"ideal": 640},
                    "height": {"ideal": 480},
                    "frameRate": {"ideal": 15, "max": 30},
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
            # Since we flip the video feed to mirror it for the user, MediaPipe sees the body mirrored.
            # We must swap the requested side to tell the analyzer to track the correct physical limbs.
            mirrored_side = "RIGHT" if side == "LEFT" else "LEFT"
            ctx.video_processor.set_exercise(exercise_key, mirrored_side)
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
