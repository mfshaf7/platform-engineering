#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/dispatch_github_workflow_from_k3s_secret.sh <workflow-file> [--ref <git-ref>] [--repo <owner/name>] [-f key=value ...] [--dry-run]

Examples:
  scripts/dispatch_github_workflow_from_k3s_secret.sh build-gateway-image.yaml --ref main -f environment=stage
  scripts/dispatch_github_workflow_from_k3s_secret.sh promote-environment.yaml --ref main -f environment=prod
USAGE
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" || $# -lt 1 ]]; then
  usage
  exit 0
fi

workflow_file=$1
shift

repo="mfshaf7/platform-engineering"
ref="main"
secret_namespace="argocd"
secret_name="platform-engineering-repo"
secret_key="password"
dry_run=0
field_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo=${2:?missing value for --repo}
      shift 2
      ;;
    --ref)
      ref=${2:?missing value for --ref}
      shift 2
      ;;
    --secret-namespace)
      secret_namespace=${2:?missing value for --secret-namespace}
      shift 2
      ;;
    --secret-name)
      secret_name=${2:?missing value for --secret-name}
      shift 2
      ;;
    --secret-key)
      secret_key=${2:?missing value for --secret-key}
      shift 2
      ;;
    -f)
      field_args+=("-f" "${2:?missing key=value for -f}")
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

token_b64=$(python3 -c 'import json,subprocess,sys; namespace,name,key=sys.argv[1:4]; raw=subprocess.check_output(["k3s","kubectl","-n",namespace,"get","secret",name,"-o","json"], text=True); data=json.loads(raw).get("data", {}); value=data.get(key, "");
import sys as _sys;
(_sys.stderr.write(f"missing secret data key: {key}\n"), _sys.exit(1)) if not value else None; print(value, end="")' "$secret_namespace" "$secret_name" "$secret_key")

export GH_TOKEN
GH_TOKEN=$(printf '%s' "$token_b64" | base64 -d | tr -d '\r\n')
if [[ -z "$GH_TOKEN" ]]; then
  echo "Decoded GH_TOKEN is empty" >&2
  exit 1
fi

cmd=(gh workflow run "$workflow_file" --repo "$repo" --ref "$ref")
cmd+=("${field_args[@]}")

if [[ $dry_run -eq 1 ]]; then
  printf 'Dispatch command:'
  for part in "${cmd[@]}"; do
    printf ' %q' "$part"
  done
  printf '\n'
  exit 0
fi

"${cmd[@]}"
