# Host Runtime Drift Recovery

## Purpose

Use this runbook for production-impacting issues caused by live host or environment drift rather than source defects.

Examples:

- Windows portproxy drift
- WSL network drift
- firewall rule drift
- Ollama listener availability
- Windows or WSL service state

## Classification rule

Use this runbook only when the failure is outside the gateway artifact and would not be fixed by rebuilding the image.

If the fix would be lost on host restart or environment reprovisioning, document the recovery step here and then decide whether the host bootstrap/runbook also needs improvement.

## Standard workflow

1. Reproduce the live failure.
2. Verify whether the source artifact is already correct.
3. Confirm the break is in host/runtime state.
4. Repair the host/runtime state.
5. Re-run the same live verification from the affected runtime path.
6. Record the exact commands and evidence.

## Example: Ollama forward path drift

Symptom:

- Telegram topic routing works
- model-backed agents fail with `fetch failed`
- gateway pod cannot reach `http://host.docker.internal:11434`

Verification:

```bash
python3 - <<'PY'
import urllib.request
for url in ['http://host.docker.internal:11434/api/tags']:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print(url, r.status)
    except Exception as e:
        print(url, e)
PY

k3s kubectl -n openclaw exec deploy/openclaw-gateway -- \
  sh -lc 'wget -qO- --timeout=5 http://host.docker.internal:11434/api/tags | head -c 120'
```

Windows-side verification:

```powershell
Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue
netsh interface portproxy show v4tov4
curl.exe http://127.0.0.1:11434/api/tags
```

Recovery:

```powershell
netsh interface portproxy delete v4tov4 listenport=11434 listenaddress=<resolved-host.docker.internal-ip>
netsh interface portproxy add v4tov4 listenport=11434 listenaddress=<resolved-host.docker.internal-ip> connectport=11434 connectaddress=127.0.0.1
```

Completion check:

- WSL can reach `host.docker.internal:11434`
- the prod pod can reach the same endpoint
- model-backed Telegram topics respond again

## Required evidence

For every environment-drift repair, record:

- failing endpoint or service
- fixed host/runtime component
- before/after connectivity or service state
- whether a repo/runbook improvement is still needed

## Escalation rule

If the same host/runtime drift happens more than once, convert it into one of:

- stronger bootstrap automation
- explicit periodic health check
- improved runbook with verification guardrails
