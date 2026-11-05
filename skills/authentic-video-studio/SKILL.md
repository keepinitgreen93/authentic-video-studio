---
name: authentic-video-studio
description: Edit raw talking-head videos into branded vertical short-form videos (captions, jump cuts, zoom, hook text, logo, CTA end card) with local FFmpeg and Whisper. Use when the user wants to edit, caption, brand or clean up a talking-head clip, pick a video template style, or set up their brand colors, fonts and logo for video. Runs natively on Windows, macOS and Linux. No API keys, no WSL.
license: MIT
compatibility: Needs FFmpeg and Python 3.10+. The spotlight and minimalist styles also need Node 18+, Remotion and its headless Chrome. The installer sets all of them up. Works offline after setup except for website branding and font downloads.
metadata:
  version: "0.2.0"
  homepage: https://github.com/keepinitgreen93/authentic-video-studio
---

# Authentic Video Studio

Turns one raw talking-head clip into a finished 1080x1920 video. Everything runs on the user's machine. A `brand.yaml` file holds colors, fonts, logo and CTA, and every template style reads it.

## First step on any new machine or new client: install, then brand

1. **Check the install.** Run the doctor. If it says NOT READY, run the installer from the repo root (`install.ps1` on Windows, `install.sh` on macOS/Linux) and re-run the doctor.
   - Windows: `python skills/authentic-video-studio/scripts/vs.py doctor`
   - Any OS, after install, the studio Python is at `%LOCALAPPDATA%\authentic-video-studio\venv` (Windows) or `~/.local/share/authentic-video-studio/venv` (macOS/Linux). `vs.py` re-launches itself inside it.
2. **Run the branding onboarding** before the first render. Follow `references/branding-onboarding.md` step by step with the user. It builds `brand/brand.yaml`, shows a preview card, and lets the user edit. Do not skip it: without it, renders use a neutral blue and orange default.
3. **Render.** See "Render" below.

## Commands (all through one entry point)

```
python scripts/vs.py doctor [--json]
python scripts/vs.py brand --url https://site.com --out brand      # branding onboarding
python scripts/vs.py brand --logo logo.png --out brand
python scripts/vs.py brand --kit brand-kit.zip --out brand
python scripts/vs.py brand --name "Acme" --primary "#0A7C86" --heading-font Montserrat --out brand
python scripts/vs.py brand edit brand --set colors.primary=#E11D48
python scripts/vs.py styles
python scripts/vs.py render --input raw.mp4 --out final.mp4 --style list-the-ways --brand brand \
    --hook-text "7 WAYS TO\nEDIT FASTER" --keyword GUIDE
python scripts/vs.py demo --out demo-output --brand brand            # sample clip in every style
python scripts/vs.py setup-remotion --install-node                   # Node, npm packages, headless Chrome (spotlight, minimalist)
```

Paths are relative to this skill folder. Pass `--brand` a folder that holds `brand.yaml`.

## Styles

| Style | Look | Use for |
|---|---|---|
| `list-the-ways` | Jump cuts at list items, slow push-in then snap back, one big word at a time, hook text, `DROP KEYWORD BELOW` end card | Counted advice: 7 ways, 5 mistakes |
| `punch-caps` | Very tight cuts, alternating 105% punch-in, 3-word ALL CAPS chunks, heavy outline, writes an `.srt` | Fast how-to, product education |
| `spotlight-lite` | Presenter in a rounded window over a branded moving grid, opening zoom-out, karaoke captions on a dark strip. FFmpeg only | Explainers, talks, no Node |
| `spotlight` | Remotion. Opening zoom-out, presenter window over the moving grid, animated key-phrase cards, large-panel moments, karaoke captions | Explainers where on-screen graphics help |
| `minimalist` | Remotion. Full-frame speaker, dark takeovers with one icon and a few words, push in and snap back | Short lessons, one idea per thought |

`spotlight` and `minimalist` need Node and Remotion. Run `vs.py doctor`; if the `remotion:` lines are not ok, run `vs.py setup-remotion --install-node`. If that cannot work (offline, locked machine), use `spotlight-lite`. Remotion is free for individuals, non-profits and companies with up to 3 employees; larger for-profit companies need a Remotion licence, so ask before using these two styles for them. Details: `references/remotion-styles.md`.

Details and every tunable value: `references/styles.md`. Override one value for one render with `--set zoom.max=1.1`.

## Render

1. Confirm the brand is set (a `brand/brand.yaml` exists) and the doctor passes.
2. Ask for: the raw clip path, the style (or recommend one from the table), optional hook text (two short lines, 16 characters or fewer each), optional CTA keyword.
3. Run `vs.py render`. The first run downloads the speech model (about 250 MB for `small.en`).
4. Look at the three stills written next to the output (`<name>_stills/`). Check hook text, captions, logo and end card for clipping. Report what you saw.
5. Verify with ffprobe: 1080x1920, 30 fps, H.264 + AAC, duration. `references/pipeline.md` has the checklist.

## Rules

- Never post, upload or send a finished video. Hand the user the file path.
- Never read or print API keys. This project needs none.
- Automatic cleanup cannot find false starts or retakes. For those, transcribe, fix the word list, and pass `--words-json corrected.json`.
- Tight selfie footage: use `--set zoom.max=1.10` so hair is not cropped and the caption stays off the mouth.
- Website fonts are not downloaded unless the user owns the licence and passes `--allow-site-fonts`. Otherwise the onboarding picks a close Google Font and says so. Report that to the user.
- Do not store client footage or brand files in this repo. Keep them in the user's own project folder.

## References (load when needed)

- `references/branding-onboarding.md`: the guided branding script. Load first for any new brand.
- `references/brand-yaml.md`: every brand.yaml field.
- `references/styles.md`: style values and how to add a new style.
- `references/remotion-styles.md`: how spotlight and minimalist work, the plan files, hand-tuning, limits.
- `references/pipeline.md`: what each render stage does, QA checklist.
- `references/troubleshooting.md`: errors and fixes, Windows notes.
