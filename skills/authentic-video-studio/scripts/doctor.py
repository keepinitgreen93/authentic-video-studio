#!/usr/bin/env python3
"""Check every dependency Authentic Video Studio needs and print an exact fix for anything missing.

  python doctor.py            human-readable report
  python doctor.py --json     machine-readable (for agents)
  python doctor.py --fix      try to pip-install missing Python packages into the current environment
Exit code 0 = ready, 1 = something required is missing.
"""
from __future__ import annotations

import argparse
import importlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vs_common as C  # noqa: E402

PKGS = [("faster_whisper", "faster-whisper", True), ("PIL", "Pillow", True), ("yaml", "PyYAML", True),
        ("requests", "requests", True), ("bs4", "beautifulsoup4", True), ("fontTools", "fonttools", True),
        ("pypdf", "pypdf", False), ("numpy", "numpy", True), ("resvg_py", "resvg-py", False)]
FILTERS = ["ass", "drawtext", "alphamerge", "overlay", "loudnorm", "alimiter", "concat", "scale", "crop"]


def check() -> list[dict]:
    res: list[dict] = []
    add = lambda name, ok, detail, fix="", required=True: res.append(  # noqa: E731
        {"name": name, "ok": bool(ok), "detail": detail, "fix": fix, "required": required})
    v = sys.version_info
    add("python", v >= (3, 10), f"{platform.python_version()} at {sys.executable}",
        "Run the installer (install.ps1 / install.sh). It sets up a private Python 3.12 environment with uv.")
    in_venv = C.APP_HOME.as_posix() in Path(sys.prefix).as_posix()
    add("environment", in_venv or all(importlib.util.find_spec(m) for m, _, req in PKGS if req),
        f"prefix {sys.prefix}", "Run the installer to create the environment at " + str(C.APP_HOME / "venv"), required=False)
    for mod, pipname, req in PKGS:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "")
            add(f"pkg:{pipname}", True, ver or "ok", required=req)
        except Exception as e:  # noqa
            add(f"pkg:{pipname}", False, f"{type(e).__name__}: {e}", f"python -m pip install {pipname}", required=req)
    ff = C.find_tool("ffmpeg")
    fp = C.find_tool("ffprobe")
    install_ff = {"nt": "winget install -e --id Gyan.FFmpeg", "posix": ("brew install ffmpeg" if sys.platform == "darwin" else "sudo apt install ffmpeg")}["nt" if C.IS_WIN else "posix"]
    add("ffmpeg", ff, ff or "not found", install_ff)
    add("ffprobe", fp, fp or "not found", install_ff)
    if ff:
        r = subprocess.run([ff, "-hide_banner", "-version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        first = (r.stdout or "").splitlines()[0] if r.stdout else ""
        add("ffmpeg version", True, first, required=False)
        fl = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        miss = [f for f in FILTERS if f" {f} " not in fl]
        add("ffmpeg filters", not miss, "all present" if not miss else "missing: " + ", ".join(miss),
            "Install a full FFmpeg build (with libass and freetype). Windows: winget install -e --id Gyan.FFmpeg. macOS: brew install ffmpeg.")
        enc = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        add("ffmpeg libx264+aac", " libx264 " in enc and " aac " in enc, "ok" if " libx264 " in enc else "libx264 missing",
            "Install a full FFmpeg build (libx264 required).")
    fonts = list(C.FONT_CACHE.glob("*.ttf")) if C.FONT_CACHE.exists() else []
    add("default fonts", bool(fonts), f"{len(fonts)} in {C.FONT_CACHE}", "python scripts/vs.py setup", required=False)
    try:
        import requests
        requests.head("https://fonts.googleapis.com", timeout=6)
        add("network (Google Fonts)", True, "reachable", required=False)
    except Exception as e:  # noqa
        add("network (Google Fonts)", False, f"{type(e).__name__}", "Needed only for website branding and Google Fonts downloads. Offline rendering still works.", required=False)
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    models = [p.name for p in cache.glob("models--*whisper*")] if cache.exists() else []
    add("whisper model cache", bool(models), ", ".join(models) or "none yet (downloads on first render, about 250 MB for small.en)",
        "python scripts/vs.py setup --model small.en", required=False)
    free = shutil.disk_usage(Path.home()).free / 1e9
    add("disk space", free > 3, f"{free:.1f} GB free", "Free at least 3 GB.", required=False)
    try:
        import vs_remotion
        res.extend(vs_remotion.status())
    except Exception as e:  # noqa
        add("remotion", False, f"{type(e).__name__}: {e}", "Reinstall the studio", required=False)
    wsl = "WSL not required" if C.IS_WIN else "n/a"
    add("wsl", True, wsl, required=False)
    return res


def main() -> int:
    C.utf8_stdio()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()
    res = check()
    if a.fix:
        bad = [r["fix"].split()[-1] for r in res if not r["ok"] and r["name"].startswith("pkg:") and r["fix"]]
        if bad:
            subprocess.run([sys.executable, "-m", "pip", "install", *bad])
            res = check()
    failed = [r for r in res if not r["ok"] and r["required"]]
    if a.json:
        print(json.dumps({"ready": not failed, "platform": platform.platform(), "checks": res}, indent=2))
    else:
        print(f"Authentic Video Studio doctor ({platform.platform()})\n")
        for r in res:
            mark = "OK  " if r["ok"] else ("FAIL" if r["required"] else "warn")
            print(f"[{mark}] {r['name']}: {r['detail']}")
            if not r["ok"] and r["fix"]:
                print(f"        fix: {r['fix']}")
        print(("\nREADY" + ("" if all(r["ok"] for r in res if r["name"].startswith("remotion")) else " (spotlight and minimalist styles need the remotion items above; spotlight-lite works without them)")) if not failed else f"\nNOT READY: {len(failed)} required item(s) missing. Apply the fixes above, or run the installer.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
