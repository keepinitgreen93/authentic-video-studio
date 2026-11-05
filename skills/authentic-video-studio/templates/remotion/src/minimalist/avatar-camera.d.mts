export type AvatarPushInput = {
  id: string;
  startFrame: number;
  endFrame: number;
  kind: 'beat' | 'closing';
  speedPerFrame?: number;
  maxScale?: number;
};
export type CompiledAvatarPush = Required<AvatarPushInput> & {
  settleFrames: number;
  settleStartAge: number;
  settleEndAge: number;
};
export type AvatarPushContext = {
  durationInFrames: number;
  avatarPassages: Array<{startFrame: number; endFrame: number}>;
  /** Evaluate the preexisting camera without avatar pushes. */
  baselineScaleAt: (frame: number) => number;
};
export const DEFAULT_AVATAR_PUSH_SPEED: number;
export const MAX_AVATAR_PUSH_SCALE: number;
export const AVATAR_PUSH_SETTLE_FRAMES: number;
export const AVATAR_PUSH_ENTRY_GUARD_FRAMES: number;
export function compileAvatarPushes(inputs: AvatarPushInput[] | undefined, context: AvatarPushContext): CompiledAvatarPush[];
export function avatarPushScaleAt(frame: number, pushes?: CompiledAvatarPush[]): number | undefined;
