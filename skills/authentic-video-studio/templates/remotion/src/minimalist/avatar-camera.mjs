/** Deterministic, source-independent camera pushes on an absolute composition clock. */
export const DEFAULT_AVATAR_PUSH_SPEED = 0.055 / 107;
export const MAX_AVATAR_PUSH_SCALE = 1.18;
export const AVATAR_PUSH_SETTLE_FRAMES = 12;
export const AVATAR_PUSH_ENTRY_GUARD_FRAMES = 30;

const MIN_SPEED = DEFAULT_AVATAR_PUSH_SPEED * 0.9;
const MAX_SPEED = DEFAULT_AVATAR_PUSH_SPEED * 1.1;
const EPSILON = 1e-12;
const INPUT_KEYS = new Set(['id', 'startFrame', 'endFrame', 'kind', 'speedPerFrame', 'maxScale']);
const requireValue = (condition, message) => {
  if (!condition) throw new Error(`avatarPushes: ${message}`);
};

/** baselineScaleAt must evaluate the existing camera without these new pushes. */
export function compileAvatarPushes(inputs, context) {
  if (inputs === undefined) return [];
  requireValue(Array.isArray(inputs), 'expected an array');
  if (inputs.length === 0) return [];
  const {durationInFrames, avatarPassages, baselineScaleAt} = context ?? {};
  requireValue(Number.isInteger(durationInFrames) && durationInFrames > 0, 'invalid durationInFrames');
  requireValue(Array.isArray(avatarPassages), 'avatarPassages must be an array');
  requireValue(typeof baselineScaleAt === 'function', 'baselineScaleAt must be a function');
  const ids = new Set();
  let previousEnd = 0;
  return inputs.map(input => {
    requireValue(input !== null && typeof input === 'object' && !Array.isArray(input), 'each push must be an object');
    const {id, startFrame, endFrame, kind} = input;
    requireValue(Object.keys(input).every(key => INPUT_KEYS.has(key)), `${id ?? 'push'} has an unsupported field`);
    requireValue(typeof id === 'string' && id.trim().length > 0 && !ids.has(id), 'push IDs must be nonempty and unique');
    requireValue(kind === 'beat' || kind === 'closing', `${id}: kind must be beat or closing`);
    requireValue(Number.isInteger(startFrame) && Number.isInteger(endFrame)
      && startFrame >= previousEnd && endFrame - startFrame >= 2 && endFrame <= durationInFrames,
    `${id}: ranges must be ordered, nonoverlapping integers with at least two frames inside the video`);
    requireValue(kind !== 'closing' || endFrame === durationInFrames, `${id}: closing must end at the video end`);
    const passage = avatarPassages.find(p => startFrame >= p.startFrame && endFrame <= p.endFrame);
    requireValue(passage !== undefined, `${id}: push must stay inside one avatar passage`);
    requireValue(endFrame === passage.endFrame, `${id}: push must end with its avatar passage to prevent a visible reset`);
    requireValue(startFrame - passage.startFrame >= AVATAR_PUSH_ENTRY_GUARD_FRAMES,
      `${id}: allow at least 30 settled avatar frames before a push`);
    for (let frame = startFrame - AVATAR_PUSH_ENTRY_GUARD_FRAMES; frame <= startFrame; frame++) {
      const scale = baselineScaleAt(frame);
      requireValue(Number.isFinite(scale) && Math.abs(scale - 1) <= EPSILON,
        `${id}: baseline camera must stay at scale 1 throughout the preceding 30 frames and the entry frame`);
    }
    const speedPerFrame = input.speedPerFrame === undefined ? DEFAULT_AVATAR_PUSH_SPEED : input.speedPerFrame;
    const maxScale = input.maxScale === undefined ? MAX_AVATAR_PUSH_SCALE : input.maxScale;
    requireValue(Number.isFinite(speedPerFrame) && speedPerFrame >= MIN_SPEED && speedPerFrame <= MAX_SPEED,
      `${id}: speedPerFrame must stay within 10% of the default fixed pace`);
    requireValue(Number.isFinite(maxScale) && maxScale >= 1 && maxScale <= MAX_AVATAR_PUSH_SCALE,
      `${id}: maxScale must be between 1 and 1.18`);
    const distance = maxScale - 1;
    // A tiny requested cap may not have room for twelve frames of deceleration.
    // Shorten only that ramp, preserving the requested initial velocity and cap.
    const settleFrames = Math.min(AVATAR_PUSH_SETTLE_FRAMES, 2 * distance / speedPerFrame);
    const settleStartAge = Math.max(0, distance / speedPerFrame - settleFrames / 2);
    const settleEndAge = settleStartAge + settleFrames;
    ids.add(id);
    previousEnd = endFrame;
    return {id, startFrame, endFrame, kind, speedPerFrame, maxScale,
      settleFrames, settleStartAge, settleEndAge};
  });
}

/** Returns undefined outside an authored push, so the existing camera remains authoritative. */
export function avatarPushScaleAt(frame, pushes = []) {
  const push = pushes.find(p => frame >= p.startFrame && frame < p.endFrame);
  if (!push) return undefined;
  const age = frame - push.startFrame;
  if (push.maxScale === 1 || age >= push.settleEndAge) return push.maxScale;
  if (age <= push.settleStartAge) return 1 + push.speedPerFrame * age;
  const elapsed = age - push.settleStartAge;
  const scale = 1 + push.speedPerFrame * push.settleStartAge
    + push.speedPerFrame * elapsed
    - push.speedPerFrame * elapsed * elapsed / (2 * push.settleFrames);
  return Math.min(push.maxScale, scale);
}
