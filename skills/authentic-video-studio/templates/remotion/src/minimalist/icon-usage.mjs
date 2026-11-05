/** Count all primary/followup/linked thoughts, including aliases of the same local image. */
export function validateIconUsage(takeovers, assetHashes = {}) {
  const thoughts = takeovers.flatMap(scene => [
    {id:scene.id,icon:scene.icon,iconIdentity:scene.iconIdentity},
    ...(scene.followup ? [{id:`${scene.id}/followup`,icon:scene.followup.icon,iconIdentity:scene.followup.iconIdentity}] : [])
  ]);
  const parent=new Map();
  const find=k=>{if(!parent.has(k))parent.set(k,k);const p=parent.get(k);if(p!==k)parent.set(k,find(p));return parent.get(k);};
  const join=(a,b)=>parent.set(find(b),find(a));
  for(const thought of thoughts){
    if(typeof thought.icon!=='string')throw new Error(`${thought.id}: select one icon path`);
    const path=`path:${thought.icon}`;find(path);
    if(thought.iconIdentity!==undefined){
      if(typeof thought.iconIdentity!=='string'||!thought.iconIdentity.trim())throw new Error(`${thought.id}: iconIdentity must be a nonempty shared identity`);
      join(path,`identity:${thought.iconIdentity}`);
    }
    if(assetHashes[thought.icon])join(path,`hash:${assetHashes[thought.icon]}`);
  }
  const groups=new Map();
  for(const thought of thoughts){const key=find(`path:${thought.icon}`);groups.set(key,[...(groups.get(key)??[]),thought]);}
  return [...groups.values()].map(group=>{
    if(group.length>2)throw new Error(`Use an icon no more than twice per video: ${group.map(t=>t.id).join(', ')} share ${group[0].icon}`);
    return {paths:[...new Set(group.map(t=>t.icon))],thoughts:group.map(t=>t.id),count:group.length};
  });
}
