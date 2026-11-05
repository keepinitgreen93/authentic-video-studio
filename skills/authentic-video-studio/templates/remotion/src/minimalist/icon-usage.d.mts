import type {TakeoverInput} from './plan.mjs';
export function validateIconUsage(takeovers:TakeoverInput[],assetHashes?:Record<string,string>):{paths:string[];thoughts:string[];count:number}[];
