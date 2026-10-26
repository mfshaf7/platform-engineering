#!/usr/bin/env python3
"""Build and serve the existing Console from private, source-bound standalone output."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile


ARTIFACT_ROOT = Path.home() / ".local/state/platform-engineering/governance-console-cross-domain/private/frontend"
MANIFEST = "platform-artifact.json"


class FrontendArtifactError(RuntimeError):
    pass


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise FrontendArtifactError("Console artifact directory must not be a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise FrontendArtifactError("Console artifact directory has a different owner")
    path.chmod(0o700)


def command(args: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise FrontendArtifactError(f"Console artifact prerequisite failed: {Path(args[0]).name}")
    return result.stdout.strip()


def toolchain() -> tuple[str, str, str]:
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        raise FrontendArtifactError("Console build requires the admitted Node/npm toolchain")
    version = command([node, "--version"])
    if not version.startswith("v22."):
        raise FrontendArtifactError("Console build requires Node22")
    return node, npm, version


def artifact_path(revision: str, node_version: str, root: Path = ARTIFACT_ROOT) -> Path:
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise FrontendArtifactError("Console artifact requires an exact source revision")
    key = hashlib.sha256(f"console-standalone/v1:{revision}:{node_version}".encode()).hexdigest()
    return root / key


def inventory(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise FrontendArtifactError("Console artifact contains a symlink")
        if rel == MANIFEST or rel.startswith(".next/cache/"):
            continue
        if rel.startswith(".next/server/route-cache/"):
            # Next15 also writes incremental HTML/RSC response data here.
            # It is not compiled code; never exempt executable modules.
            if path.is_file() and path.suffix not in {".html", ".meta", ".rsc", ".body"}:
                raise FrontendArtifactError("Console route cache contains an unexpected file type")
            continue
        if path.is_file():
            if path.name == ".env" or path.name.startswith(".env."):
                raise FrontendArtifactError("Console artifact contains an environment file")
            files[rel] = digest_file(path)
    return files


def validate_artifact(root: Path, revision: str, node_version: str) -> dict:
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.getuid():
        raise FrontendArtifactError("Console standalone artifact is unavailable or has unsafe custody")
    path = root / MANIFEST
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise FrontendArtifactError("Console artifact manifest is unavailable")
    try:
        value = json.loads(path.read_text())
    except (ValueError, OSError):
        raise FrontendArtifactError("Console artifact manifest is invalid") from None
    if (value.get("schema_version") != 1 or value.get("source_revision") != revision
            or value.get("node_version") != node_version or value.get("files") != inventory(root)
            or not all((root / required).is_file() for required in ["server.js", ".next/BUILD_ID", "package.json"])
            or not (root / ".next/static").is_dir()):
        raise FrontendArtifactError("Console artifact is incomplete, changed or bound to different source/toolchain")
    return value


def build_environment() -> dict[str, str]:
    # Never build with the live operator session, caller secrets or provider bindings.
    allowed = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}
    allowed.update({"NEXT_TELEMETRY_DISABLED": "1", "NODE_OPTIONS": "--max-old-space-size=4096"})
    return allowed


def build_command(args: list[str], source: Path, env: dict[str, str], log) -> None:
    process = subprocess.Popen(args, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        code = process.wait(timeout=900)
    except subprocess.TimeoutExpired:
        code = -1
    if code:
        # npm can leave compiler children behind; contain the whole build group.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise FrontendArtifactError("Console standalone build failed or timed out; inspect its private build log")


def prepare(source: Path, revision: str, root: Path = ARTIFACT_ROOT, *, stop_consumer=None) -> Path:
    _, npm, version = toolchain()
    if command(["git", "-C", str(source), "rev-parse", "HEAD"]) != revision or command(["git", "-C", str(source), "status", "--porcelain"]):
        raise FrontendArtifactError("Console build requires clean selected source")
    private_directory(root)
    target = artifact_path(revision, version, root)
    if target.is_symlink() or (target.exists() and target.stat().st_uid != os.getuid()):
        raise FrontendArtifactError('Console artifact has unsafe recovery custody')
    incident = root / f'.recovery-{target.name}.json'
    quarantine = root / f'.corrupt-{target.name}'
    if incident.is_symlink() or quarantine.is_symlink():
        raise FrontendArtifactError('Console recovery paths must not be symlinks')
    if target.exists():
        try:
            validate_artifact(target, revision, version)
            return target
        except FrontendArtifactError:
            if incident.exists() and json.loads(incident.read_text()).get('phase') != 'closed':
                raise FrontendArtifactError('Console artifact already consumed its repair attempt; inspect recovery evidence') from None
            if stop_consumer is not None:
                stop_consumer()
            for cwd in Path('/proc').glob('[0-9]*/cwd'):
                try:
                    if cwd.resolve(strict=True).is_relative_to(target):
                        raise FrontendArtifactError('Stop the managed Console before repairing its artifact')
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    continue
            if quarantine.exists():
                raise FrontendArtifactError('Earlier Console quarantine still requires owner disposition')
            incident.write_text(json.dumps({'phase': 'attempted', 'source_revision': revision, 'node_version': version}) + '\n')
            incident.chmod(0o600)
            target.rename(quarantine)
    elif incident.exists() and json.loads(incident.read_text()).get('phase') != 'closed':
        raise FrontendArtifactError('Interrupted Console rebuild requires inspection; no automatic replay')
    # One build at a time; the complete-runtime owner already serializes activation.
    work = Path(tempfile.mkdtemp(prefix=".building-", dir=root))
    private_directory(work)
    exported, release = work / "source", work / "release"
    exported.mkdir(mode=0o700)
    archive = work / "source.tar"
    with archive.open("wb") as output:
        result = subprocess.run(["git", "-C", str(source), "archive", "--format=tar", revision], stdout=output, stderr=subprocess.PIPE)
    if result.returncode:
        raise FrontendArtifactError("Console source export failed")
    with tarfile.open(archive) as files:
        files.extractall(exported, filter="data")
    env = build_environment()
    with (work / "build.log").open("w") as log:
        for args in ([npm, "ci"], [npm, "run", "build"]):
            build_command(args, exported, env, log)
    standalone = exported / ".next/standalone"
    if not (standalone / "server.js").is_file():
        raise FrontendArtifactError("Console build did not produce standalone output")
    for path in standalone.rglob("*"):
        if path.is_symlink() and not path.resolve().is_relative_to(exported):
            raise FrontendArtifactError("Console standalone trace escapes the isolated build")
    shutil.copytree(standalone, release)
    shutil.copytree(exported / ".next/static", release / ".next/static", dirs_exist_ok=True)
    if (exported / "public").is_dir():
        shutil.copytree(exported / "public", release / "public", dirs_exist_ok=True)
    manifest = {"schema_version": 1, "source_revision": revision, "node_version": version,
                "lock_sha256": digest_file(exported / "package-lock.json"), "files": inventory(release)}
    (release / MANIFEST).write_text(json.dumps(manifest, sort_keys=True) + "\n")
    private_directory(release)
    validate_artifact(release, revision, version)
    release.rename(target)
    if quarantine.exists():
        incident.write_text(json.dumps({'phase': 'rebuilt-awaiting-readiness', 'source_revision': revision, 'node_version': version}) + '\n')
    shutil.copyfile(work / "build.log", root / f".build-{target.name}.log")
    (root / f".build-{target.name}.log").chmod(0o600)
    shutil.rmtree(work)
    return target


def confirm_recovery(target: Path) -> None:
    """Called only after native frontend process/source/byte checks passed."""
    incident = target.parent / f'.recovery-{target.name}.json'
    quarantine = target.parent / f'.corrupt-{target.name}'
    if incident.is_symlink() or quarantine.is_symlink():
        raise FrontendArtifactError('unsafe Console recovery custody')
    if incident.exists():
        value = json.loads(incident.read_text())
        if value.get('phase') == 'rebuilt-awaiting-readiness':
            if quarantine.exists():
                shutil.rmtree(quarantine)  # only superseded derived output, never source/data
            value['phase'] = 'closed'
            incident.write_text(json.dumps(value) + '\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "serve", "inspect"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--port", type=int, default=3317)
    args = parser.parse_args()
    try:
        node, _, version = toolchain()
        if args.action == "prepare":
            if not args.source:
                raise FrontendArtifactError("Console preparation requires its owner source")
            print(prepare(args.source, args.revision))
            return 0
        if not args.artifact:
            raise FrontendArtifactError("Console inspection/start requires the selected artifact")
        value = validate_artifact(args.artifact, args.revision, version)
        if args.action == "inspect":
            print(json.dumps({"source_revision": value["source_revision"], "node_version": version, "files": len(value["files"])}))
            return 0
        if not 1024 <= args.port <= 65535:
            raise FrontendArtifactError("Console loopback port is invalid")
        os.chdir(args.artifact)
        env = dict(os.environ, NODE_ENV="production", HOSTNAME="127.0.0.1", PORT=str(args.port), NEXT_TELEMETRY_DISABLED="1",
                   NODE_OPTIONS="--max-old-space-size=2048")
        os.execve(node, [node, str(args.artifact / "server.js")], env)
    except (FrontendArtifactError, OSError, tarfile.TarError) as exc:
        print(f"Console frontend {args.action} failed: {exc}", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
