"""
MediaPipe Pose landmark indices, as used by both the legacy Python solution and
the browser Pose Landmarker. Named here so exercise rules can say "left knee"
instead of a bare number.
"""

from __future__ import annotations

from enum import IntEnum


class Landmark(IntEnum):
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
