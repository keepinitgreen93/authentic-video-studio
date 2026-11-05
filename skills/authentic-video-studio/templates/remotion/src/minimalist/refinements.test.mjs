import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {compilePlan,avatarScaleAt,avatarBlurAt} from './plan.mjs';
import {validateIconUsage} from './icon-usage.mjs';
const read=name=>JSON.parse(fs.readFileSync(new URL(`../../examples/${name}`,import.meta.url)));
const reference=()=>({...read('lesson-reference.json'),source:{src:'customer/clean.mp4',durationInFrames:3298}});
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-10,`${a} != ${b}`);

test('latest reference compiles with all three return kinds and portable selected avatar pushes',()=>{
 const p=reference(),plan=compilePlan(p);
 assert.equal(plan.avatarPushes.length,3);
 assert.deepEqual([...new Set(plan.takeovers.map(s=>s.returnStyle))].sort(),['bridge','simple','snap']);
 close(avatarScaleAt(1240,plan),1.055);close(avatarScaleAt(2292,plan),1.045);
 close(avatarScaleAt(3297,plan),1.171682242990654);
 assert.equal(avatarScaleAt(2963,plan),1);
 for(let f=2964;f<3298;f++)close(avatarScaleAt(f,plan)-avatarScaleAt(f-1,plan),.055/107);
});
test('the same closing beat extended to fifteen minutes settles and holds without resetting',()=>{
 const p=reference();p.source.durationInFrames=30000;p.avatarPushes[2].endFrame=30000;
 const plan=compilePlan(p);
 for(let f=3320;f<30000;f++)assert.equal(avatarScaleAt(f,plan),1.18);
 for(let f=2963;f<3320;f++)assert.ok(avatarScaleAt(f,plan)<=1.18);
});
test('new silent demonstration fits and includes a visible cap-and-hold ending',()=>{
 const p={...read('decisions.json'),source:{src:'__minimalist_synthetic__',durationInFrames:1900}};
 const plan=compilePlan(p);assert.equal(plan.cues.length,0);assert.equal(avatarScaleAt(1899,plan),1.18);
});
test('simple linked return adds exactly one mouse click while preserving the liked avatar drift',()=>{
 const p=reference();p.sound={enabled:true,clickSrc:'owned/typing.wav',whooshSrc:'owned/whoosh.wav',snapClickSrc:'owned/mouse.wav'};
 const plan=compilePlan(p),legacy={...p};delete legacy.treatmentVersion;delete legacy.avatarPushes;
 legacy.takeovers=legacy.takeovers.map(s=>{const copy={...s};if(copy.returnStyle==='simple')delete copy.returnStyle;return copy;});
 const previous=compilePlan(legacy);
 assert.equal(plan.cues.length,36);
 const cue=plan.cues.find(c=>c.id==='coaches-and-consultants-return');
 assert.deepEqual(cue,{id:'coaches-and-consultants-return',kind:'click',from:705,durationInFrames:6,src:'owned/mouse.wav',volume:.1});
 for(let f=705;f<806;f++){close(avatarScaleAt(f,plan),avatarScaleAt(f,previous));assert.equal(avatarBlurAt(f,plan),0);}
 const a=plan.takeovers[2],b=previous.takeovers[2];assert.deepEqual(a.motion,b.motion);
 assert.deepEqual(plan.cues.filter(c=>c.id.includes('-primary-')||c.id.includes('-followup-')),previous.cues.filter(c=>c.id.includes('-primary-')||c.id.includes('-followup-')));
});
test('simple singles cut to a static unblurred avatar and never inherit a zoom-out',()=>{
 const p=reference();p.takeovers[3].returnStyle='simple';const plan=compilePlan(p),s=plan.takeovers[3];
 for(let f=s.endFrame;f<1133;f++){assert.equal(avatarScaleAt(f,plan),1);assert.equal(avatarBlurAt(f,plan),0);}
 assert.equal(s.motion.toScale,s.motion.peakScale);
});
test('enabled refined snap/simple returns require a separate mouse asset; silent mode needs none',()=>{
 const p=reference();p.sound={enabled:true,clickSrc:'owned/typing.wav',whooshSrc:'owned/whoosh.wav'};
 assert.throws(()=>compilePlan(p),/separate customer-supplied mouse/);
 p.sound={enabled:false};assert.equal(compilePlan(p).cues.length,0);
 p.takeovers[1].returnStyle='simple';assert.throws(()=>compilePlan(p),/only the incoming linked/);
});
test('icon reuse counts primary, paired and linked thoughts, including content-hash aliases',()=>{
 const thoughts=[{id:'a',icon:'a.svg'},{id:'b',icon:'b.svg',followup:{icon:'c.svg'}}];
 assert.equal(validateIconUsage(thoughts).length,3);
 assert.throws(()=>validateIconUsage(thoughts,{'a.svg':'same','b.svg':'same','c.svg':'same'}),/no more than twice/);
 assert.throws(()=>validateIconUsage(thoughts.map(t=>({...t,icon:'same.svg'})).concat({id:'d',icon:'same.svg'})),/no more than twice/);
 assert.throws(()=>validateIconUsage(thoughts.map(t=>({...t,iconIdentity:'person',...(t.followup?{followup:{...t.followup,iconIdentity:'person'}}:{})}))),/no more than twice/);
 const p=reference();p.takeovers[0].icon=p.takeovers[2].icon;assert.throws(()=>compilePlan(p),/no more than twice/);
});
test('camera spacing reports rushed avatar passages without hardcoding recording cuts',()=>{
 const p=reference();p.pacing={minAvatarFrames:10000};assert.ok(compilePlan(p).warnings.some(w=>w.includes('breathing room')));
 p.pacing.minAvatarFrames=24;assert.throws(()=>compilePlan(p),/at least25/);
});
