# Template styles

Styles are JSON files in `templates/styles/`. They are merged over `_defaults.json`, then brand placeholders like `{brand.colors.accent}` are filled in. Add a style by copying one and changing values. List styles with `vs.py styles`.

## list-the-ways

- Cuts: shot target 7 s (hook shot 3.5 s min), split at list-item or sentence boundaries.
- Zoom: ramps from 100% to 140% over the last 3.3 s of each shot, snaps back to 100% at every cut. Cap at 110% for tight selfie framing.
- Captions: one word at a time, heading font, 100 px, white with a dark outline, numerals in the accent color, 90 ms pop.
- Hook text: two lines, white on a primary-color box, top 15%.
- End card: `DROP {KEYWORD} BELOW` on an accent-color box, last 2.4 s.

## punch-caps

- Cuts: shot target 3.4 s, tighter pause trimming (0.2 s).
- Zoom: alternates 100% and 105% on every other shot (hard punch-in).
- Captions: 3-word chunks, ALL CAPS, 92 px, 8 px outline, lower third. Writes `<output>.srt`.

## spotlight-lite

- Layout: presenter in a rounded window (940x1180) over the background color with a drifting grid of rounded tiles in the primary color.
- Zoom: opening zoom-out from 135% to 100% over 0.85 s.
- Captions: up to 4 words on a dark strip, body font, the spoken word in the accent color.
- No jump cuts. Pauses are still trimmed.

This is an FFmpeg-only approximation of the Remotion-based Spotlight look. It needs no Node.

## Common values you may override with `--set key=value`

| Key | Meaning |
|---|---|
| `zoom.max` | Peak zoom (1.1 = 110%) |
| `zoom.mode` | `ramp`, `alternate`, `open`, `none` |
| `cuts.shot_target_s` | Preferred shot length |
| `cuts.enabled` | `false` for no jump cuts |
| `captions.mode` | `word`, `chunk`, `karaoke` |
| `captions.size_px` | Caption size at 1080 px wide |
| `captions.y_frac` | Vertical position, 0 top to 1 bottom |
| `captions.case` | `as_spoken`, `upper`, `lower` |
| `captions.emphasis.extra_words` | List of words to color, e.g. `["free","today"]` |
| `cleanup.max_gap_keep_s` | Pauses longer than this are cut |
| `audio.target_lufs` | Loudness target, default -14 |
| `hook_text.font_size_px`, `end_card.last_s` | Hook size, end card duration |

Safe zones for phone UIs: keep text out of the bottom 15%, the top 8% and the right 10%. The defaults already do.
