"""
Unit tests for the pure geometry (no webcam, no MediaPipe model inference).

Run with: pytest tests/
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pose_utils import Point2D, calculate_angle, visible_enough


def test_straight_line_is_180_degrees():
    a = Point2D(0.0, 1.0)
    b = Point2D(0.0, 0.0)
    c = Point2D(0.0, -1.0)
    assert math.isclose(calculate_angle(a, b, c), 180.0, abs_tol=1e-6)


def test_right_angle_is_90_degrees():
    a = Point2D(1.0, 0.0)
    b = Point2D(0.0, 0.0)
    c = Point2D(0.0, 1.0)
    assert math.isclose(calculate_angle(a, b, c), 90.0, abs_tol=1e-6)


def test_degenerate_zero_length_vector_returns_zero():
    a = Point2D(0.0, 0.0)
    b = Point2D(0.0, 0.0)
    c = Point2D(1.0, 1.0)
    assert calculate_angle(a, b, c) == 0.0


def test_visible_enough_respects_threshold():
    ok = Point2D(0, 0, visibility=0.9)
    low = Point2D(0, 0, visibility=0.2)
    assert visible_enough(ok, ok, threshold=0.5) is True
    assert visible_enough(ok, low, threshold=0.5) is False


def test_squat_rep_counts_full_depth_rep():
    from src.exercise_rules import build_squat_spec
    from src.rep_counter import RepCounterState

    spec = build_squat_spec()
    state = RepCounterState()

    # Simulate: standing -> deep squat (below shallow_below=80) -> standing
    for angle in [170, 150, 120, 90, 75, 90, 120, 150, 170]:
        state.update(spec, {"knee": angle})

    assert state.rep_count == 1
    assert state.last_rep_shallow is False


def test_squat_rep_flagged_shallow_when_not_deep_enough():
    from src.exercise_rules import build_squat_spec
    from src.rep_counter import RepCounterState

    spec = build_squat_spec()  # down_below=100, shallow_below=80
    state = RepCounterState()

    # Simulate a partial rep: crosses into DOWN (<100) but only dips to 90,
    # never reaching full depth (<80)
    for angle in [170, 150, 120, 95, 90, 95, 120, 150, 170]:
        state.update(spec, {"knee": angle})

    assert state.rep_count == 1
    assert state.last_rep_shallow is True
