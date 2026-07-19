"""
State machines for turning a stream of per-frame angles into rep counts
(squat, curl) or hold time (plank).

Kept deliberately simple (a 2-state machine per rep-based exercise) rather
than a learned temporal model — it's transparent, has zero training cost,
and is easy to tune per-exercise by eye from a few test videos. See
README > Future Work for where an ML-based rep segmentation model would
plug in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from src.exercise_rules import ExerciseSpec


@dataclass
class RepCounterState:
    stage: str = "up"  # "up" | "down"
    rep_count: int = 0
    last_rep_shallow: bool = False
    _min_angle_this_rep: float = field(default=180.0, repr=False)

    def update(self, spec: ExerciseSpec, angles: dict[str, float]) -> None:
        if spec.rep_stage is None:
            return
        primary = angles.get(spec.rep_stage.primary_angle)
        if primary is None:
            return

        if self.stage == "down":
            self._min_angle_this_rep = min(self._min_angle_this_rep, primary)

        if primary < spec.rep_stage.down_below:
            if self.stage != "down":
                self._min_angle_this_rep = primary
            self.stage = "down"
        elif primary > spec.rep_stage.up_above and self.stage == "down":
            self.stage = "up"
            self.rep_count += 1
            shallow_threshold = spec.rep_stage.shallow_below
            self.last_rep_shallow = (
                shallow_threshold is not None and self._min_angle_this_rep > shallow_threshold
            )
            self._min_angle_this_rep = 180.0


@dataclass
class HoldTimerState:
    hold_start: float | None = None
    total_hold_seconds: float = 0.0
    in_good_form: bool = False

    def update(self, spec: ExerciseSpec, angles: dict[str, float]) -> None:
        if spec.hold_target_angle is None:
            return
        angle = angles.get(spec.hold_target_angle)
        if angle is None:
            self.in_good_form = False
            self.hold_start = None
            return

        good = spec.hold_min_ok <= angle <= spec.hold_max_ok
        now = time.monotonic()

        if good and not self.in_good_form:
            self.hold_start = now
        elif good and self.in_good_form and self.hold_start is not None:
            self.total_hold_seconds += now - self.hold_start
            self.hold_start = now
        elif not good:
            self.hold_start = None

        self.in_good_form = good

    def current_hold_seconds(self) -> float:
        if self.in_good_form and self.hold_start is not None:
            return self.total_hold_seconds + (time.monotonic() - self.hold_start)
        return self.total_hold_seconds
