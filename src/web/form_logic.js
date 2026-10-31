/*
 * Turns MediaPipe landmarks into joint angles, rep counts, hold time and form
 * feedback. Pure logic with no browser or camera access, so tests run it in
 * Node (tests/form_logic.test.js). The rules it applies come from
 * src/exercise_rules.py.
 */
(function (root) {
  const VISIBILITY_THRESHOLD = 0.5;
  // Thresholds were tuned on 4:3 video, and angles are measured on normalized
  // coordinates, so any other shape is rescaled to give the same numbers.
  const TUNED_ASPECT = 4 / 3;

  /* Angle at vertex `b`, formed by rays b->a and b->c, in degrees [0, 180]. */
  function calculateAngle(a, b, c) {
    const ba = [a.x - b.x, a.y - b.y];
    const bc = [c.x - b.x, c.y - b.y];
    const normBa = Math.hypot(...ba);
    const normBc = Math.hypot(...bc);
    if (normBa === 0 || normBc === 0) return 0;
    const cosine = (ba[0] * bc[0] + ba[1] * bc[1]) / (normBa * normBc);
    return (Math.acos(Math.min(1, Math.max(-1, cosine))) * 180) / Math.PI;
  }

  function visibleEnough(points, threshold = VISIBILITY_THRESHOLD) {
    return points.every((point) => point.visibility >= threshold);
  }

  /* A 2-state machine: below down_below goes down, above up_above counts a rep. */
  class RepCounter {
    constructor() {
      this.stage = "up";
      this.repCount = 0;
      this.lastRepShallow = false;
      this.minAngleThisRep = 180;
    }

    update(spec, angles) {
      if (spec.rep_stage === null) return;
      const primary = angles[spec.rep_stage.primary_angle];
      if (primary === undefined) return;
      if (this.stage === "down") {
        this.minAngleThisRep = Math.min(this.minAngleThisRep, primary);
      }
      if (primary < spec.rep_stage.down_below) {
        if (this.stage !== "down") this.minAngleThisRep = primary;
        this.stage = "down";
      } else if (primary > spec.rep_stage.up_above && this.stage === "down") {
        this.stage = "up";
        this.repCount += 1;
        const shallow = spec.rep_stage.shallow_below;
        this.lastRepShallow = shallow !== null && this.minAngleThisRep > shallow;
        this.minAngleThisRep = 180;
      }
    }
  }

  class HoldTimer {
    constructor() {
      this.holdStart = null;
      this.totalSeconds = 0;
      this.inGoodForm = false;
    }

    update(spec, angles, now) {
      if (spec.hold_target_angle === null) return;
      const angle = angles[spec.hold_target_angle];
      if (angle === undefined) {
        this.inGoodForm = false;
        this.holdStart = null;
        return;
      }
      const good = spec.hold_min_ok <= angle && angle <= spec.hold_max_ok;
      if (good && !this.inGoodForm) {
        this.holdStart = now;
      } else if (good && this.holdStart !== null) {
        this.totalSeconds += now - this.holdStart;
        this.holdStart = now;
      } else if (!good) {
        this.holdStart = null;
      }
      this.inGoodForm = good;
    }

    current(now) {
      if (this.inGoodForm && this.holdStart !== null) {
        return this.totalSeconds + (now - this.holdStart);
      }
      return this.totalSeconds;
    }
  }

  /* One instance per exercise choice. Holds the rep and hold state across frames. */
  class FormAnalyzer {
    constructor(spec) {
      this.spec = spec;
      this.reps = new RepCounter();
      this.hold = new HoldTimer();
    }

    process(landmarks, aspect, now) {
      if (!landmarks) return { poseDetected: false, angles: {}, feedback: [] };

      const scale = aspect / TUNED_ASPECT;
      const point = (index) => {
        const { x, y, visibility } = landmarks[index];
        return { x: x * scale, y, visibility: visibility ?? 0 };
      };

      const angles = {};
      const feedback = [];
      for (const angle of this.spec.angles) {
        const a = point(angle.point_a);
        const b = point(angle.vertex);
        const c = point(angle.point_c);
        if (!visibleEnough([a, b, c])) {
          feedback.push(`Can't see your ${angle.name.replaceAll("_", " ")} clearly - adjust the camera`);
          continue;
        }
        angles[angle.name] = calculateAngle(a, b, c);
      }

      const result = { poseDetected: true, angles, feedback, lastRepShallow: false };
      let stage = null;
      if (this.spec.rep_stage !== null) {
        this.reps.update(this.spec, angles);
        result.repCount = this.reps.repCount;
        result.lastRepShallow = this.reps.lastRepShallow;
        stage = this.reps.stage;
      } else {
        this.hold.update(this.spec, angles, now);
        result.holdSeconds = this.hold.current(now);
      }

      for (const check of this.spec.form_checks) {
        if (check.active_stage !== null && check.active_stage !== stage) continue;
        const value = angles[check.angle_name];
        if (value === undefined) continue;
        if (value < check.min_ok || value > check.max_ok) feedback.push(check.message);
      }

      if (this.spec.hold_target_angle !== null) {
        const value = angles[this.spec.hold_target_angle];
        if (value !== undefined && (value < this.spec.hold_min_ok || value > this.spec.hold_max_ok)) {
          feedback.push("Straighten your body line - hips are sagging or piking up");
        }
      }
      return result;
    }
  }

  const api = { calculateAngle, visibleEnough, RepCounter, HoldTimer, FormAnalyzer };
  if (typeof module !== "undefined") module.exports = api;
  else root.FormLogic = api;
})(typeof window !== "undefined" ? window : globalThis);
