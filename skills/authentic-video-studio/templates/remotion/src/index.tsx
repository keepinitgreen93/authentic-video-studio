import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {DEFAULT_BRAND} from './brand';
import type {Brand} from './brand';
import {FontGate} from './FontGate';
import {SpotlightComp} from './spotlight/Spotlight';
import type {SpotlightJob} from './spotlight/Spotlight';
import {Minimalist} from './minimalist/Minimalist';
import {CANVAS} from './minimalist/plan.mjs';
import type {Props as MiniProps} from './minimalist/plan.mjs';

type SpotProps = {brand: Brand; job: SpotlightJob};
type MiniPropsWrap = {brand: Brand; plan: MiniProps};

const spotDefault: SpotProps = {
  brand: DEFAULT_BRAND,
  job: {src: 'host/cut.mp4', frames: 90, sourceSize: {w: 1080, h: 1920}, faceX: 540, faceY: 700, words: [],
    scenes: [{from: 0, mode: 'full'}], swaps: [], beats: [], captionTop: {full: 1230, window: 905, panel: 905}},
};
const miniDefault: MiniPropsWrap = {
  brand: DEFAULT_BRAND,
  plan: {schemaVersion: 1, canvas: 'portrait', source: {src: 'host/cut.mp4', durationInFrames: 90}, takeovers: []},
};

const Root: React.FC = () => (
  <>
    <Composition
      id="Spotlight"
      component={(p: SpotProps) => <FontGate brand={p.brand}><SpotlightComp job={p.job} /></FontGate>}
      width={1080} height={1920} fps={30} durationInFrames={90}
      defaultProps={spotDefault}
      calculateMetadata={({props}) => ({durationInFrames: Math.max(1, props.job.frames)})}
    />
    <Composition
      id="Minimalist"
      component={(p: MiniPropsWrap) => <FontGate brand={p.brand}><Minimalist plan={p.plan} /></FontGate>}
      width={CANVAS.portrait.w} height={CANVAS.portrait.h} fps={30} durationInFrames={90}
      defaultProps={miniDefault}
      calculateMetadata={({props}) => {
        const c = CANVAS[props.plan.canvas ?? 'portrait'];
        return {durationInFrames: Math.max(1, props.plan.source.durationInFrames), width: c.w, height: c.h};
      }}
    />
  </>
);
registerRoot(Root);
