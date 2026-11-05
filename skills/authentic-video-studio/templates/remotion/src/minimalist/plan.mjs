import {zoomBridgeScale} from './motion.mjs';
import {scissorsWordOffset, SCISSORS_CLICK_WORDS} from './cadence.mjs';
import {advances} from './font-metrics.mjs';
import {compileAvatarPushes,avatarPushScaleAt} from './avatar-camera.mjs';
import {validateIconUsage} from './icon-usage.mjs';

export const FPS = 30;
export const CANVAS = Object.freeze({landscape:{w:1920,h:1080},portrait:{w:1080,h:1920}});
/** Portrait layout (1080x1920). Singles are centered; a paired window stacks the two thoughts vertically. */
export const PORTRAIT = Object.freeze({iconTop:560,capTop:907,glideDy:-300,followIconTop:880,followCapTop:1227,capLeft:60,capWidth:960,maxTextWidth:820});
export const RETURN = Object.freeze({slope:0.0005601306566593453,turnScale:1.189172055072358,peakScale:1.1903625264086481,bezier:[0.758897029455562,-0.0988707640589929,0.23531539071721136,1]});
export const DEFAULT_THEME = Object.freeze({backgroundInner:'#23496E',backgroundMiddle:'#122C47',backgroundOuter:'#081726',textColor:'#F8FAFC',highlightColor:'#F7C715',fontFamily:'Arial, Helvetica, sans-serif'});
const assert=(condition,message)=>{if(!condition)throw new Error(message);};
const integer=(n)=>Number.isInteger(n)&&n>=0;
const asset=(s)=>typeof s==='string'&&s.length>0&&!s.startsWith('/')&&!s.includes('\\')&&!s.split('/').includes('..')&&(!s.includes(':')||/^https?:\/\/[^/]+/i.test(s));
const clamp=(n)=>Math.max(0,Math.min(1,n));

/** No transcript guessing: all authored frames are already on the cleaned-source clock. */
export function makeReturn(startFrame,endFrame){
  return {fromFrame:startFrame,peakFrame:endFrame-16,toFrame:endFrame+24,fromScale:RETURN.turnScale-RETURN.slope*(endFrame-20-startFrame),peakScale:RETURN.peakScale,toScale:1,pushEase:'linear',overlapTurn:{fromFrame:endFrame-20,fromScale:RETURN.turnScale,bezier:[...RETURN.bezier]}};
}

/** Opt-in snap keeps the approved entry/peak, with no outward phase. */
export function makeSnap(bridge,paired=false){
  const peakScale=paired?zoomBridgeScale(bridge.peakFrame,{...bridge,holdFromFrame:undefined}):RETURN.peakScale;
  const endFrame=bridge.toFrame-24;
  return {fromFrame:bridge.fromFrame,peakFrame:endFrame-1,toFrame:endFrame,fromScale:bridge.fromScale,peakScale,toScale:peakScale,pushEase:paired?'moving':'linear',...(paired?{holdFromFrame:bridge.holdFromFrame}:{})};
}

function thought(input,firstFrame,label){
  assert(Array.isArray(input.words)&&input.words.length>0&&input.words.length<=24,`${label}: use 1–24 words`);
  const breaks=input.lineBreaks??[];
  assert(Array.isArray(breaks)&&breaks.length<=1&&breaks.every(n=>integer(n)&&n>0&&n<input.words.length),`${label}: use at most two nonempty lines`);
  assert(asset(input.icon),`${label}: icon must be a public-relative path or HTTP(S) URL`);
  const first=Math.floor(input.firstWordFrame??firstFrame);
  assert(integer(first),`${label}: firstWordFrame must be a nonnegative frame`);
  const words=input.words.map((w,index)=>{
    assert(w&&typeof w.text==='string'&&w.text.trim()===w.text&&w.text.length>0&&!/\s/u.test(w.text),`${label}: words must contain one nonempty token each`);
    assert(w.emphasis===undefined||typeof w.emphasis==='boolean',`${label}: emphasis must be boolean`);
    const text=index===0?w.text.charAt(0).toUpperCase()+w.text.slice(1):w.text;
    return {t:text,big:w.emphasis===true,revealFrame:first+scissorsWordOffset(index)};
  });
  const lines=breaks.length?[words.slice(0,breaks[0]),words.slice(breaks[0])]:[words];
  return {icon:input.icon,words,lines,firstWordFrame:first,settledFrame:words[words.length-1].revealFrame+17};
}

function width(text,size,measureText){
  const advance=measureText?measureText(text,size):[...text].reduce((sum,ch)=>sum+(advances[ch]??1),0)*size;
  return advance-3.15*[...text].length;
}

function checkLayoutPortrait(scene,measureText){
  const paired=scene.variant==='paired';
  const longest=Math.max(...scene.lines.map(line=>line.map(w=>w.t).join(' ').length));
  scene.fontSize=Math.min(82,PORTRAIT.maxTextWidth/(longest*.53));
  assert(scene.fontSize>=48,`${scene.id}: text needs a shorter thought or different line break (font below48px)`);
  const scale=scene.variant==='linked'?1.08:RETURN.peakScale;
  const [ox,oy]=scene.origin;
  const lineWidths=(lines)=>lines.map(line=>width(line.map(w=>w.t).join(' '),scene.fontSize,measureText));
  const widest=Math.max(...lineWidths(scene.lines));
  const primary=[ox+(540-widest/2-ox)*scale,ox+(540+widest/2-ox)*scale];
  assert(primary[0]>=8&&primary[1]<=1072,`${scene.id}: primary caption exceeds the frame at maximum scale`);
  const lh=n=>n*1.18*scene.fontSize+12;
  let bottom=PORTRAIT.capTop+lh(scene.lines.length);
  if(paired){
    const f=scene.followup,fw=Math.max(...lineWidths(f.lines));
    const sec=[ox+(540-fw/2-ox)*scale,ox+(540+fw/2-ox)*scale];
    assert(sec[0]>=8&&sec[1]<=1072,`${scene.id}: incoming caption exceeds the frame at maximum scale`);
    assert(PORTRAIT.capTop+PORTRAIT.glideDy+lh(scene.lines.length)+12<=PORTRAIT.followIconTop,`${scene.id}: paired thoughts overlap vertically; use shorter lines`);
    bottom=PORTRAIT.followCapTop+lh(f.lines.length);
  }
  assert(oy+(bottom-oy)*scale<1920-8,`${scene.id}: caption extends below the frame`);
  scene.layoutBounds={primaryX:primary,maximumScale:scale};
}

function checkLayout(scene,measureText){
  if(scene.canvas==='portrait')return checkLayoutPortrait(scene,measureText);
  const side=scene.variant==='single-side',paired=scene.variant==='paired';
  const longest=Math.max(...scene.lines.map(line=>line.map(w=>w.t).join(' ').length));
  scene.fontSize=Math.min(side?84:82,(side?790:1240)/(longest*.53));
  assert(scene.fontSize>=48,`${scene.id}: text needs a shorter thought or different line break (font below48px)`);
  const scale=scene.variant==='linked'?1.08:RETURN.peakScale;
  const rightOrigin=scene.origin[0];
  const lineWidths=(lines)=>lines.map(line=>width(line.map(w=>w.t).join(' '),scene.fontSize,measureText));
  const primaryWidths=lineWidths(scene.lines);
  const bounds=(center,w)=>[rightOrigin+(center-w/2-rightOrigin)*scale,rightOrigin+(center+w/2-rightOrigin)*scale];
  const widest=Math.max(...primaryWidths);
  const primary=side?[960+(870-960)*scale,960+(870+widest-960)*scale]:bounds(paired?540:960,widest);
  assert(primary[0]>=8&&primary[1]<=1912,`${scene.id}: primary caption exceeds the frame at maximum scale`);
  if(paired){
    const secondary=bounds(1390,Math.max(...lineWidths(scene.followup.lines)));
    assert(secondary[0]>=8&&secondary[1]<=1912,`${scene.id}: incoming caption exceeds the frame at maximum scale`);
    assert(primary[1]+12<=secondary[0],`${scene.id}: paired captions overlap; use two short lines per thought`);
  }
  const captionBottom=(side?425:612)+Math.max(scene.lines.length,scene.followup?.lines.length??0)*1.18*scene.fontSize+12;
  assert(scene.origin[1]+(captionBottom-scene.origin[1])*scale<1072,`${scene.id}: caption extends below the frame`);
  scene.layoutBounds={primaryX:primary,maximumScale:scale};
}

function buildCues(scenes,sound,refined){
  if(!sound.enabled)return [];
  assert(asset(sound.clickSrc)||asset(sound.whooshSrc)||asset(sound.snapClickSrc),'Enabled sound needs a customer-supplied clickSrc, snapClickSrc, or whooshSrc');
  const cues=[];
  for(const scene of scenes){
    if(sound.clickSrc){
      for(const [name,t] of [['primary',scene],['followup',scene.followup]]){
        if(!t)continue;
        for(const index of SCISSORS_CLICK_WORDS.filter(i=>i<t.words.length)){
          const from=Math.floor(t.words[index].revealFrame)+1-sound.clickLeadFrames;
          assert(from>=scene.startFrame&&from+3<=scene.endFrame,`${scene.id}: click falls outside its thought`);
          cues.push({id:`${scene.id}-${name}-${index}`,kind:'click',from,durationInFrames:3,src:sound.clickSrc,volume:sound.clickVolume});
        }
      }
    }
    if(scene.variant!=='linked'||scene.returnStyle==='simple'){
      if(scene.returnStyle==='snap'||scene.returnStyle==='simple'){
        if(refined)assert(asset(sound.snapClickSrc),`${scene.id}: treatment1.2 needs a separate customer-supplied mouse snapClickSrc for snap/simple returns`);
        const snapClickSrc=sound.snapClickSrc??sound.clickSrc;
        assert(asset(snapClickSrc),`${scene.id}: enabled snap return needs snapClickSrc or clickSrc`);
        cues.push({id:`${scene.id}-return`,kind:'click',from:scene.endFrame,durationInFrames:sound.snapClickDurationFrames??3,src:snapClickSrc,volume:sound.snapClickVolume??sound.clickVolume});
      }else if(sound.whooshSrc)cues.push({id:`${scene.id}-return`,kind:'whoosh',from:scene.endFrame,durationInFrames:14,src:sound.whooshSrc,volume:sound.whooshVolume});
    }
  }
  return cues;
}

export function compilePlan(props,options={}){
  assert(props&&props.schemaVersion===1,'schemaVersion must be1');
  assert(props.treatmentVersion===undefined||props.treatmentVersion==='1.2','treatmentVersion must be1.2 or omitted for legacy jobs');
  const refined=props.treatmentVersion==='1.2';
  assert(props.source&&asset(props.source.src),'source.src must be a public-relative path or HTTP(S) URL');
  const duration=props.source.durationInFrames;
  assert(integer(duration)&&duration>0,'source.durationInFrames must be a positive integer');
  assert(Array.isArray(props.takeovers),'takeovers must be an array');
  const canvas=props.canvas??'landscape';
  assert(canvas==='landscape'||canvas==='portrait','canvas must be landscape or portrait');
  const returnCadence=props.returnCadence??'bridge';
  assert(['bridge','alternating'].includes(returnCadence),'returnCadence must be bridge or alternating');
  // Linked replacements retain their own approved handoff. Only single/paired
  // windows consume a position in the optional return cadence.
  const theme={...DEFAULT_THEME,...props.theme};
  for(const key of Object.keys(DEFAULT_THEME))assert(typeof theme[key]==='string'&&theme[key].length>0,`theme.${key} must be a nonempty string`);
  for(const key of ['backgroundInner','backgroundMiddle','backgroundOuter','textColor','highlightColor'])assert(/^#[\da-f]{6}$/i.test(theme[key]),`theme.${key} must be a six-digit hex color`);
  const warnings=[];
  const pacing={minAvatarFrames:90,...props.pacing};
  if(refined)assert(integer(pacing.minAvatarFrames)&&pacing.minAvatarFrames>=25,'pacing.minAvatarFrames must be at least25');
  if(theme.fontFamily!==DEFAULT_THEME.fontFamily&&!options.measureText)warnings.push('Custom font: Node preflight uses Arial metrics; renderer verifies actual browser metrics. Ensure that font is installed on every render host.');
  const avatar={opening:true,openingFromScale:1.1,openingSettleFrames:19,driftScale:1.055,...props.avatar};
  assert(typeof avatar.opening==='boolean'&&integer(avatar.openingSettleFrames)&&avatar.openingSettleFrames>0,'Invalid avatar opening settings');
  assert(Number.isFinite(avatar.openingFromScale)&&avatar.openingFromScale>=1&&avatar.openingFromScale<=1.2,'avatar.openingFromScale must be1–1.2');
  assert(Number.isFinite(avatar.driftScale)&&avatar.driftScale>=1&&avatar.driftScale<=1.09,'avatar.driftScale must be1–1.09');
  const sound={enabled:false,clickVolume:.12,whooshVolume:.075,clickLeadFrames:0,...(refined?{snapClickVolume:.1,snapClickDurationFrames:6}:{}),...props.sound};
  assert(typeof sound.enabled==='boolean','sound.enabled must be boolean');
  for(const key of ['clickVolume','whooshVolume'])assert(Number.isFinite(sound[key])&&sound[key]>=0&&sound[key]<=1,`sound.${key} must be0–1`);
  assert(integer(sound.clickLeadFrames)&&sound.clickLeadFrames<=3,'sound.clickLeadFrames must be0–3');
  if(sound.snapClickDurationFrames!==undefined)assert(integer(sound.snapClickDurationFrames)&&sound.snapClickDurationFrames>0,'sound.snapClickDurationFrames must be a positive integer');
  if(sound.snapClickVolume!==undefined)assert(Number.isFinite(sound.snapClickVolume)&&sound.snapClickVolume>=0&&sound.snapClickVolume<=1,'sound.snapClickVolume must be0–1');
  for(const key of ['clickSrc','whooshSrc','snapClickSrc'])if(sound[key]!==undefined)assert(asset(sound[key]),`sound.${key} must be a public-relative path or HTTP(S) URL`);
  const ids=new Set();
  let returnOrdinal=0;
  const scenes=props.takeovers.map((s,index)=>{
    assert(s&&typeof s.id==='string'&&s.id.length>0&&!ids.has(s.id),'Every takeover needs a unique id');ids.add(s.id);
    assert(integer(s.startFrame)&&integer(s.endFrame)&&s.startFrame<s.endFrame&&s.endFrame<=duration,`${s.id}: invalid visual interval`);
    assert(['single-centered','single-side','paired','linked'].includes(s.variant),`${s.id}: unknown variant`);
    if(index)assert(s.startFrame>=props.takeovers[index-1].endFrame,`${s.id}: takeovers must be ordered and cannot overlap`);
    const linkedIncoming=s.variant==='linked'&&index>0&&props.takeovers[index-1].variant==='linked'&&props.takeovers[index-1].linkId===s.linkId;
    const delay=s.variant.startsWith('single')?10:linkedIncoming?0:20;
    const ordinal=s.variant==='linked'?undefined:returnOrdinal++;
    const returnStyle=s.returnStyle??(returnCadence==='alternating'&&ordinal!==undefined&&ordinal%2===1?'snap':'bridge');
    assert(['bridge','snap',...(refined?['simple']:[])].includes(returnStyle),`${s.id}: returnStyle must be bridge, snap, or treatment1.2 simple`);
    if(s.variant==='linked')assert(s.returnStyle===undefined||(refined&&linkedIncoming&&s.returnStyle==='simple'),`${s.id}: only the incoming linked thought accepts treatment1.2 simple return`);
    const t=thought(s,s.startFrame+delay,s.id);
    assert(t.firstWordFrame>=s.startFrame+delay,`${s.id}: firstWordFrame precedes its allowed entrance`);
    assert(t.settledFrame<s.endFrame,`${s.id}: words do not finish before the cut`);
    if(t.firstWordFrame>s.startFrame+delay+10)warnings.push(`${s.id}: first word starts more than10frames after the default entrance; review the image-only wait.`);
    const primaryHoldEnd=s.variant==='paired'?s.followup?.atFrame:s.endFrame;
    if(primaryHoldEnd-t.settledFrame>60)warnings.push(`${s.id}: completed text holds ${((primaryHoldEnd-t.settledFrame)/30).toFixed(2)}s before ${s.variant==='paired'?'gliding':'the cut'}; review pacing (approvedV19 also permits longer holds).`);
    const scene={...t,id:s.id,startFrame:s.startFrame,endFrame:s.endFrame,variant:s.variant,linkId:s.linkId,returnStyle,canvas,origin:canvas==='portrait'?(s.variant==='linked'?[540,980]:[540,960]):(s.variant==='linked'?[960,560]:[960,540])};
    if(s.variant==='paired'){
      assert(s.followup&&Number.isFinite(s.followup.atFrame),`${s.id}: paired variant needs followup.atFrame`);
      const at=s.followup.atFrame;
      assert(at>s.startFrame+20&&at+38<s.endFrame-16,`${s.id}: insufficient time for paired glide and return`);
      assert(t.settledFrame<=at,`${s.id}: first thought must finish before its glide`);
      scene.followup={...thought(s.followup,at+22,`${s.id} followup`),atFrame:at};
      assert(scene.followup.firstWordFrame>=Math.floor(at+22),`${s.id}: incoming words precede the image entrance`);
      assert(scene.followup.settledFrame<=s.endFrame-16,`${s.id}: incoming words must finish before the return`);
      if(s.endFrame-scene.followup.settledFrame>60)warnings.push(`${s.id} followup: completed text holds ${((s.endFrame-scene.followup.settledFrame)/30).toFixed(2)}s; review pacing.`);
    }else assert(!s.followup,`${s.id}: only paired variants accept followup`);
    if(s.variant!=='linked'){
      assert(s.startFrame<s.endFrame-20,`${s.id}: takeover is too short for locked return`);
      scene.motion=makeReturn(s.startFrame,s.endFrame);
      if(s.variant==='paired'){scene.motion.fromScale=1.07;scene.motion.pushEase='moving';scene.motion.holdFromFrame=Math.ceil(s.followup.atFrame);}
      if(returnStyle==='snap'||returnStyle==='simple')scene.motion=makeSnap(scene.motion,s.variant==='paired');
      assert(scene.motion.fromScale>=.9&&scene.motion.fromScale<=1.2,`${s.id}: window is outside supported locked motion duration`);
      const next=props.takeovers[index+1]?.startFrame??duration;
      assert(s.endFrame+24<next,`${s.id}: keep at least25frames of speaker after the takeover`);
    }
    return scene;
  });
  const links=new Map();
  for(const scene of scenes)if(scene.variant==='linked'){
    assert(typeof scene.linkId==='string'&&scene.linkId.length>0,`${scene.id}: linked variant needs linkId`);
    links.set(scene.linkId,[...(links.get(scene.linkId)??[]),scene]);
  }
  for(const [id,pair] of links){
    assert(pair.length===2&&pair[0].endFrame===pair[1].startFrame,`linkId ${id}: exactly two adjacent thoughts are required`);
    assert(pair[1].firstWordFrame===pair[1].startFrame,`linkId ${id}: incoming first word must start at replacement`);
    const motion={fromFrame:pair[0].startFrame,peakFrame:pair[1].startFrame,toFrame:pair[1].endFrame-1,fromScale:.96,peakScale:1.08,toScale:.96,pushEase:'moving'};
    pair.forEach(s=>s.motion=motion);
  }
  scenes.forEach(s=>checkLayout(s,options.measureText));
  if(refined)validateIconUsage(props.takeovers);
  const passages=[];let from=0;let previous=null;
  for(const scene of [...scenes,{startFrame:duration,endFrame:duration}]){
    if(scene.startFrame>from)passages.push({startFrame:from,endFrame:scene.startFrame,bridge:previous&&previous.variant!=='linked'&&previous.returnStyle==='bridge'?previous.motion:undefined,...(previous?.returnStyle==='snap'||(previous?.returnStyle==='simple'&&previous?.variant!=='linked')?{staticScale:1,...(previous.returnStyle==='simple'?{simpleReturn:true}:{})}:{})});
    from=scene.endFrame;previous=scene;
  }
  if(refined){
    for(const p of passages)if(p.startFrame>0&&p.endFrame<duration&&p.endFrame-p.startFrame<pacing.minAvatarFrames)warnings.push(`Avatar passage at frame${p.startFrame} is only${((p.endFrame-p.startFrame)/FPS).toFixed(2)}s; prefer at least${(pacing.minAvatarFrames/FPS).toFixed(2)}s of breathing room where the spoken beat allows.`);
    const returns=scenes.filter((s,i)=>s.variant!=='linked'||scenes[i+1]?.linkId!==s.linkId).map(s=>s.variant==='linked'?'simple':s.returnStyle);
    if(returns.some((r,i)=>r==='bridge'&&returns[i-1]==='bridge'))warnings.push('Consecutive bridge returns: prefer a snap or simple mouse-click return between whooshes.');
  }
  const cues=buildCues(scenes,sound,refined);
  assert(cues.every(c=>c.from+c.durationInFrames<=duration),'A sound cue extends beyond the source duration');
  const plan={schemaVersion:1,canvas,durationInFrames:duration,source:{...props.source},theme,avatar,sound,returnCadence,takeovers:scenes,avatarPassages:passages,cues,warnings};
  if(refined){
    plan.treatmentVersion='1.2';plan.pacing=pacing;
    plan.avatarPushes=compileAvatarPushes(props.avatarPushes??[],{durationInFrames:duration,avatarPassages:passages,baselineScaleAt:frame=>baselineAvatarScaleAt(frame,plan)});
  }
  return plan;
}

export function validatePlan(props,options={}){
  try{const plan=compilePlan(props,options);return {valid:true,errors:[],warnings:plan.warnings};}
  catch(error){return {valid:false,errors:[error instanceof Error?error.message:String(error)],warnings:[]};}
}

export function avatarScaleAt(frame,plan){
  const push=avatarPushScaleAt(frame,plan.avatarPushes??[]);
  return push??baselineAvatarScaleAt(frame,plan);
}

function baselineAvatarScaleAt(frame,plan){
  const passage=plan.avatarPassages.find(p=>frame>=p.startFrame&&frame<p.endFrame);
  if(!passage)return 1;
  if(passage.staticScale!==undefined)return passage.staticScale;
  if(passage.bridge)return zoomBridgeScale(frame,passage.bridge);
  if(passage.startFrame===0&&plan.avatar.opening){
    const t=clamp(frame/Math.min(plan.avatar.openingSettleFrames,passage.endFrame));
    return 1+(plan.avatar.openingFromScale-1)*(1-t)**3;
  }
  const t=clamp((frame-passage.startFrame)/Math.max(1,passage.endFrame-passage.startFrame-1));
  return 1+(plan.avatar.driftScale-1)*t;
}

/** Two incoming frames only; no opacity or camera change accompanies the snap. */
export function avatarBlurAt(frame,plan){
  const passage=plan.avatarPassages.find(p=>p.staticScale!==undefined&&!p.simpleReturn&&frame>=p.startFrame&&frame<p.endFrame);
  if(!passage)return 0;
  const age=frame-passage.startFrame;
  return age===0?.9:age===1?.45:0;
}
