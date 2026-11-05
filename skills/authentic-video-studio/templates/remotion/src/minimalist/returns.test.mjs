import test from 'node:test';
import assert from 'node:assert/strict';
import {compilePlan,avatarScaleAt,avatarBlurAt,RETURN} from './plan.mjs';
import {zoomBridgeScale} from './motion.mjs';
const words=()=>['Use','the','same','clear','editing','rules.'].map(text=>({text}));
const scene=(id,startFrame,endFrame,variant='single-centered')=>({id,startFrame,endFrame,variant,words:words(),lineBreaks:[3],icon:'customer/image.svg'});
const fixture=()=>({schemaVersion:1,source:{src:'customer/clean.mp4',durationInFrames:950},sound:{enabled:true,clickSrc:'customer/typing.wav',whooshSrc:'customer/whoosh.wav',clickVolume:.12,whooshVolume:.075},takeovers:[scene('one',40,150),{...scene('two',200,400,'paired'),followup:{atFrame:300,words:words(),lineBreaks:[3],icon:'customer/rules.svg'}},scene('three',450,560),scene('four',610,720,'single-side'),scene('five',770,880)]});
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-10,`${a} != ${b}`);
const returns=(p)=>p.cues.filter(c=>c.id.endsWith('-return'));
test('omitted cadence preserves bridge defaults and their calibrated handoff',()=>{
 const p=fixture(),plan=compilePlan(p);
 assert.deepEqual(plan,compilePlan({...p,returnCadence:'bridge'}));
 assert.deepEqual(plan.takeovers.map(s=>s.returnStyle),Array(5).fill('bridge'));
 for(const s of plan.takeovers){close(avatarScaleAt(s.endFrame,plan),1.1338446878938062);close(avatarScaleAt(s.endFrame+24,plan),1);}
 for(let f=0;f<plan.durationInFrames;f++)assert.equal(avatarBlurAt(f,plan),0);
});
test('five single/paired windows yield three bridge whooshes and two snap clicks',()=>{
 const p=fixture(),before=compilePlan(p),after=compilePlan({...p,returnCadence:'alternating'});
 assert.deepEqual(after.takeovers.map(s=>s.returnStyle),['bridge','snap','bridge','snap','bridge']);
 assert.deepEqual(returns(after).map(c=>c.kind),['whoosh','click','whoosh','click','whoosh']);
 for(let i=0;i<5;i++){assert.equal(returns(after)[i].from,after.takeovers[i].endFrame);assert.equal(returns(after)[i].durationInFrames,i%2?3:14);}
 assert.deepEqual(after.cues.filter(c=>!c.id.endsWith('-return')),before.cues.filter(c=>!c.id.endsWith('-return')));
 for(const i of [0,2,4])assert.deepEqual(after.takeovers[i].motion,before.takeovers[i].motion);
});
test('snap singles never pull out; paired push/hold is retained; following speaker stays at1.0',()=>{
 const before=compilePlan(fixture()),after=compilePlan({...fixture(),returnCadence:'alternating'});
 for(const i of [1,3]){
  const s=after.takeovers[i];let previous=-Infinity;
  for(let f=s.startFrame;f<s.endFrame;f++){const scale=zoomBridgeScale(f,s.motion);assert.ok(scale>=previous-1e-12);assert.ok(scale<=RETURN.peakScale+1e-10);previous=scale;}
  const passage=after.avatarPassages.find(p=>p.startFrame===s.endFrame);
  for(let f=passage.startFrame;f<passage.endFrame;f++)assert.equal(avatarScaleAt(f,after),1);
 }
 const a=after.takeovers[1],b=before.takeovers[1];
 for(let f=a.startFrame;f<=b.motion.peakFrame;f++)close(zoomBridgeScale(f,a.motion),zoomBridgeScale(f,b.motion));
 close(zoomBridgeScale(after.takeovers[3].endFrame-1,after.takeovers[3].motion),RETURN.peakScale);
});
test('linked thoughts coexist unchanged and do not consume alternating positions',()=>{
 const p=fixture();p.source.durationInFrames+=220;
 for(const s of p.takeovers.slice(1)){s.startFrame+=220;s.endFrame+=220;if(s.followup)s.followup.atFrame+=220;}
 p.takeovers.splice(1,0,{...scene('linked-a',190,270,'linked'),linkId:'link'},{...scene('linked-b',270,350,'linked'),linkId:'link'});
 const before=compilePlan(p),after=compilePlan({...p,returnCadence:'alternating'});
 assert.deepEqual(after.takeovers.filter(s=>s.variant!=='linked').map(s=>s.returnStyle),['bridge','snap','bridge','snap','bridge']);
 for(const i of [1,2])assert.deepEqual(after.takeovers[i].motion,before.takeovers[i].motion);
 assert.deepEqual(after.cues.filter(c=>c.id.startsWith('linked-')),before.cues.filter(c=>c.id.startsWith('linked-')));
 assert.equal(returns(after).length,5);assert.ok(returns(after).every(c=>!c.id.startsWith('linked-')));
 for(let f=350;f<420;f++){close(avatarScaleAt(f,after),avatarScaleAt(f,before));assert.equal(avatarBlurAt(f,after),0);}
});
test('separate snap asset, gain, and length leave typing/whoosh scheduling intact',()=>{
 const p={...fixture(),returnCadence:'alternating'},before=compilePlan(p);
 const after=compilePlan({...p,sound:{...p.sound,snapClickSrc:'customer/camera-click.wav',snapClickVolume:.1,snapClickDurationFrames:6}});
 assert.deepEqual(after.cues.filter(c=>!c.id.endsWith('-return')),before.cues.filter(c=>!c.id.endsWith('-return')));
 assert.deepEqual(after.cues.filter(c=>c.kind==='whoosh'),before.cues.filter(c=>c.kind==='whoosh'));
 for(const c of returns(after).filter(c=>c.kind==='click')){assert.equal(c.src,'customer/camera-click.wav');assert.equal(c.volume,.1);assert.equal(c.durationInFrames,6);}
 for(const c of returns(before).filter(c=>c.kind==='click')){assert.equal(c.src,p.sound.clickSrc);assert.equal(c.volume,p.sound.clickVolume);assert.equal(c.durationInFrames,3);}
});
test('incoming snap blur is exactly0.9/0.45/0 with no extra camera movement',()=>{
 const plan=compilePlan({...fixture(),returnCadence:'alternating'});
 for(let f=0;f<plan.durationInFrames;f++){
  const s=plan.takeovers.find(s=>s.returnStyle==='snap'&&(f===s.endFrame||f===s.endFrame+1));
  assert.equal(avatarBlurAt(f,plan),s?(f===s.endFrame?.9:.45):0);
 }
});
test('per-window override is supported and invalid return/sound settings are rejected',()=>{
 const p=fixture();p.takeovers[1].returnStyle='bridge';assert.equal(compilePlan({...p,returnCadence:'alternating'}).takeovers[1].returnStyle,'bridge');
 const input={...fixture(),returnCadence:'alternating'};
 assert.throws(()=>compilePlan({...input,returnCadence:'wrong'}),/returnCadence/);
 assert.throws(()=>compilePlan({...input,sound:{...input.sound,snapClickSrc:'/outside.wav'}}),/snapClickSrc/);
 for(const value of [NaN,-1,2])assert.throws(()=>compilePlan({...input,sound:{...input.sound,snapClickVolume:value}}),/snapClickVolume/);
 for(const value of [0,1.5,Infinity])assert.throws(()=>compilePlan({...input,sound:{...input.sound,snapClickDurationFrames:value}}),/positive integer/);
 assert.throws(()=>compilePlan({...input,sound:{...input.sound,snapClickDurationFrames:1000}}),/source duration/);
});
