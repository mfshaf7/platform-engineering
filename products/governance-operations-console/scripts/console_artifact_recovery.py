"""Internal artifact recovery adapter for the existing complete-runtime lifecycle."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
import yaml

PRODUCT = Path(__file__).resolve().parents[1]
SOURCE = PRODUCT.parents[1] / 'scripts/runtime_artifact_integrity.py'
POLICY = PRODUCT / 'runtime-integrity-policy.json'
INSTALL = '/usr/local/lib/platform-engineering/runtime-integrity'
WSL = '/mnt/c/Windows/System32/wsl.exe'


class RecoveryError(RuntimeError):
    pass


class RecoveryDeferred(RecoveryError):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def root_command(arguments):
    policy = json.loads(POLICY.read_text())
    host = yaml.safe_load((PRODUCT.parents[1] / 'ansible/group_vars/all/main.yml').read_text())
    if not isinstance(policy.get('distribution'), str) or policy['distribution'] != host.get('platform_windows_wsl_distro'):
        raise RecoveryError('integrity helper distribution differs from the admitted Platform host')
    return [WSL, '-d', policy['distribution'], '-u', 'root', '--', *arguments]


def helper(action):
    if action not in {'check', 'repair', 'confirm'}:
        raise RecoveryError('unsupported integrity helper action')
    # Independently bounded root process, including if the WSL caller is lost.
    command = root_command(['/usr/bin/timeout', '--kill-after=30s', '600s', '/usr/bin/python3', '-I',
                            INSTALL + '/runtime_artifact_integrity.py', action])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=640)
        value = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise RecoveryError('integrity helper unavailable; use the reviewed install-integrity procedure') from None
    if result.returncode or value.get('status') == 'operator-required':
        raise RecoveryError(value.get('reason', 'integrity check/repair failed'))
    if value.get('helper_sha256') != digest(SOURCE) or value.get('policy_sha256') != digest(POLICY):
        raise RecoveryError('installed integrity helper differs from accepted source; reinstall through the owner procedure')
    return value


def install(run):
    """Operator/admin commissioning only, called AFTER exact Security acceptance."""
    run(root_command(['/usr/bin/install', '-d', '-m', '0755', INSTALL]))
    for source, name in ((SOURCE, 'runtime_artifact_integrity.py'), (POLICY, 'policy.json')):
        run(root_command(['/usr/bin/install', '-o', 'root', '-g', 'root', '-m', '0644', str(source), INSTALL + '/' + name]))
    return helper('check')


def save(root, value):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / 'artifact-recovery.json'
    if target.is_symlink():
        raise RecoveryError('unsafe recovery journal')
    temporary = root / '.artifact-recovery.pending'
    if temporary.is_symlink():
        raise RecoveryError('unsafe recovery journal temporary path')
    temporary.write_text(json.dumps(value, sort_keys=True) + '\n'); temporary.chmod(0o600)
    with temporary.open('rb') as stream:
        os.fsync(stream.fileno())
    temporary.replace(target)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def journal(root):
    path = root / 'artifact-recovery.json'
    if path.is_symlink():
        raise RecoveryError('unsafe recovery journal')
    if not path.exists():
        return {'state': 'healthy'}
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or not isinstance(value.get('state'), str):
            raise ValueError()
        return value
    except (ValueError, OSError):
        raise RecoveryError('invalid recovery journal; preserve evidence and inspect current owner state') from None


def blocked(root):
    try:
        value = journal(root)
    except RecoveryError as exc:
        return str(exc)
    if value['state'] in {'quiescing', 'repairing', 'operator-required', 'restored-awaiting-readiness', 'resume-requested'}:
        return 'Artifact recovery: ' + value.get('reason', value['state'])
    return None


@contextmanager
def owner_guard(root, *, exclusive):
    directory = root / 'provider'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(directory / 'artifact-recovery.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RecoveryDeferred('owner work and artifact repair are mutually exclusive; retry after current operation finishes') from None
        yield
    finally:
        os.close(descriptor)


def assert_idle(root, run):
    # The caller already holds the complete-runtime lifecycle lock. Respect
    # independent owner/provider work and Helm compensation before quiescence.
    pending = json.loads(run(['helm', 'list', '-A', '--pending', '-o', 'json']).stdout)
    if pending:
        raise RecoveryDeferred('owner Helm operation/rollback is still pending; repair deferred')
    for path in (root / 'provider/operations').glob('*.json'):
        value = json.loads(path.read_text())
        if value.get('state') in {'requested', 'queued', 'running'}:
            raise RecoveryDeferred('Platform owner operation is still active; repair deferred')


def affected_controllers(report, run):
    """Plan all shared consumers before the first scale; never select data PVCs."""
    allowed = json.loads(POLICY.read_text())['namespaces']
    references = {value['reference'] for value in report['corrupt']}
    pods = json.loads(run(['k3s', 'kubectl', 'get', 'pods', '-A', '-o', 'json']).stdout)['items']
    selected, completed = {}, []
    for pod in pods:
        statuses = pod.get('status', {}).get('containerStatuses', []) + pod.get('status', {}).get('initContainerStatuses', [])
        if not any(c.get('imageID', '').removeprefix('docker-pullable://') in references for c in statuses):
            continue
        ns, name = pod['metadata']['namespace'], pod['metadata']['name']
        if ns not in allowed:
            raise RecoveryError('affected image has an unmanaged consumer; no consumers stopped')
        if pod.get('status', {}).get('phase') == 'Succeeded':
            completed.append((ns, name, pod['metadata']['uid']))
            continue
        owners = [x for x in pod['metadata'].get('ownerReferences', []) if x.get('controller')]
        if len(owners) != 1:
            raise RecoveryError('affected pod has no unique managed controller')
        owner = owners[0]
        if owner['kind'] == 'ReplicaSet':
            replica = json.loads(run(['k3s', 'kubectl', '-n', ns, 'get', 'replicaset', owner['name'], '-o', 'json']).stdout)
            owners = [x for x in replica['metadata'].get('ownerReferences', []) if x.get('controller')]
            if len(owners) != 1:
                raise RecoveryError('affected ReplicaSet has no unique deployment')
            owner = owners[0]
        if owner['kind'] not in {'Deployment', 'StatefulSet'}:
            raise RecoveryError('affected image is busy in an unsupported controller; no cache repair')
        resource = owner['kind'].lower() + '/' + owner['name']
        value = json.loads(run(['k3s', 'kubectl', '-n', ns, 'get', resource, '-o', 'json']).stdout)
        if value['metadata']['uid'] != owner['uid']:
            raise RecoveryError('consumer identity changed during repair planning')
        selected[(ns, resource)] = {'namespace': ns, 'resource': resource,
                                    'uid': owner['uid'], 'replicas': value['spec'].get('replicas', 1)}
    return list(selected.values()), completed


def recover_images(root, run, report):
    if json.loads(POLICY.read_text()).get('automatic_repair') is not True:
        raise RecoveryError('automatic image repair is disabled; consumers unchanged')
    with owner_guard(root, exclusive=True):
        return _recover_images(root, run, report)


def _recover_images(root, run, report):
    assert_idle(root, run)
    current = journal(root)
    if current['state'] in {'repairing', 'operator-required', 'restored-awaiting-readiness', 'resume-requested'}:
        raise RecoveryError('earlier uncertain/failed recovery requires operator inspection; not replayed')
    controllers, completed = affected_controllers(report, run)
    if current['state'] == 'quiescing':
        # Safe idempotent continuation before the destructive-attempt boundary.
        controllers = current['controllers']
    value = {'state': 'quiescing', 'controllers': controllers, 'corrupt': report['corrupt'], 'started_at': time.time()}
    save(root, value)
    for item in controllers:
        observed = json.loads(run(['k3s', 'kubectl', '-n', item['namespace'], 'get', item['resource'], '-o', 'json']).stdout)
        if observed['metadata']['uid'] != item['uid']:
            raise RecoveryError('consumer identity changed before quiescence')
        if observed['spec'].get('replicas', 1) == 0:
            continue
        run(['k3s', 'kubectl', '-n', item['namespace'], 'scale', item['resource'],
             '--replicas=0', '--current-replicas=' + str(item['replicas'])])
    for ns, name, uid in completed:
        # Completed pods have no mutable running work; delete only the exact UID.
        run(['k3s', 'kubectl', 'delete', '--raw', '/api/v1/namespaces/' + ns + '/pods/' + name, '-f', '-'],
            input_value=json.dumps({'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': uid}}))
    deadline = time.monotonic() + 120
    while controllers:
        remaining = []
        for item in controllers:
            observed = json.loads(run(['k3s', 'kubectl', '-n', item['namespace'], 'get', item['resource'], '-o', 'json']).stdout)
            if observed['metadata']['uid'] != item['uid']:
                raise RecoveryError('consumer was replaced during quiescence; no cache repair')
            if observed.get('status', {}).get('replicas', 0):
                remaining.append(item)
        if not remaining:
            break
        if time.monotonic() >= deadline:
            raise RecoveryError('consumers did not quiesce within120seconds; cache unchanged')
        time.sleep(2)
    value['state'] = 'repairing'; save(root, value)
    try:
        repaired = helper('repair')
    except RecoveryError as exc:
        value.update(state='operator-required', reason=str(exc)); save(root, value)
        raise
    value.update(state='restored-awaiting-readiness', repaired=repaired['repaired']); save(root, value)
    return repaired


def frontend_restartable(revision):
    import console_frontend_artifact as frontend
    try:
        _, _, version = frontend.toolchain()
        target = frontend.artifact_path(revision, version)
        incident = target.parent / ('.recovery-' + target.name + '.json')
        if incident.is_symlink():
            raise RecoveryError('unsafe frontend recovery journal')
        if incident.exists() and json.loads(incident.read_text()).get('phase') != 'closed':
            frontend.validate_artifact(target, revision, version)
    except (frontend.FrontendArtifactError, ValueError, OSError):
        raise RecoveryError('frontend repair did not produce a verified artifact; inspect retained recovery evidence') from None


def startup(root, run, *, revision=None):
    try:
        current = journal(root)
        if current['state'] == 'operator-required':
            raise RecoveryError(current.get('reason', 'earlier failed recovery requires inspection'))
        if current['state'] == 'deferred':
            assert_idle(root, run)
        if revision is not None:
            frontend_restartable(revision)
        report = helper('check')
        if report['status'] == 'corrupt':
            report = recover_images(root, run, report)
        elif journal(root)['state'] == 'repairing':
            # Fresh trusted bytes can prove a replacement completed before a
            # crash. Resume readiness without repeating destructive effects.
            save(root, {**journal(root), 'state': 'restored-awaiting-readiness'})
        elif journal(root)['state'] == 'operator-required':
            raise RecoveryError('uncertain previous recovery is latched; operator inspection required')
        return report
    except RecoveryDeferred as exc:
        save(root, {'state': 'deferred', 'reason': str(exc)})
        raise
    except RecoveryError as exc:
        current = journal(root)
        current.update(state='operator-required', reason=str(exc)); save(root, current)
        raise


def runtime_fault(run):
    allowed = json.loads(POLICY.read_text())['namespaces']
    pods = json.loads(run(['k3s', 'kubectl', 'get', 'pods', '-A', '-o', 'json']).stdout)['items']
    for pod in pods:
        if pod['metadata']['namespace'] not in allowed:
            continue
        for item in pod.get('status', {}).get('containerStatuses', []):
            state = item.get('state', {})
            if state.get('waiting', {}).get('reason') in {'CrashLoopBackOff', 'RunContainerError'}:
                return True
            if state.get('terminated', {}).get('exitCode', 0):
                return True
        if pod.get('status', {}).get('phase') == 'Running' and any(c.get('type') == 'Ready' and c.get('status') == 'False' for c in pod.get('status', {}).get('conditions', [])):
            return True
    return False


def confirmed(root):
    value = helper('confirm')
    save(root, {'state': 'healthy', 'checked_images': value['checked_images'], 'confirmed_at': time.time()})
    return value


def maintenance(root, run, supervisor, *, revision=None):
    """Existing timer: cheap fault signals first, hash only once per fault."""
    import console_frontend_artifact as frontend
    current = journal(root)
    if current['state'] in {'operator-required', 'repairing', 'resume-requested'}:
        return False
    fault = runtime_fault(run)
    active = run(['systemctl', '--user', 'is-active', '--quiet', 'governance-console-cross-domain-console.service'], check=False).returncode == 0
    if not fault and active:
        if current['state'] == 'unresolved-runtime-fault':
            save(root, {'state': 'healthy'})
        return False
    if current['state'] == 'unresolved-runtime-fault':
        return False  # no repeated full scans for the same ongoing failure
    assert_idle(root, run)
    report = helper('check')
    needs_resume = report['status'] == 'corrupt'
    if needs_resume:
        recover_images(root, run, report)
    elif not active:
        # Only a proven corrupt derived artifact authorizes automatic rebuild.
        try:
            _, _, version = frontend.toolchain()
            if revision is None:
                raise RecoveryError('failed frontend has no accepted source identity')
            selected = frontend.artifact_path(revision, version)
            frontend.validate_artifact(selected, revision, version)
        except frontend.FrontendArtifactError:
            needs_resume = True
    if not needs_resume:
        save(root, {'state': 'unresolved-runtime-fault', 'reason': 'No declared artifact corruption proven; owner diagnosis required'})
        return False
    save(root, {**journal(root), 'state': 'resume-requested'})
    # Child owner helpers must be retained by their established supervisor,
    # never created inside a short-lived timer service cgroup.
    run(['systemctl', '--user', '--no-block', 'restart', supervisor])
    return True
