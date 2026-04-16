#!/usr/bin/env bash
set -euo pipefail

OPENPROJECT_NODEPORT="${OPENPROJECT_NODEPORT:-32083}"
WINDOWS_URL="http://127.0.0.1:${OPENPROJECT_NODEPORT}"

echo "Preferred Windows/operator URL:"
echo "  ${WINDOWS_URL}"
echo
echo "WSL shell-local fallback:"
echo "  k3s kubectl -n openproject port-forward svc/openproject 8080:8080"
echo "  then open http://127.0.0.1:8080/login"
echo

if command -v powershell.exe >/dev/null 2>&1; then
  if powershell.exe -NoProfile -Command "try { \$r = Invoke-WebRequest -UseBasicParsing '${WINDOWS_URL}/login' -TimeoutSec 5; if (\$r.StatusCode -ge 200 -and \$r.StatusCode -lt 400) { exit 0 } else { exit 1 } } catch { exit 1 }" >/dev/null 2>&1; then
    echo "Windows localhost path is responding."
  else
    echo "Windows localhost path is not responding yet." >&2
    echo "If OpenProject is healthy inside k3s, refresh the managed portproxy path:" >&2
    echo "  1. make render-windows-bootstrap" >&2
    echo "  2. powershell.exe -NoProfile -Command \"Start-ScheduledTask -TaskName 'PlatformCoreHostStack'\"" >&2
  fi
fi
