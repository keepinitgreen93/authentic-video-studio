import React, {useMemo} from 'react';
import {AbsoluteFill, OffthreadVideo, Sequence} from 'remotion';
import {avatarBlurAt, avatarScaleAt, CANVAS, compilePlan} from './plan.mjs';
import type {Props} from './plan.mjs';
import {Takeover, resolveAsset} from './Takeover';
import {BODY, useBrand} from '../brand';
import {Overlays} from '../Overlays';
import {useCurrentFrame} from 'remotion';

function browserMeasure(fontFamily: string) {
  if (typeof document === 'undefined') return undefined;
  const context = document.createElement('canvas').getContext('2d');
  if (!context) return undefined;
  return (text: string, size: number) => {
    context.font = `700 ${size}px ${fontFamily}`;
    return context.measureText(text).width;
  };
}

/** The Minimalist: dark radial takeovers with one icon and a few words, over the full-frame speaker. */
export const Minimalist: React.FC<{plan: Props}> = ({plan: props}) => {
  const brand = useBrand();
  const m = brand.theme.mini;
  const full: Props = useMemo(() => ({
    ...props,
    theme: {backgroundInner: m.inner, backgroundMiddle: m.middle, backgroundOuter: m.outer, textColor: m.text, highlightColor: m.highlight, fontFamily: BODY, ...props.theme},
  }), [props, m]);
  const plan = useMemo(() => compilePlan(full, {measureText: browserMeasure(full.theme?.fontFamily ?? BODY)}), [full]);
  const frame = useCurrentFrame();
  const scale = avatarScaleAt(frame, plan);
  const blur = avatarBlurAt(frame, plan);
  const dims = CANVAS[plan.canvas];
  return (
    <AbsoluteFill style={{background: plan.theme.backgroundOuter, overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: `${dims.w / 2}px ${dims.h / 2}px`, filter: blur ? `blur(${blur}px)` : undefined}}>
        <OffthreadVideo src={resolveAsset(plan.source.src)} muted style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </AbsoluteFill>
      {plan.takeovers.map((scene) => (
        <Sequence key={scene.id} from={scene.startFrame} durationInFrames={scene.endFrame - scene.startFrame} layout="none">
          <Takeover scene={scene} theme={plan.theme} />
        </Sequence>
      ))}
      <Overlays />
    </AbsoluteFill>
  );
};
