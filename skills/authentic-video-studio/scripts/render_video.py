#!/usr/bin/env python3
"""Render one raw talking-head clip into a finished 9:16 video with a template style and a brand.

  python render_video.py --input raw.mp4 --out final.mp4 --style list-the-ways --brand brand \\
      [--hook-text "7 WAYS TO\\nEDIT FASTER"] [--keyword GUIDE] [--words-json corrected.json] \\
      [--start 0 --max-seconds 30] [--set zoom.max=1.1] [--workdir DIR]

Pipeline: transcribe (faster-whisper, local) -> remove fillers and long pauses -> jump cuts and zoom ->
captions, hook text, logo, end card -> loudness normalise -> verify. Nothing is uploaded.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vs_common as C  # noqa: E402
import vs_remotion as R  # noqa: E402


# ---------------------------------------------------------------- transcription and cleanup
def transcribe(wav: Path, model_name: str, language: str | None) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper is not installed. Run the installer, or: python scripts/vs.py doctor --fix")
    m = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(wav), word_timestamps=True, vad_filter=False, language=language,
                           condition_on_previous_text=False)
    words: list[dict] = []
    for s in segs:
        for w in s.words or []:
            t = w.word.strip()
            if not t:
                continue
            if words and re.match(r"^['\u2019]", t):  # contraction piece: 's 't 're
                words[-1]["w"] += t
                words[-1]["e"] = float(w.end)
                continue
            words.append({"w": t, "s": float(w.start), "e": float(w.end)})
    return words


def clean_words(words: list[dict], cl: dict) -> tuple[list[dict], int]:
    fill = {x.lower() for x in cl["remove_fillers"]}
    out, removed = [], 0
    for w in words:
        core = re.sub(r"[^a-z']", "", w["w"].lower())
        if core in fill:
            removed += 1
            out.append({**w, "_drop": True})
            continue
        if out and not out[-1].get("_drop") and cl.get("remove_immediate_repeats"):
            prev = re.sub(r"[^a-z0-9']", "", out[-1]["w"].lower())
            cur = re.sub(r"[^a-z0-9']", "", w["w"].lower())
            if prev and prev == cur and w["s"] - out[-1]["e"] < 0.5:
                removed += 1
                out.append({**w, "_drop": True})
                continue
        out.append(w)
    return out, removed


def build_spans(words: list[dict], cl: dict, clip_dur: float) -> list[dict]:
    spans, cur, dropped = [], None, False
    for w in words:
        if w.get("_drop"):
            dropped = True
            continue
        if cur is None:
            cur = {"s": w["s"], "e": w["e"], "words": [w]}
        else:
            gap = w["s"] - cur["e"]
            if gap > cl["max_gap_keep_s"] or dropped:
                spans.append(cur)
                cur = {"s": w["s"], "e": w["e"], "words": [w]}
            else:
                cur["e"] = w["e"]
                cur["words"].append(w)
        dropped = False
    if cur:
        spans.append(cur)
    prev_end = 0.0
    for i, sp in enumerate(spans):
        lead = cl["first_word_lead_s"] if i == 0 else cl["pad_lead_s"]
        tail = cl["end_tail_s"] if i == len(spans) - 1 else cl["pad_tail_s"]
        sp["a"] = max(prev_end, sp["s"] - lead, 0.0)
        sp["b"] = min(sp["e"] + tail, clip_dur)
        if i + 1 < len(spans):
            sp["b"] = min(sp["b"], max(sp["a"] + 0.05, (sp["e"] + spans[i + 1]["s"]) / 2))
        prev_end = sp["b"]
    return spans


def choose_cuts(out_words: list[dict], joins: list[float], total: float, cu: dict) -> list[float]:
    if not cu.get("enabled", True):
        return []
    cand = {round(j, 3) for j in joins}
    for w in out_words:
        if re.search(r"[.?!]$", w["w"]):
            cand.add(round(w["oe"] + 0.05, 3))
    cand = sorted(cand)
    boundaries = sorted({round(w["os"] - 0.02, 3) for w in out_words[1:]})
    cuts, last, first = [], 0.0, True
    while True:
        mn = cu["hook_shot_min_s"] if first else cu["shot_min_s"]
        tg = max(mn, min(cu["shot_target_s"], 4.5)) if first else max(mn, cu["shot_target_s"])
        lo, hi = last + mn, last + cu["shot_max_s"]
        if total - last < mn + cu["shot_min_s"]:
            break
        limit = total - cu["shot_min_s"]
        pool = [c for c in cand if lo <= c <= hi and c <= limit] or [c for c in boundaries if lo <= c <= hi and c <= limit]
        if not pool:
            break
        pick = min(pool, key=lambda c: abs((c - last) - tg))
        cuts.append(pick)
        last, first = pick, False
    return cuts


# ---------------------------------------------------------------- captions
def _case(txt: str, mode: str) -> str:
    return txt.upper() if mode == "upper" else txt.lower() if mode == "lower" else txt


def ts_ass(x: float) -> str:
    h = int(x // 3600); m = int((x % 3600) // 60); s = x % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ts_srt(x: float) -> str:
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def make_chunks(out_words: list[dict], cap: dict, font_path, max_px: float) -> list[list[dict]]:
    mode = cap["mode"]
    n = 1 if mode == "word" else int(cap.get("words_per_chunk") if mode == "chunk" else cap.get("max_words", 4))
    chunks, cur = [], []
    for i, w in enumerate(out_words):
        if cur:
            gap = w["os"] - cur[-1]["oe"]
            trial = " ".join(x["t"] for x in cur + [w])
            too_wide = font_path and C.text_width(font_path, cap["size_px"], trial) > max_px
            if len(cur) >= n or gap > 0.6 or too_wide or re.search(r"[.?!]$", cur[-1]["w"]):
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def write_captions(out_words: list[dict], style: dict, brand: dict, fontname: str, font_path, ass_path: Path,
                   srt_path: Path | None) -> int:
    cap = style["captions"]
    W, H = style["format"]["width"], style["format"]["height"]
    case = cap["case"] if cap["case"] != "as_spoken" else brand["captions"].get("case", "as_spoken")
    strip_chars = cap.get("strip_chars", "")
    for w in out_words:
        t = re.sub(f"[{re.escape(strip_chars)}]", " ", w["w"]).strip() if strip_chars else w["w"]
        w["t"] = _case(t.replace("\\", ""), case)
    out_words = [w for w in out_words if w["t"]]
    fill = C.ass_color(cap["fill"])
    stroke_hex = brand["captions"].get("stroke_color") or cap["stroke_color"]
    if cap["stroke_color"] != "#020617":
        stroke_hex = cap["stroke_color"]
    strip = cap.get("strip", {})
    size = cap["size_px"]
    if strip.get("enabled"):
        alpha = int(round((1 - float(strip["opacity"])) * 255))
        border_style, outline, outline_col, shadow = 3, strip["padding_px"], C.ass_color(strip["color"], alpha), 0
    else:
        border_style, outline, outline_col, shadow = 1, cap["stroke_px"], C.ass_color(stroke_hex), cap["shadow_px"]
    back = C.ass_color(stroke_hex, 0x60)
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
             "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
             "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
             f"Style: Cap,{fontname},{size},{fill},{fill},{outline_col},{back},0,0,0,0,100,100,0,0,{border_style},{outline},{shadow},5,60,60,0,1",
             "", "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"]
    xcap, ycap = int(W * cap["x_frac"]), int(H * cap["y_frac"])
    max_px = W * cap["max_width_frac"]
    emph = cap.get("emphasis", {})
    extra = {x.lower() for x in emph.get("extra_words", [])}
    emph_col = C.ass_color(emph.get("color", cap["highlight_color"]))
    hi_col = C.ass_color(cap["highlight_color"])
    pop = cap.get("pop", {})
    chunks = make_chunks(out_words, cap, font_path, max_px)
    events: list[tuple[float, float, str]] = []
    srt_items: list[tuple[float, float, str]] = []
    for ci, ch in enumerate(chunks):
        next_start = chunks[ci + 1][0]["os"] if ci + 1 < len(chunks) else None
        chunk_end = ch[-1]["oe"]
        if cap["mode"] == "word":
            w = ch[0]
            start = w["os"]
            end = min(start + cap["max_hold_s"], next_start if next_start is not None else start + cap["max_hold_s"])
            if end - start < 0.10:
                end = start + 0.10
            tag = ""
            if font_path:
                wpx = C.text_width(font_path, size, w["t"])
                if wpx > max_px:
                    tag += f"\\fs{max(24, int(size * max_px / wpx))}"
            if pop.get("enabled"):
                f0 = pop["from_scale_pct"]
                tag += f"\\fscx{f0}\\fscy{f0}\\t(0,{pop['ms']},\\fscx100\\fscy100)"
            bare = re.sub(r"[^a-z]", "", w["t"].lower())
            if (emph.get("numerals") and re.search(r"\d", w["t"])) or bare in extra:
                tag += f"\\c{emph_col}"
            events.append((start, end, f"{{\\an5\\pos({xcap},{ycap}){tag}}}{w['t']}"))
            srt_items.append((start, end, w["t"]))
        elif cap["mode"] == "chunk":
            start = ch[0]["os"]
            end = min(chunk_end + 0.25, next_start if next_start is not None else chunk_end + 0.4)
            end = max(end, start + 0.15)
            txt = " ".join(x["t"] for x in ch)
            events.append((start, end, f"{{\\an5\\pos({xcap},{ycap})}}{txt}"))
            srt_items.append((start, end, txt))
        else:  # karaoke
            for wi, w in enumerate(ch):
                start = w["os"]
                if wi + 1 < len(ch):
                    end = ch[wi + 1]["os"]
                else:
                    end = min(w["oe"] + 0.3, next_start if next_start is not None else w["oe"] + 0.4)
                end = max(end, start + 0.08)
                parts = []
                for wj, x in enumerate(ch):
                    parts.append(f"{{\\c{hi_col}}}{x['t']}{{\\c{fill}}}" if wj == wi else x["t"])
                events.append((start, end, f"{{\\an5\\pos({xcap},{ycap})}}" + " ".join(parts)))
            srt_items.append((ch[0]["os"], min(chunk_end + 0.25, next_start if next_start is not None else chunk_end + 0.4),
                              " ".join(x["t"] for x in ch)))
    for s, e, t in events:
        lines.append(f"Dialogue: 0,{ts_ass(s)},{ts_ass(e)},Cap,,0,0,0,,{t}")
    ass_path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    if srt_path:
        srt_path.write_text("".join(f"{i}\n{ts_srt(s)} --> {ts_srt(e)}\n{t}\n\n" for i, (s, e, t) in enumerate(srt_items, 1)),
                            encoding="utf-8")
    return len(events)


# ---------------------------------------------------------------- layout assets
def make_window_assets(style: dict, brand: dict, work: Path) -> dict:
    from PIL import Image, ImageDraw
    W, H = style["format"]["width"], style["format"]["height"]
    win = style["layout"]["window"]
    bgc = style["layout"]["background"]
    r = int(win.get("r", 46))
    mask = Image.new("L", (win["w"], win["h"]), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, win["w"] - 1, win["h"] - 1], r, fill=255)
    mask.save(work / "mask.png")
    Image.new("RGB", (W, H), bgc["color"]).save(work / "bg.png")
    gs = int(bgc["grid_size"])
    grid = Image.new("RGBA", (W + gs, H + gs), (0, 0, 0, 0))
    d = ImageDraw.Draw(grid)
    col = C.hex_rgb(bgc["grid_color"])
    a = int(255 * float(bgc["grid_opacity"]))
    pad = max(6, gs // 14)
    for x in range(0, W + gs, gs):
        for y in range(0, H + gs, gs):
            d.rounded_rectangle([x + pad, y + pad, x + gs - pad, y + gs - pad], gs // 6, fill=col + (a,))
    grid.save(work / "grid.png")
    return {"gs": gs}


# ---------------------------------------------------------------- Remotion styles
def render_remotion(a, style, brand, work, out, stage1, af, out_words, total, rw, rh, fps, nrem, spans, clip_dur, method, meas) -> int:
    """spotlight / minimalist: FFmpeg makes the clean cut and the audio, Remotion draws the picture, FFmpeg muxes."""
    ffmpeg = C.find_tool("ffmpeg")
    dur = C.probe_video(stage1)["duration"]
    frames = max(1, int(round(dur * fps)))
    pub = R.stage_public(work, stage1)
    hook_lines = None
    if a.hook_text:
        hook_lines = [x.strip() for x in a.hook_text.replace("\\n", "\n").split("\n") if x.strip()][: style["hook_text"]["max_lines"]]
    keyword = (a.keyword or brand["cta"].get("keyword") or "").upper()
    end_text = None
    if a.keyword or a.end_card or brand["cta"].get("keyword"):
        E = style["end_card"]
        if "{KEYWORD}" in E["text_template"] and keyword:
            end_text = E["text_template"].replace("{KEYWORD}", keyword)
        else:
            end_text = brand["cta"]["end_card"].format(keyword=keyword, text=brand["cta"]["text"]) if keyword else brand["cta"]["text"]
    hook_s = min(style["hook_text"]["max_s"], dur)
    end_s = style["end_card"]["last_s"]
    props_brand = R.build_brand_props(brand, pub, hook_lines, hook_s, end_text, end_s, show_logo=not a.no_logo and style["logo"].get("enabled", True))
    comp = style["composition"]
    print(f"[3/5] planning '{a.style}' from the cleaned transcript...", flush=True)
    notes = {}
    if comp == "Spotlight":
        face_y = a.face_y if a.face_y is not None else style.get("spotlight", {}).get("face_y_frac", 0.36)
        case = style["captions"]["case"] if style["captions"]["case"] != "as_spoken" else brand["captions"].get("case", "as_spoken")
        extra = {x.lower() for x in style["captions"].get("emphasis", {}).get("extra_words", [])}
        job = R.plan_spotlight(out_words, dur, case, extra)
        job.update({"src": "host/cut.mp4", "frames": frames, "sourceSize": {"w": rw, "h": rh}, "faceX": rw / 2, "faceY": rh * face_y,
                    "captionTop": {"full": 1230, "window": 905, "panel": 905}})
        props = {"brand": props_brand, "job": job}
        notes = {"scenes": len(job["scenes"]), "large_panels": len(job["swaps"]), "key_phrase_cards": len(job["beats"]),
                 "caption_words": len(job["words"])}
    else:
        plan = R.plan_minimalist(out_words, frames, hook_s if hook_lines else 0.0, end_s if end_text else 0.0, props_brand["theme"]["widthFactor"])
        plan["source"] = {"src": "host/cut.mp4", "durationInFrames": frames}
        plan.pop("fontWidthFactor", None)
        check = R.validate_minimalist(plan, work)
        # drop a takeover that fails layout rather than failing the render
        guard = 0
        while not check["valid"] and plan["takeovers"] and guard < 12:
            guard += 1
            print(f"  planner: {check['errors'][0]}", flush=True)
            msg = check["errors"][0]
            bad = next((t for t in plan["takeovers"] if msg.startswith(t["id"] + ":")), plan["takeovers"][-1])
            plan["takeovers"].remove(bad)
            check = R.validate_minimalist(plan, work)
        if not check["valid"]:
            sys.exit("Minimalist plan is invalid: " + "; ".join(check["errors"]))
        for w in check.get("warnings", []):
            print(f"  planner warning: {w}", flush=True)
        props = {"brand": props_brand, "plan": plan}
        notes = {"takeovers": len(plan["takeovers"]), "icons": [t["icon"] for t in plan["takeovers"]], "planner_warnings": check.get("warnings", [])}
        if not plan["takeovers"]:
            print("WARNING: the clip has no sentence that fits a takeover (needs 3+ seconds of speaker before each). Output is the plain speaker.", file=sys.stderr)
    picture = work / "picture.mp4"
    print(f"[4/5] rendering {comp} with Remotion ({frames} frames)...", flush=True)
    R.render_picture(comp, props, pub, picture, work)
    C.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-i", picture, "-i", stage1, "-map", "0:v:0", "-map", "1:a:0", "-af", af,
           "-vf", "scale=out_range=tv,format=yuv420p", "-c:v", "libx264", "-crf", style["format"]["crf"], "-preset", "medium", "-pix_fmt", "yuv420p", "-r", fps,
           "-c:a", "aac", "-b:a", style["format"]["audio_bitrate"], "-movflags", "+faststart", "-t", f"{dur:.3f}", out])
    stills = []
    if not a.no_stills:
        sd = out.parent / (out.stem + "_stills")
        sd.mkdir(exist_ok=True)
        for frac in (0.08, 0.5, 0.92):
            p = sd / f"{out.stem}_{int(frac * 100):02d}.jpg"
            C.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-ss", f"{dur * frac:.2f}", "-i", out, "-frames:v", "1", "-q:v", "3", p], check=False)
            if p.exists():
                stills.append(str(p))
    report = {"style": a.style, "engine": "remotion", "brand": brand["name"], "input": str(a.input), "output": str(out), "transcribe": method,
              "input_clip_s": round(clip_dur, 2), "output_s": round(dur, 2), "spans": len(spans), "fillers_or_repeats_removed": nrem,
              "silence_removed_s": round(clip_dur - dur, 2), "words_out": len(out_words), "hook_text": bool(hook_lines),
              "end_card_keyword": keyword or None, "stills": stills, **notes}
    (work / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("[5/5] done.", flush=True)
    print(json.dumps(report, indent=2))
    return 0


# ---------------------------------------------------------------- main render
def main(argv=None) -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--style", default="list-the-ways", help=f"one of: {', '.join(C.list_styles())} or a path to a style .json")
    ap.add_argument("--brand", default=None, help="folder with brand.yaml (default ./brand if present, else neutral defaults)")
    ap.add_argument("--workdir")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--max-seconds", type=float)
    ap.add_argument("--hook-text")
    ap.add_argument("--keyword")
    ap.add_argument("--end-card", action="store_true", help="show the brand CTA in the last seconds even without a keyword")
    ap.add_argument("--face-x", type=float, default=0.5, help="0..1 horizontal face position for landscape input")
    ap.add_argument("--face-y", type=float, default=None, help="0..1 vertical face position (spotlight style); default from the style")
    ap.add_argument("--words-json", help="corrected word list [{w,s,e}] on the input timeline (after --start)")
    ap.add_argument("--model", default="small.en", help="faster-whisper model (tiny.en, base.en, small.en, medium, large-v3)")
    ap.add_argument("--language", default="en")
    ap.add_argument("--no-logo", action="store_true")
    ap.add_argument("--no-stills", action="store_true")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a style value, e.g. zoom.max=1.1")
    a = ap.parse_args(argv)

    ffmpeg = C.need_tool("ffmpeg")
    brand = C.load_brand(a.brand)
    style = C.load_style(a.style, brand, a.set)
    remotion_style = style.get("engine") == "remotion"
    if remotion_style:
        ok, why = R.available()
        if not ok:
            sys.exit(f"Style '{a.style}' needs Node and Remotion, which are not ready: {why}\n"
                     "Fix: python scripts/vs.py setup-remotion --install-node   (or rerun the installer)\n"
                     "No-Node alternative with a similar look: --style spotlight-lite")
    src = Path(a.input).resolve()
    if not src.is_file():
        sys.exit(f"Input not found: {src}")
    out = Path(a.out).resolve()
    work = Path(a.workdir).resolve() if a.workdir else out.parent / (out.stem + "_work")
    work.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    fonts = work / "fonts"
    fonts.mkdir(exist_ok=True)

    F = style["format"]
    W, H, FPS = F["width"], F["height"], F["fps"]
    info = C.probe_video(src)
    clip_dur = info["duration"] - a.start
    if a.max_seconds:
        clip_dur = min(clip_dur, a.max_seconds)
    if not info["has_audio"]:
        sys.exit("The input has no audio track, so there is nothing to transcribe or caption.")

    # fonts -> workdir (short relative names; avoids Windows drive-letter escaping in filters)
    hp = brand["fonts"]["heading"].get("_path")
    bp = brand["fonts"]["body"].get("_path")
    role = style["captions"]["font_role"]
    cap_font_path = Path(hp if role == "heading" else bp or hp) if (hp or bp) else None
    for nm, p in (("heading.ttf", hp), ("body.ttf", bp or hp)):
        if p and Path(p).exists():
            (fonts / nm).write_bytes(Path(p).read_bytes())
    fontname = C.font_info(cap_font_path)["family"] if cap_font_path else "Arial"
    draw_font = "fonts/heading.ttf" if (fonts / "heading.ttf").exists() else None
    if not draw_font:
        print("WARNING: no font file found for hook text; run the branding onboarding to fetch fonts.", file=sys.stderr)

    # 1. words
    if a.words_json:
        words = json.loads(Path(a.words_json).read_text(encoding="utf-8"))
        method = "words-json"
    else:
        key = f"{src.stat().st_size}-{int(src.stat().st_mtime)}-{a.start}-{a.max_seconds}-{a.model}-{a.language}"
        cache = work / "words_raw.json"
        words = None
        if cache.exists():
            try:
                blob = json.loads(cache.read_text(encoding="utf-8"))
                if isinstance(blob, dict) and blob.get("key") == key:
                    words = blob["words"]
            except Exception:
                pass
        if words is None:
            wav = work / "audio16k.wav"
            C.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-ss", a.start, "-t", clip_dur, "-i", src, "-vn",
                   "-ac", "1", "-ar", "16000", wav])
            print(f"[1/5] transcribing with faster-whisper {a.model} (first run downloads the model)...", flush=True)
            words = transcribe(wav, a.model, None if a.language == "auto" else a.language)
            cache.write_text(json.dumps({"key": key, "words": words}, indent=1), encoding="utf-8")
        method = f"faster-whisper {a.model}"
    words, nrem = clean_words(words, style["cleanup"])
    spans = build_spans(words, style["cleanup"], clip_dur)
    if not spans:
        sys.exit("No speech found in the clip.")

    # 2. timeline
    t0, out_words, joins = 0.0, [], []
    for i, sp in enumerate(spans):
        if i > 0:
            joins.append(t0)
        for w in sp["words"]:
            out_words.append({"w": w["w"], "os": t0 + (w["s"] - sp["a"]), "oe": t0 + (w["e"] - sp["a"])})
        t0 += sp["b"] - sp["a"]
    total = t0
    cuts = choose_cuts(out_words, joins, total, style["cuts"])
    Z = style["zoom"]
    bounds = [0.0] + cuts + [total]
    shots = []
    for k in range(len(bounds) - 1):
        a0, b0 = bounds[k], bounds[k + 1]
        L = b0 - a0
        shots.append({"a": round(a0, 3), "b": round(b0, 3), "len": round(L, 3),
                      "ramp_start": round(a0 + max(0.4, L - Z["ramp_s"]), 3)})

    # 3. stage 1: cut, concat, reframe
    win_mode = style["layout"]["mode"] == "window"
    rw, rh = (style["layout"]["window"]["w"], style["layout"]["window"]["h"]) if win_mode else (W, H)
    vparts, aparts = [], []
    fade = style["cleanup"]["crossfade_ms"] / 1000.0
    for i, sp in enumerate(spans):
        d = sp["b"] - sp["a"]
        vparts.append(f"[0:v]trim=start={sp['a']:.3f}:end={sp['b']:.3f},setpts=PTS-STARTPTS[v{i}]")
        aparts.append(f"[0:a]atrim=start={sp['a']:.3f}:end={sp['b']:.3f},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d={fade},afade=t=out:st={max(0, d - fade):.3f}:d={fade}[a{i}]")
    n = len(spans)
    concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
    if info["w"] / info["h"] >= rw / rh:
        fx = min(max(a.face_x, 0.0), 1.0)
        reframe = f"scale=-2:{rh},crop={rw}:{rh}:'min(max(iw*{fx}-{rw}/2,0),iw-{rw})':0"
    else:
        reframe = f"scale={rw}:{rh}:force_original_aspect_ratio=increase,crop={rw}:{rh}"
    fc = ";".join(vparts + aparts) + f";{concat_in}concat=n={n}:v=1:a=1[cv][ca];[cv]{reframe},fps={FPS},format=yuv420p[vout]"
    (work / "stage1.filter").write_text(fc, encoding="utf-8")
    stage1 = work / "stage1.mkv"
    print(f"[2/5] cutting {n} spans, {len(cuts) + 1} shots ({nrem} fillers/repeats removed)...", flush=True)
    C.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-ss", a.start, "-t", clip_dur, "-i", src,
           "-filter_complex_script", work / "stage1.filter", "-map", "[vout]", "-map", "[ca]", "-c:v", "libx264", "-crf", "12",
           "-preset", "veryfast", "-c:a", "pcm_s16le", "-ar", "48000", stage1])

    # 4. loudness measure
    A = style["audio"]
    af_pre = f"highpass=f={A['highpass_hz']}"
    r = C.run([ffmpeg, "-nostdin", "-hide_banner", "-i", stage1, "-af",
               f"{af_pre},loudnorm=I={A['target_lufs']}:TP={A['true_peak_db']}:LRA={A['lra']}:print_format=json", "-f", "null", "-"],
              capture=True, check=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    meas = json.loads(m.group(0)) if m else None
    if meas:
        ln = (f"loudnorm=I={A['target_lufs']}:TP={A['true_peak_db']}:LRA={A['lra']}:measured_I={meas['input_i']}:"
              f"measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:"
              f"offset={meas['target_offset']}:linear=true")
    else:
        ln = f"loudnorm=I={A['target_lufs']}:TP={A['true_peak_db']}:LRA={A['lra']}"
    limit = 10 ** ((A["true_peak_db"] - 0.8) / 20)
    af = f"{af_pre},{ln},alimiter=limit={limit:.3f}:attack=3:release=40:level=0,aresample={A['sample_rate']}"

    if remotion_style:
        return render_remotion(a, style, brand, work, out, stage1, af, out_words, total, rw, rh, FPS, nrem, spans, clip_dur, method, meas)

    # 5. captions, overlays, layout
    ass = work / "captions.ass"
    srt = out.with_suffix(".srt") if style.get("srt") else None
    ncap = write_captions(out_words, style, brand, fontname, cap_font_path, ass, srt)
    mode = Z["mode"]
    if mode == "ramp":
        terms = "+".join(f"between(t,{s['a']:.3f},{s['b'] - 0.0001:.4f})*clip((t-{s['ramp_start']:.3f})/{Z['ramp_s']},0,1)" for s in shots)
        zexpr = f"(1+{Z['max'] - Z['base']:.3f}*({terms}))"
    elif mode == "alternate":
        terms = "+".join(f"between(t,{s['a']:.3f},{s['b'] - 0.0001:.4f})" for k, s in enumerate(shots) if k % 2 == 1) or "0"
        zexpr = f"(1+{Z['max'] - Z['base']:.3f}*({terms}))"
    elif mode == "open":
        zexpr = f"(1+{Z['open_from'] - 1:.3f}*pow(max(0,1-t/{Z['open_s']}),2))"
    else:
        zexpr = "1"
    inputs: list = []
    graph: list[str] = []
    zoomf = (f"scale=w='trunc({rw}*{zexpr}/2)*2':h=-2:eval=frame:flags=bicubic,crop={rw}:{rh}" if zexpr != "1" else "null")
    cur = "v0"
    if win_mode:
        assets = make_window_assets(style, brand, work)
        win = style["layout"]["window"]
        inputs += ["-framerate", FPS, "-loop", "1", "-i", work / "bg.png", "-framerate", FPS, "-loop", "1", "-i", work / "grid.png",
                   "-loop", "1", "-i", work / "mask.png"]
        graph.append(f"[0:v]{zoomf},format=rgba[vid]")
        graph.append("[3:v]format=gray[m]")
        graph.append("[vid][m]alphamerge[vr]")
        graph.append(f"[1:v][2:v]overlay=x='-mod(t*24,{assets['gs']})':y='-mod(t*10,{assets['gs']})'[bgm]")
        graph.append(f"[bgm][vr]overlay={win['x']}:{win['y']}:format=auto,format=yuv420p[{cur}]")
        nxt_idx = 4
    else:
        graph.append(f"[0:v]{zoomf}[{cur}]")
        nxt_idx = 1
    lg = brand.get("logo", {})
    if style["logo"].get("enabled") and not a.no_logo and lg.get("show_in_videos") and lg.get("_path"):
        scale = float(lg.get("scale") or 0.16)
        pos = lg.get("position", "top-right")
        mar, top = style["logo"]["margin_px"], style["logo"]["top_px"]
        x = f"W-w-{mar}" if "right" in pos else str(mar)
        y = str(top) if "top" in pos else f"H-h-{top}"
        inputs += ["-loop", "1", "-i", lg["_path"]]
        graph.append(f"[{nxt_idx}:v]scale={int(W * scale)}:-1,format=rgba,colorchannelmixer=aa={style['logo']['opacity']}[lgo]")
        graph.append(f"[{cur}][lgo]overlay={x}:{y}:format=auto[v1]")
        cur = "v1"
    chain = []
    if a.hook_text and draw_font:
        Hk = style["hook_text"]
        lines_ = [x.strip() for x in a.hook_text.replace("\\n", "\n").split("\n") if x.strip()][:Hk["max_lines"]]
        step = int(Hk["font_size_px"] * 1.55)
        for li, line in enumerate(lines_):
            if len(line) > Hk["max_chars_per_line"]:
                print(f"WARNING: hook line '{line}' is {len(line)} chars; over {Hk['max_chars_per_line']} it may run past the frame edge.", file=sys.stderr)
            (work / f"hook{li}.txt").write_bytes(line.encode("utf-8"))
            chain.append(f"drawtext=fontfile={draw_font}:textfile=hook{li}.txt:fontsize={Hk['font_size_px']}:fontcolor={Hk['fill']}:"
                         f"box=1:boxcolor=0x{Hk['box_color'].lstrip('#')}@{Hk['box_opacity']}:boxborderw=22:"
                         f"x=(w-text_w)/2:y=h*{Hk['y_frac']}+{li * step}:enable='between(t,0,{min(Hk['max_s'], total):.2f})'")
    keyword = (a.keyword or brand["cta"].get("keyword") or "").upper()
    if (a.keyword or a.end_card or brand["cta"].get("keyword")) and draw_font:
        E = style["end_card"]
        tpl = E["text_template"]
        if "{KEYWORD}" in tpl and keyword:
            text = tpl.replace("{KEYWORD}", keyword)
        else:
            text = brand["cta"]["end_card"].format(keyword=keyword, text=brand["cta"]["text"]) if keyword else brand["cta"]["text"]
        (work / "endcard.txt").write_bytes(text.encode("utf-8"))
        chain.append(f"drawtext=fontfile={draw_font}:textfile=endcard.txt:fontsize={E['font_size_px']}:fontcolor={E['fill']}:"
                     f"box=1:boxcolor=0x{E['box_color'].lstrip('#')}@{E['box_opacity']}:boxborderw=26:"
                     f"x=(w-text_w)/2:y=h*{E['y_frac']}:enable='gte(t,{max(0, total - E['last_s']):.2f})'")
    chain.append("ass=captions.ass:fontsdir=fonts")
    graph.append(f"[{cur}]" + ",".join(chain) + "[vf]")
    graph.append(f"[0:a]{af}[af]")
    (work / "stage2.filter").write_text(";".join(graph), encoding="utf-8")
    print(f"[3/5] rendering style '{a.style}' with brand '{brand['name']}' ({ncap} caption events)...", flush=True)
    cmd = [ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-i", "stage1.mkv"] + [str(x) if not isinstance(x, Path) else x.name for x in inputs]
    cmd += ["-filter_complex_script", "stage2.filter", "-map", "[vf]", "-map", "[af]", "-r", FPS, "-c:v", "libx264", "-crf", F["crf"],
            "-preset", F["preset"], "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", F["audio_bitrate"], "-movflags", "+faststart",
            "-t", f"{total:.3f}", out]
    C.run(cmd, cwd=work)

    stills = []
    if not a.no_stills:
        sd = out.parent / (out.stem + "_stills")
        sd.mkdir(exist_ok=True)
        for frac in (0.08, 0.5, 0.92):
            p = sd / f"{out.stem}_{int(frac * 100):02d}.jpg"
            C.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-ss", f"{total * frac:.2f}", "-i", out, "-frames:v", "1", "-q:v", "3", p], check=False)
            if p.exists():
                stills.append(str(p))
    report = {"style": a.style, "brand": brand["name"], "input": str(src), "output": str(out), "transcribe": method,
              "input_clip_s": round(clip_dur, 2), "output_s": round(total, 2), "spans": len(spans), "fillers_or_repeats_removed": nrem,
              "silence_removed_s": round(clip_dur - total, 2), "shots": len(shots), "cut_times_s": [round(c, 2) for c in cuts],
              "captions": ncap, "words_out": len(out_words), "hook_text": bool(a.hook_text), "end_card_keyword": keyword or None,
              "loudnorm_measured": meas, "stills": stills, "srt": str(srt) if srt else None}
    (work / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("[4/5] done.", flush=True)
    print(json.dumps({k: v for k, v in report.items() if k != "loudnorm_measured"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
