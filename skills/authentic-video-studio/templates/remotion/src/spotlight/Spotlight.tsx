import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {BODY, useBrand} from '../brand';
import {Overlays} from '../Overlays';
import {Caption, Reel, buildChunks} from './Reel';
import type {CapWord, ReelConfig} from './Reel';
import {KeyPhrase} from './graphics';
import type {BeatGraphic} from './graphics';

export type SpotlightJob = {
  src: string;                       // clean cut, relative to the staged public folder
  frames: number;
  sourceSize: {w: number; h: number};
  faceX: number;
  faceY: number;
  words: CapWord[];
  scenes: ReelConfig['scenes'];
  swaps: ReelConfig['swaps'];
  beats: {start: number; end: number; words: string[]; over?: boolean}[];
  captionTop: {full: number; window: number; panel: number};
};

const smooth = (v: number) => {
  const x = Math.max(0, Math.min(1, v));
  return x * x * (3 - 2 * x);
};

export const SpotlightComp: React.FC<{job: SpotlightJob}> = ({job}) => {
  const brand = useBrand();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const win = job.scenes.find((s) => s.mode === 'window');
  let top = job.captionTop.full + (job.captionTop.window - job.captionTop.full) * (win ? smooth((t - win.from) / 0.5) : 0);
  for (const s of job.swaps) top += (job.captionTop.panel - job.captionTop.window) * (smooth((t - s.in) / 0.5) - smooth((t - s.out) / 0.5));
  const beats = React.useMemo(() => job.beats.map((b) => {
    const G: BeatGraphic = ({beatStart, beatEnd}) => <KeyPhrase beatStart={beatStart} beatEnd={beatEnd} words={b.words} />;
    return {start: b.start, end: b.end, G, over: b.over};
  }), [job.beats]);
  const config: ReelConfig = {
    src: job.src, frames: job.frames, srcSize: job.sourceSize, faceX: job.faceX, faceY: job.faceY, words: [], voiceGain: 0,
    open: {from: 1.4, dur: 0.85}, grid: {light: brand.theme.gridLight}, scenes: job.scenes, swaps: job.swaps, beats,
  };
  const chunks = React.useMemo(() => buildChunks(job.words), [job.words]);
  return (
    <AbsoluteFill style={{fontFamily: BODY}}>
      <Reel config={config} />
      <Caption words={job.words} chunks={chunks} top={top} accent={brand.theme.accentOnDark} />
      <Overlays />
    </AbsoluteFill>
  );
};
