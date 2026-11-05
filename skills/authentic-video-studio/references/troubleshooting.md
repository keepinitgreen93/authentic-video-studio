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
