"""
Ties everything together: takes a raw BGR frame, runs MediaPipe pose
detection, computes the angles the current exercise needs, updates rep/hold
state, runs form checks, and draws the annotated overlay.

This is the single entry point the Streamlit app calls per frame — it does
not know about Streamlit, webcam I/O, or UI at all, which keeps it unit
testable (see tests/test_angles.py) independent of any of that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import mediapipe as mp

from src.exercise_rules import EXERCISES, ExerciseSpec
from src.pose_utils import calculate_angle, landmark_to_point, mp_pose, visible_enough
from src.rep_counter import HoldTimerState, RepCounterState

mp_drawing = mp.solutions.drawing_utils


@dataclass
class FrameResult:
    annotated_frame: "cv2.Mat"
    pose_detected: bool
    angles: dict[str, float] = field(default_factory=dict)
    feedback: list[str] = field(default_factory=list)
    rep_count: int | None = None
    hold_seconds: float | None = None
    last_rep_shallow: bool = False


class ExerciseAnalyzer:
    """One instance per active session/exercise choice. Holds the MediaPipe
    Pose model and the rep/hold state across frames — do not share a single
    instance across two different live sessions."""

    def __init__(self, exercise_key: str, side: str = "LEFT",
                 min_detection_confidence: float = 0.6,
                 min_tracking_confidence: float = 0.6):
        if exercise_key not in EXERCISES:
            raise ValueError(f"Unknown exercise '{exercise_key}'. Options: {list(EXERCISES)}")

        self.spec: ExerciseSpec = EXERCISES[exercise_key](side)
        self.pose = mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.rep_state = RepCounterState()
        self.hold_state = HoldTimerState()

    def close(self) -> None:
        self.pose.close()

    def process(self, frame_bgr) -> FrameResult:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        results = self.pose.process(frame_rgb)
        frame_rgb.flags.writeable = True
        annotated = frame_bgr.copy()

        if not results.pose_landmarks:
            cv2.putText(annotated, "No person detected", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return FrameResult(annotated_frame=annotated, pose_detected=False)

        landmarks = results.pose_landmarks.landmark
        mp_drawing.draw_landmarks(annotated, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        angles: dict[str, float] = {}
        feedback: list[str] = []
        for angle_spec in self.spec.angles:
            a = landmark_to_point(landmarks, angle_spec.point_a)
            b = landmark_to_point(landmarks, angle_spec.vertex)
            c = landmark_to_point(landmarks, angle_spec.point_c)
            if not visible_enough(a, b, c):
                feedback.append(f"Can't see your {angle_spec.name.replace('_', ' ')} clearly — adjust the camera")
                continue
            angles[angle_spec.name] = calculate_angle(a, b, c)

        rep_count = None
        hold_seconds = None
        last_rep_shallow = False

        if self.spec.rep_stage is not None:
            self.rep_state.update(self.spec, angles)
            rep_count = self.rep_state.rep_count
            last_rep_shallow = self.rep_state.last_rep_shallow
            current_stage = self.rep_state.stage
        else:
            self.hold_state.update(self.spec, angles)
            hold_seconds = self.hold_state.current_hold_seconds()
            current_stage = None

        for check in self.spec.form_checks:
            if check.active_stage is not None and check.active_stage != current_stage:
                continue
            angle_value = angles.get(check.angle_name)
            if angle_value is None:
                continue
            if not (check.min_ok <= angle_value <= check.max_ok):
                feedback.append(check.message)

        if self.spec.hold_target_angle is not None:
            angle_value = angles.get(self.spec.hold_target_angle)
            if angle_value is not None and not (self.spec.hold_min_ok <= angle_value <= self.spec.hold_max_ok):
                feedback.append("Straighten your body line — hips are sagging or piking up")

        self._draw_hud(annotated, angles, rep_count, hold_seconds, feedback)

        return FrameResult(
            annotated_frame=annotated,
            pose_detected=True,
            angles=angles,
            feedback=feedback,
            rep_count=rep_count,
            hold_seconds=hold_seconds,
            last_rep_shallow=last_rep_shallow,
        )

    @staticmethod
    def _draw_hud(frame, angles, rep_count, hold_seconds, feedback) -> None:
        y = 30
        if rep_count is not None:
            cv2.putText(frame, f"Reps: {rep_count}", (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            y += 35
        if hold_seconds is not None:
            cv2.putText(frame, f"Hold: {hold_seconds:0.1f}s", (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            y += 35
        for msg in feedback[:2]:  # keep the overlay from getting cluttered
            cv2.putText(frame, msg, (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            y += 25
