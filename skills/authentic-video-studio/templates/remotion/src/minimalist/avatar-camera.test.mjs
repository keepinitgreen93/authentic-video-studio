import test from 'node:test';
import assert from 'node:assert/strict';
import {compileAvatarPushes, avatarPushScaleAt, DEFAULT_AVATAR_PUSH_SPEED as SPEED} from './avatar-camera.mjs';

const context = (durationInFrames = 2000, overrides = {}) => ({durationInFrames,
  avatarPassages: [{startFrame: 0, endFrame: durationInFrames}], baselineScaleAt: () => 1, ...overrides});
const input = (overrides = {}) => ({id: 'example', startFrame: 60, endFrame: 2000, kind: 'beat', ...overrides});
const compile = (overrides = {}, ctx = context()) => compileAvatarPushes([input(overrides)], ctx);
const near = (a, b, tolerance = 1e-12) => assert.ok(Math.abs(a - b) < tolerance, `${a} differs from ${b}`);

test('omitted or empty pushes leave the existing camera authoritative', () => {
  assert.deepEqual(compileAvatarPushes(undefined, context()), []);
  assert.deepEqual(compileAvatarPushes([], context()), []);
  assert.equal(avatarPushScaleAt(500, []), undefined);
  const pushes = compile();
  assert.equal(avatarPushScaleAt(59, pushes), undefined);
  assert.equal(avatarPushScaleAt(2000, pushes), undefined);
  assert.equal(avatarPushScaleAt(60, pushes), 1);
});

test('approved V8 pace and three endpoints are retained independently of passage duration', () => {
  const pushes = compileAvatarPushes([
    {id: 'first', kind: 'beat', startFrame: 1133, endFrame: 1241},
    {id: 'shorter', kind: 'beat', startFrame: 2207, endFrame: 2293, speedPerFrame: 0.045 / 85},
    {id: 'last', kind: 'closing', startFrame: 2963, endFrame: 3298},
  ], context(3298, {avatarPassages: [
    {startFrame: 900, endFrame: 1241}, {startFrame: 1968, endFrame: 2293}, {startFrame: 2800, endFrame: 3298},
  ]}));
  near(avatarPushScaleAt(1240, pushes), 1.055);
  near(avatarPushScaleAt(2292, pushes), 1.045);
  for (let age = 0; age <= 334; age++) {
    // V8's original normalized linear expression, including its stored closing endpoint.
    near(avatarPushScaleAt(2963 + age, pushes), 1 + (1.171682242990654 - 1) * age / 334);
  }
  near(pushes[2].settleStartAge, 344.181818181818);
});

test('the final twelve frames smoothly bring velocity to zero and hold the cap', () => {
  const pushes = compile(); const p = pushes[0];
  assert.equal(p.settleFrames, 12);
  const a = p.startFrame + p.settleStartAge, b = p.startFrame + p.settleEndAge;
  near(avatarPushScaleAt(a, pushes), 1 + SPEED * p.settleStartAge);
  near(avatarPushScaleAt(b, pushes), 1.18);
  const h = 0.001;
  const left = (at) => (avatarPushScaleAt(at, pushes) - avatarPushScaleAt(at - h, pushes)) / h;
  const right = (at) => (avatarPushScaleAt(at + h, pushes) - avatarPushScaleAt(at, pushes)) / h;
  near(left(a), SPEED, 1e-9); near(left(a), right(a), 3e-8);
  near(right(b), 0); near(left(b), right(b), 3e-8);
  assert.equal(avatarPushScaleAt(b + 10, pushes), 1.18);
  assert.equal(avatarPushScaleAt(1999, pushes), 1.18);
});

test('short passages keep the fixed pace; 60-second and 15-minute passages remain bounded', () => {
  for (const duration of [62, 1800, 27000]) {
    const pushes = compile({endFrame: duration}, context(duration));
    near(avatarPushScaleAt(61, pushes), 1 + SPEED);
    let previous = 1;
    for (let f = 60; f < duration; f++) {
      const value = avatarPushScaleAt(f, pushes);
      assert.ok(value >= previous && value >= 1 && value <= 1.18);
      previous = value;
    }
    if (duration >= 1800) assert.equal(previous, 1.18);
  }
});

test('lower caps and explicit fixed speeds retain continuity without exceeding the cap', () => {
  for (const cap of [1, 1.0001, 1.001, 1.02, 1.18]) {
    const pushes = compile({maxScale: cap});
    assert.ok(pushes[0].settleFrames <= 12);
    assert.equal(avatarPushScaleAt(60, pushes), 1);
    assert.equal(avatarPushScaleAt(1999, pushes), cap);
    let previous = 1;
    for (let f = 60; f < 500; f += 0.25) {
      const value = avatarPushScaleAt(f, pushes);
      assert.ok(value >= previous - 1e-14 && value <= cap);
      previous = value;
    }
  }
  const pushes = compile({speedPerFrame: 0.045 / 85});
  near(avatarPushScaleAt(145, pushes), 1.045);
});

test('absolute frame evaluation never restarts at arbitrary internal cleanup splices', () => {
  const pushes = compile({kind: 'closing'});
  for (const frame of [85, 145, 211, 299]) {
    near(avatarPushScaleAt(frame + 1, pushes) - avatarPushScaleAt(frame, pushes), SPEED);
    near(avatarPushScaleAt(frame, pushes), 1 + SPEED * (frame - 60));
  }
  // Render order cannot change a pure camera trajectory.
  const frames = [1999, 300, 60, 500, 74];
  assert.deepEqual(frames.map(f => avatarPushScaleAt(f, pushes)),
    frames.map(f => avatarPushScaleAt(f, compile({kind: 'closing'}))));
});

test('entry requires thirty prior frames at baseline one, including after a settled return', () => {
  assert.throws(() => compile({startFrame: 29}), /30 settled/);
  assert.doesNotThrow(() => compile({startFrame: 30}));
  for (const frame of [30, 41, 59, 60]) {
    assert.throws(() => compile({}, context(2000, {baselineScaleAt: f => f === frame ? 1.01 : 1})), /baseline camera/);
  }
  assert.throws(() => compile({}, context(2000, {baselineScaleAt: () => NaN})), /baseline camera/);
  assert.throws(() => compile({}, context(2000, {baselineScaleAt: () => 1.05})), /baseline camera/);
});

test('invalid schemas, ordering, ranges, unsafe speeds and visible reset points fail', () => {
  for (const value of [null, {}, 'push']) assert.throws(() => compileAvatarPushes(value, context()), /array/);
  for (const patch of [{id: ''}, {kind: 'wrong'}, {startFrame: -1}, {startFrame: 60.5},
    {endFrame: 2001}, {endFrame: 61}, {endFrame: 1500}, {speedPerFrame: 0},
    {speedPerFrame: SPEED * 1.11}, {speedPerFrame: SPEED * 0.89}, {speedPerFrame: NaN}, {speedPerFrame: null},
    {maxScale: 0.99}, {maxScale: 1.181}, {maxScale: Infinity}, {maxScale: null}, {fromScale: 1}]) {
    assert.throws(() => compile(patch), /avatarPushes/);
  }
  const ctx = context(500, {avatarPassages: [{startFrame: 0, endFrame: 200}, {startFrame: 250, endFrame: 500}]});
  assert.throws(() => compile({kind: 'closing', endFrame: 200}, ctx), /closing/);
  assert.throws(() => compile({endFrame: 500}, ctx), /one avatar passage/);
  const first = input({id: 'one', startFrame: 30, endFrame: 200});
  const second = input({id: 'two', startFrame: 280, endFrame: 500});
  assert.doesNotThrow(() => compileAvatarPushes([first, second], ctx));
  assert.throws(() => compileAvatarPushes([second, first], ctx), /ordered/);
  assert.throws(() => compileAvatarPushes([first, {...second, id: 'one'}], ctx), /unique/);
  assert.throws(() => compileAvatarPushes([first, {...second, startFrame: 190}], ctx), /ordered/);
});

test('compilation does not mutate input or passage objects', () => {
  const pushes = [Object.freeze(input())]; const ctx = context();
  ctx.avatarPassages.forEach(Object.freeze); Object.freeze(ctx.avatarPassages);
  const compiled = compileAvatarPushes(Object.freeze(pushes), Object.freeze(ctx));
  assert.notEqual(compiled[0], pushes[0]);
  assert.equal(pushes[0].speedPerFrame, undefined);
});
