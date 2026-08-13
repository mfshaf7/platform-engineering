#!/usr/bin/env bash
set -euo pipefail

readonly WINDOWS_TASK_NAME="${WINDOWS_TASK_NAME:-PlatformCoreHostStack}"
readonly WINDOWS_LISTEN_PORT="${WINDOWS_LISTEN_PORT:-18183}"
readonly WSL_NODE_PORT="${WSL_NODE_PORT:-32183}"

command -v powershell.exe >/dev/null 2>&1 || {
  echo "powershell.exe is required to refresh Windows localhost access." >&2
  exit 1
}

[[ "${WINDOWS_TASK_NAME}" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "WINDOWS_TASK_NAME contains unsupported characters." >&2
  exit 1
}
[[ "${WINDOWS_LISTEN_PORT}" =~ ^[0-9]+$ && "${WSL_NODE_PORT}" =~ ^[0-9]+$ ]] || {
  echo "Windows listen and WSL node ports must be numeric." >&2
  exit 1
}

powershell.exe -NoProfile -Command "
\$ErrorActionPreference = 'Stop'
\$TaskName = '${WINDOWS_TASK_NAME}'
\$ListenPort = [int]${WINDOWS_LISTEN_PORT}
\$ConnectPort = [int]${WSL_NODE_PORT}
Start-ScheduledTask -TaskName \$TaskName

\$deadline = (Get-Date).AddSeconds(30)
do {
  \$rows = netsh interface portproxy show v4tov4 | Out-String
  \$pattern = '(?m)^\s*127\.0\.0\.1\s+' + \$ListenPort + '\s+\S+\s+' + \$ConnectPort + '\s*$'
  if (\$rows -match \$pattern) {
    Write-Output \"Windows localhost mapping ready: 127.0.0.1:\$ListenPort -> WSL:\$ConnectPort\"
    exit 0
  }
  Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt \$deadline)

throw \"Windows localhost mapping did not appear: 127.0.0.1:\$ListenPort -> WSL:\$ConnectPort\"
"
