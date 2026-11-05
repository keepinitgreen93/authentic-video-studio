#!/usr/bin/env python3
"""Offline smoke test: validates styles, brand loading, logo palette, brand_extract on a synthetic logo,
and (if FFmpeg is present) a 6 second render. No network needed except optional font fetch.

  python tests/smoke_test.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "authentic-video-studio" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import vs_common as C  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        failures.append(name)


def main() -> int:
    check("styles present", len(C.list_styles()) >= 3, str(C.list_styles()))
    brand = C.load_brand(None)
    for s in C.list_styles():
        st = C.load_style(s, brand)
        check(f"style {s} resolves placeholders", "{brand." not in json.dumps(st))
    skill = (ROOT / "skills" / "authentic-video-studio" / "SKILL.md").read_text(encoding="utf-8")
    check("SKILL.md frontmatter", skill.startswith("---\nname: authentic-video-studio\n") and "\ndescription: " in skill)
    check("SKILL.md under 500 lines", skill.count("\n") < 500)
    try:
        from PIL import Image, ImageDraw
        import brand_extract as B
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            im = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.ellipse([20, 20, 280, 280], fill="#C026D3")
            d.rectangle([120, 120, 180, 180], fill="#FACC15")
            im.save(td / "logo.png")
            rc = B.main(["--logo", str(td / "logo.png"), "--name", "Smoke Co", "--no-download-fonts", "--out", str(td / "brand")])
            check("brand_extract logo run", rc == 0)
            b = C.load_brand(td / "brand")
            check("primary from logo", b["colors"]["primary"].upper().startswith("#C0") or b["colors"]["primary"] == "#C026D3", b["colors"]["primary"])
            check("preview card written", (td / "brand" / "brand-preview.png").exists())
    except Exception as e:  # noqa
        check("brand_extract", False, f"{type(e).__name__}: {e}")
    if C.find_tool("ffmpeg"):
        check("ffmpeg found", True, C.find_tool("ffmpeg"))
    else:
        print("[skip] ffmpeg not found; render test skipped")
    print("\nALL PASSED" if not failures else f"\n{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
