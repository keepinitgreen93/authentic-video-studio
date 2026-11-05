# Pipeline and QA

## Stages (render_video.py)

1. **Transcribe.** Audio is extracted to 16 kHz mono WAV and transcribed with faster-whisper (CPU, int8) with word timestamps. The result is cached in the work folder, keyed on file size, modified time, range and model.
2. **Clean.** Fillers (um, uh, er, hmm) and immediate repeats are removed. Pauses longer than `cleanup.max_gap_keep_s` are cut to about 0.2 s. Cuts land at word midpoints in silence, with a 6 ms crossfade.
3. **Shots and zoom.** Cut points are chosen at sentence ends and span joins, near the style's shot target. Zoom is applied per shot.
4. **Compose.** Reframe to 9:16 (landscape input is cropped around `--face-x`), optional window layout and moving grid, logo, hook text, end card, captions (ASS via libass).
5. **Audio.** High-pass at 70 Hz, two-pass loudnorm to -14 LUFS with a true-peak ceiling of -1.5 dBTP, then a safety limiter.
6. **Stills.** Three JPEGs at 8%, 50% and 92% of the video for review.

Outputs: `<out>.mp4`, optional `<out>.srt`, `<out>_stills/`, and `<out>_work/report.json` (counts, cut times, loudness measurement).

## Limits

- Automatic cleanup cannot find false starts or retakes. Review the transcript in `<out>_work/words_raw.json`, delete the bad words, and pass the fixed list back with `--words-json`.
- Zoom is whole-frame, with no face tracking.
- Whisper can normalize stutters away. If exact wording matters, check the transcript.

## QA checklist (do all of it)

1. `ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration -of default=nw=1 out.mp4` shows h264, 1080, 1920, 30/1, aac, and a sensible duration.
2. View all three stills. Check: hook text readable and inside the frame, caption not over the mouth, logo not clipped, end card readable in the last 2.4 s.
3. Check `loudnorm_measured` and the rendered file: integrated loudness near -14 LUFS, true peak at or below -1 dBTP.
4. Play it once if you can. Stills do not prove natural cadence.
5. Report: duration, resolution, style, brand name, number of cuts, what you saw in the stills, and any warning printed.
