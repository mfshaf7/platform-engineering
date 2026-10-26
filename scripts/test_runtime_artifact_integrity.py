#!/usr/bin/env python3
"""Faithful archive/filesystem corruption and bounded cache repair tests."""
import hashlib
import io
import json
from pathlib import Path
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
                with patch.object(integrity, 'image_users', return_value=[]), patch.object(integrity, 'baseline'), patch.object(integrity, 'command') as command, patch.object(integrity.subprocess, 'run') as run, patch.object(integrity, 'compare', return_value=({}, differences)):
                    run.return_value.returncode = 1
                    if differences:
                        with self.assertRaises(integrity.IntegrityError): integrity.repair('repo@sha256:exact', ['repo:tag'], {'config': 'id', 'chain': 'chain'}, incident)
                    else:
                        integrity.repair('repo@sha256:exact', ['repo:tag'], {'config': 'id', 'chain': 'chain'}, incident)
                    self.assertIn(unittest.mock.call(['crictl', 'pull', 'repo@sha256:exact'], timeout=300), command.call_args_list)
                    self.assertNotEqual(json.loads(incident.read_text())['phase'], 'closed')


if __name__ == '__main__':
    unittest.main()
