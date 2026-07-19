"""
Pose landmark extraction and joint-angle geometry.

Wraps MediaPipe's legacy Pose solution (mp.solutions.pose) — chosen over the
newer Tasks API because it ships its own model weights (no external .task
file to download at runtime), which keeps the app self-contained and easy
to deploy on Streamlit Cloud.

NOTE: mp.solutions.pose requires mediapipe<=0.10.14 (the legacy `solutions`
namespace was dropped in later releases in favor of the Tasks API). Pin the
version in requirements.txt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import mediapipe as mp
import numpy as np

mp_pose = mp.solutions.pose
Landmark = mp_pose.PoseLandmark


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float
    visibility: float = 1.0


def landmark_to_point(landmarks, name: Landmark) -> Point2D:
    """Pull a single named landmark out of MediaPipe's result and normalize
    it into our own Point2D so the rest of the code doesn't depend on
    MediaPipe's protobuf types directly."""
    lm = landmarks[name.value]
    return Point2D(x=lm.x, y=lm.y, visibility=lm.visibility)


def calculate_angle(a: Point2D, b: Point2D, c: Point2D) -> float:
    """Angle at vertex `b`, formed by rays b->a and b->c, in degrees [0, 180].

    This is the core primitive every exercise rule is built on: e.g. the
    knee angle is calculate_angle(hip, knee, ankle).
    """
    a_arr = np.array([a.x, a.y])
    b_arr = np.array([b.x, b.y])
    c_arr = np.array([c.x, c.y])

    ba = a_arr - b_arr
    bc = c_arr - b_arr

    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    if norm_ba == 0 or norm_bc == 0:
        return 0.0

    cosine_angle = np.dot(ba, bc) / (norm_ba * norm_bc)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine_angle)))


def visible_enough(*points: Point2D, threshold: float = 0.5) -> bool:
    """MediaPipe reports a per-landmark visibility/confidence score. If a
    joint needed for the current rule is occluded or off-frame, we should
    say so rather than silently emitting a garbage angle."""
    return all(p.visibility >= threshold for p in points)


def pixel_coords(point: Point2D, frame_width: int, frame_height: int) -> tuple[int, int]:
    """Convert MediaPipe's normalized [0,1] coordinates to pixel coordinates
    for drawing overlays on the actual frame."""
    return int(point.x * frame_width), int(point.y * frame_height)
