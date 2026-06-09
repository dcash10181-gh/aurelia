# AURELIA installer — Windows PowerShell.
#   irm https://raw.githubusercontent.com/dcash10181-gh/aurelia/main/install.ps1 | iex
$ErrorActionPreference = "Stop"
$Repo = "https://github.com/dcash10181-gh/aurelia.git"
$Target = if ($env:AURELIA_DIR) { $env:AURELIA_DIR } else { "$HOME\aurelia" }

function Say($m) { Write-Host "[aurelia] $m" -ForegroundColor Yellow }
function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Error "[aurelia] $cmd not found. $hint"
  }
}

Need python "Install Python 3.10+ from https://python.org"
Need git    "Install git from https://git-scm.com"
Need node   "Install Node 18+ from https://nodejs.org"
Need npm    "npm ships with Node."

if (Test-Path "$Target\.git") { Say "updating $Target"; git -C $Target pull --ff-only }
else { Say "cloning into $Target"; git clone $Repo $Target }
Set-Location $Target

Say "creating virtualenv"
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
pip install -q --upgrade pip
pip install -q -e services/api -e packages/cli
try { pip install -q -e packages/mini_llm; Say "mini LLM installed" }
catch { Say "WARN: mini LLM (torch) install failed — fallback provider still works." }

Say "installing frontend"
Push-Location apps\web; npm install --no-audit --no-fund; Pop-Location

if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Say "created .env" }
New-Item -ItemType Directory -Force data | Out-Null
python -c "from aurelia_api.config import settings; from aurelia_api.storage.db import Database; Database(settings.db_path); print('[aurelia] storage ready')"

Say "Done. Run:  aurelia start   then in another terminal:  cd apps\web; npm run dev"
Say "Open: http://localhost:3000"
