#!/usr/bin/env python3
"""Authentic Video Studio command line. Works with any Python 3.9+; re-runs itself inside the studio environment.

  python vs.py doctor [--json]          check dependencies
  python vs.py setup [--model small.en] fetch default fonts (and the speech model)
  python vs.py brand --url https://... | --logo file | --kit file | --name ... --primary ...   (branding onboarding)
  python vs.py brand edit brand --set colors.primary=#E11D48
  python vs.py brand preview brand      write brand-preview.png
  python vs.py styles                   list template styles
  python vs.py sample [--out file]      make a synthetic test clip
  python vs.py render --input raw.mp4 --out final.mp4 --style list-the-ways --brand brand
  python vs.py demo --out outdir        sample clip rendered in every style
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def app_home() -> Path:
    env = os.environ.get("VS_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "authentic-video-studio"
    return Path.home() / ".local" / "share" / "authentic-video-studio"


def venv_python() -> Path | None:
    h = app_home() / "venv"
    p = h / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return p if p.exists() else None


def reexec_if_needed() -> None:
    vp = venv_python()
    if vp is None or os.environ.get("VS_IN_VENV") == "1":
        return
    try:
        if Path(sys.executable).resolve() == vp.resolve():
            return
    except OSError:
        pass
    env = dict(os.environ, VS_IN_VENV="1")
    env.pop("PYTHONPATH", None)  # a stray PYTHONPATH can shadow the environment's packages
    r = subprocess.run([str(vp), "-I", str(Path(__file__).resolve()), *sys.argv[1:]], env=env)
    sys.exit(r.returncode)


def main() -> int:
    reexec_if_needed()
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    sys.path.insert(0, str(HERE))
    if cmd == "doctor":
        import doctor
        sys.argv = ["doctor", *rest]
        return doctor.main()
    if cmd == "setup":
        return setup(rest)
    if cmd == "brand":
        import brand_extract
        return brand_extract.main(rest)
    if cmd == "styles":
        import vs_common as C
        import json
        for n in C.list_styles():
            d = json.loads((C.STYLES_DIR / f"{n}.json").read_text(encoding="utf-8"))
            print(f"{n}\n    {d.get('description', '')}")
        return 0
    if cmd == "sample":
        import make_sample
        sys.argv = ["make_sample", *rest]
        return make_sample.main()
    if cmd == "render":
        import render_video
        return render_video.main(rest)
    if cmd == "demo":
        return demo(rest)
    print(f"Unknown command: {cmd}\n{__doc__}")
    return 2


def setup(rest: list[str]) -> int:
    import argparse
    import vs_common as C
    import brand_extract as B
    ap = argparse.ArgumentParser(prog="vs.py setup")
    ap.add_argument("--model", default=None, help="also download this faster-whisper model (e.g. small.en)")
    a = ap.parse_args(rest)
    C.FONT_CACHE.mkdir(parents=True, exist_ok=True)
    for fam, weights in (("Poppins", [800]), ("Poppins", [600]), ("Inter", [500])):
        got = B.download_google_font(fam, weights, C.FONT_CACHE)
        print(f"font {fam} {weights}: {'ok ' + str(got[0].name) if got else 'FAILED (offline?)'}")
    if a.model:
        from faster_whisper import WhisperModel
        print(f"downloading speech model {a.model} ...")
        WhisperModel(a.model, device="cpu", compute_type="int8")
        print("model ready")
    return 0


def demo(rest: list[str]) -> int:
    import argparse
    import vs_common as C
    import make_sample
    import render_video
    ap = argparse.ArgumentParser(prog="vs.py demo")
    ap.add_argument("--out", default="demo-output")
    ap.add_argument("--brand", default=None)
    ap.add_argument("--input", default=None, help="use this clip instead of generating a synthetic one")
    ap.add_argument("--styles", default=None, help="comma list; default all")
    ap.add_argument("--max-seconds", type=float, default=None)
    a = ap.parse_args(rest)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    clip = Path(a.input) if a.input else out / "sample-talk.mp4"
    if not clip.exists():
        sys.argv = ["make_sample", "--out", str(clip)]
        make_sample.main()
    styles = a.styles.split(",") if a.styles else C.list_styles()
    for s in styles:
        args = ["--input", str(clip), "--out", str(out / f"demo_{s}.mp4"), "--style", s, "--hook-text", "7 WAYS TO\\nEDIT FASTER",
                "--keyword", "GUIDE", "--workdir", str(out / f"_work_{s}")]
        if a.brand:
            args += ["--brand", a.brand]
        if a.max_seconds:
            args += ["--max-seconds", str(a.max_seconds)]
        print(f"\n=== {s} ===")
        rc = render_video.main(args)
        if rc:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
