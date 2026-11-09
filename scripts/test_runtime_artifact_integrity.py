#!/usr/bin/env python3
"""Faithful archive/filesystem corruption and bounded cache repair tests."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import runtime_artifact_integrity as integrity


def archive(items):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as value:
        for name, body, kind in items:
            member = tarfile.TarInfo(name); member.mode = 0o755
            if kind == 'link':
                member.type = tarfile.SYMTYPE; member.linkname = body
                value.addfile(member)
            elif kind == 'hardlink':
                member.type = tarfile.LNKTYPE; member.linkname = body
                value.addfile(member)
            else:
                body = body.encode(); member.size = len(body)
                value.addfile(member, io.BytesIO(body))
    output.seek(0)
    return output


class IntegrityTests(unittest.TestCase):
    def test_confirmation_reuses_only_same_helper_and_policy_proof(self):
        reference = 'docker.io/example/tool@sha256:' + 'a'*64
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        for changed in ('none', 'helper_sha256', 'policy_sha256'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                prior = {'status': 'healthy', 'boot_id': boot, 'checked_monotonic': 100,
                         'checked_references': [reference], 'helper_sha256': 'current-helper',
                         'policy_sha256': 'current-policy', 'cache_readbacks': [{'recovered': True}]}
                if changed != 'none': prior[changed] = 'previous-version'
                integrity.write(root / 'last-result.json', prior)
                with patch.object(integrity, 'STATE', root), patch.object(integrity, 'cleanup_stale_inspection_views'), \
                     patch.object(integrity, 'admitted_inventory', return_value=([(reference, [reference])], [])), \
                     patch.object(integrity, 'sha', side_effect=['current-helper', 'current-policy']), \
                     patch.object(integrity.time, 'monotonic', return_value=200), \
                     patch.object(integrity, 'compare', return_value=({}, [])) as compare:
                    result = integrity.operate('confirm', {})
                self.assertEqual(compare.call_count, 0 if changed == 'none' else 1)
                self.assertEqual(result['cache_readbacks'], prior['cache_readbacks'] if changed == 'none' else [])

    def test_clean_cache_reread_requires_read_only_fd_and_fresh_trusted_bytes(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root / 'program'; target.write_bytes(b'healthy')
            entries = integrity.filesystem_inventory(root); state = {'evicted': False}
            original_sha = integrity.sha
            def read_sha(path):
                return 'a'*64 if Path(path) == target and not state['evicted'] else original_sha(path)
            def advise(fd, offset, length, advice):
                self.assertEqual(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE, os.O_RDONLY)
                self.assertEqual((offset, length, advice), (0, 0, os.POSIX_FADV_DONTNEED))
                state['evicted'] = True
            with patch.object(integrity, 'baseline', return_value={'entries': entries}) as baseline, \
                 patch.object(integrity, 'mounted') as mounted, patch.object(integrity, 'sha', side_effect=read_sha), \
                 patch.object(integrity.os, 'posix_fadvise', side_effect=advise), patch.object(integrity, 'repair') as repair:
                mounted.return_value.__enter__.return_value = root
                result, differences = integrity.compare('admitted@sha256:' + 'a'*64)
            self.assertEqual(differences, [])
            self.assertTrue(baseline.call_args.kwargs['fresh'])
            self.assertTrue(result['cache_readbacks'][0]['recovered'])
            self.assertEqual(target.read_bytes(), b'healthy')
            repair.assert_not_called()

    def test_persistent_bad_bytes_and_unavailable_advice_never_become_healthy(self):
        for unsupported in (False, True):
            with self.subTest(unsupported=unsupported), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); target = root / 'program'; target.write_bytes(b'healthy')
                entries = integrity.filesystem_inventory(root); target.write_bytes(b'bad disk bytes')
                with patch.object(integrity, 'baseline', return_value={'entries': entries}), \
                     patch.object(integrity, 'mounted') as mounted, \
                     patch.object(integrity.os, 'posix_fadvise', side_effect=OSError('unsupported') if unsupported else None):
                    mounted.return_value.__enter__.return_value = root
                    result, differences = integrity.compare('admitted@sha256:' + 'a'*64)
                self.assertEqual(differences, ['program'])
                self.assertFalse(any(item['recovered'] for item in result['cache_readbacks']))
                self.assertEqual(target.read_bytes(), b'bad disk bytes')

    def test_cache_mismatch_recurring_in_a_fresh_mount_is_not_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root / 'program'; target.write_bytes(b'healthy')
            entries = integrity.filesystem_inventory(root); state = {'mount': 0, 'evicted': False}
            original_sha = integrity.sha
            def enter():
                state['mount'] += 1
                return root
            def read_sha(path):
                if Path(path) == target and (not state['evicted'] or state['mount'] >= 3):
                    return 'a'*64
                return original_sha(path)
            def advise(*args): state['evicted'] = True
            with patch.object(integrity, 'baseline', return_value={'entries': entries}), \
                 patch.object(integrity, 'mounted') as mounted, patch.object(integrity, 'sha', side_effect=read_sha), \
                 patch.object(integrity.os, 'posix_fadvise', side_effect=advise):
                mounted.return_value.__enter__.side_effect = enter
                result, differences = integrity.compare('admitted@sha256:' + 'a'*64)
            self.assertEqual(differences, ['program'])
            self.assertFalse(result['cache_readbacks'][0]['recovered'])
            self.assertEqual(state['mount'], 3)

    def test_cache_advice_excludes_escaped_paths_and_links(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); root = base / 'image'; root.mkdir()
            outside = base / 'outside'; outside.mkdir(); (outside / 'data').write_text('preserve')
            (root / 'parent').symlink_to(outside, target_is_directory=True)
            (root / 'leaf').symlink_to(outside / 'data')
            entries = {name: {'kind': 'file', 'sha256': 'a'*64} for name in
                       ('../outside/data', str(outside / 'data'), 'parent/data', 'leaf')}
            actual = {name: {'kind': 'file', 'sha256': 'b'*64} for name in entries}
            with patch.object(integrity.os, 'posix_fadvise') as advise:
                self.assertEqual(integrity.reread_clean_file_cache(root, entries, actual), [])
            advise.assert_not_called()
            self.assertEqual((outside / 'data').read_text(), 'preserve')

    def test_metadata_only_mismatch_does_not_discard_file_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'program').write_text('healthy')
            entries = integrity.filesystem_inventory(root)
            actual = {**entries, 'program': {**entries['program'], 'mode': 0o777}}
            with patch.object(integrity.os, 'posix_fadvise') as advise:
                self.assertEqual(integrity.reread_clean_file_cache(root, entries, actual), [])
            advise.assert_not_called()

    def test_only_unmounted_pre_boot_admitted_read_views_are_reclaimed(self):
        for case in ('eligible', 'current-boot', 'snapshot-current', 'mounted', 'active-snapshot',
                     'foreign-parent', 'foreign-label', 'symlink', 'nonempty', 'unsafe-custody',
                     'invalid-baseline-reference', 'snapshot-already-collected'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); view = root / 'mount-oldview1'; view.mkdir(mode=0o700)
                chain = 'sha256:' + 'a'*64; reference = 'docker.io/example/tool@sha256:' + 'b'*64
                value = {'reference': reference, 'chain': chain, 'config': 'sha256:' + 'c'*64, 'entries': {}}
                if case == 'invalid-baseline-reference': value['reference'] = None
                integrity.write(root / 'known.baseline.json', {'value': value,
                    'digest': hashlib.sha256(integrity.canonical(value)).hexdigest()})
                old = '1970-01-01T00:16:40+00:00'; new = '2100-01-01T00:00:00+00:00'
                created = new if case == 'current-boot' else old
                label = str(root / 'another-view') if case == 'foreign-label' else str(view)
                leases = f'ID CREATED LABELS\n{view} {created} containerd.io/gc.ref.snapshot.overlayfs={label}\n'.encode()
                info = {'Name': str(view), 'Kind': 'Active' if case == 'active-snapshot' else 'View',
                        'Parent': 'sha256:' + 'd'*64 if case == 'foreign-parent' else chain,
                        'Created': new if case == 'snapshot-current' else created}
                if case == 'symlink':
                    view.rmdir(); view.symlink_to(root / 'unique-data')
                elif case == 'nonempty':
                    (view / 'unique-data').write_text('preserve')
                elif case == 'unsafe-custody':
                    view.chmod(0o777)
                calls = []
                def native(args, **kwargs):
                    calls.append(args)
                    if args[4:6] == ['snapshots', 'info']:
                        return subprocess.CompletedProcess(args, 0, json.dumps(info).encode(), b'')
                    if case == 'snapshot-already-collected' and args[4:6] == ['snapshots', 'rm']:
                        return subprocess.CompletedProcess(args, 1, b'', b'not found')
                    return subprocess.CompletedProcess(args, 0, b'', b'')
                original_read = Path.read_text
                def read(path, *args, **kwargs):
                    if str(path) == '/proc/self/mountinfo' and case == 'mounted':
                        return f'1 0 0:1 / {view} ro - overlay overlay ro\n'
                    return original_read(path, *args, **kwargs)
                wall = float(Path('/proc/uptime').read_text().split()[0]) + 10000
                with patch.object(integrity, 'STATE', root), patch.object(integrity, 'command', return_value=leases), \
                     patch.object(integrity.subprocess, 'run', side_effect=native), \
                     patch.object(integrity.time, 'time', return_value=wall), patch.object(Path, 'read_text', read):
                    removed = integrity.cleanup_stale_inspection_views({'repositories': ['docker.io/example/tool']})
                eligible = case in ('eligible', 'snapshot-already-collected')
                self.assertEqual(len(removed), 1 if eligible else 0)
                self.assertEqual(any(args[4:6] == ['leases', 'rm'] for args in calls), eligible)
                if case == 'nonempty': self.assertEqual((view / 'unique-data').read_text(), 'preserve')

    def test_aliases_recreated_by_cri_pull_are_not_tagged_again_or_overwritten(self):
        reference = 'repo@sha256:' + 'a'*64
        rows = ('REF TYPE DIGEST\nrepo:tag type sha256:' + 'a'*64 + '\nsha256:config type sha256:' + 'a'*64 + '\n').encode()
        with patch.object(integrity, 'command', return_value=rows) as command:
            integrity.restore_aliases(reference, ['repo:tag', 'sha256:config'])
            self.assertEqual(command.call_count, 1)
        with patch.object(integrity, 'command', return_value=rows.replace(b'a'*64, b'b'*64)) as command, self.assertRaises(integrity.IntegrityError):
            integrity.restore_aliases(reference, ['repo:tag'])
        self.assertEqual(command.call_count, 1)

    def test_retained_job_without_a_pod_still_covers_its_cached_tool(self):
        reference = 'docker.io/minio/mc@sha256:' + 'a'*64
        policy = {'namespaces': ['devint-proof'], 'repositories': ['docker.io/minio/mc']}
        job = {'kind': 'Job', 'metadata': {'namespace': 'devint-proof'},
               'spec': {'template': {'spec': {'containers': [{'image': 'minio/mc:release'}]}}}}
        cached = {'id': 'sha256:' + 'b'*64, 'repoTags': ['docker.io/minio/mc:release'], 'repoDigests': [reference]}
        self.assertEqual(integrity.declared_references(policy, [job], [cached]), {reference})
        self.assertEqual(integrity.declared_references(policy, [job], []), set())
        cached['repoDigests'].append('docker.io/minio/mc@sha256:' + 'c'*64)
        with self.assertRaises(integrity.IntegrityError): integrity.declared_references(policy, [job], [cached])
        job['spec']['template']['spec']['containers'][0]['image'] = 'minio/mc:release@sha256:' + 'a'*64
        self.assertEqual(integrity.declared_references(policy, [job], [cached]), {reference})
        job['spec']['template']['spec']['containers'][0]['image'] = 'ghcr.io/unadmitted/dormant:old'
        self.assertEqual(integrity.declared_references(policy, [job], [cached]), set())

    def test_read_only_view_is_removed_even_when_verification_fails(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(integrity, 'STATE', Path(directory)), patch.object(integrity, 'command') as command:
            with self.assertRaises(integrity.IntegrityError):
                with integrity.mounted('repo@sha256:' + 'a'*64):
                    raise integrity.IntegrityError('synthetic verification failure')
            self.assertIn('--rm', command.call_args.args[0])
            self.assertEqual(command.call_args.args[0][3:5], ['images', 'unmount'])

    def test_stage_prod_unknown_registry_and_nonexplicit_scope_are_denied(self):
        policy = {'schema_version': 1, 'lane': 'dev-integration', 'automatic_repair': True,
                  'namespaces': ['devint-proof'], 'repositories': ['docker.io/library/postgres']}
        self.assertEqual(integrity.validate_admission(policy), policy)
        for delta in ({'namespaces': ['prod']}, {'namespaces': ['*']}, {'lane': 'stage'},
                      {'repositories': ['https://evil.invalid/repo']}, {'repositories': []}):
            with self.subTest(delta=delta), self.assertRaises(integrity.IntegrityError):
                integrity.validate_admission({**policy, **delta})

    def test_layer_whiteouts_links_and_one_bit_corruption(self):
        entries = {}
        integrity.layer_inventory(archive([('bin/check', 'healthy', 'file'), ('bin/old', 'old', 'file'), ('bin/link', 'check', 'link')]), entries)
        integrity.layer_inventory(archive([('bin/.wh.old', '', 'file'), ('bin/copy', 'bin/check', 'hardlink')]), entries)
        self.assertNotIn('bin/old', entries)
        self.assertEqual(entries['bin/copy'], entries['bin/check'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'bin').mkdir()
            (root / 'bin/check').write_text('healthy'); (root / 'bin/check').chmod(0o755)
            (root / 'bin/copy').write_text('healthy'); (root / 'bin/copy').chmod(0o755)
            (root / 'bin/link').symlink_to('check')
            actual = integrity.filesystem_inventory(root)
            self.assertEqual(actual['bin/check'], entries['bin/check'])
            data = bytearray((root / 'bin/check').read_bytes()); data[0] ^= 1
            (root / 'bin/check').write_bytes(data)
            with patch.object(integrity, 'baseline', return_value={'entries': entries}) as baseline, patch.object(integrity, 'mounted') as mounted:
                mounted.return_value.__enter__.return_value = root
                _, differences = integrity.compare('admitted@sha256:' + 'a'*64)
            self.assertIn('bin/check', differences)
            self.assertTrue(baseline.call_args.kwargs['fresh'])

    def test_opaque_whiteout_does_not_remove_new_layer_entries(self):
        entries = {}
        integrity.layer_inventory(archive([('a/old', 'old', 'file')]), entries)
        integrity.layer_inventory(archive([('a/new', 'new', 'file'), ('a/.wh..wh..opq', '', 'file')]), entries)
        self.assertEqual(set(entries), {'a/new'})

    def test_archive_escape_is_rejected_without_filesystem_effects(self):
        for name in ('../escape', '/etc/passwd', 'x/../../escape'):
            with self.subTest(name=name), self.assertRaises(integrity.IntegrityError):
                integrity.layer_inventory(archive([(name, 'bad', 'file')]), {})

    def test_content_digest_checked_independently(self):
        class Process:
            def wait(self, **kwargs): return 0
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def copy(args, stdout, **kwargs):
                stdout.write(b'changed compressed bytes'); stdout.flush(); return Process()
            with patch.object(integrity.subprocess, 'Popen', side_effect=copy), self.assertRaises(integrity.IntegrityError):
                integrity.verified_blob('sha256:' + 'a'*64, root)

    def test_shared_users_refuse_before_cache_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(integrity, 'image_users', return_value=[{'id': 'shared'}]), patch.object(integrity, 'command') as command, self.assertRaises(integrity.IntegrityError):
                integrity.repair('image@digest', ['alias'], {'config': 'config'}, Path(directory) / 'incident.json')
            command.assert_not_called()

    def test_interrupted_or_failed_attempt_is_not_replayed(self):
        for phase in ('attempted', 'restored-awaiting-readiness'):
            with tempfile.TemporaryDirectory() as directory:
                incident = Path(directory) / 'incident.json'; integrity.write(incident, {'phase': phase})
                with patch.object(integrity, 'command') as command, self.assertRaises(integrity.IntegrityError):
                    integrity.repair('image@digest', ['alias'], {'config': 'config'}, incident)
                command.assert_not_called()

    def test_same_exact_image_restore_and_failed_reverification_latches(self):
        for differences in ([], ['bin/check']):
            with tempfile.TemporaryDirectory() as directory:
                incident = Path(directory) / 'incident.json'
                with patch.object(integrity, 'STATE', Path(directory)), patch.object(integrity, 'retain_archive'), patch.object(integrity, 'verify_archive'), patch.object(integrity, 'image_users', return_value=[]), patch.object(integrity, 'baseline'), patch.object(integrity, 'command') as command, patch.object(integrity.subprocess, 'run') as run, patch.object(integrity, 'compare', return_value=({}, differences)):
                    run.return_value.returncode = 1
                    if differences:
                        with self.assertRaises(integrity.IntegrityError): integrity.repair('repo@sha256:' + 'a'*64, ['repo:tag'], {'config': 'id', 'chain': 'chain'}, incident)
                    else:
                        integrity.repair('repo@sha256:' + 'a'*64, ['repo:tag'], {'config': 'id', 'chain': 'chain'}, incident)
                    self.assertTrue(any(call.args[0][3:5] == ['images', 'import'] for call in command.call_args_list))
                    self.assertFalse(any(call.args[0][0] == 'crictl' for call in command.call_args_list))
                    self.assertNotEqual(json.loads(incident.read_text())['phase'], 'closed')


if __name__ == '__main__':
    unittest.main()
