#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import console_artifact_recovery as recovery


class RecoveryTests(unittest.TestCase):
    def test_root_invocation_matches_canonical_platform_host_not_an_assumed_distro(self):
        expected = recovery.yaml.safe_load((recovery.PRODUCT.parents[1] / 'ansible/group_vars/all/main.yml').read_text())['platform_windows_wsl_distro']
        self.assertEqual(recovery.root_command(['/usr/bin/id', '-u'])[1:3], ['-d', expected])
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / 'policy.json'; policy.write_text('{"distribution":"unadmitted-other-distro"}')
            with patch.object(recovery, 'POLICY', policy), self.assertRaises(recovery.RecoveryError):
                recovery.root_command(['/usr/bin/id', '-u'])

    def test_real_owner_lock_excludes_repair_and_new_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with recovery.owner_guard(root, exclusive=False):
                with self.assertRaises(recovery.RecoveryDeferred):
                    with recovery.owner_guard(root, exclusive=True): self.fail('must not quiesce busy owner')
            with recovery.owner_guard(root, exclusive=True):
                with self.assertRaises(recovery.RecoveryDeferred):
                    with recovery.owner_guard(root, exclusive=False): self.fail('must not start a new worker during repair')

    def test_healthy_tick_does_not_hash_or_restart(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(recovery, 'runtime_fault', return_value=False), patch.object(recovery, 'helper') as helper:
            calls = []
            def run(args, **kwargs):
                calls.append(args); return subprocess.CompletedProcess(args, 0, '')
            self.assertFalse(recovery.maintenance(Path(directory), run, 'supervisor.service'))
            helper.assert_not_called()
            self.assertEqual(len(calls), 1)

    def test_active_helm_or_owner_work_defers_without_quiescence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def pending(args, **kwargs): return subprocess.CompletedProcess(args, 0, '[{"status":"pending-rollback"}]')
            with self.assertRaises(recovery.RecoveryDeferred): recovery.assert_idle(root, pending)
            (root / 'provider/operations').mkdir(parents=True)
            (root / 'provider/operations/current.json').write_text('{"state":"running"}')
            def idle(args, **kwargs): return subprocess.CompletedProcess(args, 0, '[]')
            with self.assertRaises(recovery.RecoveryDeferred): recovery.assert_idle(root, idle)

    def test_foreign_shared_image_user_blocks_before_any_scale(self):
        pod = {'metadata': {'namespace': 'outside-admission', 'name': 'busy'}, 'status': {'containerStatuses': [{'imageID': 'repo@sha256:exact'}]}}
        report = {'corrupt': [{'reference': 'repo@sha256:exact'}]}
        def run(args, **kwargs):
            self.assertEqual(args[1:4], ['kubectl', 'get', 'pods'])
            return subprocess.CompletedProcess(args, 0, json.dumps({'items': [pod]}))
        with self.assertRaisesRegex(recovery.RecoveryError, 'unmanaged'):
            recovery.affected_controllers(report, run)

    def test_failed_or_uncertain_recovery_does_not_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); recovery.save(root, {'state': 'repairing'})
            with patch.object(recovery, 'assert_idle'), patch.object(recovery, 'affected_controllers') as consumers, self.assertRaises(recovery.RecoveryError):
                recovery.recover_images(root, None, {})
            consumers.assert_not_called()

    def test_recovery_requests_retained_supervisor_and_never_launches_owner_helpers(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(recovery, 'runtime_fault', return_value=True), patch.object(recovery, 'assert_idle'), patch.object(recovery, 'helper', return_value={'status': 'corrupt'}), patch.object(recovery, 'recover_images'):
            calls = []
            def run(args, **kwargs):
                calls.append(args); return subprocess.CompletedProcess(args, 0, '')
            root = Path(directory)
            self.assertTrue(recovery.maintenance(root, run, 'retained.service'))
            self.assertIn(['systemctl', '--user', '--no-block', 'restart', 'retained.service'], calls)
            self.assertEqual(recovery.journal(root)['state'], 'resume-requested')
            self.assertFalse(recovery.maintenance(root, run, 'retained.service'))

    def test_unknown_runtime_failure_does_not_become_restart_loop(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(recovery, 'runtime_fault', return_value=True), patch.object(recovery, 'assert_idle'), patch.object(recovery, 'helper', return_value={'status': 'healthy'}) as helper:
            def run(args, **kwargs): return subprocess.CompletedProcess(args, 0, '')
            root = Path(directory)
            self.assertFalse(recovery.maintenance(root, run, 'retained.service'))
            self.assertFalse(recovery.maintenance(root, run, 'retained.service'))
            self.assertEqual(helper.call_count, 1)
            self.assertEqual(recovery.journal(root)['state'], 'unresolved-runtime-fault')

    def test_symlink_journal_denied_and_root_command_is_finite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'artifact-recovery.json').symlink_to(root / 'outside')
            with self.assertRaises(recovery.RecoveryError): recovery.save(root, {'state': 'healthy'})
        with self.assertRaises(recovery.RecoveryError): recovery.helper('repair; rm -rf /')


if __name__ == '__main__':
    unittest.main()
