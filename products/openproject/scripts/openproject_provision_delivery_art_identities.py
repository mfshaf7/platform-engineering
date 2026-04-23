#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = SCRIPT_DIR.parent
DEFAULT_CONTRACT_PATH = PRODUCT_DIR / "delivery-art-identities.json"
DEFAULT_PROVISIONER = SCRIPT_DIR / "openproject_provision_identity.sh"


def load_contract(path: Path) -> dict:
    payload = json.loads(path.read_text())
    identities = payload.get("identities")
    if not isinstance(identities, list) or not identities:
        raise SystemExit(f"{path} must declare a non-empty identities array")

    seen_logins: set[str] = set()
    for entry in identities:
        login = entry.get("login")
        if not isinstance(login, str) or not login.strip():
            raise SystemExit(f"{path} contains an identity without a login")
        if login in seen_logins:
            raise SystemExit(f"{path} contains a duplicate login: {login}")
        seen_logins.add(login)
        if not isinstance(entry.get("project_identifiers"), list) or not entry["project_identifiers"]:
            raise SystemExit(f"{path} entry {login} must declare project_identifiers")
        if not isinstance(entry.get("role_names"), list) or not entry["role_names"]:
            raise SystemExit(f"{path} entry {login} must declare role_names")
    return payload


def build_env(entry: dict) -> dict[str, str]:
    env = os.environ.copy()
    env["TARGET_LOGIN"] = entry["login"]
    env["TARGET_FIRSTNAME"] = entry["firstname"]
    env["TARGET_LASTNAME"] = entry["lastname"]
    env["TARGET_MAIL"] = entry["mail"]
    env["TARGET_PROJECT_IDENTIFIER"] = entry["project_identifiers"][0]
    env["TARGET_PROJECT_IDENTIFIERS_JSON"] = json.dumps(entry["project_identifiers"])
    env["TARGET_ROLE_NAMES_JSON"] = json.dumps(entry["role_names"])
    env["ISSUE_API_TOKEN"] = "true" if entry.get("issue_api_token") else "false"
    if entry.get("token_name"):
        env["TARGET_TOKEN_NAME"] = entry["token_name"]
    else:
        env.pop("TARGET_TOKEN_NAME", None)
    if entry.get("vault_secret_path"):
        env["VAULT_SECRET_PATH"] = entry["vault_secret_path"]
    else:
        env.pop("VAULT_SECRET_PATH", None)
    return env


def main() -> int:
    contract_path = Path(os.environ.get("OPENPROJECT_DELIVERY_ART_IDENTITY_CONTRACT", DEFAULT_CONTRACT_PATH))
    provisioner = Path(os.environ.get("OPENPROJECT_IDENTITY_PROVISIONER", DEFAULT_PROVISIONER))

    if not contract_path.is_file():
        raise SystemExit(f"missing contract file: {contract_path}")
    if not provisioner.is_file():
        raise SystemExit(f"missing provisioner script: {provisioner}")

    contract = load_contract(contract_path)
    identities = contract["identities"]
    print(
        f"Provisioning {len(identities)} Workspace Delivery ART identities from {contract_path}",
        file=sys.stderr,
    )
    for entry in identities:
        print(f"- {entry['login']}", file=sys.stderr)
        subprocess.run([str(provisioner)], check=True, env=build_env(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
