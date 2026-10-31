/*
 * Unit tests for the browser form logic (no webcam, no model inference).
 * Run with: node --test tests/form_logic.test.js
 */
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { describe, it } = require("node:test");

const { FormAnalyzer, HoldTimer, RepCounter, calculateAngle, visibleEnough } = require("../src/web/form_logic.js");

const specs = JSON.parse(readFileSync(path.join(__dirname, "fixtures", "specs.json"), "utf8"));
const point = (x, y, visibility = 1) => ({ x, y, visibility });
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} is not ${expected}`);

// Places hip, knee and ankle so the knee bends by `angle` on a 4:3 frame.
function squatFrame(angle, aspect = 4 / 3, spec = specs.squat.LEFT) {
  const radians = (angle * Math.PI) / 180;
  const landmarks = Array.from({ length: 33 }, () => point(0.5, 0.5));
  const [knee, hipLean] = spec.angles;
  const scale = (4 / 3) / aspect;
  landmarks[knee.vertex] = point(0.5, 0.5);
  landmarks[knee.point_c] = point(0.5, 0.8);
  landmarks[knee.point_a] = point(0.5 + 0.3 * Math.sin(radians) * scale, 0.5 + 0.3 * Math.cos(radians));
  landmarks[hipLean.point_a] = point(landmarks[knee.point_a].x, landmarks[knee.point_a].y - 0.3);
  return landmarks;
}

describe("calculateAngle", () => {
  it("is 180 degrees for a straight line", () => {
    close(calculateAngle(point(0, 1), point(0, 0), point(0, -1)), 180);
  });

  it("is 90 degrees for a right angle", () => {
    close(calculateAngle(point(1, 0), point(0, 0), point(0, 1)), 90);
  });

  it("returns zero for a degenerate zero-length vector", () => {
    assert.equal(calculateAngle(point(0, 0), point(0, 0), point(1, 1)), 0);
  });
});

describe("visibleEnough", () => {
  it("respects the threshold", () => {
    assert.equal(visibleEnough([point(0, 0, 0.9), point(0, 0, 0.9)], 0.5), true);
    assert.equal(visibleEnough([point(0, 0, 0.9), point(0, 0, 0.2)], 0.5), false);
  });
});

describe("RepCounter", () => {
  const run = (angles, spec = specs.squat.LEFT) => {
    const counter = new RepCounter();
    for (const knee of angles) counter.update(spec, { knee });
    return counter;
  };

  it("counts a full depth rep", () => {
    const counter = run([170, 150, 120, 90, 75, 90, 120, 150, 170]);
    assert.equal(counter.repCount, 1);
    assert.equal(counter.lastRepShallow, false);
  });

  it("flags a rep that was not deep enough", () => {
    const counter = run([170, 150, 120, 95, 90, 95, 120, 150, 170]);
    assert.equal(counter.repCount, 1);
    assert.equal(counter.lastRepShallow, true);
  });

  it("does not count until the person stands back up", () => {
    assert.equal(run([170, 90, 75, 120, 150]).repCount, 0);
  });

  it("clears the shallow flag after a good rep", () => {
    assert.equal(run([170, 90, 170, 75, 170]).lastRepShallow, false);
  });

  it("ignores frames without the primary angle", () => {
    const counter = new RepCounter();
    counter.update(specs.squat.LEFT, {});
    assert.equal(counter.stage, "up");
  });
});

describe("HoldTimer", () => {
  const spec = { hold_target_angle: "body_line", hold_min_ok: 160, hold_max_ok: 180 };

  it("adds up time in good form", () => {
    const timer = new HoldTimer();
    for (const now of [0, 1, 2]) timer.update(spec, { body_line: 170 }, now);
    assert.equal(timer.current(3), 3);
  });

  it("keeps the total but stops counting when form breaks", () => {
    const timer = new HoldTimer();
    timer.update(spec, { body_line: 170 }, 0);
    timer.update(spec, { body_line: 170 }, 2);
    timer.update(spec, { body_line: 120 }, 3);
    assert.equal(timer.current(10), 2);
  });

  it("stops counting when the joint is lost", () => {
    const timer = new HoldTimer();
    timer.update(spec, { body_line: 170 }, 0);
    timer.update(spec, {}, 1);
    assert.equal(timer.inGoodForm, false);
  });
});

describe("FormAnalyzer", () => {
  const aspect = 4 / 3;

  it("reports when nobody is in frame", () => {
    const result = new FormAnalyzer(specs.squat.LEFT).process(undefined, aspect, 0);
    assert.equal(result.poseDetected, false);
  });

  it("counts a squat from landmarks", () => {
    const analyzer = new FormAnalyzer(specs.squat.LEFT);
    let result;
    for (const angle of [170, 120, 75, 120, 170]) result = analyzer.process(squatFrame(angle), aspect, 0);
    assert.equal(result.repCount, 1);
    assert.equal(result.lastRepShallow, false);
  });

  it("measures the same angle on 16:9 as on the 4:3 video the thresholds were tuned on", () => {
    const measure = (frameAspect) =>
      new FormAnalyzer(specs.squat.LEFT).process(squatFrame(90, frameAspect), frameAspect, 0).angles.knee;
    close(measure(16 / 9), measure(4 / 3));
    close(measure(16 / 9), 90);
  });

  it("uses the side the person chose", () => {
    const left = squatFrame(170, aspect, specs.squat.LEFT);
    const analyzer = new FormAnalyzer(specs.squat.RIGHT);
    for (const name of ["point_a", "vertex", "point_c"]) {
      assert.notEqual(specs.squat.LEFT.angles[0][name], specs.squat.RIGHT.angles[0][name]);
    }
    assert.ok(analyzer.process(left, aspect, 0).angles.knee < 170);
  });

  it("says which joint it cannot see instead of guessing", () => {
    const frame = squatFrame(170);
    frame[specs.squat.LEFT.angles[0].vertex].visibility = 0.1;
    const result = new FormAnalyzer(specs.squat.LEFT).process(frame, aspect, 0);
    assert.equal(result.angles.knee, undefined);
    assert.match(result.feedback[0], /Can't see your knee clearly/);
  });

  it("treats a missing visibility score as not visible", () => {
    const frame = squatFrame(170).map(({ x, y }) => ({ x, y }));
    assert.equal(new FormAnalyzer(specs.squat.LEFT).process(frame, aspect, 0).angles.knee, undefined);
  });

  it("only applies a stage-specific form check in that stage", () => {
    const spec = specs.squat.LEFT;
    const leaning = (angle) => {
      const frame = squatFrame(angle);
      const hip = frame[spec.angles[1].vertex];
      frame[spec.angles[1].point_a] = point(hip.x - 0.3, hip.y + 0.1);
      return frame;
    };
    const analyzer = new FormAnalyzer(spec);
    assert.deepEqual(analyzer.process(leaning(170), aspect, 0).feedback, []);
    assert.match(analyzer.process(leaning(90), aspect, 0).feedback.join(), /Keep your chest up/);
  });
});
