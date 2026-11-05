import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {useBrand} from '../brand';

const CELL = 58, GAP = 12, STEP = CELL + GAP;
const SPEED = 22;

/** Moving rounded-tile grid. Colors come from the brand theme. */
export const GridBg: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const th = useBrand().theme;
  const light = th.gridLight;
  const cols = Math.ceil(width / STEP) + 3;
  const rows = Math.ceil(height / STEP) + 1;
  const shift = ((frame / fps) * SPEED) % STEP;
  const cells: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const seed = (r * 29 + c * 53) % 97;
      const glow = seed % 11 === 0;
      let bg = light ? `rgba(${th.tileRgb},0.055)` : 'rgba(245,243,238,0.035)';
      if (glow) {
        const b = 0.5 + 0.5 * Math.sin((frame / fps) * 1.05 + seed * 0.7);
        bg = light ? `rgba(${th.accentRgb}, ${(0.2 + 0.3 * b).toFixed(3)})` : `rgba(${th.accentRgb}, ${(0.05 + 0.16 * b).toFixed(3)})`;
      }
      cells.push(<div key={`${r}-${c}`} style={{position: 'absolute', left: c * STEP, top: r * STEP, width: CELL, height: CELL, borderRadius: 9, background: bg}} />);
    }
  }
  const base = light
    ? `radial-gradient(130% 110% at 50% 0%, ${th.bg[0]} 0%, ${th.bg[1]} 55%, ${th.bg[2]} 100%)`
    : `radial-gradient(130% 110% at 50% 0%, ${th.bg[0]} 0%, ${th.bg[1]} 55%, ${th.bg[2]} 100%)`;
  return (
    <AbsoluteFill style={{background: base}}>
      <div style={{position: 'absolute', left: -STEP - shift, top: -GAP, width: cols * STEP, height: rows * STEP}}>{cells}</div>
      <AbsoluteFill style={{background: light
        ? `radial-gradient(120% 92% at 50% 42%, transparent 52%, rgba(${th.vignetteRgb},0.14))`
        : 'radial-gradient(120% 92% at 50% 42%, transparent 52%, rgba(0,0,0,0.42))', pointerEvents: 'none'}} />
    </AbsoluteFill>
  );
};
