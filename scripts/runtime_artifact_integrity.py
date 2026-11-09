#!/usr/bin/env python3
"""Finite, root-installed dev-integration image integrity and cache recovery.

No caller-supplied paths, image references, namespaces or shell commands. The
installed policy is the admission boundary. Container writable layers and data
volumes are never mounted or modified by this helper.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import ssl
import stat
import subprocess
import tarfile
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler, ProxyHandler

INSTALL = Path('/usr/local/lib/platform-engineering/runtime-integrity')
STATE = Path('/var/lib/platform-engineering/runtime-integrity')
K3S = '/usr/local/bin/k3s'
DIGEST = re.compile(r'sha256:[0-9a-f]{64}\Z')
ENVIRONMENT = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
               'HOME': '/root', 'KUBECONFIG': '/etc/rancher/k3s/k3s.yaml'}


class IntegrityError(RuntimeError):
    pass


def validate_admission(policy):
    if (policy.get('schema_version') != 1 or policy.get('lane') != 'dev-integration'
        or not isinstance(policy.get('automatic_repair'), bool)):
        raise IntegrityError('invalid local image recovery admission')
    for name in ('namespaces', 'repositories'):
        if not isinstance(policy.get(name), list) or not 1 <= len(policy[name]) <= 64:
            raise IntegrityError('invalid admitted image recovery scope')
    if any(not isinstance(ns, str) or len(ns) > 63 or not re.fullmatch(r'devint-[a-z0-9][a-z0-9-]*', ns) for ns in policy['namespaces']):
        raise IntegrityError('only explicit dev-integration namespaces are admitted')
    if any(not isinstance(repo, str) or not re.fullmatch(r'(docker.io|ghcr.io)/(?:[a-z0-9][a-z0-9._-]*/)+[a-z0-9][a-z0-9._-]*', repo) for repo in policy['repositories']):
        raise IntegrityError('only explicit public image repositories are admitted')
    return policy


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def cleanup_stale_inspection_views(policy):
    """Retire only our unmounted, pre-boot read views of admitted image chains."""
    chains = set()
    for path in STATE.glob('*.baseline.json'):
        if path.is_symlink():
            continue
        try:
            envelope = json.loads(path.read_bytes())
            value = envelope['value']
            if (envelope['digest'] == hashlib.sha256(canonical(value)).hexdigest()
                and value['reference'].split('@')[0] in policy['repositories']
                and DIGEST.fullmatch(value['chain'])):
                chains.add(value['chain'])
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue  # Unknown custody/content never authorizes cleanup.
    if not chains:
        return []
    boot_start = time.time() - float(Path('/proc/uptime').read_text().split()[0])
    mounted_paths = {line.split()[4] for line in Path('/proc/self/mountinfo').read_text().splitlines()}
    removed = []
    for line in command(ctr('leases', 'ls')).decode().splitlines()[1:]:
        fields = line.split(None, 2)
        if len(fields) != 3:
            continue
        key, created, labels = fields
        if not re.fullmatch(re.escape(str(STATE)) + r'/mount-[a-z0-9_-]{6,32}', key):
            continue
        labels = dict(item.split('=', 1) for item in labels.split(',') if '=' in item)
        if labels.get('containerd.io/gc.ref.snapshot.overlayfs') != key or key in mounted_paths:
            continue
        try:
            created_at = datetime.fromisoformat(created.replace('Z', '+00:00'))
            if created_at.tzinfo is None or created_at.timestamp() >= boot_start:
                continue
        except ValueError:
            continue
        path = Path(key)
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o022 or any(path.iterdir())):
                continue
        result = subprocess.run([K3S, *ctr('snapshots', 'info', key)],
                                capture_output=True, timeout=30, env=ENVIRONMENT)
        if result.returncode:
            if b'not found' in result.stderr.lower():
                continue
            raise IntegrityError('cannot inspect retained verifier view')
        info = json.loads(result.stdout)
        try:
            snapshot_created = datetime.fromisoformat(info['Created'].replace('Z', '+00:00'))
            eligible = (info['Name'] == key and info['Kind'] == 'View' and info['Parent'] in chains
                        and snapshot_created.tzinfo is not None and snapshot_created.timestamp() < boot_start)
        except (KeyError, ValueError, TypeError):
            eligible = False
        if not eligible:
            continue
        for args in (ctr('leases', 'rm', key), ctr('snapshots', 'rm', key)):
            result = subprocess.run([K3S, *args], capture_output=True, timeout=30, env=ENVIRONMENT)
            if result.returncode and b'not found' not in result.stderr.lower():
                raise IntegrityError('retained verifier view cleanup failed; inspect owner state')
        if path.exists():
            path.rmdir()  # Never recursively remove files or follow a link.
        removed.append({'view': key, 'parent': info['Parent'], 'created': created})
    if removed:
        write(STATE / 'last-view-cleanup.json', {
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'removed': removed})
    return removed


def write(path, value):
    temporary = path.with_suffix('.pending')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def command(args, timeout=120):
    result = subprocess.run([K3S, *args], capture_output=True, timeout=timeout, env=ENVIRONMENT)
    if result.returncode:
        raise IntegrityError('native image operation failed: ' + ' '.join(args[:3]))
    return result.stdout


def native_json(args):
    return json.loads(command(args))


def ctr(*args):
    return ['ctr', '-n', 'k8s.io', *args]


def path_key(name):
    while name.startswith('./'):
        name = name[2:]
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\x00' in name:
        raise IntegrityError('unsafe image archive path')
    return path.as_posix().rstrip('/')


def layer_inventory(archive, entries):
    """Replay OCI changes without extracting untrusted paths or following links."""
    updates, removals = {}, []
    with tarfile.open(fileobj=archive, mode='r|*') as layer:
        for member in layer:
            name = path_key(member.name)
            if name in ('', '.'):
                continue
            for parent in PurePosixPath(name).parents:
                item = updates.get(str(parent), entries.get(str(parent), {}))
                if item.get('kind') in {'link', 'hardlink'}:
                    raise IntegrityError('unsupported OCI parent-link traversal; cache unchanged')
            base = PurePosixPath(name).name
            parent = str(PurePosixPath(name).parent)
            prefix = '' if parent == '.' else parent + '/'
            if base == '.wh..wh..opq':
                removals.extend(key for key in entries if key.startswith(prefix))
                continue
            if base.startswith('.wh.'):
                victim = prefix + base[4:]
                removals.extend(key for key in entries if key == victim or key.startswith(victim + '/'))
                continue
            item = {'mode': member.mode & 0o7777}
            if member.isfile():
                h = hashlib.sha256()
                source = layer.extractfile(member)
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    h.update(block)
                item.update(kind='file', sha256=h.hexdigest())
            elif member.issym():
                item = {'kind': 'link', 'target': member.linkname}
            elif member.islnk():
                item.update(kind='hardlink', target=path_key(member.linkname))
            elif member.isdir():
                item.update(kind='directory')
            else:
                # Device/FIFO nodes are metadata, never opened or executed.
                item.update(kind='special')
            updates[name] = item
    for name in removals:
        entries.pop(name, None)
    for name, item in updates.items():
        if item['kind'] != 'directory' and entries.get(name, {}).get('kind') == 'directory':
            for old in list(entries):
                if old.startswith(name + '/'):
                    del entries[old]
        entries[name] = item
    for name, item in list(entries.items()):
        if item['kind'] == 'hardlink':
            target = entries.get(item['target'])
            if not target or target['kind'] != 'file':
                raise IntegrityError('unresolved image hard link')
            entries[name] = dict(target)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def registry_blob(reference, digest, target, *, manifest=False):
    """Public pull only; no ambient Docker/GitHub credentials or tag resolution."""
    repository = reference.split('@')[0]
    if repository.startswith('docker.io/'):
        name, host, realm, service = repository[len('docker.io/'):], 'registry-1.docker.io', 'auth.docker.io', 'registry.docker.io'
    elif repository.startswith('ghcr.io/'):
        name, host, realm, service = repository[len('ghcr.io/'):], 'ghcr.io', 'ghcr.io', 'ghcr.io'
    else:
        raise IntegrityError('no admitted independent registry resolver')
    try:
        token_url = 'https://' + realm + '/token?' + urlencode({'service': service, 'scope': 'repository:' + name + ':pull'})
        opener = build_opener(NoRedirect, ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile='/etc/ssl/certs/ca-certificates.crt')))
        with opener.open(token_url, timeout=30) as stream:
            token = json.loads(stream.read(1024 * 1024))
        token = token.get('token', token.get('access_token'))
        if not isinstance(token, str):
            raise IntegrityError('public registry entitlement unavailable')
        address = 'https://' + host + '/v2/' + name + ('/manifests/' if manifest else '/blobs/') + digest
        headers = {'Authorization': 'Bearer ' + token, 'Accept': ', '.join([
            'application/vnd.oci.image.index.v1+json', 'application/vnd.oci.image.manifest.v1+json',
            'application/vnd.docker.distribution.manifest.list.v2+json', 'application/vnd.docker.distribution.manifest.v2+json'])}
        for attempt in range(6):
            try:
                response = opener.open(Request(address, headers=headers), timeout=30)
                break
            except HTTPError as exc:
                if exc.code not in (301, 302, 303, 307, 308) or attempt == 5:
                    raise
                address = exc.headers['Location']
                parsed = urlparse(address)
                allowed = (parsed.hostname in {'registry-1.docker.io', 'ghcr.io', 'pkg-containers.githubusercontent.com'}
                           or (parsed.hostname or '').endswith(('.docker.com', '.r2.cloudflarestorage.com', '.githubusercontent.com')))
                if parsed.scheme != 'https' or parsed.username or parsed.password or not allowed:
                    raise IntegrityError('unadmitted registry blob redirect')
                headers = {}  # never forward the scoped registry token to blob storage
        total, checksum = 0, hashlib.sha256()
        with response, target.open('wb') as output:
            for block in iter(lambda: response.read(1024 * 1024), b''):
                total += len(block)
                if total > (4 * 1024**2 if manifest else 4 * 1024**3):
                    raise IntegrityError('registry artifact exceeds verification budget')
                checksum.update(block); output.write(block)
        if 'sha256:' + checksum.hexdigest() != digest:
            raise IntegrityError('independent registry bytes failed expected digest')
    except (HTTPError, URLError, OSError, ValueError, KeyError):
        raise IntegrityError('exact public registry artifact unavailable; cache/data unchanged') from None


def verified_blob(digest, directory, *, reference=None, manifest=False, archive=None):
    if not DIGEST.fullmatch(digest):
        raise IntegrityError('invalid content digest')
    target = directory / digest.split(':')[1]
    with target.open('wb') as output:
        process = subprocess.Popen([K3S, *ctr('content', 'get', digest)], stdout=output, stderr=subprocess.DEVNULL, env=ENVIRONMENT)
        try:
            code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()
            raise IntegrityError('content read timed out') from None
    if code or target.stat().st_size > 4 * 1024**3 or 'sha256:' + sha(target) != digest:
        if archive is not None:
            # The complete archive graph was validated once for this fresh
            # baseline. Restore its content without contacting an upstream.
            with archive.extractfile('blobs/sha256/' + digest.split(':')[1]) as source, target.open('wb') as output:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    output.write(block)
            if target.stat().st_size > 4 * 1024**3 or 'sha256:' + sha(target) != digest:
                raise IntegrityError('retained archive content failed fresh digest verification')
            return target
        if reference is None:
            raise IntegrityError('trusted image content is unavailable or corrupt; operator required')
        # containerd may discard compressed layers after unpack. Missing/bad
        # local content cannot be promoted into the trusted baseline.
        registry_blob(reference, digest, target, manifest=manifest)
    return target


def trusted_inventory(reference, directory, *, archive=None):
    digest = reference.split('@', 1)[1]
    metadata = json.loads(verified_blob(digest, directory, reference=reference, manifest=True, archive=archive).read_bytes())
    if 'manifests' in metadata:
        candidates = [x for x in metadata['manifests'] if x.get('platform', {}).get('os') == 'linux'
                      and x.get('platform', {}).get('architecture') == 'amd64']
        if len(candidates) != 1:
            raise IntegrityError('image has no unique admitted linux/amd64 platform')
        metadata = json.loads(verified_blob(candidates[0]['digest'], directory, reference=reference, manifest=True, archive=archive).read_bytes())
    config = metadata['config']['digest']
    info = json.loads(verified_blob(config, directory, reference=reference, archive=archive).read_bytes())
    if info.get('os') != 'linux' or info.get('architecture') != 'amd64':
        raise IntegrityError('image platform mismatch')
    entries = {}
    for descriptor in metadata['layers']:
        path = verified_blob(descriptor['digest'], directory, reference=reference, archive=archive)
        with path.open('rb') as stream:
            layer_inventory(stream, entries)
        path.unlink()
    chain = None
    for diff in info['rootfs']['diff_ids']:
        chain = diff if chain is None else 'sha256:' + hashlib.sha256((chain + ' ' + diff).encode()).hexdigest()
    return {'reference': reference, 'config': config, 'chain': chain, 'entries': entries}


def filesystem_inventory(root):
    entries = {}
    for directory, names, files in os.walk(root, followlinks=False):
        for name in names + files:
            path = Path(directory) / name
            metadata = path.lstat()
            key = path.relative_to(root).as_posix()
            if stat.S_ISLNK(metadata.st_mode):
                entries[key] = {'kind': 'link', 'target': os.readlink(path)}
            elif stat.S_ISREG(metadata.st_mode):
                entries[key] = {'kind': 'file', 'mode': stat.S_IMODE(metadata.st_mode), 'sha256': sha(path)}
            elif stat.S_ISDIR(metadata.st_mode):
                entries[key] = {'kind': 'directory', 'mode': stat.S_IMODE(metadata.st_mode)}
            else:
                entries[key] = {'kind': 'special', 'mode': stat.S_IMODE(metadata.st_mode)}
    return entries


@contextmanager
def mounted(reference):
    with tempfile.TemporaryDirectory(prefix='mount-', dir=STATE) as directory:
        path = Path(directory)
        command(ctr('images', 'mount', '--platform', 'linux/amd64', reference, str(path)))
        try:
            yield path
        finally:
            command(ctr('images', 'unmount', '--rm', str(path)))


def baseline(reference, *, fresh=False):
    key = hashlib.sha256(reference.encode()).hexdigest()
    path = STATE / (key + '.baseline.json')
    if path.exists() and not fresh:
        try:
            envelope = json.loads(path.read_bytes())
            if envelope['digest'] == hashlib.sha256(canonical(envelope['value'])).hexdigest() and envelope['value']['reference'] == reference:
                return envelope['value']
        except (ValueError, KeyError, TypeError):
            pass
    with tempfile.TemporaryDirectory(prefix='content-', dir=STATE) as directory:
        saved = archive_path(reference)
        if saved.exists() or saved.is_symlink():
            verify_archive(saved, reference)
            with tarfile.open(saved, 'r:') as archive:
                value = trusted_inventory(reference, Path(directory), archive=archive)
        else:
            value = trusted_inventory(reference, Path(directory))
    write(path, {'value': value, 'digest': hashlib.sha256(canonical(value)).hexdigest()})
    return value


def reread_clean_file_cache(root, expected, observed):
    """Discard only clean cached pages of mismatched immutable regular files."""
    readbacks = []
    for name, wanted in expected.items():
        seen = observed.get(name, {})
        if (wanted.get('kind') != 'file' or seen.get('kind') != 'file'
            or wanted.get('sha256') == seen.get('sha256')):
            continue
        descriptor = None
        try:
            target = root / name
            if path_key(name) != name or not target.resolve().is_relative_to(root.resolve()):
                continue
            descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                continue
            # No sync, file write or global cache reset. The kernel retains
            # dirty pages; a persistent mismatch still needs normal recovery.
            os.posix_fadvise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
            readbacks.append({'file': name, 'before_sha256': seen.get('sha256'),
                              'expected_sha256': wanted['sha256']})
        except (IntegrityError, OSError, AttributeError, RuntimeError):
            pass  # Advice failure cannot substitute for the following hash proof.
        finally:
            if descriptor is not None:
                os.close(descriptor)
    return readbacks


def compare(reference):
    expected = baseline(reference)
    readbacks = []
    with mounted(reference) as root:
        actual = filesystem_inventory(root)
    if actual != expected['entries']:
        # A cached baseline is an optimization, never the final corruption proof.
        expected = baseline(reference, fresh=True)
        with mounted(reference) as root:
            readbacks = reread_clean_file_cache(root, expected['entries'], actual)
            actual = filesystem_inventory(root)
        if readbacks and actual == expected['entries']:
            # A good read in one mount is insufficient when corrupted cached
            # pages can recur. Require a separate native view before recovery.
            with mounted(reference) as root:
                actual = filesystem_inventory(root)
        for item in readbacks:
            item['after_sha256'] = actual.get(item['file'], {}).get('sha256')
            item['recovered'] = actual.get(item['file']) == expected['entries'][item['file']]
    differences = [key for key in sorted(actual.keys() | expected['entries'].keys()) if actual.get(key) != expected['entries'].get(key)]
    return {**expected, 'cache_readbacks': readbacks, 'mismatch_evidence': {key: {'expected': expected['entries'].get(key), 'observed': actual.get(key)} for key in differences[:10]}}, differences


def normalized_image(value):
    value = value.removeprefix('docker-pullable://')
    if DIGEST.fullmatch(value):
        return value
    name, separator, digest = value.partition('@')
    if '/' not in name:
        name = 'docker.io/library/' + name
    elif '.' not in name.split('/')[0] and name.split('/')[0] != 'localhost':
        name = 'docker.io/' + name
    if separator:
        if not DIGEST.fullmatch(digest):
            raise IntegrityError('invalid declared image digest')
        name = name.rsplit(':', 1)[0] if ':' in name.rsplit('/', 1)[-1] else name
        return name + '@' + digest
    return name if ':' in name.rsplit('/', 1)[-1] else name + ':latest'


def declared_references(policy, workloads, cached_images):
    """Include retained Job/controller templates even after finished Pods retire."""
    references = set()
    for item in workloads:
        if item['metadata']['namespace'] not in policy['namespaces']:
            continue
        owner = item.get('spec', {})
        if item.get('kind') == 'CronJob':
            owner = owner.get('jobTemplate', {}).get('spec', {})
        template = owner.get('template', {}).get('spec', {})
        for container in template.get('containers', []) + template.get('initContainers', []):
            requested = normalized_image(container['image'])
            repository = requested.split('@')[0]
            repository = repository.rsplit(':', 1)[0] if ':' in repository.rsplit('/', 1)[-1] else repository
            if not DIGEST.fullmatch(requested) and repository not in policy['repositories']:
                continue  # no privileged repair admission for historical/unused foreign images
            candidates = set()
            for cached in cached_images:
                aliases = {normalized_image(x) for x in cached.get('repoTags', []) + cached.get('repoDigests', [])}
                if cached.get('id') != requested and requested not in aliases:
                    continue
                for reference in cached.get('repoDigests', []):
                    reference = normalized_image(reference)
                    if '@' in requested and reference != requested:
                        continue
                    if reference.split('@')[0] in policy['repositories'] and (DIGEST.fullmatch(requested) or reference.split('@')[0] == repository):
                        candidates.add(reference)
            if len(candidates) > 1:
                raise IntegrityError('declared cached image identity is ambiguous')
            references.update(candidates)
    return references


def admitted_inventory(policy):
    pods = native_json(['kubectl', 'get', 'pods', '-A', '-o', 'json'])['items']
    references = set()
    for pod in pods:
        if pod['metadata']['namespace'] not in policy['namespaces']:
            continue
        for container in pod.get('status', {}).get('containerStatuses', []) + pod.get('status', {}).get('initContainerStatuses', []):
            reference = container.get('imageID', '').removeprefix('docker-pullable://')
            if '@' not in reference or reference.split('@')[0] not in policy['repositories'] or not DIGEST.fullmatch(reference.split('@')[1]):
                raise IntegrityError('managed image has no admitted immutable identity')
            references.add(reference)
    workloads = native_json(['kubectl', 'get', 'deployments,statefulsets,daemonsets,jobs,cronjobs', '-A', '-o', 'json'])['items']
    cached_images = native_json(['crictl', 'images', '-o', 'json'])['images']
    references.update(declared_references(policy, workloads, cached_images))
    path = STATE / 'inventory.json'
    # Retain identities across a reboot/owner shutdown. Never substitute a tag.
    prior = json.loads(path.read_bytes()) if path.exists() else []
    for reference in prior:
        if reference.split('@')[0] not in policy['repositories'] or not DIGEST.fullmatch(reference.split('@')[-1]):
            raise IntegrityError('retained image inventory is invalid')
    current_repositories = {reference.split('@')[0] for reference in references}
    references.update(reference for reference in prior if reference.split('@')[0] not in current_repositories)
    # An unresolved replacement remains in scope even when another version of
    # its repository is present or its native image metadata was removed.
    for incident_path in STATE.glob('*.incident.json'):
        record = json.loads(incident_path.read_bytes())
        if record.get('phase') == 'closed':
            continue
        reference = record.get('reference', '')
        if (reference.split('@')[0] not in policy['repositories']
            or not DIGEST.fullmatch(reference.split('@')[-1])
            or incident_path.name != hashlib.sha256(reference.encode()).hexdigest() + '.incident.json'):
            raise IntegrityError('retained image incident has invalid admission')
        references.add(reference)
    available = command(ctr('images', 'list')).decode().splitlines()
    result = []
    for reference in sorted(references):
        digest = reference.split('@')[1]
        aliases = [row.split()[0] for row in available[1:] if len(row.split()) >= 3 and row.split()[2] == digest]
        if aliases:
            # Restore a digest alias only to the existing exact target, no pull/upgrade.
            if reference not in aliases:
                command(ctr('images', 'tag', aliases[0], reference))
                aliases.append(reference)
            result.append((reference, aliases))
        else:
            incident = STATE / (hashlib.sha256(reference.encode()).hexdigest() + '.incident.json')
            if incident.exists() and json.loads(incident.read_bytes()).get('phase') != 'closed':
                if json.loads(incident.read_bytes()).get('phase') != 'attempted' or policy.get('automatic_repair') is not True:
                    raise IntegrityError('interrupted repair has missing image metadata; operator required')
                verify_archive(archive_path(reference), reference)
                result.append((reference, []))
    write(path, sorted(references))
    return result, pods


def image_users(config, reference):
    containers = native_json(['crictl', 'ps', '-a', '-o', 'json'])['containers']
    return [x for x in containers if x.get('imageRef') in (config, reference, reference.split('@')[1])
            or x.get('imageId') == config]


def restore_aliases(reference, aliases):
    rows = command(ctr('images', 'list')).decode().splitlines()[1:]
    targets = {row.split()[0]: row.split()[2] for row in rows if len(row.split()) >= 3}
    for alias in aliases:
        if alias in targets:
            if targets[alias] != reference.split('@')[1]:
                raise IntegrityError('original image alias changed during repair')
        else:
            command(ctr('images', 'tag', reference, alias))


def archive_path(reference):
    if '@' not in reference or not DIGEST.fullmatch(reference.split('@', 1)[1]):
        raise IntegrityError('archive requires the admitted immutable image')
    root = STATE / 'verified-archives'
    if root.is_symlink():
        raise IntegrityError('unsafe image archive directory')
    root.mkdir(mode=0o700, exist_ok=True)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o022:
        raise IntegrityError('image archive has foreign custody')
    return root / (hashlib.sha256(reference.encode()).hexdigest() + '.oci.tar')


def verify_archive(path, reference):
    """Validate the selected OCI graph without extracting or trusting aliases."""
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
        or info.st_mode & 0o022 or info.st_size > 4 * 1024**3):
        raise IntegrityError('unsafe or oversized image archive')
    try:
        with tarfile.open(path, 'r:') as archive:
            members = {}
            for member in archive:
                if member.isdir() and member.name in {'blobs', 'blobs/sha256'}:
                    continue
                if (not member.isfile() or member.name in members or len(members) >= 1024 or
                    member.name not in {'oci-layout', 'index.json'} and not re.fullmatch(r'blobs/sha256/[0-9a-f]{64}', member.name)):
                    raise IntegrityError('invalid OCI archive member')
                members[member.name] = member
                if member.name.startswith('blobs/'):
                    digest = hashlib.sha256()
                    with archive.extractfile(member) as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b''):
                            digest.update(block)
                    if digest.hexdigest() != member.name.rsplit('/', 1)[1]:
                        raise IntegrityError('image archive blob digest mismatch')

            def document(name):
                member = members[name]
                if member.size > 1024 * 1024:
                    raise IntegrityError('oversized image archive metadata')
                with archive.extractfile(member) as stream:
                    return json.load(stream)

            def blob(descriptor):
                digest = descriptor['digest']
                if not DIGEST.fullmatch(digest):
                    raise IntegrityError('invalid image archive descriptor')
                name = 'blobs/sha256/' + digest.split(':')[1]
                if members[name].size != descriptor['size']:
                    raise IntegrityError('image archive descriptor size mismatch')
                return name

            if document('oci-layout') != {'imageLayoutVersion': '1.0.0'}:
                raise IntegrityError('unsupported OCI archive layout')
            index = document('index.json')
            roots = index['manifests']
            if (index['schemaVersion'] != 2 or len(roots) != 1 or
                roots[0]['digest'] != reference.split('@')[1] or
                roots[0].get('annotations', {}).get('io.containerd.image.name') != reference or
                roots[0].get('annotations', {}).get('org.opencontainers.image.ref.name', '@' + reference.split('@')[1]) != '@' + reference.split('@')[1]):
                raise IntegrityError('image archive does not bind the exact original reference')
            manifest = document(blob(roots[0]))
            if 'manifests' in manifest:
                selected = [item for item in manifest['manifests'] if item.get('platform', {}).get('os') == 'linux'
                            and item.get('platform', {}).get('architecture') == 'amd64']
                if len(selected) != 1:
                    raise IntegrityError('image archive has no unique admitted platform')
                manifest = document(blob(selected[0]))
            config = document(blob(manifest['config']))
            if config.get('os') != 'linux' or config.get('architecture') != 'amd64':
                raise IntegrityError('image archive platform mismatch')
            for layer in manifest['layers']:
                blob(layer)
    except (OSError, tarfile.TarError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise IntegrityError('image archive is incomplete or invalid') from exc


def retain_archive(reference):
    target = archive_path(reference)
    if target.exists() or target.is_symlink():
        verify_archive(target, reference)
        return target
    # Export trusted compressed content, never the damaged unpacked filesystem.
    # Keep this proof before the first destructive image/snapshot operation.
    with tempfile.TemporaryDirectory(prefix='.preparing-', dir=target.parent) as directory:
        temporary = Path(directory) / 'image.oci.tar'
        command(ctr('images', 'export', '--platform', 'linux/amd64', '--skip-manifest-json',
                    str(temporary), reference), timeout=180)
        temporary.chmod(0o600)
        verify_archive(temporary, reference)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        temporary.replace(target)
        descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return target


def restore_archive(reference, aliases, incident, record):
    target = archive_path(reference)
    verify_archive(target, reference)
    # This is the same bounded replacement attempt. A failed/uncertain import
    # is not replayed; a later check can still prove that it finished safely.
    write(incident, {**record, 'phase': 'importing-archive'})
    command(ctr('images', 'import', '--platform', 'linux/amd64', '--base-name',
                reference.split('@')[0], '--digests', str(target)), timeout=180)
    restore_aliases(reference, aliases)
    _, differences = compare(reference)
    if differences:
        raise IntegrityError('replacement failed trusted byte verification; operator required')
    write(incident, {**record, 'phase': 'restored-awaiting-readiness', 'replacement': 'verified-local-archive'})


def repair(reference, aliases, expected, incident, policy=None):
    if incident.exists() and json.loads(incident.read_bytes()).get('phase') != 'closed':
        raise IntegrityError('this artifact already consumed its repair attempt; operator required')
    deadline = time.monotonic() + (120 if policy else 0)
    while True:
        users = image_users(expected['config'], reference)
        if not users:
            break
        if policy:
            pod_uids = {p['metadata']['uid'] for p in native_json(['kubectl', 'get', 'pods', '-A', '-o', 'json'])['items']}
            for user in users:
                labels = user.get('labels', {})
                if (user.get('state') == 'CONTAINER_EXITED'
                    and labels.get('io.kubernetes.pod.namespace') in policy['namespaces']
                    and labels.get('io.kubernetes.pod.uid') not in pod_uids
                    and re.fullmatch('[0-9a-f]{64}', user.get('id', ''))):
                    command(['crictl', 'rm', user['id']])
        if time.monotonic() >= deadline:
            raise IntegrityError('affected image still has consumers; cache unchanged')
        time.sleep(2)
    # Recheck all content before destructive cache metadata effects.
    baseline(reference, fresh=True)
    retain_archive(reference)
    record = {'phase': 'attempted', 'reference': reference, 'aliases': aliases,
              'started_at': time.time(), 'mismatch_evidence': expected.get('mismatch_evidence', {})}
    write(incident, record)
    command(ctr('images', 'rm', '--sync', *aliases), timeout=180)
    result = subprocess.run([K3S, *ctr('snapshots', 'info', expected['chain'])], capture_output=True, timeout=30, env=ENVIRONMENT)
    if result.returncode == 0:
        raise IntegrityError('unpacked snapshot retained by another user; operator required')
    restore_archive(reference, aliases, incident, record)


def operate(action, policy):
    cleanup_stale_inspection_views(policy)
    assets, pods = admitted_inventory(policy)
    if action == 'repair' and policy.get('automatic_repair') is not True:
        raise IntegrityError('automatic repair disabled by root admission policy')
    report = {'status': 'healthy', 'checked_images': len(assets), 'corrupt': [], 'repaired': [], 'cache_readbacks': [],
              'helper_sha256': sha(Path(__file__)), 'policy_sha256': sha(INSTALL / 'policy.json'),
              'checked_references': [ref for ref, _ in assets], 'checked_monotonic': time.monotonic(),
              'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    previous = STATE / 'last-result.json'
    if action == 'confirm' and previous.exists():
        prior = json.loads(previous.read_bytes())
        fresh = (prior.get('status') == 'healthy' and prior.get('boot_id') == report['boot_id']
                 and prior.get('helper_sha256') == report['helper_sha256']
                 and prior.get('policy_sha256') == report['policy_sha256']
                 and prior.get('checked_references') == report['checked_references']
                 and 0 <= time.monotonic() - prior.get('checked_monotonic', -1) <= 1800)
    else:
        fresh = False
    if fresh:
        report['cache_readbacks'] = prior.get('cache_readbacks', [])
    for reference, aliases in assets:
        incident = STATE / (hashlib.sha256(reference.encode()).hexdigest() + '.incident.json')
        if not aliases:
            record = json.loads(incident.read_bytes())
            if record.get('phase') != 'attempted' or record.get('reference') != reference:
                raise IntegrityError('missing image is outside the retained replacement attempt')
            if action == 'repair':
                expected = baseline(reference)
                if image_users(expected['config'], reference):
                    raise IntegrityError('interrupted replacement has image consumers')
                restore_archive(reference, record['aliases'], incident, record)
                report['repaired'].append(reference)
            elif action == 'check':
                report['corrupt'].append({'reference': reference, 'files': [], 'count': 0,
                    'reason': 'interrupted-image-replacement', 'resume_from_archive': True})
            else:
                raise IntegrityError('image replacement has not completed')
            continue
        expected, differences = ({}, []) if fresh else compare(reference)
        report['cache_readbacks'].extend({'reference': reference, **item} for item in expected.get('cache_readbacks', []))
        if differences:
            report['corrupt'].append({'reference': reference, 'files': differences[:10], 'count': len(differences),
                                      'mismatch_evidence': expected['mismatch_evidence']})
            if action == 'repair':
                repair(reference, aliases, expected, incident, policy)
                report['repaired'].append(reference)
        elif action == 'check' and incident.exists() and json.loads(incident.read_bytes()).get('phase') in {'attempted', 'importing-archive'}:
            previous = json.loads(incident.read_bytes())
            # A crash after the replacement can resume from freshly proven
            # bytes without repeating image removal/pull. Restore only absent
            # original aliases; never replace another target.
            restore_aliases(reference, previous['aliases'])
            write(incident, {**previous, 'phase': 'restored-awaiting-readiness'})
        elif action == 'confirm' and incident.exists():
            unhealthy = [p for p in pods if p['metadata']['namespace'] in policy['namespaces']
                         and not p['metadata'].get('deletionTimestamp')
                         and p.get('status', {}).get('phase') not in ('Succeeded',)
                         and not any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in p.get('status', {}).get('conditions', []))]
            if unhealthy:
                raise IntegrityError('consumer readiness has not recovered; incident remains open')
            write(incident, {**json.loads(incident.read_bytes()), 'phase': 'closed',
                             'confirmed_monotonic': time.monotonic(), 'boot_id': report['boot_id']})
    if report['corrupt'] and action != 'repair':
        report['status'] = 'corrupt'
    write(STATE / 'last-result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'repair', 'confirm'])
    args = parser.parse_args()
    def interrupted(*_):
        raise IntegrityError('integrity operation interrupted; preserve incident and inspect current state')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if os.geteuid() != 0 or Path(__file__).resolve() != INSTALL / 'runtime_artifact_integrity.py':
            raise IntegrityError('use the root-installed reviewed helper')
        for path in (INSTALL, INSTALL / 'policy.json', Path(__file__)):
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
                raise IntegrityError('unsafe installed helper/policy custody')
        policy = validate_admission(json.loads((INSTALL / 'policy.json').read_bytes()))
        STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
        if STATE.is_symlink() or STATE.stat().st_uid != 0 or stat.S_IMODE(STATE.stat().st_mode) & 0o077:
            raise IntegrityError('unsafe integrity state custody')
        with (STATE / 'operation.lock').open('a') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = operate(args.action, policy)
        print(json.dumps(result))
        return 0
    except (IntegrityError, OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'operator-required', 'reason': str(exc)[:400]}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
