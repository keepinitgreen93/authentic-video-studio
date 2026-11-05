# Install

This page is written for people and for AI agents. Every step has an exact command and a check that proves it worked. Nothing here needs WSL or Docker. Node.js is needed only for the `spotlight` and `minimalist` styles, and the installer adds it for you.

## Requirements

- Windows 10/11, macOS 12+, or a mainstream Linux
- About 4 GB free disk (FFmpeg, Python packages, the speech model, Node, Remotion and its Chrome)
- Internet for the first install
- Windows: PowerShell 5.1 or newer (built in). `winget` helps but is not required. No admin rights needed.
- macOS: Homebrew (https://brew.sh)
- Linux: `sudo` for the FFmpeg package. Debian and Ubuntu also need a few libraries for headless Chrome (step 2).

## 1. Get the code

```
git clone https://github.com/keepinitgreen93/authentic-video-studio
cd authentic-video-studio
```

For a private repo, sign in first with `gh auth login`. No git? Download the ZIP from GitHub and unzip it.

## 2. Run the installer

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

macOS and Linux:

```bash
chmod +x install.sh
./install.sh
```

Options:

| Windows | macOS/Linux | Meaning |
|---|---|---|
| `-Model base.en` | `--model base.en` | Smaller, faster speech model. `none` skips the download. Default `small.en`. |
| `-CheckOnly` | `--check-only` | Install nothing; run the check. |
| `-SkipRemotion` | `--skip-remotion` | Do not set up Node and Remotion. `spotlight` and `minimalist` stay unavailable. |
| `-InstallSkill claude\|hermes\|both` | `--install-skill claude\|hermes\|both` | Also copy the skill into the agent's skills folder. |

What it does, in order: FFmpeg (winget, scoop, choco, then direct download on Windows; brew or your package manager elsewhere), uv, a private Python 3.12 environment, the packages from `requirements.txt`, the default fonts, the speech model, Node.js and Remotion (below), then the doctor. Running it again skips whatever is already done.

**Node and Remotion** (for `spotlight` and `minimalist`). The installer runs `vs.py setup-remotion --install-node`, which:

1. Uses Node 18 or newer if it is already on the machine (PATH, Program Files, nvm, Homebrew).
2. Otherwise downloads the newest Node 22 LTS release from nodejs.org into `%LOCALAPPDATA%\authentic-video-studio\node` (`~/.local/share/authentic-video-studio/node` elsewhere), checks its SHA-256, and uses it only for this studio. No admin rights, no change to your PATH. If you prefer a system install: `winget install -e --id OpenJS.NodeJS.LTS` (Windows), `brew install node` (macOS), or your package manager or nvm (Linux), then run the installer again.
3. Copies the Remotion project to `<studio folder>/remotion` and runs `npm ci` there (pinned versions from the lockfile).
4. Runs `remotion browser ensure`, which downloads Chrome Headless Shell (about 110 MB) once.

If this step fails, the other three styles still work, and the doctor lists the Remotion items as warnings. Retry with `python skills/authentic-video-studio/scripts/vs.py setup-remotion --install-node`. Debian and Ubuntu may need: `sudo apt install -y libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2t64 libxrandr2 libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2` (`libasound2` on releases before 24.04).

The environment lives at `%LOCALAPPDATA%\authentic-video-studio\venv` on Windows and `~/.local/share/authentic-video-studio/venv` elsewhere. Set `VS_HOME` to move it.

## 3. Verify

```
python skills/authentic-video-studio/scripts/vs.py doctor
```

Expected: every line `[OK  ]`, then `READY`, exit code 0. The `remotion:` lines (node, npm, project, npm packages, headless browser) are marked `warn` rather than `FAIL` when missing, because only two styles need them; the doctor then says so after `READY`. Any `[FAIL]` line prints a `fix:` command. Run it, then run the doctor again. For machines and agents add `--json`; read `ready` and each check's `fix`.

`vs.py` re-launches itself inside the studio environment, so system Python 3.9 or newer is enough to start it. If you have no Python at all, run the installer; it brings its own.

## 4. Set up your brand (first step after install)

```
python skills/authentic-video-studio/scripts/vs.py brand --url https://your-site.com --out brand
```

Use the source you have:

```
vs.py brand --logo path/to/logo.png --out brand
vs.py brand --kit path/to/brand-kit.zip --out brand
vs.py brand --name "Acme" --primary "#0A7C86" --accent "#F26B21" --heading-font Montserrat --keyword GUIDE --out brand
```

Open `brand/brand-preview.png`, confirm it looks right, and change anything with:

```
vs.py brand edit brand --set colors.primary=#E11D48 --set cta.keyword=START
```

Agents: follow `skills/authentic-video-studio/references/branding-onboarding.md` and ask the user one question at a time.

## 5. Try it

```
vs.py demo --out demo-output --brand brand
```

This makes a synthetic clip (text-to-speech over a plain background) and renders it in every style. Remotion styles are skipped with a message if Node is not set up. Check:

```
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration -of default=nw=1 demo-output/demo_list-the-ways.mp4
```

Expected: `h264`, `1080`, `1920`, `30/1`, `aac`, and a duration around 27 seconds. The same check applies to `demo_spotlight.mp4` and `demo_minimalist.mp4`. The first run downloads nothing extra if the installer already fetched the model.

On Linux the sample clip needs `espeak-ng`. Without it, use `vs.py demo --input your-clip.mp4`.

## 6. Use it from an agent

**Claude Code (skill):** copy the skill folder.

```
# macOS/Linux
cp -R skills/authentic-video-studio ~/.claude/skills/
# Windows PowerShell
Copy-Item -Recurse skills\authentic-video-studio $env:USERPROFILE\.claude\skills\
```

Start a new session and ask: "Set up my branding for Authentic Video Studio, then edit this clip."

**Claude Code (plugin):**

```
claude plugin marketplace add keepinitgreen93/authentic-video-studio
claude plugin install authentic-video-studio@authentic-video-studio
```

**Hermes (plugin):**

```
hermes plugins install keepinitgreen93/authentic-video-studio --enable
hermes plugins doctor authentic-video-studio
```

In a Hermes session, type `/video-studio`, or load the skill with `skill_view("authentic-video-studio:authentic-video-studio")`. The plugin adds the tools `video_studio_doctor`, `video_studio_brand`, `video_studio_styles` and `video_studio_render`.

**Hermes (skill only):** copy the folder to `~/.hermes/skills/`.

The plugin and the skill call the same scripts. Run the installer once (step 2) so the environment exists.

## For AI agents: runbook

Follow these in order. This section is the full agent contract for the repo.

Ground rules:

- Run everything locally. Never upload, post or send a video. Give the user the file path.
- This project needs no API keys. Do not ask for any. Never print secrets you happen to see.
- Do not use WSL or Docker. Do not install with admin rights unless the user agrees. Do not install or upgrade Node system-wide; the installer's portable Node is enough.
- Remotion needs a licence for for-profit companies with more than three employees. If the user is such a company, tell them before rendering `spotlight` or `minimalist` and offer `spotlight-lite`.
- Do not put the user's footage, `brand/` folders or client files inside this repo.
- Report only what tools returned. If a command fails, show the error and the fix you tried.
- On Windows in git-bash, pass `C:/Users/...` paths to native programs. Unset `PYTHONPATH` before running Python, or use `python -I`.

Steps:

1. **Install.** Run `install.ps1` (Windows) or `install.sh` (macOS/Linux) from the repo root. A first install takes several minutes, so run it as a background job if your tool has a timeout. Done when `python skills/authentic-video-studio/scripts/vs.py doctor --json` returns `"ready": true`. For each failed required check, run its `fix` and re-run the doctor.
2. **Brand.** Before any render, follow `skills/authentic-video-studio/references/branding-onboarding.md`: ask where the brand folder goes, ask which sources the user has (website, logo, brand kit, nothing), run `vs.py brand ...`, show `brand/brand-preview.png`, read back colors, fonts (real or substitute), logo and notes, apply edits with `vs.py brand edit`, and continue only after the user says yes.
3. **Render.** Ask for the clip path, a style (`vs.py styles`), optional two-line hook text (16 characters or fewer per line) and an optional CTA keyword. Run `vs.py render --input <clip> --out <out.mp4> --style <style> --brand brand`. Verify with ffprobe (1080x1920, 30 fps, H.264, AAC, duration) and view the three stills in `<out>_stills/`. Report clipped or unreadable text. Hand over the mp4, the stills and, for `punch-caps`, the `.srt`.
4. **Smoke test** (proves the install): `vs.py demo --out demo-output --styles list-the-ways --brand brand`. Success is exit code 0 and an mp4 that ffprobe reads.
5. **Remotion styles** (`spotlight`, `minimalist`). Check `vs.py doctor --json` for checks whose name starts with `remotion:`. If any is not ok, run `vs.py setup-remotion --install-node` (or the `video_studio_setup_remotion` tool) and re-run the doctor. Then render with `--style spotlight` or `--style minimalist`. For a hand-tuned edit, read `skills/authentic-video-studio/references/remotion-styles.md`. Always look at the stills (`<out>_stills/`) and extract more with ffmpeg at the takeover and card moments before reporting; check that text and the logo sit inside the frame.

Hermes plugin tools, if you run as the plugin: `video_studio_doctor`, `video_studio_brand`, `video_studio_styles`, `video_studio_render`.

Editing this repo: Python 3.9+ syntax, cross-platform code only (`pathlib`, no shell pipes), plain direct docs with no em dashes or hype words. Before committing run `python tests/smoke_test.py` and `python tests/secret_scan.py`.

## Updating

```
git pull
powershell -ExecutionPolicy Bypass -File .\install.ps1     # or ./install.sh
```

## Uninstalling

Delete the environment folder named above (it also holds the portable Node, the Remotion project and its Chrome), delete the skill folder from your agent, and run `hermes plugins remove authentic-video-studio` if you installed the plugin. FFmpeg and uv stay; remove them with your package manager if you want.

## Common problems

See [troubleshooting](skills/authentic-video-studio/references/troubleshooting.md). The usual ones: an old terminal that has not picked up the new PATH (open a new window), a `PYTHONPATH` variable pointing at another Python (unset it), and a blocked script policy on Windows (use `-ExecutionPolicy Bypass` as shown).
