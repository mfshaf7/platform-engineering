#!/usr/bin/env python3
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


def run(cmd):
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"command failed: {cmd}")
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubectl", default="k3s kubectl")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--secret-name", required=True)
    parser.add_argument("--vault-addr", default=os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200"))
    parser.add_argument("--vault-token", default=os.environ.get("VAULT_TOKEN"))
    parser.add_argument("--vault-path", required=True, help="Full KV v2 path under the mount, for example openclaw/stage/gateway")
    parser.add_argument("--mount", default="kv")
    args = parser.parse_args()

    if not args.vault_token:
        print("vault token missing; set --vault-token or VAULT_TOKEN", file=sys.stderr)
        return 1

    secret_json = run(
        args.kubectl.split()
        + ["-n", args.namespace, "get", "secret", args.secret_name, "-o", "json"]
    )
    secret = json.loads(secret_json)
    data = {
        key: base64.b64decode(value).decode("utf-8")
        for key, value in secret.get("data", {}).items()
    }

    payload = json.dumps({"data": data}).encode("utf-8")
    url = f"{args.vault_addr.rstrip('/')}/v1/{args.mount}/data/{args.vault_path.lstrip('/')}"
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Vault-Token": args.vault_token,
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            if response.status not in (200, 204):
                print(f"vault write failed with status {response.status}", file=sys.stderr)
                return 1
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1

    print(
        f"migrated {args.namespace}/{args.secret_name} to {args.mount}/{args.vault_path.lstrip('/')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
