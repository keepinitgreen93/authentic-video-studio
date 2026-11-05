#!/usr/bin/env python3
"""Scan the repo for secrets, personal paths and private names before committing. Exit 1 on any hit.

  python tests/secret_scan.py [--extra-terms "client one,client two"]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "api key": re.compile(r"(?i)\b(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|fal-[A-Za-z0-9\-]{20,})"),
    "key assignment": re.compile(r"(?i)\b[A-Z_]*(API_KEY|SECRET|TOKEN|PASSWORD)[A-Z_]*\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "personal path": re.compile(r"(?i)(gem en eye|C:[\\/]+Users[\\/]+[^\\/\s'\"]+[\\/]+(Documents|AppData|Projects))"),
    "private term": re.compile(r"(?i)\b(tam-aios|company brain|horus|HorusDeliverables|plantbasedtone|toni\b|product champ|gemeneye|gemini omni|sarah2ill)"),
}
# Terms allowed because the repo owner's public GitHub handle and brand name are intentionally in the docs.
ALLOW_LINES = re.compile(r"keepinitgreen93|Truly Authentic Marketing")
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".mp4", ".ttf", ".otf", ".woff", ".woff2", ".ico", ".zip"}
SELF = Path(__file__).resolve()


def files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [ROOT / l for l in out.splitlines() if l]
    except Exception:
        return [p for p in ROOT.rglob("*") if p.is_file() and not (set(p.parts) & SKIP_DIRS)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-terms", default="")
    a = ap.parse_args()
    extra = [re.compile(re.escape(t.strip()), re.I) for t in a.extra_terms.split(",") if t.strip()]
    hits = 0
    scanned = 0
    for p in files():
        if p.suffix.lower() in SKIP_SUFFIX or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        scanned += 1
        for n, line in enumerate(text.splitlines(), 1):
            if p.resolve() == SELF:
                continue
            for name, pat in list(PATTERNS.items()) + [("extra term", e) for e in extra]:
                m = pat.search(line)
                if m and not (name == "private term" and ALLOW_LINES.search(line)):
                    hits += 1
                    print(f"{p.relative_to(ROOT)}:{n}: [{name}] {m.group(0)[:60]}")
    # binary content sanity: no real photos or large files
    for p in files():
        if p.is_file() and p.stat().st_size > 1_500_000:
            hits += 1
            print(f"{p.relative_to(ROOT)}: [large file] {p.stat().st_size // 1024} KB")
    print(f"scanned {scanned} text files: {'CLEAN' if not hits else str(hits) + ' finding(s)'}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
