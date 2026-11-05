"""Shared helpers for Authentic Video Studio. Standard library plus lazy imports only."""
from __future__ import annotations

import colorsys
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
STYLES_DIR = SKILL_DIR / "templates" / "styles"
BRANDS_DIR = SKILL_DIR / "templates" / "brands"
IS_WIN = os.name == "nt"


def app_home() -> Path:
    env = os.environ.get("VS_HOME")
    if env:
        return Path(env)
    if IS_WIN:
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "authentic-video-studio"
    return Path.home() / ".local" / "share" / "authentic-video-studio"


APP_HOME = app_home()
CONFIG_PATH = APP_HOME / "config.json"
FONT_CACHE = APP_HOME / "fonts"


def utf8_stdio() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _candidate_dirs(name: str) -> list[str]:
    exe = name + (".exe" if IS_WIN else "")
    out: list[str] = []
    home = Path.home()
    if IS_WIN:
        la = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("ProgramFiles", "C:/Program Files")
        out += glob.glob(f"{la}/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin/{exe}")
        out += glob.glob(f"{la}/Microsoft/WinGet/Packages/BtbN.FFmpeg*/*/bin/{exe}")
        out += [f"{la}/Microsoft/WinGet/Links/{exe}", f"{home}/scoop/shims/{exe}",
                f"C:/ProgramData/chocolatey/bin/{exe}", f"C:/ffmpeg/bin/{exe}",
                f"{pf}/ffmpeg/bin/{exe}", str(APP_HOME / "bin" / exe)]
    else:
        out += [f"/opt/homebrew/bin/{exe}", f"/usr/local/bin/{exe}", f"/usr/bin/{exe}",
                f"/snap/bin/{exe}", str(APP_HOME / "bin" / exe)]
    return out


def find_tool(name: str) -> str | None:
    env = os.environ.get(name.upper())
    if env and Path(env).exists():
        return env
    cfg = load_config().get("tools", {})
    if cfg.get(name) and Path(cfg[name]).exists():
        return cfg[name]
    w = shutil.which(name)
    if w:
        return w
    for c in _candidate_dirs(name):
        if Path(c).exists():
            return c
    return None


def need_tool(name: str) -> str:
    p = find_tool(name)
    if not p:
        sys.exit(f"Missing {name}. Run the installer (install.ps1 or install.sh) or: python scripts/vs.py doctor")
    return p


def run(cmd, cwd=None, capture=False, check=True):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, stdin=subprocess.DEVNULL,
                       capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        tail = ((r.stderr or "") + (r.stdout or ""))[-2000:] if capture else ""
        sys.exit(f"command failed ({r.returncode}): {' '.join(str(c) for c in cmd)[:300]}\n{tail}")
    return r


def ffprobe_json(path) -> dict:
    r = run([need_tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", path], capture=True)
    return json.loads(r.stdout)


def probe_video(path) -> dict:
    j = ffprobe_json(path)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    if not v:
        sys.exit(f"No video stream in {path}")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) in (90, 270):
        w, h = h, w
    fr = v.get("avg_frame_rate", "30/1")
    try:
        a, b = fr.split("/")
        fps = float(a) / float(b) if float(b) else 30.0
    except Exception:
        fps = 30.0
    return {"w": w, "h": h, "fps": fps, "duration": float(j["format"].get("duration", 0)),
            "has_audio": any(s["codec_type"] == "audio" for s in j["streams"]),
            "vcodec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt")}


# ---------- colour helpers ----------
HEX_RE = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")


def norm_hex(s: str) -> str | None:
    s = s.strip()
    m = re.fullmatch(r"#?([0-9a-fA-F]{3,8})", s)
    if not m:
        return None
    h = m.group(1)
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    elif len(h) == 8:
        h = h[:6]
    elif len(h) != 6:
        return None
    return "#" + h.upper()


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_hex(r: float, g: float, b: float) -> str:
    return "#%02X%02X%02X" % (max(0, min(255, round(r))), max(0, min(255, round(g))), max(0, min(255, round(b))))


def hsv(h: str) -> tuple[float, float, float]:
    r, g, b = hex_rgb(h)
    return colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)


def luminance(h: str) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable_on(bg: str, light="#FFFFFF", dark="#111111") -> str:
    return light if contrast(bg, light) >= contrast(bg, dark) else dark


def ass_color(hex_: str, alpha: int = 0) -> str:
    r, g, b = hex_rgb(hex_)
    return "&H%02X%02X%02X%02X&" % (alpha, b, g, r)


# ---------- fonts ----------
def font_info(path) -> dict:
    from fontTools.ttLib import TTFont
    f = TTFont(str(path), lazy=True, fontNumber=0)
    name = f["name"]

    def nm(i):
        r = name.getName(i, 3, 1, 0x409) or name.getName(i, 1, 0, 0) or name.getName(i, 3, 0, 0x409)
        return str(r) if r else ""
    upm = f["head"].unitsPerEm
    os2 = f["OS/2"] if "OS/2" in f else None
    hhea = f["hhea"]
    asc = getattr(os2, "usWinAscent", 0) or hhea.ascent
    desc = getattr(os2, "usWinDescent", 0) or abs(hhea.descent)
    return {"family": nm(1) or nm(16), "typographic_family": nm(16) or nm(1), "subfamily": nm(2),
            "full_name": nm(4), "license": nm(13), "license_url": nm(14), "upm": upm,
            "cell": (asc + desc) / upm, "weight": getattr(os2, "usWeightClass", 400)}


def text_width(font_path, size_ass: float, text: str) -> float:
    """Pixel width of text as libass will draw it (ASS size is the cell height)."""
    from PIL import ImageFont
    try:
        fi = font_info(font_path)
        em = size_ass / fi["cell"]
        return ImageFont.truetype(str(font_path), max(1, int(round(em)))).getlength(text)
    except Exception:
        return len(text) * size_ass * 0.55


# ---------- brand + style loading ----------
def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _yaml():
    import yaml
    return yaml


def load_brand(path=None) -> dict:
    """Load brand.yaml (file or folder). Missing values fall back to the neutral default brand."""
    yaml = _yaml()
    default = yaml.safe_load((BRANDS_DIR / "default.brand.yaml").read_text(encoding="utf-8"))
    if not path:
        p = Path("brand")
        path = p if p.exists() else None
    if not path:
        brand, base = default, BRANDS_DIR
    else:
        p = Path(path).resolve()  # absolute, because ffmpeg runs inside the work folder
        base = p if p.is_dir() else p.parent
        f = p / "brand.yaml" if p.is_dir() else p
        if not f.exists():
            sys.exit(f"brand.yaml not found at {f}. Run the branding onboarding: python scripts/vs.py brand --help")
        brand = deep_merge(default, yaml.safe_load(f.read_text(encoding="utf-8")) or {})
    brand["_dir"] = str(base)
    for role in ("heading", "body"):
        fnt = brand["fonts"].get(role) or {}
        fp = fnt.get("file")
        resolved = None
        if fp:
            cand = Path(fp) if Path(fp).is_absolute() else base / fp
            if cand.exists():
                resolved = cand
        if not resolved:
            resolved = _fallback_font(role)
        fnt["_path"] = str(resolved) if resolved else None
        brand["fonts"][role] = fnt
    lg = brand.get("logo") or {}
    if lg.get("file"):
        c = Path(lg["file"]) if Path(lg["file"]).is_absolute() else base / lg["file"]
        lg["_path"] = str(c) if c.exists() else None
    brand["logo"] = lg
    for k, v in list(brand["colors"].items()):
        n = norm_hex(str(v))
        if not n:
            sys.exit(f"brand.yaml colors.{k} is not a hex colour: {v}")
        brand["colors"][k] = n
    return brand


def _fallback_font(role: str):
    for name in (("Poppins-ExtraBold.ttf",) if role == "heading" else ("Poppins-SemiBold.ttf",)) + ("Poppins-ExtraBold.ttf",):
        p = FONT_CACHE / name
        if p.exists():
            return p
    sys_candidates = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
                      "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
    for c in sys_candidates:
        if Path(c).exists():
            return Path(c)
    return None


def _fmt(obj, brand):
    if isinstance(obj, dict):
        return {k: _fmt(v, brand) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_fmt(v, brand) for v in obj]
    if isinstance(obj, str) and "{brand." in obj:
        def rep(m):
            cur = brand
            for part in m.group(1).split("."):
                cur = cur[part]
            return str(cur)
        return re.sub(r"\{brand\.([a-zA-Z0-9_.]+)\}", rep, obj)
    return obj


def list_styles() -> list[str]:
    return sorted(p.stem for p in STYLES_DIR.glob("*.json") if not p.stem.startswith("_"))


def load_style(name: str, brand: dict, sets: list[str] | None = None) -> dict:
    p = Path(name)
    if not p.exists():
        p = STYLES_DIR / f"{name}.json"
    if not p.exists():
        sys.exit(f"Unknown style '{name}'. Available: {', '.join(list_styles())}")
    base = json.loads((STYLES_DIR / "_defaults.json").read_text(encoding="utf-8"))
    style = deep_merge(base, json.loads(p.read_text(encoding="utf-8")))
    for kv in sets or []:
        k, v = kv.split("=", 1)
        try:
            v = json.loads(v)
        except Exception:
            pass
        d = style
        ks = k.split(".")
        for kk in ks[:-1]:
            d = d.setdefault(kk, {})
        d[ks[-1]] = v
    return _fmt(style, brand)
