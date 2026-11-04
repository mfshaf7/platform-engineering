"""Private record bindings within the existing accepted Console lifecycle.

This does not enable a candidate policy or create a provider grant. Preparation
retains one installation identity; binding follows the existing WGCF migration.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import uuid

from agent_source_instance import strict_object

SECRET_NAME = "governance-console-instance-records"
MIGRATION = "0016_instance_records"


def _private(path: Path):
    try: path.mkdir(mode=0o700)
    except FileExistsError: pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink() or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077 or path.resolve() != path:
        raise RuntimeError("Internal registration requires its original private runtime state.")


def _read(path: Path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 16384:
            raise RuntimeError("The original installation binding is invalid.")
        return json.loads(stream.read(16385), object_pairs_hook=strict_object)


def _write(path: Path, value):
    if path.is_symlink(): raise RuntimeError("The private installation binding is linked.")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as stream:
            temporary = Path(stream.name); stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def enabled(policy):
    return policy.get("instance_records", {}).get("enabled") is True


def prepare(policy, *, state_root: Path, gateway: str, provider_secret: str, wgcf_port: int):
    if not enabled(policy): return None
    if str(state_root) != policy.get("runtime_state_root") or not state_root.is_absolute():
        raise RuntimeError("Internal registration must reuse the accepted runtime state root.")
    address = ipaddress.ip_address(gateway)
    if address.version != 4 or not any(address in ipaddress.ip_network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")):
        raise RuntimeError("The protected host provider must use the existing private CNI gateway.")
    if type(wgcf_port) is not int or not 1 <= wgcf_port <= 65535 or not isinstance(provider_secret, str) or len(provider_secret) < 32:
        raise RuntimeError("The existing protected runtime connection is incomplete.")
    _private(state_root); private = state_root / "private"; _private(private)
    original = private / "instance-installation.json"
    if original.exists():
        value = _read(original)
    else:
        if any((private / name).exists() for name in ("instance-source-reader.json", "instance-source-host.json")):
            raise RuntimeError("The original installation identity is missing; preserve derived bindings and recover it.")
        value = {"schema_version": 1, "instance_id": f"installation:{uuid.uuid4()}", "source_reader_secret": secrets.token_urlsafe(48)}
        _write(original, value)  # Original identity precedes every derived binding.
    if (not isinstance(value, dict) or set(value) != {"schema_version", "instance_id", "source_reader_secret"} or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["instance_id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value["instance_id"])
            or not isinstance(value["source_reader_secret"], str) or len(value["source_reader_secret"]) < 32 or value["source_reader_secret"] == provider_secret):
        raise RuntimeError("The retained installation identity is invalid or shares a caller credential.")
    _write(private / "instance-source-reader.json", {"schema_version": 1, "instance_id": value["instance_id"],
        "base_url": f"http://127.0.0.1:{wgcf_port}", "caller_id": "platform-engineering-source-reader", "caller_secret": value["source_reader_secret"]})
    _write(private / "instance-source-host.json", {"schema_version": 1, "instance_id": value["instance_id"],
        "connection": {"baseUrl": f"http://{gateway}:{policy['runtime']['provider_port']}", "callerId": "operator-orchestration-service",
            "callerSecret": provider_secret, "allowHttp": True, "allowPrivateHttp": True}})
    return value


def bind(policy, *, state_root: Path, operator: str, run):
    if not enabled(policy): return
    private = state_root / "private"; _private(private)
    value = _read(private / "instance-installation.json")
    wgcf = policy["repository_provisioning"]["wgcf"]
    ns = wgcf["namespace_pattern"].format(operator=operator)
    deployment = wgcf["deployment"]
    observed = run(["k3s", "kubectl", "-n", ns, "exec", f"deployment/{deployment}", "--", "alembic", "current"])
    revisions = re.findall(r"(?m)^([A-Za-z0-9_]{1,32})(?:\s+\(head\))?\s*$", observed.stdout.strip())
    if len(revisions) != 1:
        raise RuntimeError("Internal registration requires the accepted WGCF migration before enabling its readers or writes.")
    if revisions[0] != MIGRATION:
        history = run(["k3s", "kubectl", "-n", ns, "exec", f"deployment/{deployment}", "--", "alembic", "history", "-r", f"{MIGRATION}:{revisions[0]}"])
        if MIGRATION not in history.stdout or revisions[0] not in history.stdout:
            raise RuntimeError("Internal registration requires its WGCF migration as an ancestor of the current database revision.")
    manifest = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": SECRET_NAME, "namespace": ns}, "type": "Opaque",
        "stringData": {"WGCF_INSTANCE_RECORDS_ENABLED": "true", "WGCF_INSTANCE_ID": value["instance_id"],
            "WGCF_INSTANCE_SOURCE_CALLER_ID": "platform-engineering-source-reader", "WGCF_INSTANCE_SOURCE_CALLER_SECRET": value["source_reader_secret"]}}
    run(["k3s", "kubectl", "apply", "-f", "-"], input_value=json.dumps(manifest))
    run(["k3s", "kubectl", "-n", ns, "set", "env", f"deployment/{deployment}", f"--from=secret/{SECRET_NAME}"])
    run(["k3s", "kubectl", "-n", ns, "rollout", "status", f"deployment/{deployment}", "--timeout=300s"])
    runtime = policy["runtime"]; oos_ns = runtime["namespace_pattern"].format(operator=operator)
    # Same original OOS role/credential; no registration rights for the source reader.
    env = {"OOS_INSTANCE_RECORDS_ENABLED": "true", "OOS_INSTANCE_ID": value["instance_id"],
        "WGCF_INSTANCE_RECORDS_BASE_URL": f"http://{wgcf['service']}.{ns}.svc.cluster.local:{wgcf['port']}"}
    manifest = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": SECRET_NAME, "namespace": oos_ns}, "type": "Opaque", "stringData": env}
    run(["k3s", "kubectl", "apply", "-f", "-"], input_value=json.dumps(manifest))
    run(["k3s", "kubectl", "-n", oos_ns, "set", "env", f"deployment/{runtime['oos_deployment']}", f"--from=secret/{SECRET_NAME}"])
    run(["k3s", "kubectl", "-n", oos_ns, "rollout", "status", f"deployment/{runtime['oos_deployment']}", "--timeout=300s"])
