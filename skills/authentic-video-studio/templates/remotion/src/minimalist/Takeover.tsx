import React from 'react';
import {Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {zoomBridgeScale} from './motion.mjs';
import {PORTRAIT} from './plan.mjs';
import type {CompiledScene,ScheduledWord,Theme} from './plan.mjs';

const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
const mix=(f:number,a:number,b:number,x:number,y:number,easing:(n:number)=>number)=>interpolate(f,[a,b],[x,y],{...clamp,easing});
const wordEase=Easing.bezier(.08,.755,.376,.972);
const opacityEase=Easing.bezier(.1,.55,.35,1);
const imageEase=Easing.bezier(.22,.61,.36,1);
const glideEase=Easing.bezier(0,.85566,.5197,.98315);
export const resolveAsset=(src:string)=>/^https?:\/\//i.test(src)?src:staticFile(src);
function imageEntrance(frame:number){
  const progress=mix(frame,0,20,0,1,imageEase);
  return {translate:`0 ${330*(1-progress)}px`,opacity:progress};
}
function Caption({lines,globalFrame,theme,style}:{lines:ScheduledWord[][];globalFrame:number;theme:Theme;style:React.CSSProperties}){
  return <div style={{position:'absolute',overflow:'visible',fontFamily:theme.fontFamily,fontWeight:700,lineHeight:1.18,letterSpacing:-3.15,paddingBottom:12,...style}}>
    {lines.map((line,index)=><div key={index} style={{whiteSpace:'nowrap',overflow:'visible'}}>{line.map((word,wi)=>{
      const age=globalFrame-word.revealFrame;
      return <React.Fragment key={wi}><span style={{display:'inline-block',overflow:'visible',color:word.big?theme.highlightColor:theme.textColor,translate:`0 ${mix(age,0,17,330,0,wordEase)}px`,opacity:mix(age,0,15,0,1,opacityEase)}}>{word.t}</span>{wi<line.length-1?' ':''}</React.Fragment>;
    })}</div>)}
  </div>;
}
function Icon({src,style}:{src:string;style:React.CSSProperties}){
  return <Img src={resolveAsset(src)} style={style}/>;
}
/** Adapted from the frozen V19 renderer; all camera/entrance/cadence numbers are retained. */
export const Takeover:React.FC<{scene:CompiledScene;theme:Theme}>=({scene,theme})=>{
  const frame=useCurrentFrame(),globalFrame=scene.startFrame+frame;
  const P=scene.canvas==='portrait';
  // The side-by-side layout does not fit a portrait canvas, so single-side is drawn centered there.
  const side=!P&&scene.variant==='single-side',paired=Boolean(scene.followup);
  const scale=zoomBridgeScale(globalFrame,scene.motion);
  const glide=scene.followup?mix(globalFrame-scene.followup.atFrame,0,38,0,1,glideEase):0;
  return <div style={{position:'absolute',inset:0,overflow:'hidden',background:`radial-gradient(ellipse at 50% 42%,${theme.backgroundInner} 0%,${theme.backgroundMiddle} 48%,${theme.backgroundOuter} 100%)`}}>
    <div style={{position:'absolute',inset:0,scale:String(scale),translate:'0px 0px',transformOrigin:`${scene.origin[0]}px ${scene.origin[1]}px`}}>
      <div style={{position:'absolute',inset:0,overflow:'visible',translate:P?`0px ${PORTRAIT.glideDy*glide}px`:`${-420*glide}px 0`,scale:'1',transformOrigin:P?'540px 960px':'960px 560px'}}>
        <Icon src={scene.icon} style={{position:'absolute',left:P?360:side?455:780,top:P?PORTRAIT.iconTop:side?350:265,width:360,height:300,objectFit:'contain',...imageEntrance(frame)}}/>
        <Caption lines={scene.lines} globalFrame={globalFrame} theme={theme} style={{left:P?PORTRAIT.capLeft:side?870:paired?520:310,top:P?PORTRAIT.capTop:side?425:612,width:P?PORTRAIT.capWidth:side?800:paired?880:1300,textAlign:side?'left':'center',fontSize:scene.fontSize}}/>
      </div>
      {scene.followup&&<div style={{position:'absolute',inset:0,overflow:'visible'}}>
        <Icon src={scene.followup.icon} style={{position:'absolute',left:P?360:1210,top:P?PORTRAIT.followIconTop:265,width:360,height:300,objectFit:'contain',...imageEntrance(globalFrame-scene.followup.atFrame-2)}}/>
        <Caption lines={scene.followup.lines} globalFrame={globalFrame} theme={theme} style={{left:P?PORTRAIT.capLeft:950,top:P?PORTRAIT.followCapTop:612,width:P?PORTRAIT.capWidth:880,textAlign:'center',fontSize:scene.fontSize}}/>
      </div>}
    </div>
  </div>;
};
