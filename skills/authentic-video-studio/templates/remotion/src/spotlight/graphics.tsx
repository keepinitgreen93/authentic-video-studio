import React from 'react';
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {HEADING, useBrand} from '../brand';

export type BeatGraphic = React.FC<{beatStart: number; beatEnd: number}>;

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

/**
 * The one built-in graphic: a dark card that shows the key words of the beat, one word at a time,
 * with an accent bar. It sits in the area above the presenter window. Agents can add more graphics
 * here and name them in a plan file.
 */
export const KeyPhrase: React.FC<{beatStart: number; beatEnd: number; words: string[]}> = ({beatStart, beatEnd, words}) => {
  const brand = useBrand();
  const th = brand.theme;
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps - beatStart;
  if (t < 0) return null;
  const dur = Math.max(0.6, beatEnd - beatStart);
  const n = Math.max(1, words.length);
  // words arrive 0.18 s apart; the last one is in place at least 1 s before the beat ends when it fits
  const gap = Math.min(0.22, Math.max(0.1, (dur - 1.4) / n));
  const cardIn = interpolate(t, [0, 0.4], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const bar = interpolate(t, [0.15, 0.2 + gap * n + 0.4], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const idle = Math.sin(t * 1.6) * 5;
  const text = words.join(' ');
  const size = Math.max(56, Math.min(120, Math.floor(780 / Math.max(6, Math.max(...words.map((w) => w.length)) * 0.62 * th.widthFactor))));
  const lines: string[][] = [];
  let cur: string[] = [];
  for (const w of words) {
    const trial = [...cur, w].join(' ');
    if (cur.length && trial.length * size * 0.6 * th.widthFactor > 780) { lines.push(cur); cur = [w]; } else cur.push(w);
  }
  if (cur.length) lines.push(cur);
  let idx = 0;
  return (
    <div style={{position: 'absolute', left: 90, top: 380 + idle, width: 900, height: 460, opacity: cardIn, transform: `translateY(${(1 - cardIn) * 40}px)`}}>
      <div style={{position: 'absolute', inset: 0, borderRadius: 44, background: th.ink,
        boxShadow: `0 30px 80px rgba(0,0,0,0.35), 0 0 60px rgba(${th.accentRgb},0.18)`, border: '1.5px solid rgba(255,255,255,0.10)'}} />
      <div style={{position: 'absolute', left: 60, top: 54, width: 120 * bar, height: 12, borderRadius: 6, background: th.accentOnDark}} />
      <div style={{position: 'absolute', left: 60, right: 60, top: 80, bottom: 40, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
        {lines.map((line, li) => (
          <div key={li} style={{display: 'flex', flexWrap: 'nowrap', whiteSpace: 'nowrap', lineHeight: 1.12}}>
            {line.map((w) => {
              const i = idx++;
              const a = interpolate(t, [0.2 + i * gap, 0.2 + i * gap + 0.28], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
              const last = i === n - 1;
              return (
                <span key={i} aria-label={text} style={{fontFamily: HEADING, fontWeight: 800, fontSize: size, marginRight: Math.round(size * 0.24),
                  color: last ? th.accentOnDark : th.label, opacity: a, transform: `translateY(${(1 - a) * 36}px)`, display: 'inline-block'}}>{w}</span>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};
