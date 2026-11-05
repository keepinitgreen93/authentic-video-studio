"""Hermes plugin wrapper for Authentic Video Studio.

Registers four tools that call the same CLI the skill documents (skills/authentic-video-studio/scripts/vs.py),
a /video-studio slash command, and the bundled skill (loaded as authentic-video-studio:authentic-video-studio).
Nothing here posts or uploads anything.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SKILL_DIR = _ROOT / "skills" / "authentic-video-studio"
_VS = _SKILL_DIR / "scripts" / "vs.py"


def _app_home() -> Path:
    env = os.environ.get("VS_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "authentic-video-studio"
    return Path.home() / ".local" / "share" / "authentic-video-studio"


def _python() -> str:
    p = _app_home() / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(p) if p.exists() else sys.executable


def _run(args: list[str], timeout: int = 1800) -> str:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run([_python(), "-I", str(_VS), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env, stdin=subprocess.DEVNULL)
        return json.dumps({"ok": r.returncode == 0, "exit_code": r.returncode, "stdout": r.stdout[-6000:],
                           "stderr": r.stderr[-2000:]})
    except subprocess.TimeoutExpired:
        return json.dumps({"ok": False, "error": f"timed out after {timeout}s"})
    except Exception as e:  # never raise out of a handler
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})


def _doctor(args: dict, **kwargs) -> str:
    return _run(["doctor", "--json"], 120)


def _setup_remotion(args: dict, **kwargs) -> str:
    return _run(["setup-remotion", "--install-node"], 1500)


def _styles(args: dict, **kwargs) -> str:
    return _run(["styles"], 60)


def _brand(args: dict, **kwargs) -> str:
    out = args.get("out") or "brand"
    mode = args.get("mode", "create")
    if mode == "edit":
        cmd = ["brand", "edit", out]
        for kv in args.get("set", []) or []:
            cmd += ["--set", str(kv)]
        return _run(cmd, 300)
    if mode == "preview":
        return _run(["brand", "preview", out], 120)
    cmd = ["brand", "--out", out]
    for flag in ("url", "logo", "kit", "name", "tagline", "primary", "accent", "background", "text", "keyword", "tone",
                 "cta_text", "heading_font", "body_font", "handle"):
        if args.get(flag):
            cmd += [f"--{flag.replace('_', '-')}", str(args[flag])]
    if args.get("allow_site_fonts"):
        cmd.append("--allow-site-fonts")
    return _run(cmd, 600)


def _render(args: dict, **kwargs) -> str:
    if not args.get("input") or not args.get("out"):
        return json.dumps({"ok": False, "error": "input and out are required"})
    cmd = ["render", "--input", str(args["input"]), "--out", str(args["out"]), "--style", str(args.get("style", "list-the-ways"))]
    if args.get("brand"):
        cmd += ["--brand", str(args["brand"])]
    for flag in ("hook_text", "keyword", "words_json", "model", "workdir"):
        if args.get(flag):
            cmd += [f"--{flag.replace('_', '-')}", str(args[flag])]
    for flag in ("start", "max_seconds", "face_x", "face_y"):
        if args.get(flag) is not None:
            cmd += [f"--{flag.replace('_', '-')}", str(args[flag])]
    for kv in args.get("set", []) or []:
        cmd += ["--set", str(kv)]
    return _run(cmd, 3000)


_SCHEMAS = {
    "video_studio_doctor": {
        "name": "video_studio_doctor",
        "description": "Check that every dependency for Authentic Video Studio (FFmpeg, Python packages, fonts, speech model) is installed. Returns JSON with a fix command for anything missing. Run before the first render.",
        "parameters": {"type": "object", "properties": {}},
    },
    "video_studio_setup_remotion": {
        "name": "video_studio_setup_remotion",
        "description": "Install what the spotlight and minimalist styles need: Node.js LTS (only if missing, downloaded into the studio folder with no admin rights), the Remotion npm packages and its headless Chrome. Safe to run again. Needs internet the first time.",
        "parameters": {"type": "object", "properties": {}},
    },
    "video_studio_styles": {
        "name": "video_studio_styles",
        "description": "List the video template styles (list-the-ways, punch-caps, spotlight-lite, spotlight, minimalist) with a one-line description of each. spotlight and minimalist need Node and Remotion; video_studio_doctor reports whether they are ready.",
        "parameters": {"type": "object", "properties": {}},
    },
    "video_studio_brand": {
        "name": "video_studio_brand",
        "description": "Branding onboarding. mode=create builds brand.yaml in the folder 'out' from any mix of: url (website), logo (file path), kit (PDF/ZIP/folder/doc path), or plain answers (name, tagline, primary, accent, background, text, heading_font, body_font, cta_text, keyword). mode=edit applies 'set' items like colors.primary=#E11D48. mode=preview rewrites brand-preview.png. Always show the user brand-preview.png and get a yes before rendering. Read the skill reference branding-onboarding.md for the guided questions.",
        "parameters": {"type": "object", "properties": {
            "mode": {"type": "string", "enum": ["create", "edit", "preview"]},
            "out": {"type": "string", "description": "Brand folder, default 'brand'"},
            "url": {"type": "string"}, "logo": {"type": "string"}, "kit": {"type": "string"},
            "name": {"type": "string"}, "tagline": {"type": "string"}, "primary": {"type": "string"},
            "accent": {"type": "string"}, "background": {"type": "string"}, "text": {"type": "string"},
            "heading_font": {"type": "string"}, "body_font": {"type": "string"}, "cta_text": {"type": "string"},
            "keyword": {"type": "string"}, "tone": {"type": "string"}, "handle": {"type": "string"},
            "allow_site_fonts": {"type": "boolean", "description": "Only if the user owns the website font licence"},
            "set": {"type": "array", "items": {"type": "string"}, "description": "For mode=edit: KEY=VALUE items"}}},
    },
    "video_studio_render": {
        "name": "video_studio_render",
        "description": "Render one raw talking-head clip into a finished 1080x1920 branded video with a template style. Writes the mp4, review stills and optionally an .srt. Slow on first run (speech model download). Never uploads or posts.",
        "parameters": {"type": "object", "properties": {
            "input": {"type": "string", "description": "Raw video path"},
            "out": {"type": "string", "description": "Output mp4 path"},
            "style": {"type": "string", "enum": ["list-the-ways", "punch-caps", "spotlight-lite", "spotlight", "minimalist"]},
            "brand": {"type": "string", "description": "Folder containing brand.yaml"},
            "hook_text": {"type": "string", "description": "Up to two lines, each 16 characters or fewer, separated by \\n"},
            "keyword": {"type": "string", "description": "CTA keyword for the end card"},
            "words_json": {"type": "string", "description": "Corrected word list [{w,s,e}] to drop false starts"},
            "start": {"type": "number"}, "max_seconds": {"type": "number"}, "face_x": {"type": "number"},
            "face_y": {"type": "number", "description": "spotlight only: vertical face position 0..1 of the frame"},
            "model": {"type": "string"}, "workdir": {"type": "string"},
            "set": {"type": "array", "items": {"type": "string"}, "description": "Style overrides, e.g. zoom.max=1.1"}},
            "required": ["input", "out"]},
    },
}
_HANDLERS = {"video_studio_doctor": _doctor, "video_studio_styles": _styles, "video_studio_brand": _brand,
             "video_studio_render": _render, "video_studio_setup_remotion": _setup_remotion}


def _slash(raw_args: str) -> str:
    return ("Authentic Video Studio. Load the skill with skill_view('authentic-video-studio:authentic-video-studio'), "
            "run video_studio_doctor, then follow references/branding-onboarding.md to set up the brand before the first render. "
            f"Request: {raw_args or '(none)'}")


def register(ctx):
    for name, schema in _SCHEMAS.items():
        ctx.register_tool(name=name, toolset="video_studio", schema=schema, handler=_HANDLERS[name])
    ctx.register_skill("authentic-video-studio", _SKILL_DIR / "SKILL.md")
    try:
        ctx.register_command("video-studio", _slash, description="Start Authentic Video Studio: install check, branding, render")
    except Exception:
        pass
