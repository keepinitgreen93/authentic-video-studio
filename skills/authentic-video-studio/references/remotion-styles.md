# spotlight and minimalist (Remotion styles)

Two styles are drawn with Remotion (React rendered in a headless browser). FFmpeg still does the speech cleanup, the audio and the final encode. Node.js is the only extra runtime, and the installer sets it up.

## Pipeline

1. Transcribe with faster-whisper (word timestamps). Remove fillers, repeats and long pauses. Same as the other styles.
2. FFmpeg writes the clean cut (`stage1.mkv`) in the work folder.
3. `vs_remotion.py` builds two JSON files from the cleaned transcript and `brand.yaml`:
   - `spotlight-props.json` or `minimalist-props.json` in the work folder. It holds the `brand` object (colors, fonts, logo, derived dark-surface colors) and the `job` or `plan`.
4. `remotion render` draws the picture (muted) from `<app home>/remotion`, with a per-render public folder holding the cut, the brand fonts, the logo and the icons.
5. FFmpeg joins the picture with the cleaned and loudness-normalised audio (-14 LUFS), encodes H.264 yuv420p and AAC, and writes stills.

Why the old Spotlight said "use Linux": its setup and render scripts assumed a Unix shell and installed WhisperX with PyTorch pins, which have no stable Windows wheels. This version has no shell scripts and uses the faster-whisper words the studio already produces, so Windows, macOS and Linux behave the same.

## Brand to Remotion

Nothing visual is hard coded. `build_brand_props` maps `brand.yaml` to the Remotion `Brand` type (`templates/remotion/src/brand.ts`):

| brand.yaml | Used for |
|---|---|
| `colors.primary` | Hook box, dark card and takeover background (a darkened tint of it), grid vignette |
| `colors.accent` | Active caption word, accent bars, end card box, takeover highlight (lightened if needed to read on dark) |
| `colors.background`, `colors.text` | Grid background and tiles (light brands) |
| `fonts.heading`, `fonts.body` | Loaded from the font files in the brand folder (`VSHeading`, `VSBody`) |
| `logo.*` | Logo position, scale and visibility |
| `cta.*` | End card text |

If a brand is dark (`colors.background` luminance low), the grid switches to its dark variant.

## Plans and hand tuning

The automatic plan is a sensible default, not a finished edit. For a hand-tuned video, run the render once, open the props JSON in the work folder, edit it, then render from it:

```
cd <app home>/remotion
node node_modules/@remotion/cli/remotion-cli.js render src/index.tsx Spotlight out.mp4 --props=<props.json> --public-dir=<work>/remotion_public --muted
```

Spotlight job fields: `scenes` (`full` at 0, then `window`), `swaps` (`{in,out}` large-panel intervals in seconds, `out: 999` holds to the end), `beats` (`{start,end,words}` key-phrase cards), `words` (`{t,s,e,h?}` captions), `captionTop`, `faceX`, `faceY`.

Minimalist plan fields: `takeovers` (`id`, `startFrame`, `endFrame`, `variant` one of `single-centered`, `single-side` (drawn centered in portrait), `paired`, `linked`, `words`, `lineBreaks`, `icon`), `returnCadence`, `treatmentVersion` `1.2`, optional `avatarPushes`. Frames are 30 fps. The planner (`src/minimalist/plan.mjs`) rejects layouts that overflow the frame and warns about short speaker gaps. Validate a plan with `node validate-plan.mjs plan.json`.

Rules that matter for quality:

- Each takeover needs at least 25 frames of speaker after it and, in 1.2, three seconds is preferred.
- Use each icon at most twice. The twelve icons are in `templates/remotion/public/icons/` with meanings in `index.json`.
- A key-phrase card shows words from the sentence; do not add words that were not spoken.
- Keep text inside the 1080x1920 frame and out of the bottom 15% and the top 8%.

## Adding a graphic or icon

- Spotlight graphics are React components in `templates/remotion/src/spotlight/graphics.tsx` that take `{beatStart, beatEnd}`. Use only the Remotion frame clock (`useCurrentFrame`) for animation and `useBrand()` for colors.
- Add an icon by putting a 360x300 SVG with a gray/white style in `templates/remotion/public/icons/` and listing it in `index.json` and in `ICON_KEYS` in `vs_remotion.py`.

## Checks

```
cd skills/authentic-video-studio/templates/remotion
npm ci
npm run typecheck
npm test            # 34 planner tests
```

## Licence

Remotion is free for individuals, non-profits, and for-profit companies with up to three employees. Larger for-profit companies need a Remotion company licence (https://www.remotion.dev/docs/license). Tell the user before rendering these styles for such a company, and offer `spotlight-lite`.
