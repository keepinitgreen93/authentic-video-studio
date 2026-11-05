# Authentic Video Studio

Edit a raw talking-head clip into a branded 1080x1920 short-form video. It cuts dead air and filler words, adds captions, a hook, your logo and a call to action, and sets the loudness. It runs on your own computer with FFmpeg and Whisper. No API keys. No cloud upload. No WSL on Windows.

You can use it three ways:

- **As an Agent Skill.** Drop `skills/authentic-video-studio` into Claude Code, Hermes or any agent that reads `SKILL.md`, and ask for a video.
- **As a Hermes plugin.** `hermes plugins install` adds four tools and a `/video-studio` command.
- **As a command line.** `python skills/authentic-video-studio/scripts/vs.py render ...`

## 60-second quickstart

Windows (PowerShell):

```powershell
git clone https://github.com/keepinitgreen93/authentic-video-studio
cd authentic-video-studio
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

macOS or Linux:

```bash
git clone https://github.com/keepinitgreen93/authentic-video-studio
cd authentic-video-studio
./install.sh
```

The installer sets up FFmpeg, a private Python environment, the packages, default fonts and the speech model, then runs a check (`doctor`). It is safe to run again.

**Then set up your brand. This is the first step after install.**

```
python skills/authentic-video-studio/scripts/vs.py brand --url https://your-site.com --out brand
```

Or give it a logo (`--logo logo.png`), a brand kit (`--kit brand-kit.zip`), or just answers (`--name "Acme" --primary "#0A7C86"`). It writes `brand/brand.yaml`, a preview card (`brand/brand-preview.png`) and the fonts. Look at the card, say what to change, and the agent edits it for you. Details: [branding onboarding](skills/authentic-video-studio/references/branding-onboarding.md).

Render a clip:

```
python skills/authentic-video-studio/scripts/vs.py render --input raw.mp4 --out final.mp4 \
  --style list-the-ways --brand brand --hook-text "7 WAYS TO\nEDIT FASTER" --keyword GUIDE
```

No footage yet? `python skills/authentic-video-studio/scripts/vs.py demo --out demo-output --brand brand` renders a synthetic sample clip in every style.

## Branding onboarding

The agent walks you through it one question at a time. It accepts any of these, alone or together:

| You have | It reads |
|---|---|
| A website URL | Logo, colors (CSS variables, theme color, most used colors), fonts (Google Fonts links, `@font-face`, `font-family`), name, tagline, headlines |
| A logo file (PNG, SVG, JPG, WEBP) | Trimmed transparent PNG and the dominant colors |
| A brand kit (PDF, ZIP, folder, Word doc, style guide) | Colors with their roles, font names, font files, the best logo variant |
| None of these | A short list of plain questions |

Output is `brand.yaml`, which every style reads. You see a preview card, confirm, and can edit any value later. Fonts: Google Fonts are downloaded. A custom font from a website is not downloaded unless you own the licence and pass `--allow-site-fonts`; otherwise it picks a close Google Font and tells you which.

## Styles

| Style | What it looks like |
|---|---|
| `list-the-ways` | Jump cuts at list items. Slow push-in, then a snap back at each cut. One big word at a time. Hook text on top. `DROP KEYWORD BELOW` end card. |
| `punch-caps` | Very tight cuts with a small alternating punch-in. Three-word ALL CAPS captions with a heavy outline. Also writes an `.srt`. |
| `spotlight-lite` | You in a rounded window over a drifting grid in your brand color. Opening zoom-out. Karaoke captions on a dark strip, spoken word in your accent color. |

Every color, font and the logo come from `brand.yaml`. The values for each style are plain JSON in `skills/authentic-video-studio/templates/styles/`. See [styles](skills/authentic-video-studio/references/styles.md).

## What it installs

| Dependency | Why | Windows | macOS | Linux |
|---|---|---|---|---|
| FFmpeg (full build with libass, freetype, x264) | Cut, caption, mix, encode | winget `Gyan.FFmpeg`, then scoop, choco, direct download | Homebrew | apt, dnf, pacman, zypper |
| uv | Manages Python | winget `astral-sh.uv` or the astral.sh script | astral.sh script | astral.sh script |
| Python 3.12 (private environment) | Runs the scripts | uv | uv | uv |
| faster-whisper, PyAV | Local speech to text | pip via uv | same | same |
| Pillow, fonttools, resvg-py | Logos, fonts, preview card | same | same | same |
| requests, beautifulsoup4, pypdf, PyYAML, numpy | Branding onboarding | same | same | same |
| Google Fonts (Poppins, Inter by default) | Captions | downloaded | downloaded | downloaded |
| espeak-ng (Linux only, optional) | Synthetic sample clip | n/a | `say` is built in | apt |

No Node, no Remotion, no Docker, no WSL.

## Check your install

```
python skills/authentic-video-studio/scripts/vs.py doctor
```

It lists each dependency as OK or FAIL and prints the exact fix.

## Install as a skill or plugin

- **Claude Code or any SKILL.md agent:** copy `skills/authentic-video-studio` to `~/.claude/skills/` (or run `install.ps1 -InstallSkill claude` / `./install.sh --install-skill claude`).
- **Hermes skill:** copy it to `~/.hermes/skills/` (or `-InstallSkill hermes`).
- **Hermes plugin:** `hermes plugins install keepinitgreen93/authentic-video-studio`, then `hermes plugins enable authentic-video-studio`. Private repo: Hermes uses your `gh auth` or `GITHUB_TOKEN`.
- **Claude Code plugin:** `claude plugin marketplace add keepinitgreen93/authentic-video-studio`, then `claude plugin install authentic-video-studio@authentic-video-studio`.

Full steps, for humans and for agents: [INSTALL.md](INSTALL.md). It ends with a runbook an AI agent can follow to install, brand and render.

## Limits

- Automatic cleanup cannot find false starts or retakes. Fix the transcript and pass it back with `--words-json`.
- Zoom is whole frame. No face tracking.
- `spotlight-lite` is an FFmpeg version of a richer Remotion look. It does not build custom animated graphics.
- Speech runs on CPU. A 30-second clip takes about a minute after the first run.

## Privacy

Everything runs locally. The only network calls are the website you name, Google Fonts, and the one-time speech model download. Do not commit your raw footage, `brand/` folders or client files to a public repo. The `.gitignore` here excludes them.

## License

MIT. See [LICENSE](LICENSE). FFmpeg, Whisper models, fonts and the Python packages keep their own licences.
