"""Dedicated Codex account custody through a fixed Platform Vault KV path."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request

from model_configuration import digest, locked
from ollama_adapter import ProviderIntegrityError, ProviderUnavailable


class NoCredentialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Vault redirect is not an accepted credential destination", headers, fp)


class VaultCodexAccount:
    def __init__(self, *, address: str, mount: str, path: str, token_file: Path,
                 runtime_root: Path, opener=None):
        # All values come from the accepted owner runtime, never an API body.
        if not address.startswith(("https://", "http://127.0.0.1:", "http://vault.")):
            raise ProviderIntegrityError("Vault must use the accepted Platform endpoint.")
        if any(part in {"", ".", ".."} for part in (mount + "/" + path).split("/")):
            raise ProviderIntegrityError("Dedicated Vault account path is invalid.")
        self.url = address.rstrip("/") + "/v1/" + mount + "/data/" + path
        self.token_file, self.runtime_root = token_file, runtime_root
        self.opener = opener or urllib.request.build_opener(NoCredentialRedirect()).open

    def _request(self, payload=None):
        try:
            resolved = self.token_file.resolve(strict=True)
            if not resolved.is_relative_to(self.token_file.parent.resolve()) or resolved.stat().st_mode & 0o077:
                raise ValueError()
            token = self.token_file.read_text().strip()
            if not token:
                raise ValueError()
            request = urllib.request.Request(self.url, data=None if payload is None else json.dumps(payload).encode(),
                                             headers={"X-Vault-Token": token, "Content-Type": "application/json"})
            with self.opener(request, timeout=8) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError()
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            if error.code == 404 and payload is None:
                return None
            raise ProviderUnavailable("Dedicated provider account custody is unavailable.") from None
        except (OSError, ValueError, urllib.error.URLError):
            raise ProviderUnavailable("Dedicated provider account custody is unavailable.") from None

    @staticmethod
    def validate_account(raw: bytes):
        try:
            value = json.loads(raw)
            if len(raw) > 1_000_000 or value.get("auth_mode") != "chatgpt" or not isinstance(value.get("tokens"), dict) or not value["tokens"] or value.get("OPENAI_API_KEY"):
                raise ValueError()
            return value
        except (ValueError, TypeError, AttributeError):
            raise ProviderIntegrityError("A dedicated managed ChatGPT account is required; API-key billing is a separate backend.") from None

    @contextmanager
    def project(self, *, allow_missing=False, login_command_id=None):
        self.runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        # A native refresh or sign-in is serialized with every reader; no
        # concurrent app-server can silently overwrite a newer account state.
        with locked(self.runtime_root / "account.lock", blocking=False):
            retained = self._request()
            version = retained["data"]["metadata"]["version"] if retained else 0
            account = retained["data"]["data"].get("account") if retained else None
            if account is None and not allow_missing:
                raise ProviderUnavailable("Sign in to the dedicated Codex backend through Model Operations.")
            with tempfile.TemporaryDirectory(prefix="account-", dir=self.runtime_root) as temporary:
                home = Path(temporary)
                original = None
                if account is not None:
                    original = json.dumps(account, sort_keys=True).encode()
                    self.validate_account(original)
                    fd = os.open(home / "auth.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(original)
                def persist(raw: bytes):
                    value = self.validate_account(raw)
                    if original is not None and value == account and login_command_id is None:
                        return
                    data = dict(retained["data"]["data"]) if retained else {}
                    data["account"] = value
                    if login_command_id is not None:
                        data["login_command_id"] = login_command_id
                    self._request({"options": {"cas": version}, "data": data})
                # Stable across token refresh, different after another native
                # login. Kept on the custody callback, never in projected HOME
                # or browser-facing metadata.
                persist.account_binding = digest({
                    "login": retained["data"]["data"].get("login_command_id") if retained else None,
                    "account": account.get("tokens", {}).get("account_id") or digest(account),
                }) if account else None
                yield home, persist

    def completed_login(self, command_id):
        value = self._request()
        if not value or value["data"]["data"].get("login_command_id") != command_id:
            return False
        self.validate_account(json.dumps(value["data"]["data"].get("account")).encode())
        return True
