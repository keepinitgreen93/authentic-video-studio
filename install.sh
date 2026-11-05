#!/usr/bin/env bash
# Authentic Video Studio installer for macOS and Linux. Safe to run again.
#   ./install.sh [--model small.en|none] [--check-only] [--skip-remotion] [--install-skill claude|hermes|both]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="${VS_HOME:-$HOME/.local/share/authentic-video-studio}"
VENV="$APP_HOME/venv"
VENV_PY="$VENV/bin/python"
SKILL="$REPO/skills/authentic-video-studio"
VS="$SKILL/scripts/vs.py"
MODEL="small.en"; CHECK=0; SKIP_REMOTION=0; INSTALL_SKILL="none"
unset PYTHONPATH

while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL="$2"; shift 2;;
    --check-only) CHECK=1; shift;;
    --skip-remotion) SKIP_REMOTION=1; shift;;
    --install-skill) INSTALL_SKILL="$2"; shift 2;;
    -h|--help) sed -n 2,3p "$0"; exit 0;;
    *) echo "unknown option $1"; exit 2;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    ok: %s\n' "$1"; }
warn() { printf '    warn: %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }
OS="$(uname -s)"
mkdir -p "$APP_HOME"
echo "Authentic Video Studio installer ($OS)"; echo "Repo: $REPO"; echo "Home: $APP_HOME"

if [ "$CHECK" -eq 0 ]; then
  step "FFmpeg"
  if have ffmpeg && have ffprobe; then ok "found $(command -v ffmpeg)"
  else
    if [ "$OS" = "Darwin" ]; then
      have brew || { echo "Homebrew is needed to install FFmpeg on macOS: https://brew.sh"; exit 1; }
      brew install ffmpeg
    elif have apt-get; then sudo apt-get update -y && sudo apt-get install -y ffmpeg espeak-ng
    elif have dnf; then sudo dnf install -y ffmpeg espeak-ng || sudo dnf install -y ffmpeg-free espeak-ng
    elif have pacman; then sudo pacman -S --noconfirm ffmpeg espeak-ng
    elif have zypper; then sudo zypper install -y ffmpeg espeak-ng
    else echo "Install FFmpeg with your package manager, then run this script again."; exit 1; fi
    have ffmpeg || { echo "FFmpeg install did not put ffmpeg on PATH."; exit 1; }
    ok "installed $(command -v ffmpeg)"
  fi
  if [ "$OS" = "Linux" ] && ! have espeak-ng && ! have espeak; then warn "espeak-ng missing: only the synthetic sample clip needs it (sudo apt install espeak-ng)"; fi

  step "uv (Python manager)"
  if ! have uv; then
    if have curl; then curl -LsSf https://astral.sh/uv/install.sh | sh; else wget -qO- https://astral.sh/uv/install.sh | sh; fi
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  fi
  have uv || { echo "uv install failed. See https://docs.astral.sh/uv/"; exit 1; }
  ok "uv at $(command -v uv)"

  step "Private Python 3.12 environment"
  [ -x "$VENV_PY" ] && ok "environment exists at $VENV" || { uv venv "$VENV" --python 3.12; ok "created $VENV"; }
  uv pip install --python "$VENV_PY" -r "$REPO/requirements.txt"
  ok "packages installed"

  cat > "$APP_HOME/config.json" <<EOF
{"tools": {"ffmpeg": "$(command -v ffmpeg)", "ffprobe": "$(command -v ffprobe)", "uv": "$(command -v uv)"}, "repo": "$REPO", "skill": "$SKILL"}
EOF

  step "Default fonts and speech model"
  if [ "$MODEL" = "none" ]; then "$VENV_PY" -I "$VS" setup || warn "font setup had problems (offline?)"
  else "$VENV_PY" -I "$VS" setup --model "$MODEL" || warn "setup had problems (offline?). Rerun later."; fi

  if [ "$SKIP_REMOTION" -eq 1 ]; then warn "skipping Node and Remotion (--skip-remotion). Styles spotlight and minimalist will not run."
  else
    step "Node.js, Remotion packages and headless Chrome (for spotlight and minimalist)"
    if [ "$OS" = "Linux" ]; then
      warn "Linux needs a few system libraries for headless Chrome. On Debian/Ubuntu: sudo apt install -y libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2t64 libxrandr2 libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 (libasound2 on older releases)"
    fi
    "$VENV_PY" -I "$VS" setup-remotion --install-node || warn "Remotion setup did not finish. The other styles work. Retry: $VENV_PY $VS setup-remotion --install-node"
  fi

  if [ "$INSTALL_SKILL" != "none" ]; then
    step "Installing the skill into your agent"
    targets=()
    case "$INSTALL_SKILL" in claude|both) targets+=("$HOME/.claude/skills/authentic-video-studio");; esac
    case "$INSTALL_SKILL" in hermes|both) targets+=("${HERMES_HOME:-$HOME/.hermes}/skills/authentic-video-studio");; esac
    for t in "${targets[@]}"; do rm -rf "$t"; mkdir -p "$(dirname "$t")"; cp -R "$SKILL" "$t"; ok "copied to $t"; done
  fi
fi

step "Doctor"
PY="$VENV_PY"; [ -x "$PY" ] || PY="$(command -v python3)"
set +e; "$PY" -I "$VS" doctor; rc=$?; set -e
echo
if [ $rc -eq 0 ]; then
  echo "Ready. Next step: set up your brand."
  echo "  $VENV_PY $VS brand --url https://your-site.com --out brand"
  echo "  (or ask your agent: 'set up my branding for Authentic Video Studio')"
else echo "Not ready. Fix the items marked FAIL above and run this script again."; fi
exit $rc
