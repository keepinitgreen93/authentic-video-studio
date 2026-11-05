import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {HEADING, useBrand} from './brand';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/** Logo, hook text and end card. Same placement rules as the FFmpeg styles. */
export const Overlays: React.FC = () => {
  const brand = useBrand();
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const t = frame / fps;
  const total = durationInFrames / fps;
  const th = brand.theme;
  const logo = brand.logo;
  const maxW = width * 0.9;
  const fit = (text: string, size: number) => Math.min(size, Math.floor(maxW / (Math.max(1, text.length) * 0.66 * th.widthFactor)));
  const box = (lines: string[], size: number, color: string, bg: string, top: number, opacity: number) => (
    <div style={{position: 'absolute', left: 0, right: 0, top, display: 'flex', flexDirection: 'column', alignItems: 'center', opacity}}>
      {lines.map((line, i) => (
        <div key={i} style={{fontFamily: HEADING, fontWeight: 800, fontSize: fit(line, size), lineHeight: 1.1, color, background: bg,
          padding: '14px 28px', marginTop: i ? 14 : 0, borderRadius: 6, whiteSpace: 'nowrap'}}>{line}</div>
      ))}
    </div>
  );
  const hook = brand.hook;
  const end = brand.endCard;
  const hookOpacity = hook ? interpolate(t, [0, 0.15, hook.seconds - 0.2, hook.seconds], [0, 1, 1, 0], clamp) : 0;
  const endStart = end ? Math.max(0, total - end.seconds) : 0;
  const endOpacity = end ? interpolate(t, [endStart, endStart + 0.2], [0, 1], clamp) : 0;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      {logo.file && (
        <Img src={staticFile(logo.file)} style={{position: 'absolute', top: 120, width: Math.round(width * logo.scale),
          ...(logo.position.includes('right') ? {right: 48} : {left: 48}), opacity: 0.95}} />
      )}
      {hook && hookOpacity > 0.01 && box(hook.lines, 84, th.hookText, th.hookBox, Math.round(height * 0.15), hookOpacity)}
      {end && endOpacity > 0.01 && box([end.text], 84, th.endText, th.endBox, Math.round(height * 0.15), endOpacity)}
    </AbsoluteFill>
  );
};
