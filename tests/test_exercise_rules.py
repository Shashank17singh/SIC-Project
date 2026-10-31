"""
Unit tests for the exercise rules and the page built from them. The rep and
angle logic itself runs in the browser and is tested in form_logic.test.js.
Run with: pytest tests/
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import EXERCISE_LABELS
from src.camera_page import build_config, build_page
from src.exercise_rules import EXERCISES, build_squat_spec
from src.pose_utils import Landmark

FIXTURE = Path(__file__).parent / "fixtures" / "specs.json"


def test_every_offered_exercise_has_rules():
    assert set(EXERCISE_LABELS) <= set(EXERCISES)


def test_sides_use_different_landmarks():
    left = build_squat_spec("LEFT").angles[0]
    right = build_squat_spec("RIGHT").angles[0]
    assert left.vertex == Landmark.LEFT_KNEE
    assert right.vertex == Landmark.RIGHT_KNEE


def test_landmark_indices_match_mediapipe():
    assert Landmark.LEFT_SHOULDER == 11
    assert Landmark.RIGHT_HIP == 24
    assert Landmark.RIGHT_ANKLE == 28


def test_config_serializes_landmarks_as_plain_numbers():
    config = json.loads(json.dumps(build_config(EXERCISE_LABELS)))
    knee = config["specs"]["squat"]["LEFT"]["angles"][0]
    assert knee["vertex"] == 25
    assert config["specs"]["squat"]["LEFT"]["rep_stage"]["down_below"] == 100


def test_javascript_tests_use_the_current_rules():
    specs = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert specs == json.loads(json.dumps(build_config(EXERCISE_LABELS)["specs"]))


def test_page_has_no_unfilled_markers():
    page = build_page(EXERCISE_LABELS)
    assert "/*__" not in page
    assert "window.POSTURE_CONFIG = {" in page
    assert "class FormAnalyzer" in page
    assert 'window.POSE_WORKER_SOURCE = "' in page


def test_rule_text_cannot_close_the_script_tag():
    labels = {"squat": "</script><b>"}
    assert "</script><b>" not in build_page(labels)
