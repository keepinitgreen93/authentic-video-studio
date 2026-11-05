#!/usr/bin/env python3
"""Branding onboarding: build brand.yaml from a website, a logo, a brand kit, or plain answers.

Examples:
  python brand_extract.py --url https://example.com --out brand
  python brand_extract.py --logo my-logo.png --out brand
  python brand_extract.py --kit brand-guide.pdf --out brand
  python brand_extract.py --name "Acme" --primary "#0A7" --heading-font "Montserrat" --out brand
  python brand_extract.py --url https://example.com --logo logo.svg --name "Acme" --out brand   (sources combine)
  python brand_extract.py edit brand --set colors.primary=#E11D48 --set cta.keyword=START
  python brand_extract.py preview brand

Priority when sources disagree: your answers > brand kit > website > logo palette.
Nothing is uploaded. The only network calls are the page you name and Google Fonts downloads.
"""
from __future__ import annotations

import argparse
import colorsys
import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vs_common as C  # noqa: E402

UA = "Mozilla/5.0 (compatible; AuthenticVideoStudio/1.0; brand-onboarding)"
GENERIC_FONTS = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-sans-serif", "ui-serif",
                 "ui-monospace", "inherit", "initial", "unset", "-apple-system", "blinkmacsystemfont", "emoji",
                 "math", "fangsong", "ui-rounded", "revert", "segoe ui", "roboto", "helvetica neue", "helvetica",
                 "arial", "apple color emoji", "segoe ui emoji", "segoe ui symbol", "noto color emoji", "oxygen",
                 "ubuntu", "cantarell", "fira sans", "droid sans", "sans", "var"}
ICON_FONT_HINT = re.compile(r"icon|awesome|glyph|symbol|material|dingbat|emoji|fontello|ionicons", re.I)

# Common commercial / system faces -> close Google Fonts match
GOOGLE_ALTERNATIVES = {
    "helvetica": "Inter", "helvetica neue": "Inter", "arial": "Arimo", "proxima nova": "Montserrat",
    "gotham": "Montserrat", "futura": "Jost", "avenir": "Nunito Sans", "avenir next": "Nunito Sans",
    "circular": "DM Sans", "circular std": "DM Sans", "sf pro": "Inter", "sf pro display": "Inter",
    "san francisco": "Inter", "segoe ui": "Open Sans", "calibri": "Carlito", "cambria": "Caladea",
    "georgia": "Gelasio", "times new roman": "Tinos", "times": "Tinos", "garamond": "EB Garamond",
    "gill sans": "Lato", "myriad pro": "Source Sans 3", "din": "Barlow", "din pro": "Barlow",
    "akzidenz-grotesk": "Inter", "univers": "Inter", "frutiger": "Open Sans", "trebuchet ms": "Fira Sans",
    "verdana": "DejaVu Sans", "tahoma": "Noto Sans", "courier new": "Cousine", "brandon grotesque": "Montserrat",
    "gt walsheim": "DM Sans", "graphik": "Inter", "sofia pro": "Poppins", "museo sans": "Nunito",
    "lato": "Lato", "bebas neue": "Bebas Neue", "impact": "Anton", "optima": "Marcellus", "didot": "Playfair Display",
    "bodoni": "Libre Bodoni", "baskerville": "Libre Baskerville", "rockwell": "Roboto Slab",
    "trade gothic": "Barlow Condensed", "franklin gothic": "Libre Franklin", "ibm plex sans": "IBM Plex Sans",
}
SERIF_HINT = re.compile(r"serif(?!.*sans)|garamond|georgia|times|baskerville|didot|bodoni|caslon|palatino|minion|merriweather|playfair|lora", re.I)
MONO_HINT = re.compile(r"mono|code|courier|consolas|menlo", re.I)
SCRIPT_HINT = re.compile(r"script|hand|brush|pacifico|cursive", re.I)


# ---------------------------------------------------------------- utils
def say(msg: str) -> None:
    print(msg, flush=True)


def http_get(url: str, binary=False, timeout=25, **kw):
    import requests
    r = requests.get(url, headers={"User-Agent": kw.pop("ua", UA), "Accept-Language": "en"}, timeout=timeout, **kw)
    r.raise_for_status()
    return r.content if binary else r.text


def parse_css_color(tok: str) -> str | None:
    tok = tok.strip().lower()
    if tok.startswith("#"):
        return C.norm_hex(tok)
    m = re.match(r"rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)(?:[\s,/]+([\d.]+%?))?\s*\)", tok)
    if m:
        vals = []
        for v in m.groups()[:3]:
            vals.append(float(v[:-1]) * 2.55 if v.endswith("%") else float(v))
        a = m.group(4)
        if a is not None:
            af = float(a[:-1]) / 100 if a.endswith("%") else float(a)
            if af < 0.5:
                return None
        return C.rgb_hex(*vals)
    m = re.match(r"hsla?\(\s*([\d.]+)(?:deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%", tok)
    if m:
        h, s, l = float(m.group(1)) / 360, float(m.group(2)) / 100, float(m.group(3)) / 100
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return C.rgb_hex(r * 255, g * 255, b * 255)
    return None


COLOR_TOKEN = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)")


def is_chromatic(h: str, min_sat=0.25, min_val=0.18) -> bool:
    hh, s, v = C.hsv(h)
    return s >= min_sat and v >= min_val


def hue_dist(a: str, b: str) -> float:
    d = abs(C.hsv(a)[0] - C.hsv(b)[0]) * 360
    return min(d, 360 - d)


# ---------------------------------------------------------------- website
def extract_website(url: str, out: Path, allow_site_fonts: bool) -> dict:
    from bs4 import BeautifulSoup
    if not re.match(r"https?://", url):
        url = "https://" + url
    say(f"[web] fetching {url}")
    html = http_get(url)
    soup = BeautifulSoup(html, "html.parser")
    res: dict = {"source": "website", "url": url, "notes": []}

    def meta(*names):
        for n in names:
            t = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if t and t.get("content"):
                return t["content"].strip()
        return None

    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    site_name = meta("og:site_name", "application-name") or ""
    if not site_name and title:
        site_name = re.split(r"\s[\|\-–—:·•]\s", title)[0].strip()
    if not site_name:
        site_name = urlparse(url).netloc.replace("www.", "").split(".")[0].title()
    desc = meta("og:description", "description", "twitter:description") or ""
    h1 = soup.find("h1")
    h1t = re.sub(r"\s+", " ", h1.get_text(" ", strip=True))[:160] if h1 else ""
    res.update(name=site_name[:80], tagline=(desc or h1t)[:200], title=title[:160], h1=h1t,
               headings=[re.sub(r"\s+", " ", h.get_text(" ", strip=True))[:100] for h in soup.find_all(["h1", "h2"])[:8]])
    cta_btn = None
    for a in soup.find_all(["a", "button"]):
        cls = " ".join(a.get("class", [])) if a.get("class") else ""
        txt = a.get_text(" ", strip=True)
        if txt and 2 <= len(txt) <= 30 and re.search(r"btn|button|cta", cls, re.I) and not re.search(r"cookie|accept|consent|reject|privacy|close|menu|search|log ?in|sign ?in|skip|pause|play|animation|toggle|language|translate|dismiss", txt + " " + cls, re.I):
            cta_btn = txt
            break
    res["cta_text"] = cta_btn

    # ----- CSS
    css_chunks = [s.get_text() for s in soup.find_all("style")]
    sheets, fonts_links = [], []
    for l in soup.find_all("link"):
        rel = " ".join(l.get("rel", [])).lower() if l.get("rel") else ""
        href = l.get("href")
        if not href:
            continue
        full = urljoin(url, href)
        if "fonts.googleapis.com" in full:
            fonts_links.append(full)
        elif "stylesheet" in rel:
            sheets.append(full)
    for s in sheets[:8]:
        try:
            css_chunks.append(http_get(s, timeout=15)[:1_500_000])
        except Exception as e:  # noqa
            res["notes"].append(f"stylesheet skipped: {s} ({type(e).__name__})")
    css = "\n".join(css_chunks) + "\n" + "\n".join(t.get("style", "") for t in soup.find_all(style=True))
    css_nocomment = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    # CSS variables
    varcolors = {}
    for m in re.finditer(r"--([\w-]+)\s*:\s*([^;}{]+)[;}]", css_nocomment):
        toks = COLOR_TOKEN.findall(m.group(2))
        if toks:
            c = parse_css_color(toks[0])
            if c:
                varcolors.setdefault(m.group(1).lower(), c)
    res["css_vars"] = varcolors

    counts: Counter = Counter()
    for tok in COLOR_TOKEN.findall(css_nocomment):
        c = parse_css_color(tok)
        if c:
            counts[c] += 1
    score: Counter = Counter()
    for c, n in counts.items():
        if is_chromatic(c):
            score[c] += n
    for name, c in varcolors.items():
        if not is_chromatic(c):
            continue
        if re.search(r"primary|brand|main|theme|key", name):
            score[c] += 200
        elif re.search(r"accent|highlight|secondary|cta|action|link", name):
            score[c] += 90
    tc = meta("theme-color", "msapplication-TileColor")
    if tc:
        c = parse_css_color(tc)
        if c and is_chromatic(c, 0.15, 0.1):
            score[c] += 150
            res["theme_color"] = c
    res["color_scores"] = [[c, n] for c, n in score.most_common(12)]
    res["all_colors"] = [[c, n] for c, n in counts.most_common(15)]

    # body background / text
    bg = fg = None
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css_nocomment):
        sel = m.group(1).strip().lower()
        if re.search(r"(^|,)\s*(html|body|:root)\s*(,|$)", sel):
            d = m.group(2)
            mb = re.search(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", d)
            if mb and not bg:
                t = COLOR_TOKEN.findall(mb.group(1))
                bg = parse_css_color(t[0]) if t else (C.norm_hex("#FFFFFF") if re.search(r"\bwhite\b", mb.group(1)) else None)
            mf = re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", d)
            if mf and not fg:
                t = COLOR_TOKEN.findall(mf.group(1))
                fg = parse_css_color(t[0]) if t else None
    for name in ("background", "bg", "body-bg", "color-background", "surface"):
        if not bg and varcolors.get(name):
            bg = varcolors[name]
    for name in ("foreground", "text", "body-color", "color-text", "ink"):
        if not fg and varcolors.get(name):
            fg = varcolors[name]
    res["background"], res["text"] = bg, fg

    # ----- fonts
    fam_count: Counter = Counter()
    heading_fams: Counter = Counter()
    body_fams: Counter = Counter()
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css_nocomment):
        sel, d = m.group(1).strip().lower(), m.group(2)
        mf = re.search(r"font-family\s*:\s*([^;]+)", d)
        if not mf:
            continue
        fams = [f.strip().strip("'\"") for f in mf.group(1).split(",")]
        first = next((f for f in fams if f and f.lower() not in GENERIC_FONTS and not f.startswith("var(")
                      and not ICON_FONT_HINT.search(f)), None)
        if not first:
            continue
        fam_count[first] += 1
        if re.search(r"(^|[\s,.#>])h[1-3]\b|heading|title|display|hero", sel):
            heading_fams[first] += 1
        if re.search(r"(^|,)\s*(html|body|:root|p)\s*(,|$)", sel):
            body_fams[first] += 1
    for name, c in list(varcolors.items()):
        pass
    for m in re.finditer(r"--([\w-]*font[\w-]*)\s*:\s*([^;}{]+)", css_nocomment):
        if re.search(r"size|weight|style|height|spacing|stretch|variant|feature", m.group(1), re.I) or re.match(r"\s*[\d.\-]", m.group(2)):
            continue
        fams = [f.strip().strip("'\"") for f in m.group(2).split(",")]
        first = next((f for f in fams if f and f.lower() not in GENERIC_FONTS and not f.startswith("var(")
                      and not ICON_FONT_HINT.search(f)), None)
        if first:
            fam_count[first] += 1
            if re.search(r"head|title|display", m.group(1), re.I):
                heading_fams[first] += 2
            elif re.search(r"body|text|base|sans", m.group(1), re.I):
                body_fams[first] += 2
    ff_faces = {}
    for m in re.finditer(r"@font-face\s*\{([^}]*)\}", css_nocomment):
        d = m.group(1)
        fm = re.search(r"font-family\s*:\s*['\"]?([^;'\"]+)", d)
        if not fm:
            continue
        fam = fm.group(1).strip()
        urls = re.findall(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", d)
        wt = re.search(r"font-weight\s*:\s*(\d+)", d)
        ff_faces.setdefault(fam, []).append({"urls": [urljoin(url, u) for u in urls], "weight": int(wt.group(1)) if wt else 400})
    google = {}
    for link in fonts_links:
        for fm in re.finditer(r"family=([^&:]+)", link):
            google[fm.group(1).replace("+", " ")] = True
    for fam in re.findall(r"@import\s+url\([^)]*fonts\.googleapis\.com[^)]*family=([^&:)'\"]+)", css_nocomment):
        google[fam.replace("+", " ")] = True
    res["fonts"] = {"google": list(google), "font_face": {k: len(v) for k, v in ff_faces.items()},
                    "heading_candidates": heading_fams.most_common(3), "body_candidates": body_fams.most_common(3),
                    "frequent": fam_count.most_common(5)}
    heading = (heading_fams.most_common(1) or [(None, 0)])[0][0] or (list(google)[0] if google else None) or \
              (fam_count.most_common(1) or [(None, 0)])[0][0]
    body = (body_fams.most_common(1) or [(None, 0)])[0][0] or (list(google)[-1] if google else None) or \
           (fam_count.most_common(1) or [(None, 0)])[0][0]
    res["heading_font"], res["body_font"] = heading, body
    res["_ff_faces"] = ff_faces
    res["_allow_site_fonts"] = allow_site_fonts

    # ----- logo
    logo_path = find_site_logo(soup, url, out, res)
    res["logo_file"] = logo_path
    return res


def find_site_logo(soup, base_url: str, out: Path, res: dict) -> str | None:
    cands: list[tuple[int, str, str]] = []  # (priority, kind, url or svg markup)
    for img in soup.find_all("img"):
        blob = " ".join([img.get("src", ""), img.get("alt", ""), " ".join(img.get("class", []) or []), img.get("id", "") or ""]).lower()
        if "logo" in blob or "brand" in blob:
            src = img.get("src") or img.get("data-src")
            if src and not src.startswith("data:"):
                inheader = bool(img.find_parent(["header", "nav"]))
                cands.append((0 if inheader else 1, "url", urljoin(base_url, src)))
    for svg in soup.find_all("svg"):
        blob = " ".join([" ".join(svg.get("class", []) or []), svg.get("id", "") or "", svg.get("aria-label", "") or ""]).lower()
        par = svg.find_parent(["a", "div", "span", "header"])
        pblob = " ".join(par.get("class", []) or []).lower() if par else ""
        if "logo" in blob or "logo" in pblob:
            markup = str(svg)
            if "xmlns" not in markup[:200]:
                markup = markup.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            cands.append((1, "svg", markup))
    for l in soup.find_all("link"):
        rel = " ".join(l.get("rel", [])).lower() if l.get("rel") else ""
        if "apple-touch-icon" in rel and l.get("href"):
            cands.append((3, "url", urljoin(base_url, l["href"])))
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        cands.append((4, "url", urljoin(base_url, og["content"])))
    for l in soup.find_all("link"):
        rel = " ".join(l.get("rel", [])).lower() if l.get("rel") else ""
        if "icon" in rel and l.get("href") and "apple" not in rel:
            u = urljoin(base_url, l["href"])
            cands.append((5 if u.lower().endswith(".svg") else 6, "url", u))
    cands.append((7, "url", urljoin(base_url, "/favicon.ico")))
    cands.sort(key=lambda t: t[0])
    out.mkdir(parents=True, exist_ok=True)
    tried = 0
    for prio, kind, val in cands:
        if tried >= 8:
            break
        tried += 1
        try:
            if kind == "svg":
                data, ext = val.encode("utf-8"), ".svg"
            else:
                data = http_get(val, binary=True, timeout=20)
                ext = Path(urlparse(val).path).suffix.lower() or ".png"
                if data[:200].lstrip().startswith(b"<") and b"<svg" in data[:2000]:
                    ext = ".svg"
            raw = out / ("logo-original" + (ext if ext in (".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif") else ".png"))
            raw.write_bytes(data)
            png = normalise_logo(raw, out / "logo.png")
            if png:
                res["logo_source"] = val if kind == "url" else "inline <svg>"
                res["logo_kind"] = "logo" if prio <= 2 else ("share-image/icon (not a true logo)" if prio >= 3 else "icon")
                return str(png)
        except Exception as e:  # noqa
            res["notes"].append(f"logo candidate failed: {str(val)[:80]} ({type(e).__name__})")
    return None


# ---------------------------------------------------------------- logo
def normalise_logo(src: Path, dst: Path, width=1000) -> Path | None:
    """Convert any logo (svg/png/jpg/webp/ico) to a trimmed RGBA PNG."""
    from PIL import Image, ImageChops
    ext = src.suffix.lower()
    if ext == ".svg":
        import resvg_py
        png_bytes = bytes(resvg_py.svg_to_bytes(svg_string=src.read_text(encoding="utf-8", errors="replace"), width=width))
        im = Image.open(io.BytesIO(png_bytes))
    else:
        im = Image.open(src)
    im = im.convert("RGBA")
    if im.width < 8 or im.height < 8:
        return None
    # opaque white/black background (JPG) -> make it transparent if the four corners agree
    px = im.load()
    corners = [px[0, 0], px[im.width - 1, 0], px[0, im.height - 1], px[im.width - 1, im.height - 1]]
    if all(c[3] == 255 for c in corners) and len({c[:3] for c in corners}) == 1:
        bgc = corners[0][:3]
        diff = ImageChops.difference(im.convert("RGB"), Image.new("RGB", im.size, bgc)).convert("L")
        mask = diff.point(lambda v: 0 if v < 24 else 255)
        if mask.getbbox() and sum(1 for v in mask.getdata() if v == 0) > 0.1 * im.width * im.height:
            im.putalpha(mask)
    bbox = im.getchannel("A").getbbox()
    if bbox:
        im = im.crop(bbox)
    if im.width > width:
        im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
    im.save(dst)
    return dst


def logo_palette(png: Path, n=6) -> list[tuple[str, float]]:
    """Dominant colours of a logo, ignoring transparent pixels. Returns [(hex, share)]."""
    from PIL import Image
    im = Image.open(png).convert("RGBA")
    im.thumbnail((160, 160))
    buckets: dict = {}
    w, h = im.size
    px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 140:
                continue
            k = (r >> 4, g >> 4, b >> 4)
            s = buckets.setdefault(k, [0, 0, 0, 0])
            s[0] += r; s[1] += g; s[2] += b; s[3] += 1
    total = sum(v[3] for v in buckets.values()) or 1
    items = sorted(buckets.values(), key=lambda v: -v[3])[:40]
    merged: list[list] = []
    for sr, sg, sb, k in items:
        avg = (sr / k, sg / k, sb / k)
        for m in merged:
            if sum(abs(x - y) for x, y in zip(m[0], avg)) < 60:
                t = m[1] + k
                m[0] = tuple((m[0][i] * m[1] + avg[i] * k) / t for i in range(3))
                m[1] = t
                break
        else:
            merged.append([avg, k])
    merged.sort(key=lambda m: -m[1])
    return [(C.rgb_hex(*m[0]), m[1] / total) for m in merged[:n]]


def extract_logo(path: str, out: Path) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Logo file not found: {p}")
    out.mkdir(parents=True, exist_ok=True)
    png = normalise_logo(p, out / "logo.png")
    if not png:
        sys.exit("Logo image is too small or unreadable.")
    pal = logo_palette(png)
    say(f"[logo] palette: " + ", ".join(f"{h} ({s:.0%})" for h, s in pal))
    return {"source": "logo", "logo_file": str(png), "palette": pal, "original": str(p)}


# ---------------------------------------------------------------- brand kit
ROLE_WORDS = [("primary", r"primary|main|brand colou?r|core"), ("accent", r"accent|secondary|highlight|cta"),
              ("background", r"background|backdrop|canvas|surface|paper"), ("text", r"text|body copy|ink|type colou?r|foreground")]


def kit_text_colours(text: str) -> tuple[list[tuple[str, str | None]], list[str]]:
    found: list[tuple[str, str | None]] = []
    for m in re.finditer(r"#([0-9a-fA-F]{6})\b|rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)|\bRGB[:\s]+(\d{1,3})[,\s]+(\d{1,3})[,\s]+(\d{1,3})", text):
        if m.group(1):
            c = C.norm_hex("#" + m.group(1))
        elif m.group(2):
            c = C.rgb_hex(int(m.group(2)), int(m.group(3)), int(m.group(4)))
        else:
            c = C.rgb_hex(int(m.group(5)), int(m.group(6)), int(m.group(7)))
        ctx = text[max(0, m.start() - 60):m.start()].lower()
        role = None
        for r, pat in ROLE_WORDS:
            if re.search(pat, ctx):
                role = r
        found.append((c, role))
    fonts = []
    for m in re.finditer(r"(?:typeface|font|heading|headline|body)s?\s*[:\-–]\s*([A-Z][A-Za-z0-9 ]{2,30})", text):
        fonts.append(m.group(1).strip())
    return found, fonts


def extract_kit(path: str, out: Path) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Brand kit not found: {p}")
    work = Path(out) / "_kit"
    files: list[Path] = []
    if p.is_dir():
        files = [f for f in p.rglob("*") if f.is_file()]
    elif p.suffix.lower() == ".zip":
        work.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                if info.is_dir() or info.file_size > 60_000_000:
                    continue
                dest = (work / info.filename).resolve()
                if not str(dest).startswith(str(work.resolve())):
                    continue  # zip slip
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(info))
                files.append(dest)
    else:
        files = [p]
    res: dict = {"source": "kit", "colors": [], "font_names": [], "font_files": [], "logo_candidates": [], "notes": []}
    texts: list[str] = []
    for f in files:
        ext = f.suffix.lower()
        low = f.name.lower()
        if ext in (".ttf", ".otf"):
            res["font_files"].append(str(f))
        elif ext in (".woff", ".woff2"):
            res["font_files"].append(str(f))
        elif ext in (".png", ".svg", ".jpg", ".jpeg", ".webp"):
            if re.search(r"logo|mark|wordmark|brand", low):
                res["logo_candidates"].append(str(f))
        elif ext == ".pdf":
            try:
                from pypdf import PdfReader
                rd = PdfReader(str(f))
                for page in rd.pages[:40]:
                    texts.append(page.extract_text() or "")
                    try:
                        for fn, fo in (page["/Resources"].get("/Font") or {}).items():
                            base = str(fo.get_object().get("/BaseFont", ""))
                            base = re.sub(r"^/?[A-Z]{6}\+", "", base).lstrip("/")
                            fam = re.split(r"[-,]", base)[0]
                            fam = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", fam)
                            if fam and not re.match(r"(Arial|Helvetica|Times|Courier|Symbol)", fam):
                                res["font_names"].append(fam)
                    except Exception:
                        pass
            except Exception as e:  # noqa
                res["notes"].append(f"pdf unreadable: {f.name} ({type(e).__name__})")
        elif ext == ".docx":
            try:
                with zipfile.ZipFile(f) as z:
                    xml = z.read("word/document.xml").decode("utf-8", "replace")
                texts.append(re.sub(r"<[^>]+>", " ", xml))
                res["font_names"] += re.findall(r'w:ascii="([^"]+)"', xml)
                res["colors"] += [(C.norm_hex("#" + h), None) for h in re.findall(r'w:(?:color|fill)\s+w:val="([0-9A-Fa-f]{6})"', xml)]
            except Exception as e:  # noqa
                res["notes"].append(f"docx unreadable: {f.name} ({type(e).__name__})")
        elif ext in (".md", ".txt", ".json", ".css", ".html", ".yaml", ".yml", ".ase", ".scss"):
            try:
                texts.append(f.read_text(encoding="utf-8", errors="replace")[:400_000])
            except Exception:
                pass
    for t in texts:
        cols, fonts = kit_text_colours(t)
        res["colors"] += cols
        res["font_names"] += fonts
    res["colors"] = [(c, r) for c, r in res["colors"] if c]
    res["font_names"] = [n for n, _ in Counter(res["font_names"]).most_common(6)]
    # pick the best logo: prefer svg, then png with "primary"/"full"/"color"
    def logo_rank(s):
        l = s.lower()
        return (0 if l.endswith(".svg") else 1, 0 if re.search(r"primary|full|color|colour", l) else 1, 1 if re.search(r"white|reverse|dark|mono|black|favicon|icon", l) else 0)
    res["logo_candidates"].sort(key=logo_rank)
    if res["logo_candidates"]:
        out.mkdir(parents=True, exist_ok=True)
        for cand in res["logo_candidates"][:6]:
            try:
                png = normalise_logo(Path(cand), out / "logo.png")
                if png:
                    res["logo_file"] = str(png)
                    res["palette"] = logo_palette(png)
                    break
            except Exception:
                continue
    say(f"[kit] {len(files)} files, {len(res['colors'])} colour mentions, fonts: {res['font_names'] or res['font_files'] or 'none'}")
    return res


# ---------------------------------------------------------------- fonts
WEIGHT_WORDS = re.compile(r"(?i)\b(extra|ultra|semi|demi)?[\s-]*(thin|light|regular|medium|bold|black|heavy|italic|oblique|book|roman|condensed|narrow)\b")
SPECIAL = {"source sans pro": "Source Sans 3", "source serif pro": "Source Serif 4", "source code pro": "Source Code Pro"}


def clean_font_name(name: str | None) -> str | None:
    if not name:
        return name
    n = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name.replace("_", " ").replace("-", " "))
    n = WEIGHT_WORDS.sub("", n)
    n = re.sub(r"\s+", " ", n).strip()
    return SPECIAL.get(n.lower(), n) or name


def google_family_for(name: str | None, role: str) -> tuple[str, str]:
    """Return (google family, reason)."""
    if name:
        key = name.lower().strip()
        if key in GOOGLE_ALTERNATIVES:
            return GOOGLE_ALTERNATIVES[key], f"closest Google Font to '{name}'"
        if SERIF_HINT.search(name):
            return ("Playfair Display" if role == "heading" else "Lora"), f"'{name}' looks like a serif; closest Google Font"
        if MONO_HINT.search(name):
            return "JetBrains Mono", f"'{name}' looks monospaced; closest Google Font"
        if SCRIPT_HINT.search(name):
            return "Pacifico", f"'{name}' looks like a script; closest Google Font"
    return ("Poppins" if role == "heading" else "Inter"), (f"no match for '{name}'; neutral default" if name else "default")


def _pin_weight(path: Path, weight: int) -> None:
    """Google serves variable fonts for some families. libass needs a static instance, so pin the weight."""
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(str(path))
        if "fvar" not in f:
            return
        from fontTools.varLib import instancer
        axes = {a.axisTag: a for a in f["fvar"].axes}
        loc = {}
        for tag, ax in axes.items():
            if tag == "wght":
                loc[tag] = max(ax.minValue, min(ax.maxValue, weight))
            else:
                loc[tag] = ax.defaultValue
        inst = instancer.instantiateVariableFont(f, loc, updateFontNames=True)
        inst.save(str(path))
    except Exception as e:  # noqa
        print(f"[font] could not pin weight for {path.name}: {type(e).__name__}", file=sys.stderr)


def download_google_font(family: str, weights: list[int], dest_dir: Path) -> tuple[Path, int] | None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    fam_q = family.replace(" ", "+")
    for w in weights:
        for q in (f"https://fonts.googleapis.com/css2?family={fam_q}:wght@{w}&display=swap",):
            try:
                css = http_get(q, timeout=20)
            except Exception:
                continue
            m = re.search(r"src:\s*url\((https://[^)]+)\)\s*format\('(truetype|opentype)'\)", css)
            if not m:
                continue
            fn = dest_dir / f"{family.replace(' ', '')}-{w}.ttf"
            if not fn.exists():
                fn.write_bytes(http_get(m.group(1), binary=True, timeout=30))
                _pin_weight(fn, w)
            return fn, w
    try:  # family without weight axis (single-weight display fonts)
        css = http_get(f"https://fonts.googleapis.com/css2?family={fam_q}&display=swap", timeout=20)
        m = re.search(r"src:\s*url\((https://[^)]+)\)\s*format\('(truetype|opentype)'\)", css)
        if m:
            fn = dest_dir / f"{family.replace(' ', '')}-400.ttf"
            if not fn.exists():
                fn.write_bytes(http_get(m.group(1), binary=True, timeout=30))
            return fn, 400
    except Exception:
        pass
    return None


def resolve_font(role: str, wanted: str | None, info: dict, out: Path, kit_fonts: list[str], notes: list[str],
                 download=True) -> dict:
    """Return a brand.yaml font block. Tries: kit font file, site @font-face (only if allowed), Google Font, close Google match."""
    fonts_dir = out / "fonts"
    weights = [800, 700, 600, 400] if role == "heading" else [500, 400]
    block: dict = {"family": wanted or ("Poppins" if role == "heading" else "Inter"), "file": None, "source": "default",
                   "license": "", "note": ""}
    # 1. font files from a brand kit
    for f in kit_fonts:
        try:
            tmp = Path(f)
            if tmp.suffix.lower() in (".woff", ".woff2"):
                from fontTools.ttLib import TTFont
                t = TTFont(str(tmp))
                t.flavor = None
                fonts_dir.mkdir(parents=True, exist_ok=True)
                tmp = fonts_dir / (tmp.stem + ".ttf")
                t.save(str(tmp))
            fi = C.font_info(tmp)
            if wanted and wanted.lower().replace(" ", "") not in (fi["family"] + fi["typographic_family"]).lower().replace(" ", ""):
                continue
            dst = fonts_dir / tmp.name
            fonts_dir.mkdir(parents=True, exist_ok=True)
            if tmp.resolve() != dst.resolve():
                dst.write_bytes(tmp.read_bytes())
            heavy = fi["weight"] >= 600 or "bold" in fi["subfamily"].lower() or "black" in fi["full_name"].lower()
            if role == "heading" and not heavy and len(kit_fonts) > 1:
                continue
            block.update(family=fi["typographic_family"] or fi["family"], file=f"fonts/{tmp.name}", source="brand kit file",
                         license=(fi["license"] or "see font file")[:160], note="Supplied by the user's brand kit. Confirm the licence allows video use.")
            return block
        except Exception as e:  # noqa
            notes.append(f"kit font {Path(f).name} unusable: {type(e).__name__}")
    if not download:
        block["note"] = "Not downloaded (--no-download-fonts). Place a .ttf in brand/fonts and set fonts.%s.file." % role
        return block
    # 2. website @font-face (licence unknown): download only when the owner allowed it
    faces = info.get("_ff_faces", {}) if info else {}
    if wanted and wanted in faces and info.get("_allow_site_fonts"):
        for face in sorted(faces[wanted], key=lambda f: abs(f["weight"] - weights[0])):
            for u in face["urls"]:
                if re.search(r"\.(ttf|otf|woff2?)(\?|$)", u, re.I):
                    try:
                        raw = http_get(u, binary=True, timeout=30)
                        ext = ".woff2" if ".woff2" in u.lower() else (".woff" if ".woff" in u.lower() else ".ttf")
                        fonts_dir.mkdir(parents=True, exist_ok=True)
                        tmp = fonts_dir / (re.sub(r"\W+", "", wanted) + f"-{face['weight']}{ext}")
                        tmp.write_bytes(raw)
                        if ext != ".ttf":
                            from fontTools.ttLib import TTFont
                            t = TTFont(str(tmp))
                            t.flavor = None
                            ttf = tmp.with_suffix(".ttf")
                            t.save(str(ttf))
                            tmp.unlink()
                            tmp = ttf
                        block.update(family=wanted, file=f"fonts/{tmp.name}", source="website @font-face (owner confirmed licence)",
                                     license="owner confirmed", note="Downloaded because --allow-site-fonts was passed. Do not redistribute this repo with the font inside.")
                        return block
                    except Exception as e:  # noqa
                        notes.append(f"site font download failed for {wanted}: {type(e).__name__}")
    # 3. Google Fonts: exact family if it exists, else a close match
    cleaned = clean_font_name(wanted)
    exact = download_google_font(cleaned, weights, fonts_dir) if cleaned else None
    if exact and cleaned != wanted:
        notes.append(f"{role} font: website uses '{wanted}'; matched Google Font '{cleaned}' (same or renamed family)")
    if exact:
        fp, w = exact
        block.update(family=cleaned, file=f"fonts/{fp.name}", source=f"Google Fonts ({wanted} {w})",
                     license="Open font licence (Google Fonts)", note="")
        return block
    fam, reason = google_family_for(cleaned or wanted, role)
    got = download_google_font(fam, weights, fonts_dir)
    if got:
        fp, w = got
        why = ""
        if wanted:
            if wanted in faces:
                why = f"'{wanted}' is a custom font on the website, and its licence is unknown, so it was not downloaded. "
            why += f"Using {fam} instead ({reason}). Replace it by dropping your licensed .ttf in brand/fonts and setting fonts.{role}.file."
        block.update(family=fam, file=f"fonts/{fp.name}", source=f"Google Fonts substitute ({fam} {w})", license="Open font licence (Google Fonts)",
                     note=why, requested=wanted)
        notes.append(f"{role} font: {why or 'default ' + fam}")
        return block
    block["note"] = "No font could be downloaded (offline?). Renders fall back to a system font."
    notes.append(block["note"])
    return block


# ---------------------------------------------------------------- merge + write
def pick_palette(web: dict | None, kit: dict | None, logo: dict | None, answers: dict) -> tuple[dict, dict]:
    prov: dict = {}
    cols: dict = {}
    cand_scores: Counter = Counter()
    if web:
        for c, n in web.get("color_scores", []):
            cand_scores[c] += n
    # logo palette (from site logo, supplied logo or kit logo) adds weight to chromatic colours
    for src in (logo, kit):
        pal = (src or {}).get("palette") or []
        for h, share in pal:
            if is_chromatic(h):
                cand_scores[h] += int(share * 400)
    if web and web.get("logo_file"):
        try:
            for h, share in logo_palette(Path(web["logo_file"])):
                if is_chromatic(h):
                    cand_scores[h] += int(share * 300)
        except Exception:
            pass
    ranked = [c for c, _ in cand_scores.most_common(30)]
    # kit: roles stated in the text win
    if kit:
        for c, role in kit.get("colors", []):
            if role and role not in cols:
                cols[role] = c
                prov[role] = "brand kit"
        unlabeled = [c for c, r in kit.get("colors", []) if not r and is_chromatic(c)]
        for c in unlabeled:
            cand_scores[c] += 120
        ranked = [c for c, _ in cand_scores.most_common(30)]
    if "primary" not in cols and ranked:
        cols["primary"] = ranked[0]
        prov["primary"] = "most prominent brand colour (" + ("website CSS" if web else "logo/kit") + ")"
    if "primary" in cols and "accent" not in cols:
        for c in ranked:
            if c != cols["primary"] and hue_dist(c, cols["primary"]) >= 25 and C.contrast(c, cols["primary"]) > 1.2:
                cols["accent"] = c
                prov["accent"] = "next most prominent distinct colour"
                break
        if "accent" not in cols:
            h, s, v = C.hsv(cols["primary"])
            r, g, b = colorsys.hsv_to_rgb((h + 0.08) % 1, max(0.5, s), min(1, max(v, 0.9)))
            cols["accent"] = C.rgb_hex(r * 255, g * 255, b * 255)
            prov["accent"] = "derived from primary (no second brand colour found)"
    if web:
        if "background" not in cols and web.get("background"):
            cols["background"] = web["background"]
            prov["background"] = "website body background"
        if "text" not in cols and web.get("text"):
            cols["text"] = web["text"]
            prov["text"] = "website body text"
    # explicit answers override everything
    for k in ("primary", "accent", "background", "text"):
        v = C.norm_hex(str(answers.get(k, ""))) if answers.get(k) else None
        if v:
            cols[k] = v
            prov[k] = "your answer"
    cols.setdefault("primary", "#2563EB")
    prov.setdefault("primary", "default (nothing found)")
    cols.setdefault("accent", "#F59E0B")
    prov.setdefault("accent", "default (nothing found)")
    cols.setdefault("background", "#FFFFFF")
    prov.setdefault("background", "default (not found)")
    if "text" not in cols:
        cols["text"] = C.readable_on(cols["background"], "#FFFFFF", "#111827")
        prov["text"] = "chosen for contrast with background"
    # readability guard
    if C.contrast(cols["text"], cols["background"]) < 4.0:
        cols["text"] = C.readable_on(cols["background"], "#FFFFFF", "#111827")
        prov["text"] += " (adjusted for contrast)"
    return cols, prov


def build_brand(args, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    web = kit = logo = None
    answers = {k: v for k, v in vars(args).items() if v is not None and k in
               ("name", "tagline", "primary", "accent", "background", "text", "heading_font", "body_font", "cta_text",
                "keyword", "tone", "website", "handle")}
    if args.answers:
        data = Path(args.answers).read_text(encoding="utf-8")
        import yaml
        ans = yaml.safe_load(data) or {}
        for k, v in ans.items():
            answers.setdefault(k.replace("-", "_"), v)
    if args.url:
        try:
            web = extract_website(args.url, out, args.allow_site_fonts)
        except Exception as e:
            notes.append(f"website fetch failed: {type(e).__name__}: {e}")
            say(f"[web] FAILED: {e}")
    if args.kit:
        kit = extract_kit(args.kit, out)
    if args.logo:
        logo = extract_logo(args.logo, out)

    colors, prov = pick_palette(web, kit, logo, answers)
    logo_file = (logo or {}).get("logo_file") or (kit or {}).get("logo_file") or (web or {}).get("logo_file")
    if logo_file and Path(logo_file).exists() and Path(logo_file).resolve().parent == out.resolve():
        logo_rel = Path(logo_file).name
    elif logo_file:
        import shutil
        shutil.copy2(logo_file, out / "logo.png")
        logo_rel = "logo.png"
    else:
        logo_rel = None
    kit_font_files = (kit or {}).get("font_files", [])
    kit_names = (kit or {}).get("font_names", [])
    head_want = answers.get("heading_font") or (kit_names[0] if kit_names else None) or (web or {}).get("heading_font")
    body_want = answers.get("body_font") or (kit_names[1] if len(kit_names) > 1 else None) or (web or {}).get("body_font")
    dl = not args.no_download_fonts
    info = web or {}
    heading = resolve_font("heading", head_want, info, out, kit_font_files, notes, dl)
    if body_want and body_want == head_want:
        body = dict(heading)
    else:
        body = resolve_font("body", body_want, info, out, kit_font_files, notes, dl)
    name = answers.get("name") or (web or {}).get("name") or "My Brand"
    tagline = answers.get("tagline") or (web or {}).get("tagline") or ""
    cta_text = answers.get("cta_text") or (web or {}).get("cta_text") or "Follow for more"
    keyword = (answers.get("keyword") or "").upper()
    brand = {
        "schema": 1,
        "name": name,
        "tagline": tagline,
        "website": answers.get("website") or (web or {}).get("url", ""),
        "handle": answers.get("handle", ""),
        "colors": colors,
        "fonts": {"heading": {k: v for k, v in heading.items() if not k.startswith("_")},
                  "body": {k: v for k, v in body.items() if not k.startswith("_")}},
        "logo": {"file": logo_rel, "position": "top-right", "scale": 0.16, "show_in_videos": bool(logo_rel)},
        "captions": {"case": "as_spoken", "highlight_color": colors["accent"], "stroke_color": "#000000"},
        "cta": {"text": cta_text, "keyword": keyword, "end_card": "DROP {keyword} BELOW" if keyword else "{text}"},
        "voice": {"tone": answers.get("tone") or "", "headline_samples": (web or {}).get("headings", [])[:5]},
        "provenance": prov,
        "notes": notes,
    }
    report = {"web": {k: v for k, v in (web or {}).items() if not k.startswith("_")},
              "kit": {k: v for k, v in (kit or {}).items()}, "logo": logo}
    (out / "extract-report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return brand


def write_brand(brand: dict, out: Path) -> Path:
    import yaml
    header = ("# brand.yaml: read by every template style in Authentic Video Studio.\n"
              "# Edit by hand or ask your agent. Paths are relative to this file.\n")
    clean = json.loads(json.dumps(brand, default=str))
    p = out / "brand.yaml"
    p.write_text(header + yaml.safe_dump(clean, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    return p


# ---------------------------------------------------------------- preview card
def preview_card(brand_dir: Path, out_png: Path | None = None) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    b = C.load_brand(brand_dir)
    col = b["colors"]
    W, H = 1600, 900
    bg = Image.new("RGB", (W, H), col["background"])
    d = ImageDraw.Draw(bg)
    hp, bp = b["fonts"]["heading"].get("_path"), b["fonts"]["body"].get("_path")

    def F(path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()
    d.rectangle([0, 0, W, 14], fill=col["primary"])
    d.text((60, 50), "BRAND PROFILE PREVIEW", font=F(bp, 22), fill=col["text"])
    d.text((60, 90), b["name"][:34], font=F(hp, 64), fill=col["text"])
    tag = (b.get("tagline") or "")[:110]
    if tag:
        words, line, y = tag.split(), "", 175
        for w in words:
            if d.textlength(line + " " + w, font=F(bp, 28)) > 820:
                d.text((60, y), line.strip(), font=F(bp, 28), fill=col["text"])
                y += 38
                line = w
            else:
                line += " " + w
        d.text((60, y), line.strip(), font=F(bp, 28), fill=col["text"])
    lg = (b.get("logo") or {}).get("_path")
    if lg:
        L = Image.open(lg).convert("RGBA")
        L.thumbnail((360, 200))
        panel = Image.new("RGB", (400, 240), "#FFFFFF" if C.luminance(col["background"]) < 0.5 else "#1F2937")
        # show the logo on both a light and a dark chip so problems are visible
        for i, chipc in enumerate(("#FFFFFF", "#111827")):
            chip = Image.new("RGB", (190, 110), chipc)
            Lc = L.copy()
            Lc.thumbnail((170, 90))
            chip.paste(Lc, ((190 - Lc.width) // 2, (110 - Lc.height) // 2), Lc)
            bg.paste(chip, (60 + i * 205, 330))
        d.text((60, 448), "logo on light / dark", font=F(bp, 18), fill=col["text"])
    # swatches
    sy = 520
    for i, key in enumerate(("primary", "accent", "background", "text")):
        x = 60 + i * 205
        d.rounded_rectangle([x, sy, x + 185, sy + 120], 14, fill=col[key], outline="#9CA3AF", width=2)
        d.text((x, sy + 130), key, font=F(bp, 22), fill=col["text"])
        d.text((x, sy + 158), col[key], font=F(bp, 22), fill=col["text"])
    # font specimens
    hf, bf = b["fonts"]["heading"], b["fonts"]["body"]
    d.text((60, 735), f"Heading: {hf.get('family')}", font=F(hp, 40), fill=col["text"])
    d.text((60, 790), f"Body: {bf.get('family')}  ({bf.get('source') or 'n/a'})", font=F(bp, 26), fill=col["text"])
    cta = b["cta"]
    d.text((60, 840), "CTA: " + (cta["end_card"].format(keyword=cta["keyword"], text=cta["text"]) if cta else ""), font=F(bp, 24), fill=col["text"])
    # mock 9:16 frame with caption
    fw, fh = 405, 720
    fx, fy = W - fw - 90, 90
    frame = Image.new("RGB", (fw, fh), col["primary"])
    fd = ImageDraw.Draw(frame)
    for i in range(fh):
        t = i / fh
        c0, c1 = C.hex_rgb(col["primary"]), C.hex_rgb(col["background"])
        fd.line([(0, i), (fw, i)], fill=tuple(int(c0[k] * (1 - t * 0.55) + c1[k] * t * 0.55) for k in range(3)))
    cap_font = F(hp, 54)
    words = [("THIS", False), ("IS", False), ("YOUR", True), ("BRAND", True)]
    text_line = "YOUR BRAND"
    tw = fd.textlength(text_line, font=cap_font)
    x0, y0 = (fw - tw) / 2, fh * 0.64
    for wd, hi in words[2:]:
        fill = col["accent"] if hi else "#FFFFFF"
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                fd.text((x0 + dx, y0 + dy), wd, font=cap_font, fill=b["captions"]["stroke_color"])
        fd.text((x0, y0), wd, font=cap_font, fill=fill if wd != "YOUR" else "#FFFFFF")
        x0 += fd.textlength(wd + " ", font=cap_font)
    if lg:
        L2 = Image.open(lg).convert("RGBA")
        L2.thumbnail((int(fw * 0.22), 90))
        frame.paste(L2, (fw - L2.width - 20, 22), L2)
    bg.paste(frame, (fx, fy))
    d.text((fx, fy + fh + 12), "caption + logo placement", font=F(bp, 18), fill=col["text"])
    out_png = out_png or (brand_dir / "brand-preview.png")
    bg.save(out_png)
    return out_png


# ---------------------------------------------------------------- summary
def summary(brand: dict) -> str:
    c = brand["colors"]
    lines = [f"BRAND: {brand['name']}", f"Tagline: {brand.get('tagline') or '-'}",
             "Colours: " + "  ".join(f"{k}={v}" for k, v in c.items()),
             f"Heading font: {brand['fonts']['heading']['family']}  [{brand['fonts']['heading'].get('source')}]",
             f"Body font:    {brand['fonts']['body']['family']}  [{brand['fonts']['body'].get('source')}]",
             f"Logo: {brand['logo'].get('file') or 'none (add one with --logo)'}",
             f"CTA: {brand['cta']['end_card'].format(keyword=brand['cta']['keyword'], text=brand['cta']['text'])}"]
    for k, v in brand.get("provenance", {}).items():
        lines.append(f"  where {k} came from: {v}")
    for n in brand.get("notes", []):
        lines.append(f"  NOTE: {n}")
    return "\n".join(lines)


def cmd_edit(a) -> None:
    import yaml
    d = Path(a.dir)
    f = d / "brand.yaml" if d.is_dir() else d
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    for kv in a.set:
        k, v = kv.split("=", 1)
        try:
            v = json.loads(v)
        except Exception:
            pass
        cur = data
        ks = k.split(".")
        for kk in ks[:-1]:
            cur = cur.setdefault(kk, {})
        if ks[-1] in ("primary", "accent", "background", "text") and ks[-2:-1] == ["colors"]:
            h = C.norm_hex(str(v))
            if not h:
                sys.exit(f"{v} is not a hex colour")
            v = h
        cur[ks[-1]] = v
        data.setdefault("provenance", {})[ks[-1]] = "your edit"
    f.write_text("# brand.yaml: read by every template style in Authentic Video Studio.\n" +
                 yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    base = f.parent
    # font family changed without a file: fetch it
    for role in ("heading", "body"):
        fb = data["fonts"][role]
        if any(s.startswith(f"fonts.{role}.family=") for s in a.set):
            nb = resolve_font(role, fb["family"], {}, base, [], [])
            data["fonts"][role] = nb
    f.write_text("# brand.yaml: read by every template style in Authentic Video Studio.\n" +
                 yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    say(summary(C.load_brand(base)))
    say(f"preview: {preview_card(base)}")


def main(argv=None) -> int:
    C.utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "edit":
        ap = argparse.ArgumentParser(prog="brand_extract.py edit")
        ap.add_argument("dir")
        ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
        cmd_edit(ap.parse_args(argv[1:]))
        return 0
    if argv and argv[0] == "preview":
        ap = argparse.ArgumentParser(prog="brand_extract.py preview")
        ap.add_argument("dir")
        ap.add_argument("--out")
        a = ap.parse_args(argv[1:])
        say("preview: " + str(preview_card(Path(a.dir), Path(a.out) if a.out else None)))
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="company website to read logo, colours, fonts and tone from")
    ap.add_argument("--logo", help="logo file (PNG, SVG, JPG, WEBP)")
    ap.add_argument("--kit", help="brand kit: PDF, ZIP, folder, DOCX, or style guide text/markdown file")
    ap.add_argument("--answers", help="YAML/JSON file with plain answers (name, tagline, primary, accent, ...)")
    ap.add_argument("--name"); ap.add_argument("--tagline"); ap.add_argument("--website"); ap.add_argument("--handle")
    ap.add_argument("--primary"); ap.add_argument("--accent"); ap.add_argument("--background"); ap.add_argument("--text")
    ap.add_argument("--heading-font", dest="heading_font"); ap.add_argument("--body-font", dest="body_font")
    ap.add_argument("--cta-text", dest="cta_text"); ap.add_argument("--keyword", help="CTA keyword, e.g. GUIDE")
    ap.add_argument("--tone", help="plain words: warm, direct, playful ...")
    ap.add_argument("--allow-site-fonts", action="store_true",
                    help="download the website's own @font-face files (only if you own the site and its font licence)")
    ap.add_argument("--no-download-fonts", action="store_true")
    ap.add_argument("--out", default="brand", help="output folder (default ./brand)")
    a = ap.parse_args(argv)
    if not any([a.url, a.logo, a.kit, a.answers, a.name, a.primary]):
        ap.error("give at least one source: --url, --logo, --kit, --answers, or answers like --name/--primary")
    out = Path(a.out)
    brand = build_brand(a, out)
    f = write_brand(brand, out)
    import shutil
    shutil.rmtree(out / "_kit", ignore_errors=True)
    card = preview_card(out)
    say("")
    say(summary(C.load_brand(out)))
    say(f"\nwrote {f}\npreview card: {card}\nConfirm with the user, then edit with:  brand_extract.py edit {out} --set colors.primary=#RRGGBB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
