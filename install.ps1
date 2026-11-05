<#
.SYNOPSIS
  Authentic Video Studio installer for Windows 10/11. Native. No WSL, no admin rights needed.

.DESCRIPTION
  Installs or verifies: FFmpeg (winget, then scoop, then choco, then direct download), uv, a private
  Python 3.12 environment, the Python packages, default fonts, and the speech model. Then Node.js LTS (only if
  missing, downloaded into the studio folder, no admin rights), the Remotion packages and its headless Chrome for the
  spotlight and minimalist styles. Safe to run again.

  Run from the repo folder:
    powershell -ExecutionPolicy Bypass -File .\install.ps1

.PARAMETER Model       Speech model to pre-download. Default small.en. Use "none" to skip.
.PARAMETER SkipRemotion  Do not set up Node and Remotion. The spotlight and minimalist styles then stay unavailable;
                 spotlight-lite (FFmpeg only) still works.
.PARAMETER CheckOnly   Do not install anything. Run the doctor and exit.
.PARAMETER InstallSkill  Copy the skill into an agent: claude, hermes, both, or none (default).
#>
[CmdletBinding()]
param(
  [string]$Model = "small.en",
  [switch]$CheckOnly,
  [switch]$SkipRemotion,
  [ValidateSet("none", "claude", "hermes", "both")][string]$InstallSkill = "none"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppHome = if ($env:VS_HOME) { $env:VS_HOME } else { Join-Path $env:LOCALAPPDATA "authentic-video-studio" }
$VenvDir = Join-Path $AppHome "venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
$Skill = Join-Path $Repo "skills\authentic-video-studio"
$Vs = Join-Path $Skill "scripts\vs.py"
Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue

function Step($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    ok: $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    warn: $m" -ForegroundColor Yellow }
function Refresh-Path {
  $m = [Environment]::GetEnvironmentVariable("Path", "Machine"); $u = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$m;$u;$env:Path"
}
function Find-Tool($name) {
  $c = Get-Command $name -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $roots = @(
    "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\$name.exe",
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\$name.exe",
    "$env:USERPROFILE\scoop\shims\$name.exe",
    "C:\ProgramData\chocolatey\bin\$name.exe",
    (Join-Path $AppHome "bin\$name.exe"),
    "$env:USERPROFILE\.local\bin\$name.exe",
    "$env:LOCALAPPDATA\hermes\bin\$name.exe")
  foreach ($r in $roots) { $hit = Get-ChildItem $r -ErrorAction SilentlyContinue | Select-Object -First 1; if ($hit) { return $hit.FullName } }
  return $null
}

Write-Host "Authentic Video Studio installer (Windows native, no WSL)" -ForegroundColor White
Write-Host "Repo:  $Repo"
Write-Host "Home:  $AppHome"
New-Item -ItemType Directory -Force -Path $AppHome | Out-Null

if (-not $CheckOnly) {
  # 1. FFmpeg ---------------------------------------------------------------
  Step "FFmpeg"
  $ff = Find-Tool "ffmpeg"
  if ($ff) { Ok "found $ff" }
  else {
    $done = $false
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      Write-Host "    installing with winget (Gyan.FFmpeg)..."
      try { winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements --silent | Out-Host; Refresh-Path; $done = [bool](Find-Tool "ffmpeg") } catch { Warn "winget failed: $_" }
    }
    if (-not $done -and (Get-Command scoop -ErrorAction SilentlyContinue)) {
      Write-Host "    installing with scoop..."; try { scoop install ffmpeg | Out-Host; Refresh-Path; $done = [bool](Find-Tool "ffmpeg") } catch { Warn "scoop failed: $_" }
    }
    if (-not $done -and (Get-Command choco -ErrorAction SilentlyContinue)) {
      Write-Host "    installing with choco (needs an admin shell)..."; try { choco install ffmpeg -y | Out-Host; Refresh-Path; $done = [bool](Find-Tool "ffmpeg") } catch { Warn "choco failed: $_" }
    }
    if (-not $done) {
      Write-Host "    downloading a static FFmpeg build directly (gyan.dev)..."
      $zip = Join-Path $env:TEMP "ffmpeg-vs.zip"; $tmp = Join-Path $env:TEMP "ffmpeg-vs"
      Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $zip -UseBasicParsing
      if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
      Expand-Archive $zip -DestinationPath $tmp -Force
      $bin = Get-ChildItem $tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1
      New-Item -ItemType Directory -Force -Path (Join-Path $AppHome "bin") | Out-Null
      Copy-Item (Join-Path $bin.DirectoryName "ffmpeg.exe") (Join-Path $AppHome "bin") -Force
      Copy-Item (Join-Path $bin.DirectoryName "ffprobe.exe") (Join-Path $AppHome "bin") -Force
      Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
      $done = [bool](Find-Tool "ffmpeg")
    }
    $ff = Find-Tool "ffmpeg"
    if (-not $ff) { throw "FFmpeg could not be installed. Install it manually (winget install -e --id Gyan.FFmpeg) and run this script again." }
    Ok "installed $ff"
  }

  # 2. uv + Python ----------------------------------------------------------
  Step "uv (Python manager)"
  $uv = Find-Tool "uv"
  if (-not $uv) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      try { winget install -e --id astral-sh.uv --accept-source-agreements --accept-package-agreements --silent | Out-Host; Refresh-Path; $uv = Find-Tool "uv" } catch { Warn "winget uv failed: $_" }
    }
    if (-not $uv) {
      Write-Host "    installing uv from astral.sh..."
      Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
      Refresh-Path; $uv = Find-Tool "uv"
    }
  }
  if (-not $uv) { throw "uv could not be installed. See https://docs.astral.sh/uv/getting-started/installation/" }
  Ok "uv at $uv"

  Step "Private Python 3.12 environment"
  if (Test-Path $VenvPy) { Ok "environment exists at $VenvDir" }
  else { & $uv venv $VenvDir --python 3.12; if ($LASTEXITCODE -ne 0) { throw "uv venv failed" } ; Ok "created $VenvDir" }
  Write-Host "    installing packages (cached on repeat runs)..."
  & $uv pip install --python $VenvPy -r (Join-Path $Repo "requirements.txt")
  if ($LASTEXITCODE -ne 0) { throw "package install failed" }
  Ok "packages installed"

  # 3. record tool paths ----------------------------------------------------
  $ffprobe = Find-Tool "ffprobe"
  $cfg = @{ tools = @{ ffmpeg = $ff; ffprobe = $ffprobe; uv = $uv }; repo = $Repo; skill = $Skill } | ConvertTo-Json -Depth 4
  [System.IO.File]::WriteAllText((Join-Path $AppHome "config.json"), $cfg, (New-Object System.Text.UTF8Encoding($false)))

  # 4. fonts + model --------------------------------------------------------
  Step "Default fonts and speech model"
  $setupArgs = @($Vs, "setup")
  if ($Model -ne "none") { $setupArgs += @("--model", $Model) }
  & $VenvPy -I @setupArgs
  if ($LASTEXITCODE -ne 0) { Warn "setup step had problems (offline?). Rendering still works with system fonts; rerun later." }

  # 4b. Node + Remotion (spotlight and minimalist styles) ------------------
  if ($SkipRemotion) { Warn "skipping Node and Remotion (-SkipRemotion). Styles spotlight and minimalist will not run." }
  else {
    Step "Node.js, Remotion packages and headless Chrome (for spotlight and minimalist)"
    & $VenvPy -I $Vs setup-remotion --install-node
    if ($LASTEXITCODE -ne 0) { Warn "Remotion setup did not finish. The other styles work. Retry later: $VenvPy $Vs setup-remotion --install-node" }
  }

  # 5. optional: copy skill into an agent -----------------------------------
  if ($InstallSkill -ne "none") {
    Step "Installing the skill into your agent"
    $targets = @()
    if ($InstallSkill -in @("claude", "both")) { $targets += (Join-Path $env:USERPROFILE ".claude\skills\authentic-video-studio") }
    if ($InstallSkill -in @("hermes", "both")) {
      $hh = if ($env:HERMES_HOME) { $env:HERMES_HOME } else { Join-Path $env:USERPROFILE ".hermes" }
      $targets += (Join-Path $hh "skills\authentic-video-studio")
    }
    foreach ($t in $targets) {
      if (Test-Path $t) { Remove-Item $t -Recurse -Force }
      New-Item -ItemType Directory -Force -Path (Split-Path $t) | Out-Null
      Copy-Item $Skill $t -Recurse -Force
      Ok "copied to $t"
    }
  }
}

# 6. doctor -----------------------------------------------------------------
Step "Doctor"
$py = if (Test-Path $VenvPy) { $VenvPy } else { (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $py) { throw "No Python found. Run this script without -CheckOnly to create the environment." }
& $py -I $Vs doctor
$rc = $LASTEXITCODE
Write-Host ""
if ($rc -eq 0) {
  Write-Host "Ready. Next step: set up your brand." -ForegroundColor Green
  Write-Host "  & `"$VenvPy`" `"$Vs`" brand --url https://your-site.com --out brand"
  Write-Host "  (or ask your agent: 'set up my branding for Authentic Video Studio')"
} else { Write-Host "Not ready. Fix the items marked FAIL above and run this script again." -ForegroundColor Red }
exit $rc
