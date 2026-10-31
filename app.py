"""
Streamlit application for real-time AI physiotherapy posture checking.
Architecture note: the camera, MediaPipe pose estimation and form feedback all
run in the browser (src/web), so video is shown directly and never uploaded.
Python defines the exercise rules and serves the page.
"""

import streamlit as st

from src.camera_page import build_page

st.set_page_config(page_title="AI Physiotherapy Posture Checker", layout="wide")

EXERCISE_LABELS = {
    "squat": "Squat",
    "push_up": "Push-up",
}


def main() -> None:
    """Main application entry point for the Streamlit UI."""
    st.title("AI-Based Physiotherapy Posture Checker")
    st.caption(
        "Real-time pose estimation (MediaPipe) checks exercise form and counts reps - "
        "runs entirely in your browser, and your video is never uploaded or stored."
    )
    st.iframe(build_page(EXERCISE_LABELS), height="content")
    st.markdown(
        "**Camera tip:** stand side-on to the camera (sagittal view) so the "
        "knee/hip/elbow angles used for form-checking are clearly visible."
    )
    st.markdown(
        "**Disclaimer:** this is a form-feedback demo, not a medical device. "
        "It does not diagnose injuries or replace guidance from a physiotherapist."
    )


if __name__ == "__main__":
    main()
