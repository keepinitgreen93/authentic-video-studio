/** One absolute-frame camera move shared across an opaque takeover/avatar cut. */
export type ZoomBridge = {
  fromFrame:number;
  peakFrame:number;
  toFrame:number;
  fromScale:number;
  peakScale:number;
  toScale:number;
  pushEase?:'moving'|'linear';
  pullEase?:'opening';
  holdFromFrame?:number;
  overlapTurn?:{
    fromFrame:number;
    fromScale:number;
    bezier:[number,number,number,number];
  };
};

const smooth=(p:number)=>{const t=Math.max(0,Math.min(1,p));return t*t*(3-2*t);};

// Preserve the negative first y control: it carries the inward velocity into
// the return curve before the rounded reversal. Clamping y would create a hold.
const bezierProgress=(p:number,[x1,y1,x2,y2]:[number,number,number,number])=>{
  const t=Math.max(0,Math.min(1,p));
  if(t===0||t===1)return t;
  let lo=0,hi=1;
  for(let i=0;i<32;i++){
    const u=(lo+hi)/2,x=3*(1-u)*(1-u)*u*x1+3*(1-u)*u*u*x2+u*u*u;
    if(x<t)lo=u;else hi=u;
  }
  const u=(lo+hi)/2;
  return 3*(1-u)*(1-u)*u*y1+3*(1-u)*u*u*y2+u*u*u;
};

export function zoomBridgeScale(frame:number,bridge:ZoomBridge):number {
  if(bridge.holdFromFrame!==undefined){
    // Paired thoughts may finish their push, hold the same camera scale while
    // the next thought reveals, then inherit the locked post-peak return.
    const withoutHold={...bridge,holdFromFrame:undefined};
    const heldScale=zoomBridgeScale(bridge.peakFrame,withoutHold);
    if(frame<bridge.holdFromFrame){
      const t=Math.max(0,Math.min(1,(frame-bridge.fromFrame)/(bridge.holdFromFrame-bridge.fromFrame)));
      return bridge.fromScale+(heldScale-bridge.fromScale)*(t+t*t-t*t*t);
    }
    if(frame<bridge.peakFrame)return heldScale;
  }
  if(bridge.overlapTurn){
    const turn=bridge.overlapTurn;
    if(frame<turn.fromFrame){
      const p=Math.max(0,Math.min(1,(frame-bridge.fromFrame)/(turn.fromFrame-bridge.fromFrame)));
      return bridge.fromScale+(turn.fromScale-bridge.fromScale)*p;
    }
    const p=bezierProgress((frame-turn.fromFrame)/(bridge.toFrame-turn.fromFrame),turn.bezier);
    return turn.fromScale+(bridge.toScale-turn.fromScale)*p;
  }
  if (frame<=bridge.peakFrame) {
    const t=Math.max(0,Math.min(1,(frame-bridge.fromFrame)/(bridge.peakFrame-bridge.fromFrame)));
    // A linear push keeps its speed right up to the reversal, avoiding a slow
    // approach that reads as a hold. Existing moving/default curves keep their
    // eased turn. Image rise and word entrances overlap this parent movement.
    const p=bridge.pushEase==='linear'?t:bridge.pushEase==='moving'?t+t*t-t*t*t:smooth(t);
    return bridge.fromScale+(bridge.peakScale-bridge.fromScale)*p;
  }
  const t=Math.max(0,Math.min(1,(frame-bridge.peakFrame)/(bridge.toFrame-bridge.peakFrame)));
  // The opening's cubic ease-out starts briskly, then settles. It remains one
  // absolute-frame move when the visible content cuts from graphics to avatar.
  const p=bridge.pullEase==='opening'?1-Math.pow(1-t,3):smooth(t);
  return bridge.peakScale+(bridge.toScale-bridge.peakScale)*p;
}
