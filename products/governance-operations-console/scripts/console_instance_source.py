"""Fresh installation-bound eligibility through the existing WGCF API.

This private Platform transport reads one owner proof. It never lists records,
reads project files, accepts registration or supplies browser authority.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from agent_source_instance import (
    INSTANCE, NAME, OPERATIONS, InstanceSourceError, InstanceSourceSnapshot,
    policy_binding, strict_object, invalid_constant, validated_snapshot,
)

MAX_BYTES = 65536


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        raise InstanceSourceError("Source authority redirects are not admitted.")


class InstanceSourceReader:
    def __init__(self, *, base_url: str, caller_id: str, caller_secret: str, instance_id: str,
                 policy_reader: Callable[[], dict[str, Any]], fetch_json: Callable[[Request], Any] | None = None):
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
        except (TypeError, ValueError):
            raise InstanceSourceError("The protected Platform source-reader connection is not configured.") from None
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"} or not port or parsed.username or parsed.password
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or not isinstance(caller_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", caller_id)
                or not isinstance(caller_secret, str) or len(caller_secret) < 32 or not callable(policy_reader)
                or not isinstance(instance_id, str) or not INSTANCE.fullmatch(instance_id)):
            raise InstanceSourceError("The protected Platform source-reader connection is not configured.")
        self._base_url, self._caller_id, self._caller_secret = base_url.rstrip("/"), caller_id, caller_secret
        self._instance_id, self._policy_reader, self._fetch_json = instance_id, policy_reader, fetch_json or self._fetch

    @staticmethod
    def _fetch(request: Request) -> Any:
        try:
            with build_opener(NoRedirect()).open(request, timeout=10) as response:
                if response.status != 200:
                    raise InstanceSourceError("Current source eligibility is unavailable.")
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise InstanceSourceError("Source eligibility exceeds its read bound.")
                return json.loads(raw.decode("utf-8", errors="strict"), parse_constant=invalid_constant, object_pairs_hook=strict_object)
        except (HTTPError, URLError, OSError, UnicodeError, ValueError):
            # No response bodies, URL parameters, credentials or provider details.
            raise InstanceSourceError("Current source eligibility is unavailable; no alternate authority was selected.") from None

    def read(self, owner: str, operation: str) -> InstanceSourceSnapshot | None:
        if not isinstance(owner, str) or not NAME.fullmatch(owner) or operation not in OPERATIONS:
            raise InstanceSourceError("Select one canonical source owner and admitted operation.")
        return self._read(f"repositories/{quote(owner, safe='')}", operation, owner=owner)

    def read_provider(self, provider_repository_id: str, full_name: str, operation: str) -> InstanceSourceSnapshot | None:
        if (not isinstance(provider_repository_id, str) or not re.fullmatch(r"[1-9][0-9]{0,31}", provider_repository_id)
                or not isinstance(full_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", full_name)
                or operation not in OPERATIONS):
            raise InstanceSourceError("Select one exact provider identity and admitted operation.")
        return self._read(f"provider-repositories/github/{provider_repository_id}", operation,
            provider_repository_id=provider_repository_id, full_name=full_name)

    def _read(self, selector: str, operation: str, *, owner: str | None = None,
              provider_repository_id: str | None = None, full_name: str | None = None) -> InstanceSourceSnapshot | None:
        policy = policy_binding(self._policy_reader())
        request = Request(f"{self._base_url}/v1/instance-records/{selector}/source-authority?{urlencode({'operation': operation})}",
            method="GET", headers={"Accept": "application/json", "x-wgcf-caller-id": self._caller_id, "x-wgcf-caller-secret": self._caller_secret})
        try:
            value = self._fetch_json(request)
        except InstanceSourceError:
            raise
        except Exception:
            raise InstanceSourceError("Current source eligibility is unavailable; no alternate authority was selected.") from None
        if owner is None:
            authority = value.get("canonical_authority") if isinstance(value, dict) else None
            record_id = value.get("record_id") if isinstance(authority, dict) and authority.get("kind") == "legacy-git" else authority.get("record_id") if isinstance(authority, dict) else None
            if not isinstance(record_id, str) or not record_id.startswith("repo:") or not NAME.fullmatch(record_id[5:]):
                raise InstanceSourceError("The physical source identity has no canonical owner binding.")
            owner = record_id[5:]
        snapshot = validated_snapshot(value, instance_id=self._instance_id, owner=owner, operation=operation, policy_ref=policy)
        if snapshot is not None and provider_repository_id is not None:
            binding = snapshot.source_authority["provider_repository"]
            if binding["provider_repository_id"] != provider_repository_id or binding["full_name"] != full_name:
                raise InstanceSourceError("The current source proof differs from the selected physical repository.")
        if self._policy_reader() != policy:
            raise InstanceSourceError("Governance policy changed during source eligibility inspection.")
        return snapshot
