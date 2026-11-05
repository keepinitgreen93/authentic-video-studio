#!/usr/bin/env python3
"""Generate a synthetic test clip: FFmpeg test pattern plus text-to-speech. No real person, no real footage.

  python make_sample.py --out examples/sample/sample-talk.mp4

TTS engine per OS: Windows SAPI (built in), macOS `say`, Linux `espeak-ng` or `espeak`.
The script has filler words and long pauses on purpose, so the cleanup stage has something to remove.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vs_common as C  # noqa: E402

LINES = [
    ("Seven ways to edit video faster.", 0.9),
    ("Number one. Um, cut every long pause.", 1.4),
    ("Number two. Add captions that people can read with the sound off.", 1.2),
    ("Number three. Zoom in slowly, then snap back at every cut.", 1.5),
    ("Number four. Keep your hook under four seconds.", 1.1),
    ("Number five. Use your own brand colors and fonts.", 1.3),
    ("That is the idea. Pick one and try it today.", 0.5),
]


def tts(text: str, wav: Path) -> None:
    if os.name == "nt":
        ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              "try { $s.SelectVoice('Microsoft Zira Desktop') } catch {}; $s.Rate = 0; "
              "$s.SetOutputToWaveFile($env:VS_TTS_OUT); $s.Speak($env:VS_TTS_TEXT); $s.Dispose()")
        env = dict(os.environ, VS_TTS_OUT=str(wav), VS_TTS_TEXT=text)
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env, check=True,
                       stdin=subprocess.DEVNULL)
    elif sys.platform == "darwin":
        aiff = wav.with_suffix(".aiff")
        subprocess.run(["say", "-o", str(aiff), text], check=True)
        C.run([C.need_tool("ffmpeg"), "-nostdin", "-y", "-loglevel", "error", "-i", aiff, wav])
    else:
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe:
            sys.exit("No TTS engine found. Install espeak-ng (sudo apt install espeak-ng) or pass your own clip to the renderer.")
        subprocess.run([exe, "-s", "150", "-w", str(wav), text], check=True)


def main() -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sample-talk.mp4")
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--height", type=int, default=1280)
    a = ap.parse_args()
    ffmpeg = C.need_tool("ffmpeg")
    out = Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        parts = []
        for i, (text, gap) in enumerate(LINES):
            w = td / f"s{i}.wav"
            tts(text, w)
            norm = td / f"n{i}.wav"
            C.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-i", w, "-ar", "48000", "-ac", "1", "-af",
                   f"apad=pad_dur={gap}", norm])
            parts.append(norm)
        lst = td / "list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        speech = td / "speech.wav"
        C.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", speech])
        j = C.ffprobe_json(speech)
        d = float(j["format"]["duration"]) + 0.4
        # a plain moving test pattern with a simple face-like shape so crops and zooms are visible
        vf = (f"color=c=0x3B4A63:s={a.width}x{a.height}:r=30:d={d:.2f},format=yuv420p,"
              f"drawbox=x=0:y=ih*0.62:w=iw:h=ih*0.38:color=0x2A3550@1:t=fill,"
              f"drawbox=x=iw/2-110:y=ih*0.30:w=220:h=260:color=white@0.85:t=fill,"
              f"drawbox=x=iw/2-70:y=ih*0.30+80:w=36:h=20:color=black@0.9:t=fill,"
              f"drawbox=x=iw/2+34:y=ih*0.30+80:w=36:h=20:color=black@0.9:t=fill,"
              f"drawbox=x=iw/2-50:y=ih*0.30+170:w=100:h=14:color=black@0.9:t=fill,"
              f"drawbox=x=iw/2-170:y=ih*0.30+290:w=340:h=420:color=white@0.7:t=fill")
        C.run([ffmpeg, "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi", "-i", vf, "-i", speech, "-map", "0:v", "-map", "1:a",
               "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-shortest",
               "-movflags", "+faststart", out])
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
