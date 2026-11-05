"""Remotion support for the `spotlight` and `minimalist` styles.

Everything here is cross-platform Python (no bash). The Remotion project lives in the skill at
templates/remotion and is copied to <app home>/remotion, where `npm ci` and the headless browser download
happen, so the repo and any skill copy stay small.

  python vs.py setup-remotion [--install-node] [--check]
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import vs_common as C

PROJECT_SRC = C.SKILL_DIR / "templates" / "remotion"
NODE_MIN = 18
NODE_PIN = 22
SYNC_SKIP = {"node_modules", "out", ".remotion", ".synced"}


def remotion_home() -> Path:
    return C.APP_HOME / "remotion"


# ----------------------------------------------------------------------------- node + npm
def _node_candidates(name: str) -> list[str]:
    exe = {"node": "node.exe", "npm": "npm.cmd"}[name] if C.IS_WIN else name
    out = [str(C.APP_HOME / "node" / exe), str(C.APP_HOME / "node" / "bin" / name)]
    if C.IS_WIN:
        la = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("ProgramFiles", "C:/Program Files")
        out += [f"{pf}/nodejs/{exe}", f"{la}/Programs/nodejs/{exe}", f"{Path.home()}/scoop/apps/nodejs-lts/current/{exe}",
                f"{Path.home()}/scoop/apps/nodejs/current/{exe}", f"C:/ProgramData/chocolatey/bin/{exe}"]
    else:
        out += [f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name}"]
        nvm = Path.home() / ".nvm" / "versions" / "node"
        if nvm.exists():
            out += sorted((str(p / "bin" / name) for p in nvm.iterdir()), reverse=True)
    return out


def find_node_tool(name: str) -> str | None:
    env = os.environ.get(name.upper())
    if env and Path(env).exists():
        return env
    cfg = C.load_config().get("tools", {})
    if cfg.get(name) and Path(cfg[name]).exists():
        return cfg[name]
    # a portable install in the app home wins over PATH so the pair stays consistent
    for c in _node_candidates(name)[:2]:
        if Path(c).exists():
            return c
    w = shutil.which(name)
    if w:
        return w
    for c in _node_candidates(name):
        if Path(c).exists():
            return c
    return None


def node_version(node: str) -> tuple[int, ...] | None:
    try:
        r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
        m = re.match(r"v(\d+)\.(\d+)\.(\d+)", r.stdout.strip())
        return tuple(int(x) for x in m.groups()) if m else None
    except Exception:
        return None


def _tool_env(node: str | None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if node:
        env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    env["npm_config_update_notifier"] = "false"
    env["npm_config_fund"] = "false"
    env["npm_config_audit"] = "false"
    return env


# ----------------------------------------------------------------------------- portable Node (no admin rights)
def install_node_portable(log=print) -> str:
    """Download the newest Node 22 LTS release from nodejs.org into <app home>/node. Verifies the SHA-256."""
    base = "https://nodejs.org/dist"
    with urllib.request.urlopen(f"{base}/index.json", timeout=60) as r:
        index = json.load(r)
    # Node 22 is the line Remotion 4.0.500 was tested with here; take its newest release.
    lts = next(e for e in index if e["version"].startswith(f"v{NODE_PIN}.") and e.get("lts"))
    ver = lts["version"]
    mach = (os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("PROCESSOR_ARCHITECTURE") or "").lower() if C.IS_WIN else os.uname().machine.lower()
    arch = "arm64" if ("arm64" in mach or "aarch64" in mach) else "x64"
    if C.IS_WIN:
        fname, kind = f"node-{ver}-win-{arch}.zip", "zip"
    elif sys.platform == "darwin":
        fname, kind = f"node-{ver}-darwin-{arch}.tar.gz", "tar"
    else:
        fname, kind = f"node-{ver}-linux-{arch}.tar.xz", "tar"
    dest = C.APP_HOME / "node"
    tmp = C.APP_HOME / "_dl"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    archive = tmp / fname
    log(f"downloading Node {ver} ({fname}) ...")
    urllib.request.urlretrieve(f"{base}/{ver}/{fname}", archive)
    sums = urllib.request.urlopen(f"{base}/{ver}/SHASUMS256.txt", timeout=60).read().decode()
    want = next((ln.split()[0] for ln in sums.splitlines() if ln.endswith(" " + fname)), None)
    got = hashlib.sha256(archive.read_bytes()).hexdigest()
    if want and want != got:
        sys.exit(f"Node download failed its SHA-256 check ({fname}). Try again.")
    if kind == "zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(tmp / "x")
    else:
        with tarfile.open(archive) as t:
            t.extractall(tmp / "x")
    inner = next((tmp / "x").iterdir())
    shutil.rmtree(dest, ignore_errors=True)
    shutil.move(str(inner), str(dest))
    shutil.rmtree(tmp, ignore_errors=True)
    node = find_node_tool("node")
    log(f"Node installed at {dest}")
    return node or str(dest)


# ----------------------------------------------------------------------------- project sync + deps
def _fingerprint() -> str:
    h = hashlib.sha256()
    for p in sorted(PROJECT_SRC.rglob("*")):
        if p.is_file() and not (set(p.relative_to(PROJECT_SRC).parts) & SYNC_SKIP):
            h.update(str(p.relative_to(PROJECT_SRC)).replace("\\", "/").encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def sync_project() -> Path:
    """Copy templates/remotion to <app home>/remotion (without node_modules). Returns the target."""
    dst = remotion_home()
    fp = _fingerprint()
    marker = dst / ".synced"
    if marker.exists() and marker.read_text(encoding="utf-8").strip() == fp and (dst / "package.json").exists():
        return dst
    dst.mkdir(parents=True, exist_ok=True)
    for sub in ("src", "public", "examples"):
        shutil.rmtree(dst / sub, ignore_errors=True)
    for p in PROJECT_SRC.iterdir():
        if p.name in SYNC_SKIP:
            continue
        if p.is_dir():
            shutil.copytree(p, dst / p.name, ignore=shutil.ignore_patterns(*SYNC_SKIP))
        else:
            shutil.copy2(p, dst / p.name)
    marker.write_text(fp, encoding="utf-8")
    return dst


def _lock_hash() -> str:
    lock = PROJECT_SRC / "package-lock.json"
    return hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else ""


def deps_installed() -> bool:
    d = remotion_home()
    return (d / "node_modules" / "@remotion" / "cli" / "package.json").exists() and \
        (d / "node_modules" / ".vs-lock").exists() and (d / "node_modules" / ".vs-lock").read_text(encoding="utf-8").strip() == _lock_hash()


def npm_ci(log=print) -> None:
    node, npm = find_node_tool("node"), find_node_tool("npm")
    if not node or not npm:
        sys.exit("Node.js and npm are required for the spotlight and minimalist styles. Run the installer, or: python scripts/vs.py setup-remotion --install-node")
    d = sync_project()
    log("installing Remotion packages (npm ci) ...")
    r = subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=d, env=_tool_env(node), stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        sys.exit("npm ci failed. Check your network and run: python scripts/vs.py setup-remotion")
    (d / "node_modules" / ".vs-lock").write_text(_lock_hash(), encoding="utf-8")


def _cli_js() -> Path:
    return remotion_home() / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"


def browser_dir() -> Path | None:
    base = remotion_home() / "node_modules" / ".remotion"
    if not base.exists():
        return None
    hits = [p for p in base.rglob("chrome-headless-shell*") if p.is_file() and p.suffix in ("", ".exe")]
    return hits[0] if hits else None


def ensure_browser(log=print) -> None:
    node = find_node_tool("node")
    if browser_dir():
        return
    log("downloading Remotion's headless Chrome (about 100 MB, once) ...")
    r = subprocess.run([node, str(_cli_js()), "browser", "ensure"], cwd=remotion_home(), env=_tool_env(node), stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        sys.exit("Headless browser download failed. Check your network and run: python scripts/vs.py setup-remotion")


def setup(install_node: bool = False, log=print) -> int:
    node = find_node_tool("node")
    v = node_version(node) if node else None
    if (not node or not v or v[0] < NODE_MIN) and install_node:
        install_node_portable(log)
        node = find_node_tool("node")
        v = node_version(node) if node else None
    if not node or not v or v[0] < NODE_MIN:
        log(f"Node.js {NODE_MIN}+ not found. Install it (winget install -e --id OpenJS.NodeJS.LTS, brew install node, or your package manager) "
            "or run: python scripts/vs.py setup-remotion --install-node")
        return 1
    log(f"node {'.'.join(map(str, v))} at {node}")
    sync_project()
    if not deps_installed():
        npm_ci(log)
    else:
        log("Remotion packages already installed")
    ensure_browser(log)
    cfg = C.load_config()
    cfg.setdefault("tools", {}).update({"node": node, "npm": find_node_tool("npm")})
    C.save_config(cfg)
    log("Remotion ready")
    return 0


def status() -> list[dict]:
    """Doctor checks. All optional: only spotlight and minimalist need them."""
    out = []
    add = lambda n, ok, d, fix="": out.append({"name": n, "ok": bool(ok), "detail": d, "fix": fix, "required": False})  # noqa: E731
    fix = "python scripts/vs.py setup-remotion --install-node  (the installer does this for you)"
    node, npm = find_node_tool("node"), find_node_tool("npm")
    v = node_version(node) if node else None
    add("remotion: node", bool(v and v[0] >= NODE_MIN), (f"v{'.'.join(map(str, v))} at {node}" if v else "not found") + f" (need {NODE_MIN}+)", fix)
    add("remotion: npm", npm, npm or "not found", fix)
    add("remotion: project", (remotion_home() / ".synced").exists(), str(remotion_home()), fix)
    add("remotion: npm packages", deps_installed(), "remotion 4.0.500 installed" if deps_installed() else "not installed", fix)
    b = browser_dir()
    add("remotion: headless browser", b, str(b) if b else "not downloaded", fix)
    return out


def available() -> tuple[bool, str]:
    s = status()
    bad = [r for r in s if not r["ok"]]
    if bad:
        return False, "; ".join(f"{r['name']} ({r['detail']})" for r in bad)
    return True, ""


# ----------------------------------------------------------------------------- brand -> Remotion props
def _hsv_hex(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h, max(0, min(1, s)), max(0, min(1, v)))
    return C.rgb_hex(r * 255, g * 255, b * 255)


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = C.hex_rgb(a), C.hex_rgb(b)
    return C.rgb_hex(*(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def _rgb_csv(h: str) -> str:
    return "{},{},{}".format(*C.hex_rgb(h))


def _rgba(h: str, a: float) -> str:
    return f"rgba({_rgb_csv(h)},{a})"


def _lift_for(bg: str, color: str, ratio: float = 4.5) -> str:
    """Return color, lightened or darkened in small steps until it reads on bg."""
    if C.contrast(color, bg) >= ratio:
        return color
    h, s, v = C.hsv(color)
    for _ in range(30):
        v = min(1.0, v + 0.03)
        s = max(0.0, s - 0.015)
        c = _hsv_hex(h, s, v)
        if C.contrast(c, bg) >= ratio:
            return c
    return "#FFFFFF"


def _width_factor(font_path) -> float:
    """Heading font width relative to Arial Bold (average advance about 0.56 em on a pangram)."""
    try:
        from PIL import ImageFont
        sample = "The quick brown fox jumps over the lazy dog 0123456789"
        w = ImageFont.truetype(str(font_path), 100).getlength(sample) / (len(sample) * 100 * 0.56)
        return round(max(0.8, min(1.4, w)), 3)
    except Exception:
        return 1.0


def build_brand_props(brand: dict, work_public: Path, hook_lines: list[str] | None, hook_s: float,
                      end_text: str | None, end_s: float, show_logo: bool) -> dict:
    """Turn a loaded brand.yaml into the Brand object the Remotion project reads. Copies fonts and logo into the staged public dir."""
    col = brand["colors"]
    primary, accent, bg, text = col["primary"], col["accent"], col["background"], col["text"]
    h, s, v = C.hsv(primary)
    ink = _hsv_hex(h, min(s, 0.55), 0.13) if v > 0.2 else primary
    label = C.readable_on(ink, "#F8FAFC", "#111111")
    acc_dark = _lift_for(ink, accent)
    light = C.luminance(bg) > 0.4
    mini_s = min(s, 0.75)
    outer, middle, inner = (_hsv_hex(h, mini_s, x) for x in (0.15, 0.28, 0.43))
    fonts = {}
    (work_public / "fonts").mkdir(parents=True, exist_ok=True)
    for role, nm in (("heading", "heading.ttf"), ("body", "body.ttf")):
        fnt = brand["fonts"].get(role) or {}
        p = fnt.get("_path") or (brand["fonts"]["heading"].get("_path") if role == "body" else None)
        if p and Path(p).exists():
            shutil.copyfile(p, work_public / "fonts" / nm)
            fonts[role] = {"family": fnt.get("family") or "brand", "file": f"fonts/{nm}"}
        else:
            fonts[role] = {"family": "Arial", "file": None}
    head_path = work_public / "fonts" / "heading.ttf"
    logo = brand.get("logo") or {}
    logo_file = None
    if show_logo and logo.get("show_in_videos") and logo.get("_path") and Path(logo["_path"]).exists():
        ext = Path(logo["_path"]).suffix.lower() or ".png"
        shutil.copyfile(logo["_path"], work_public / f"logo{ext}")
        logo_file = f"logo{ext}"
    return {
        "name": brand.get("name", ""),
        "colors": {"primary": primary, "accent": accent, "background": bg, "text": text},
        "fonts": fonts,
        "logo": {"file": logo_file, "position": logo.get("position", "top-right"), "scale": float(logo.get("scale") or 0.16)},
        "theme": {
            "ink": ink, "label": label, "accentOnDark": acc_dark, "accentRgb": _rgb_csv(accent), "gridLight": light,
            "bg": [_mix(bg, primary, 0.0), _mix(bg, primary, 0.05), _mix(bg, primary, 0.12)] if light
            else [_mix(bg, "#FFFFFF", 0.10), bg, _mix(bg, "#000000", 0.35)],
            "tileRgb": _rgb_csv(text) if light else "245,243,238", "vignetteRgb": _rgb_csv(primary),
            "mini": {"inner": inner, "middle": middle, "outer": outer, "text": C.readable_on(middle, "#F8FAFC", "#111111"),
                     "highlight": _lift_for(middle, accent)},
            "hookBox": _rgba(primary, 0.92), "hookText": C.readable_on(primary, "#FFFFFF", "#111111"),
            "endBox": _rgba(accent, 0.95), "endText": C.readable_on(accent, "#FFFFFF", "#111111"),
            "widthFactor": _width_factor(head_path) if head_path.exists() else 1.0,
        },
        **({"hook": {"lines": hook_lines, "seconds": hook_s}} if hook_lines else {}),
        **({"endCard": {"text": end_text, "seconds": end_s}} if end_text else {}),
    }


# ----------------------------------------------------------------------------- plans from the cleaned transcript
STOP = set("a an the and or but if so to of in on at for with from by as is are was were be been it its this that these those i you he she we they "
           "my your our their me him her us them do does did have has had will would can could should just very really then than there here what "
           "when where who how why not no yes also about into over up out one number".split())
ICON_KEYS = [
    ("headphones", "listen audio sound hear podcast music voice"),
    ("scissors", "cut cuts trim remove short shorter delete dead pause pauses silence"),
    ("on-camera", "camera film record speak talk talking face video clip footage"),
    ("stunning-visuals", "visual visuals screen edit editing animation graphic design zoom"),
    ("text-and-image", "caption captions text subtitle words image"),
    ("simple-image", "image picture photo logo brand color colors"),
    ("reading-level", "read reading write writing simple plain level"),
    ("clear-answer", "answer clear understand explain idea point message"),
    ("rules", "rule rules step steps way ways plan process list number tip tips method"),
    ("overthink", "think thinking worry confused confusing mistake problem hard"),
    ("customize", "custom customize setting settings change adjust own personal"),
    ("business", "business product service company customer client sell sales offer"),
]
ICON_ORDER = [i for i, _ in ICON_KEYS]


def _split_long(words: list[dict], g: list[int], max_s: float, min_s: float) -> list[list[int]]:
    """Split a long run of words at its widest gaps so no piece is much longer than max_s or shorter than min_s."""
    def dur(idx):
        return words[idx[-1]]["oe"] - words[idx[0]]["os"]
    if dur(g) <= max_s or len(g) < 4:
        return [g]
    best, best_gap = None, -1.0
    for k in range(1, len(g)):
        left, right = g[:k], g[k:]
        if dur(left) < min_s or dur(right) < min_s:
            continue
        gap = words[g[k]]["os"] - words[g[k - 1]]["oe"]
        if gap > best_gap:
            best, best_gap = k, gap
    if best is None:
        return [g]
    return _split_long(words, g[:best], max_s, min_s) + _split_long(words, g[best:], max_s, min_s)


def sentences(words: list[dict], gap: float = 0.7, min_s: float = 1.3, max_s: float = 6.0) -> list[dict]:
    """Group output-timeline words into sentences. Each: {i0, i1, s, e}.
    Splits at sentence punctuation and long pauses, splits long runs at their widest pauses, merges tiny groups."""
    groups, cur = [], []
    for i, w in enumerate(words):
        if cur and w["os"] - words[cur[-1]]["oe"] > gap:
            groups.append(cur)
            cur = []
        cur.append(i)
        if re.search(r"[.?!]$", w["w"]):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    pieces: list[list[int]] = []
    for g in groups:
        pieces += _split_long(words, g, max_s, max(min_s, 1.8))
    out: list[dict] = []
    for g in pieces:
        item = {"i0": g[0], "i1": g[-1], "s": words[g[0]]["os"], "e": words[g[-1]]["oe"]}
        if out and (out[-1]["e"] - out[-1]["s"]) < min_s:
            out[-1] = {"i0": out[-1]["i0"], "i1": item["i1"], "s": out[-1]["s"], "e": item["e"]}
        else:
            out.append(item)
    if len(out) > 1 and (out[-1]["e"] - out[-1]["s"]) < min_s:
        last = out.pop()
        out[-1] = {"i0": out[-1]["i0"], "i1": last["i1"], "s": out[-1]["s"], "e": last["e"]}
    return out


def _core(w: str) -> str:
    return re.sub(r"[^A-Za-z0-9']", "", w)


def key_words(tokens: list[str], limit: int = 3) -> list[str]:
    cands = [(i, _core(t)) for i, t in enumerate(tokens) if _core(t) and _core(t).lower() not in STOP and _core(t).lower() not in NUMBER_WORDS and not _core(t).isdigit()]
    if not cands:
        cands = [(i, _core(t)) for i, t in enumerate(tokens) if _core(t)][:2]
    pick = sorted(sorted(cands, key=lambda x: (-len(x[1]), x[0]))[:limit], key=lambda x: x[0])
    return [w[:1].upper() + w[1:] for _, w in pick] or ["Listen"]


def plan_spotlight(words: list[dict], total: float, case: str, extra_emph: set[str]) -> dict:
    """Spotlight job: full frame opening, window home position, large-panel moments, key-phrase graphics."""
    sents = sentences(words)
    cap_words = []
    for w in words:
        t = w["w"].replace("\\", "")
        t = t.upper() if case == "upper" else t.lower() if case == "lower" else t
        item = {"t": t, "s": round(w["os"], 3), "e": round(w["oe"], 3)}
        if re.search(r"\d", t) or _core(t).lower() in extra_emph:
            item["h"] = 1
        cap_words.append(item)
    scenes = [{"from": 0, "mode": "full"}]
    swaps, beats = [], []
    if total >= 5 and len(sents) >= 2:
        first_end = min(max(sents[0]["e"], 2.0), 4.5)
        scenes.append({"from": round(first_end, 3), "mode": "window"})
        prev_end = first_end
        for n, s in enumerate(sents[1:], start=1):
            last = n == len(sents) - 1
            if (n % 3 == 0 or last) and s["e"] - prev_end >= 2.0 and not (swaps and abs(swaps[-1]["out"] - prev_end) < 1e-6):
                swaps.append({"in": round(prev_end, 3), "out": 999 if last else round(s["e"], 3)})
            elif s["e"] - s["s"] >= 1.5:
                toks = [words[i]["w"] for i in range(s["i0"], s["i1"] + 1)]
                beats.append({"start": round(s["s"], 3), "end": round(s["e"], 3), "words": key_words(toks)})
            prev_end = s["e"]
    return {"words": cap_words, "scenes": scenes, "swaps": swaps, "beats": beats}


def pick_icon(text: str, used: dict[str, int], start: int) -> str:
    low = set(re.findall(r"[a-z']+", text.lower()))
    for icon, keys in ICON_KEYS:
        if used.get(icon, 0) < 2 and low & set(keys.split()):
            used[icon] = used.get(icon, 0) + 1
            return icon
    for k in range(len(ICON_ORDER)):
        icon = ICON_ORDER[(start + k) % len(ICON_ORDER)]
        if used.get(icon, 0) < 1:
            used[icon] = used.get(icon, 0) + 1
            return icon
    icon = min(ICON_ORDER, key=lambda i: used.get(i, 0))
    used[icon] = used.get(icon, 0) + 1
    return icon


def _offset(i: int) -> float:
    offs = [0, 4, 8.25, 15.45, 19.65, 23.65]
    return offs[i] if i < len(offs) else offs[5] + 4 * (i - 5)


NUMBER_WORDS = set("one two three four five six seven eight nine ten eleven twelve first second third fourth fifth".split())


def clean_clause(tokens: list[str], max_words: int = 6) -> list[str]:
    """Pick the first clause of a sentence for on-screen text: drop list markers ('number two'), stop at a comma,
    cap the length and do not end on a function word."""
    toks = [t for t in tokens if _core(t)]
    out: list[str] = []
    i = 0
    while i < len(toks):
        low = _core(toks[i]).lower()
        if low == "number" and (i + 1 >= len(toks) or _core(toks[i + 1]).lower() in NUMBER_WORDS or re.fullmatch(r"\d+", _core(toks[i + 1]))):
            i += 2
            continue
        out.append(toks[i])
        if toks[i].endswith(",") and len(out) >= 3:
            break
        i += 1
    out = out[:max_words]
    while len(out) > 2 and _core(out[-1]).lower() in STOP | {"number"}:
        out.pop()
    return [re.sub(r"[;:,]+$", "", t).replace("\\", "") for t in out]


def plan_minimalist(words: list[dict], total_frames: int, hook_s: float, end_s: float, width_factor: float) -> dict:
    """Minimalist plan: one takeover per chosen sentence, with at least three seconds of speaker between takeovers."""
    sents = sentences(words, min_s=1.0)
    first_ok = max(75, int(hook_s * 30) + 10)
    tail = int(end_s * 30) + 30 if end_s else 30
    takeovers, used = [], {}
    last_end = 0
    for s in sents:
        start_f = int(round(s["s"] * 30))
        if start_f < max(first_ok, last_end + 24 + 90):
            continue
        clause = clean_clause([words[i]["w"] for i in range(s["i0"], s["i1"] + 1)])
        n = len(clause)
        max_chars = int(26 / max(1.0, width_factor))
        while n > 2 and max(len(" ".join(clause[:(n + 1) // 2])), len(" ".join(clause[(n + 1) // 2:])) if n > 3 else len(" ".join(clause))) > max_chars:
            clause = clause[:-1]
            n = len(clause)
        if n < 1:
            continue
        end_f = int(start_f + 10 + _offset(n - 1) + 17 + 42)
        if end_f + 25 > total_frames - tail:
            break
        emph_i = next((i for i, t in enumerate(clause) if re.search(r"\d", t)), None)
        if emph_i is None:
            long_i = max(range(n), key=lambda i: (len(_core(clause[i])), -i))
            emph_i = long_i if len(_core(clause[long_i])) >= 6 and n > 1 else None
        item = {
            "id": f"t{len(takeovers) + 1}", "startFrame": start_f, "endFrame": end_f, "variant": "single-centered",
            "words": [{"text": t, **({"emphasis": True} if i == emph_i else {})} for i, t in enumerate(clause)],
            "icon": f"icons/{pick_icon(' '.join(clause), used, len(takeovers))}.svg",
        }
        if n > 3:
            item["lineBreaks"] = [(n + 1) // 2]
        takeovers.append(item)
        last_end = end_f
    return {"schemaVersion": 1, "treatmentVersion": "1.2", "returnCadence": "alternating", "canvas": "portrait",
            "fontWidthFactor": width_factor, "takeovers": takeovers}


def validate_minimalist(plan: dict, work: Path) -> dict:
    node = find_node_tool("node")
    p = work / "minimalist-plan.json"
    p.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    script = remotion_home() / "validate-plan.mjs"
    r = subprocess.run([node, str(script), str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=_tool_env(node), stdin=subprocess.DEVNULL)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"valid": False, "errors": [(r.stderr or r.stdout)[-500:]], "warnings": []}


# ----------------------------------------------------------------------------- stage + render
def stage_public(work: Path, cut_src: Path) -> Path:
    pub = work / "remotion_public"
    shutil.rmtree(pub, ignore_errors=True)
    (pub / "host").mkdir(parents=True)
    shutil.copyfile(cut_src, pub / "host" / "cut.mp4")
    shutil.copytree(remotion_home() / "public" / "icons", pub / "icons", ignore=shutil.ignore_patterns("index.json"))
    return pub


def render_picture(composition: str, props: dict, pub: Path, out_mp4: Path, work: Path) -> None:
    node = find_node_tool("node")
    pj = work / f"{composition.lower()}-props.json"
    pj.write_text(json.dumps(props, indent=1), encoding="utf-8")
    cmd = [node, str(_cli_js()), "render", "src/index.tsx", composition, str(out_mp4), f"--props={pj}", f"--public-dir={pub}",
           "--muted", "--crf=18", "--concurrency=2", "--timeout=180000", "--log=warn"]
    r = subprocess.run(cmd, cwd=remotion_home(), env=_tool_env(node), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not out_mp4.exists():
        tail = ((r.stderr or "") + (r.stdout or ""))[-2500:]
        sys.exit(f"Remotion render failed ({r.returncode}).\n{tail}\nFallback: use --style spotlight-lite (FFmpeg only).")
