import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {compilePlan,validatePlan,avatarScaleAt,makeReturn} from './plan.mjs';
import {zoomBridgeScale} from './motion.mjs';
import {scissorsWordOffset} from './cadence.mjs';
const input=()=>({...JSON.parse(fs.readFileSync(new URL('../../examples/legacy-decisions.json',import.meta.url),'utf8')),returnCadence:'bridge',source:{src:'customer/cleaned.mp4',durationInFrames:1050}});
const close=(a,b,epsilon=1e-12)=>assert.ok(Math.abs(a-b)<epsilon,`${a} != ${b}`);
test('all four variants compile without media, and narration source identity survives',()=>{
  const props=input();props.source.identity={sha256:'fixture'};
  const plan=compilePlan(props);
  assert.deepEqual([...new Set(plan.takeovers.map(s=>s.variant))],['single-centered','single-side','paired','linked']);
  assert.equal(plan.durationInFrames,1050);assert.equal(plan.source.identity.sha256,'fixture');
  assert.equal(plan.cues.length,0);
});
test('scissors cadence preserves fractional frame intervals and continues every four frames',()=>{
  assert.deepEqual(Array.from({length:9},(_,i)=>scissorsWordOffset(i)),[0,4,8.25,15.45,19.65,23.65,27.65,31.65,35.65]);
  const p=input();p.takeovers[0].firstWordFrame=84.9;
  assert.deepEqual(compilePlan(p).takeovers[0].words.map(w=>w.revealFrame),[84,88,92.25,99.45]);
});
test('single camera is one absolute curve before and after the avatar cut',()=>{
  const plan=compilePlan(input()),scene=plan.takeovers[0],cut=scene.endFrame;
  assert.equal(scene.motion.overlapTurn.fromFrame,cut-20);assert.equal(scene.motion.peakFrame,cut-16);assert.equal(scene.motion.toFrame,cut+24);
  for(let frame=cut;frame<=cut+24;frame++)close(avatarScaleAt(frame,plan),zoomBridgeScale(frame,scene.motion));
  close(avatarScaleAt(cut+24,plan),1);
  assert.ok(zoomBridgeScale(cut-16,scene.motion)>zoomBridgeScale(cut-20,scene.motion));
});
test('paired thoughts inherit the same held camera, then take the same avatar return',()=>{
  const plan=compilePlan(input()),scene=plan.takeovers.find(s=>s.variant==='paired');
  const held=zoomBridgeScale(scene.motion.holdFromFrame,scene.motion);
  close(held,zoomBridgeScale(scene.motion.peakFrame,scene.motion));
  close(held,zoomBridgeScale(scene.followup.settledFrame,scene.motion));
  close(avatarScaleAt(scene.endFrame,plan),zoomBridgeScale(scene.endFrame,scene.motion));
});
test('linked replacement shares exact peak and starts new image and word on the cut',()=>{
  const plan=compilePlan(input()),a=plan.takeovers[3],b=plan.takeovers[4];
  assert.deepEqual(a.motion,b.motion);assert.equal(b.firstWordFrame,b.startFrame);
  close(zoomBridgeScale(b.startFrame,a.motion),1.08);close(zoomBridgeScale(b.endFrame-1,b.motion),.96);
});
test('customer sound cues follow actual reveal frames and whoosh lives after visual cut',()=>{
  const p=input();p.sound={enabled:true,clickSrc:'owned/click.wav',whooshSrc:'owned/whoosh.wav'};
  const plan=compilePlan(p),scene=plan.takeovers[0];
  const clicks=plan.cues.filter(c=>c.id.startsWith(scene.id+'-primary'));
  assert.deepEqual(clicks.map(c=>c.from),[scene.words[0],scene.words[2]].map(w=>Math.floor(w.revealFrame)+1));
  assert.equal(plan.cues.find(c=>c.id===scene.id+'-return').from,scene.endFrame);
  assert.equal(plan.cues.filter(c=>c.kind==='whoosh').length,3);
  assert.ok(plan.cues.every(c=>c.from+c.durationInFrames<=plan.durationInFrames));
});
test('rejects nonfinite, overlapping, unsafe assets, incomplete words, and missing linked thought',()=>{
  const cases=[
    p=>p.source.durationInFrames=Infinity,
    p=>p.takeovers[1].startFrame=200,
    p=>p.source.src='/private/source.mp4',
    p=>p.source.src='ftp://server/source.mp4',
    p=>p.takeovers[0].icon='../outside.svg',
    p=>p.takeovers[0].firstWordFrame=219,
    p=>p.takeovers[0].lineBreaks=[1,2],
    p=>p.takeovers.pop(),
    p=>p.takeovers[2].followup.firstWordFrame=655,
    p=>p.takeovers[0].words=[{text:'a sentence'}],
    p=>p.takeovers[0].words=[{text:'W'.repeat(90)}],
    p=>p.takeovers[1].startFrame=240,
  ];
  for(const mutate of cases){const p=input();mutate(p);assert.equal(validatePlan(p).valid,false);assert.throws(()=>compilePlan(p));}
});
test('paired hold warning counts only the time before its glide',()=>{
  const p=input(),plan=compilePlan(p),scene=plan.takeovers[2];
  const seconds=((scene.followup.atFrame-scene.settledFrame)/30).toFixed(2);
  assert.ok(plan.warnings.some(w=>w.includes(`paired: completed text holds ${seconds}s before gliding`)));
});
test('browser font measurement can reject an unsafe custom font',()=>{
  const p=input();p.theme={fontFamily:'Customer Font'};
  assert.ok(compilePlan(p).warnings.some(w=>w.includes('Custom font')));
  assert.throws(()=>compilePlan(p,{measureText:(text,size)=>text.length*size*2}),/exceeds|overlap/);
});
test('frozen numeric helpers retain their exact approved source bytes',()=>{
  for(const filename of ['zoomBridge.ts','typingCadence.ts']){
    const frozen=new URL('./frozen/'+filename,import.meta.url);
    const archived=new URL(frozen.href+'.txt');
    const path=fs.existsSync(frozen)?frozen:archived;
    assert.ok(fs.existsSync(path),`Missing frozen reference ${filename}`);
    assert.equal(fs.readFileSync(path,'utf8'),fs.readFileSync(new URL('./'+filename,import.meta.url),'utf8'));
  }
});
