import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, Easing } from 'remotion';
import { BODY, useBrand } from '../brand';
import { GridBg } from './GridBg';
export type CapWord = { t: string; s: number; e: number; h?: 1 };
type Mode = 'full' | 'window';
export type { Mode };
export type BeatGraphic = React.FC<{
    beatStart: number;
    beatEnd: number;
}>;
export type ReelConfig = {
    src: string;
    grid?: {
        light?: boolean;
        strong?: boolean;
        whiteTiles?: boolean;
        accentRgb?: string;
        accentAltRgb?: string;
    };
    voiceGain?: number;
    voiceIntro?: {
        from: number;
        dur: number;
    };
    srcSize?: {
        w: number;
        h: number;
    };
    faceX: number;
    faceY: number;
    frames: number;
    words: CapWord[];
    open: {
        from: number;
        dur: number;
    };
    scenes: {
        from: number;
        mode: Mode;
        exitLeft?: boolean;
    }[];
    avatarCuts?: number[];
    swaps: {
        in: number;
        out: number;
    }[];
    beats: {
        start: number;
        end: number;
        G: BeatGraphic;
        over?: boolean;
        swipe?: boolean;
        captionTop?: number;
    }[];
    punches?: {
        at: number;
        amt?: number;
    }[];
    avatarMotion?: number;
};
type Rect = {
    x: number;
    y: number;
    w: number;
    h: number;
    r: number;
};
const FULL: Rect = { x: 0, y: 0, w: 1080, h: 1920, r: 0 };
export const LOWER_THIRD_GLASS_RECT = { x: 70, y: 1185, w: 940, h: 605, r: 46 } as const;
const WINDOW: Rect = LOWER_THIRD_GLASS_RECT;
const FULLPANEL: Rect = { x: 26, y: 26, w: 1028, h: 1868, r: 42 };
const SWAP4 = 0.5;
const TRANS = 0.5;
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const lerp = (a: number, b: number, e: number) => a + (b - a) * e;
const rectOf = (m: Mode) => (m === 'full' ? FULL : WINDOW);
const scene = (t: number, cfg: ReelConfig) => {
    const S = cfg.scenes;
    let i = 0;
    for (let k = 0; k < S.length; k++)
        if (t >= S[k].from)
            i = k;
    const cur = S[i], prev = i > 0 ? S[i - 1] : cur;
    const src = rectOf(prev.mode), tgt = rectOf(cur.mode);
    const e = easeInOut(clamp01((t - cur.from) / TRANS));
    const rect: Rect = { x: lerp(src.x, tgt.x, e), y: lerp(src.y, tgt.y, e), w: lerp(src.w, tgt.w, e), h: lerp(src.h, tgt.h, e), r: lerp(src.r, tgt.r, e) };
    const exiting = !!prev.exitLeft && i > 0 && t < cur.from + SWAP4;
    const avatarRect: Rect = exiting ? { ...WINDOW } : rect;
    const avatarOffsetX = exiting ? lerp(0, -1300, easeInOut(clamp01((t - cur.from) / SWAP4))) : 0;
    const nextFrom = i + 1 < S.length ? S[i + 1].from : Infinity;
    let push = 1;
    if (i === 0)
        push = interpolate(t, [0, cfg.open.dur], [cfg.open.from, 1.0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
    else if (cur.mode === 'full')
        push = 1 + 0.05 * clamp01((t - cur.from) / Math.min(6, nextFrom - cur.from));
    if (cfg.avatarMotion) {
        const segs = ([] as (readonly [number, number])[])
            .concat((cfg.beats ?? []).filter((b) => b.swipe).map((b) => [b.start, b.end] as const))
            .sort((a, b) => a[0] - b[0]);
        let segStart = 0, inGap = true;
        for (const [s0, e0] of segs) {
            if (t < s0)
                break;
            if (t < e0) {
                inGap = false;
                break;
            }
            segStart = e0;
        }
        if (inGap && segStart > 0) {
            push = interpolate(t - segStart, [0, cfg.open.dur], [cfg.open.from, 1.0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
        }
    }
    if (cfg.punches) {
        for (const p of cfg.punches) {
            const dt = t - p.at;
            if (dt >= 0 && dt < 0.87) {
                const amt = Math.min(0.08, p.amt ?? 0.06);
                const env = dt < 0.27 ? 1 - Math.pow(1 - dt / 0.27, 3)
                    : 1 - easeInOut(clamp01((dt - 0.27) / 0.6));
                push += amt * env;
            }
        }
    }
    const glass = clamp01((1 - rect.h / 1920) / (1 - WINDOW.h / 1920));
    return { rect, push, glass, avatarRect, avatarOffsetX, avatarGlass: exiting ? 1 : glass };
};
const Avatar: React.FC<{
    src: string;
    faceX: number;
    faceY: number;
    rect: Rect;
    push: number;
    glass: number;
    offsetX?: number;
    srcW?: number;
    srcH?: number;
    voiceGain?: number;
    voiceIntro?: {
        from: number;
        dur: number;
    };
}> = ({ src, faceX, faceY, rect, push, glass, offsetX = 0, srcW = 1920, srcH = 1080, voiceGain = 1, voiceIntro }) => {
    const { fps } = useVideoConfig();
    const scale = Math.max(rect.w / srcW, rect.h / srcH);
    const dispW = srcW * scale, dispH = srcH * scale;
    const left = Math.min(0, Math.max(rect.w - dispW, rect.w / 2 - faceX * scale));
    const top = Math.min(0, Math.max(rect.h - dispH, rect.h / 2 - faceY * scale));
    const faceYpx = faceY * scale + top;
    return (<div style={{ position: 'absolute', left: rect.x, top: rect.y, width: rect.w, height: rect.h, overflow: 'hidden', borderRadius: rect.r, border: `2px solid rgba(255,255,255,${(0.16 * glass).toFixed(3)})`, boxShadow: `0 34px 90px rgba(0,0,0,${(0.55 * glass).toFixed(3)})`, transform: offsetX ? `translateX(${offsetX}px)` : undefined }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: `${rect.w / 2}px ${faceYpx}px` }}>
        <OffthreadVideo src={staticFile(src)} volume={voiceIntro
            ? (f) => voiceGain * lerp(voiceIntro.from, 1, clamp01(f / (voiceIntro.dur * fps)))
            : voiceGain} style={{ position: 'absolute', left, top, width: dispW, height: dispH }}/>
      </div>
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 2, background: `rgba(255,255,255,${(0.24 * glass).toFixed(3)})` }}/>
    </div>);
};
const MAX_WORDS = 5, CHAR_BUDGET = 22;
export const buildChunks = (words: CapWord[]): number[][] => {
    const out: number[][] = [];
    let cur: number[] = [];
    let chars = 0;
    const flush = () => { if (cur.length) {
        out.push(cur);
        cur = [];
        chars = 0;
    } };
    for (let i = 0; i < words.length; i++) {
        const wl = words[i].t.length;
        if (cur.length && (cur.length >= MAX_WORDS || chars + 1 + wl > CHAR_BUDGET))
            flush();
        cur.push(i);
        chars += (cur.length > 1 ? 1 : 0) + wl;
        if (/[.!?]$/.test(words[i].t))
            flush();
    }
    flush();
    return out;
};
const fitSize = (text: string) => Math.min(62, Math.floor(900 / Math.max(text.length * 0.6, 1)));
export const Caption: React.FC<{
    top: number;
    words: CapWord[];
    chunks: number[][];
    accent: string;
}> = ({ top, words, chunks, accent }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();
    const t = frame / fps;
    let ci = -1;
    for (let i = 0; i < chunks.length; i++)
        if (t >= words[chunks[i][0]].s - 0.12)
            ci = i;
    if (ci < 0)
        return null;
    const chunk = chunks[ci];
    const chunkEnd = words[chunk[chunk.length - 1]].e;
    const nextStart = ci + 1 < chunks.length ? words[chunks[ci + 1][0]].s : Infinity;
    if (t > chunkEnd + 0.6 && t < nextStart - 0.12)
        return null;
    const text = chunk.map((i) => words[i].t).join(' ');
    const size = fitSize(text);
    const appear = spring({ frame: frame - Math.round((words[chunk[0]].s - 0.12) * fps), fps, config: { damping: 20, stiffness: 150 }, durationInFrames: 8 });
    return (<div style={{ position: 'absolute', left: 0, right: 0, top, display: 'flex', justifyContent: 'center' }}>
      <div style={{ display: 'inline-flex', whiteSpace: 'nowrap', alignItems: 'baseline', background: 'rgba(0,0,0,0.52)', borderRadius: 16, padding: '14px 30px', opacity: interpolate(appear, [0, 1], [0, 1]), transform: `translateY(${interpolate(appear, [0, 1], [16, 0])}px)` }}>
        {chunk.map((wi, k) => {
            const w = words[wi];
            const active = t >= w.s && t <= w.e + 0.06;
            const hdt = w.h ? t - w.s : -1;
            const hScale = hdt >= 0 && hdt < 0.4 ? 1 + 0.14 * Math.sin(Math.PI * clamp01(hdt / 0.4)) : 1;
            const hOn = w.h ? hdt >= 0 : false;
            return <span key={k} style={{ fontSize: size, fontWeight: hOn ? 800 : 500, lineHeight: 1.1,
                    color: active || hOn ? accent : '#FFFFFF',
                    display: hOn ? 'inline-block' : undefined,
                    transform: hOn ? `scale(${hScale.toFixed(4)})` : undefined,
                    transformOrigin: 'center 78%',
                    marginRight: k < chunk.length - 1 ? Math.round(size * 0.28) : 0 }}>{w.t}</span>;
        })}
      </div>
    </div>);
};
const GraphicLayer: React.FC<{
    glass: number;
    beats: ReelConfig['beats'];
}> = ({ glass, beats }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();
    const t = frame / fps;
    if (glass < 0.04)
        return null;
    return (<AbsoluteFill style={{ opacity: glass }}>
      {beats.map((b, i) => {
            const G = b.G;
            if (b.swipe) {
                if (t < b.start || t >= b.end + SWAP4)
                    return null;
                const eIn = easeInOut(clamp01((t - b.start) / (SWAP4 * 0.72)));
                const eOut = easeInOut(clamp01((t - b.end) / SWAP4));
                const offsetX = t >= b.end ? lerp(0, -1300, eOut) : lerp(1300, 0, eIn);
                return <AbsoluteFill key={i} style={{ transform: `translateX(${offsetX}px)` }}><G beatStart={b.start} beatEnd={b.end}/></AbsoluteFill>;
            }
            const fade = interpolate(t, [b.start - 0.05, b.start + 0.28, b.end - 0.05, b.end + 0.32], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            if (fade <= 0.001)
                return null;
            return <AbsoluteFill key={i} style={{ opacity: fade }}><G beatStart={b.start} beatEnd={b.end}/></AbsoluteFill>;
        })}
    </AbsoluteFill>);
};
export const Reel: React.FC<{
    config: ReelConfig;
}> = ({ config }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();
    const t = frame / fps;
    const { rect, push, glass, avatarRect, avatarOffsetX, avatarGlass } = scene(t, config);
    const defaultCapTop = interpolate(glass, [0, 1], [1230, 905]);
    const captionBeat = config.beats.find((b) => t >= b.start && t < b.end);
    const capTop = captionBeat?.captionTop ?? defaultCapTop;
    const chunks = React.useMemo(() => buildChunks(config.words), [config.words]);
    const brand = useBrand();
    const accent = brand.theme.accentOnDark;
    const mswaps = React.useMemo(() => {
        const out: {
            in: number;
            out: number;
            cuts: number[];
        }[] = [];
        for (const s of config.swaps) {
            const last = out[out.length - 1];
            if (last && s.in <= last.out + SWAP4 + 1e-6) {
                last.cuts.push(last.out);
                last.out = s.out;
            }
            else
                out.push({ in: s.in, out: s.out, cuts: [] });
        }
        return out;
    }, [config.swaps]);
    const sw = mswaps.find((s) => t >= s.in && t < s.out + SWAP4);
    let avatar: React.ReactNode;
    const cutAt = sw?.cuts.find((c) => t >= c && t < c + SWAP4);
    const avatarCutAt = config.avatarCuts?.find((c) => t >= c && t < c + SWAP4);
    if (sw && cutAt !== undefined) {
        const eOld = easeInOut(clamp01((t - cutAt) / SWAP4));
        const eNew = easeInOut(clamp01((t - cutAt) / (SWAP4 * 0.72)));
        avatar = (<>
        <Avatar src={config.src} srcW={config.srcSize?.w} srcH={config.srcSize?.h} faceX={config.faceX} faceY={config.faceY} rect={FULLPANEL} push={1} glass={0.55} offsetX={lerp(0, -1300, eOld)} voiceGain={config.voiceGain} voiceIntro={config.voiceIntro}/>
        <Avatar src={config.src} srcW={config.srcSize?.w} srcH={config.srcSize?.h} faceX={config.faceX} faceY={config.faceY} rect={FULLPANEL} push={1} glass={0.55} offsetX={lerp(1300, 0, eNew)} voiceGain={config.voiceGain} voiceIntro={config.voiceIntro}/>
      </>);
    }
    else if (sw) {
        const eIn = easeInOut(clamp01((t - sw.in) / SWAP4));
        const eInFull = easeInOut(clamp01((t - sw.in) / (SWAP4 * 0.72)));
        const pOut = clamp01((t - sw.out) / SWAP4);
        const eOut = easeInOut(pOut);
        const eOutWin = easeInOut(clamp01((t - sw.out) / (SWAP4 * 0.72)));
        const winOff = pOut > 0 ? lerp(1300, 0, eOutWin) : lerp(0, -1300, eIn);
        const fullOff = pOut > 0 ? lerp(0, -1300, eOut) : lerp(1300, 0, eInFull);
        avatar = (<>
        <Avatar src={config.src} srcW={config.srcSize?.w} srcH={config.srcSize?.h} faceX={config.faceX} faceY={config.faceY} rect={WINDOW} push={1} glass={1} offsetX={winOff} voiceGain={config.voiceGain} voiceIntro={config.voiceIntro}/>
        <Avatar src={config.src} srcW={config.srcSize?.w} srcH={config.srcSize?.h} faceX={config.faceX} faceY={config.faceY} rect={FULLPANEL} push={1} glass={0.55} offsetX={fullOff} voiceGain={config.voiceGain} voiceIntro={config.voiceIntro}/>
      </>);
    }
    else if (avatarCutAt !== undefined) {
        const eOld = easeInOut(clamp01((t - avatarCutAt) / SWAP4));
        const eNew = easeInOut(clamp01((t - avatarCutAt) / (SWAP4 * 0.72)));
        avatar = (<>
        <Avatar src={config.src} srcW={config.srcSize?.w} srcH={config.srcSize?.h} faceX={config.faceX} faceY={config.faceY} rect={avatarRect} push={push} glass={avatarGlass} offsetX={lerp(0, -1300, eOld)} voiceGain={config.voiceGain} voiceIntro={config.voiceIntro}/>
        <Avatar src={config.src} srcW={config.srcSize?.w} srcH={config.srcSize?.h} faceX={config.faceX} faceY={config.faceY} rect={avatarRect} push={push} glass={avatarGlass} offsetX={lerp(1300, 0, eNew)} voiceGain={0} voiceIntro={config.voiceIntro}/>
      </>);
    }
    else {
        avatar = <Avatar src={config.src} srcW={config.srcSize?.w} srcH={config.srcSize?.h} faceX={config.faceX} faceY={config.faceY} rect={avatarRect} push={push} glass={avatarGlass} offsetX={avatarOffsetX} voiceGain={config.voiceGain} voiceIntro={config.voiceIntro}/>;
    }
    const underBeats = config.beats.filter((b) => !b.over);
    const overBeats = config.beats.filter((b) => b.over);
    return (<AbsoluteFill style={{ backgroundColor: brand.theme.ink, fontFamily: BODY }}>
      <GridBg/>
      <GraphicLayer glass={glass} beats={underBeats}/>
      {avatar}
      
      {overBeats.length > 0 && <GraphicLayer glass={1} beats={overBeats}/>}
      <Caption top={capTop} words={config.words} chunks={chunks} accent={accent}/>
    </AbsoluteFill>);
};
