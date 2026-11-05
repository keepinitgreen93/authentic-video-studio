# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Missing ffmpeg` | FFmpeg not on PATH and not in a known location | Run the installer, or `winget install -e --id Gyan.FFmpeg`, then open a new terminal. The doctor lists the paths it checks. |
| `ImportError ... PIL._imaging` or wrong package versions | A stray `PYTHONPATH` points at another Python's packages | Unset `PYTHONPATH`. `vs.py` and the installers do this for you. Run scripts as `python -I script.py`. |
| `open() got an unexpected keyword argument 'metadata_errors'` | PyAV 16 or newer with faster-whisper 1.2 | `requirements.txt` pins `av>=14,<16`. Rerun the installer. |
| First render is slow | Speech model download (about 250 MB) and CPU transcription | Run `vs.py setup --model small.en` ahead of time. Use `--model base.en` for speed. |
| Captions use the wrong font | `brand.yaml` font file missing | Run `vs.py brand edit brand --set fonts.heading.family="Poppins"` to fetch it, or set `fonts.heading.file`. |
| Hook text runs off the frame | A line is over 16 characters | Shorten it. The renderer prints a warning. |
| Logo not shown | `logo.show_in_videos: false` or no `logo.png` | Provide a logo (`vs.py brand --logo file`) or edit the setting. |
| Website extract finds few colors | The site renders in JavaScript, or blocks bots | Use a logo, a brand kit, or the questions in the onboarding. |
| `LF will be replaced by CRLF` from git | Windows line endings | Harmless. `.gitattributes` keeps shell scripts LF. |
| Execution policy blocks install.ps1 | PowerShell policy | `powershell -ExecutionPolicy Bypass -File .\install.ps1` |
| No TTS for the sample clip on Linux | espeak-ng missing | `sudo apt install espeak-ng`, or pass your own clip. |

## Windows notes

- Everything is native. No WSL, no Linux subsystem, no Docker.
- FFmpeg comes from winget (Gyan.FFmpeg full build, which includes libass and freetype). Fallbacks: scoop, choco, then a direct download into `%LOCALAPPDATA%\authentic-video-studio\bin`.
- The studio Python lives in `%LOCALAPPDATA%\authentic-video-studio\venv`. Delete that folder to start clean.
- Use forward slashes or quoted paths in git-bash. Native tools do not understand `/c/Users/...`.

## Uninstall

Delete `%LOCALAPPDATA%\authentic-video-studio` (Windows) or `~/.local/share/authentic-video-studio` (macOS/Linux). Remove the skill folder from your agent. FFmpeg and uv stay installed; remove them with winget/brew/apt if you want.

## spotlight and minimalist (Remotion)

| Symptom | Fix |
|---|---|
| `Style 'spotlight' needs Node and Remotion, which are not ready` | Run `python scripts/vs.py setup-remotion --install-node`, then `vs.py doctor`. Offline: use `spotlight-lite`. |
| `npm ci failed` | Network or proxy problem. Run `setup-remotion` again. Behind a proxy set `HTTPS_PROXY`. |
| `Headless browser download failed` | Retry. The file comes from Google storage via Remotion; a firewall may block it. |
| Linux: `error while loading shared libraries` from Chrome | Install the libraries listed in INSTALL.md step 2. |
| `Remotion render failed ... timeout` | Close other heavy programs, or lower the load: the render uses 2 browser tabs. Retry. |
| Text looks wrong after a font change | The brand font file is copied for each render. Run `vs.py brand preview brand` to check the font loaded. |
| Windows: `node` found in the wrong version | The studio prefers its own portable Node in `%LOCALAPPDATA%\authentic-video-studio\node`. Delete that folder to fall back to the system Node. |
| `minimalist` output has no takeovers | The clip has no sentence with three seconds of speaker before it. Use a longer clip or a plan file. |
