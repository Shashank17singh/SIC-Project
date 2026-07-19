"""
Per-exercise rule definitions.

Each exercise is a small, declarative spec: which joint angles it needs,
what counts as "up"/"down" for rep counting, and what form-error checks to
run. Adding a new exercise means adding a new EXERCISES entry, not touching
the analyzer's control flow.

All angles are computed in the 2D image plane from MediaPipe's normalized
landmarks. This is a real limitation (see README > Limitations) — no true
depth, so form errors that only show up from the side (e.g. rounded lower
back) are only reliable when the camera is roughly perpendicular to the
plane of motion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.pose_utils import Landmark

Side = str  # "LEFT" or "RIGHT"


@dataclass(frozen=True)
class AngleSpec:
    """Defines one angle to compute each frame: angle at `vertex`, formed by
    rays toward `point_a` and `point_c`."""
    name: str
    point_a: Landmark
    vertex: Landmark
    point_c: Landmark


@dataclass(frozen=True)
class RepStage:
    """Rep counting is a simple 2-state machine driven by one primary angle:
    down_below crosses -> state DOWN; up_above crosses while DOWN -> +1 rep.

    shallow_below: if the primary angle never drops below this during the
    DOWN phase, the completed rep is flagged as shallow (e.g. a squat that
    didn't go low enough). Optional — omit for exercises with no useful
    "depth" notion (e.g. bicep curl)."""
    primary_angle: str
    down_below: float
    up_above: float
    shallow_below: float | None = None


@dataclass(frozen=True)
class FormCheck:
    """A single form-error rule: if `angle_name` falls outside
    [min_ok, max_ok] (only checked while in `active_stage`, or always if
    active_stage is None), show `message`."""
    angle_name: str
    min_ok: float
    max_ok: float
    message: str
    active_stage: str | None = None


@dataclass(frozen=True)
class ExerciseSpec:
    display_name: str
    angles: list[AngleSpec]
    rep_stage: RepStage | None  # None for holds (e.g. plank) instead of reps
    form_checks: list[FormCheck] = field(default_factory=list)
    hold_target_angle: str | None = None
    hold_min_ok: float | None = None
    hold_max_ok: float | None = None


def _side_angles(side: Side) -> dict:
    L = Landmark
    prefix = side
    hip = getattr(L, f"{prefix}_HIP")
    knee = getattr(L, f"{prefix}_KNEE")
    ankle = getattr(L, f"{prefix}_ANKLE")
    shoulder = getattr(L, f"{prefix}_SHOULDER")
    elbow = getattr(L, f"{prefix}_ELBOW")
    wrist = getattr(L, f"{prefix}_WRIST")
    return dict(hip=hip, knee=knee, ankle=ankle, shoulder=shoulder, elbow=elbow, wrist=wrist)


def build_squat_spec(side: Side = "LEFT") -> ExerciseSpec:
    j = _side_angles(side)
    return ExerciseSpec(
        display_name="Squat",
        angles=[
            AngleSpec("knee", j["hip"], j["knee"], j["ankle"]),
            AngleSpec("hip_lean", j["shoulder"], j["hip"], j["knee"]),
        ],
        # down_below=100: crossing this enters the DOWN phase at all.
        # shallow_below=80: if the knee angle never drops below this during
        # the DOWN phase, the rep still counts but gets flagged as shallow
        # (partial squat) — must be strictly less than down_below.
        rep_stage=RepStage(primary_angle="knee", down_below=100, up_above=160, shallow_below=80),
        form_checks=[
            FormCheck(
                angle_name="hip_lean",
                min_ok=45, max_ok=180,
                message="Keep your chest up — you're leaning too far forward",
                active_stage="down",
            ),
        ],
    )


def build_bicep_curl_spec(side: Side = "LEFT") -> ExerciseSpec:
    j = _side_angles(side)
    return ExerciseSpec(
        display_name="Bicep Curl",
        angles=[
            AngleSpec("elbow", j["shoulder"], j["elbow"], j["wrist"]),
            AngleSpec("shoulder_swing", j["hip"], j["shoulder"], j["elbow"]),
        ],
        rep_stage=RepStage(primary_angle="elbow", down_below=50, up_above=155),
        form_checks=[
            FormCheck(
                angle_name="shoulder_swing",
                min_ok=10, max_ok=180,
                message="Keep your elbow tucked in — stop swinging your shoulder",
                active_stage=None,
            ),
        ],
    )


def build_plank_spec(side: Side = "LEFT") -> ExerciseSpec:
    j = _side_angles(side)
    return ExerciseSpec(
        display_name="Plank",
        angles=[
            AngleSpec("body_line", j["shoulder"], j["hip"], j["ankle"]),
        ],
        rep_stage=None,
        hold_target_angle="body_line",
        hold_min_ok=160,
        hold_max_ok=180,
    )


EXERCISES = {
    "squat": build_squat_spec,
    "bicep_curl": build_bicep_curl_spec,
    "plank": build_plank_spec,
}
