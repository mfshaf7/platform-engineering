#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import console_artifact_recovery as recovery


class RecoveryTests(unittest.TestCase):
    def healthy_report(self):
        return {'status': 'healthy', 'corrupt': [], 'pending_repairs': [],
                'checked_images': 1, 'checked_references': ['repo@sha256:' + 'a'*64],
                'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'checked_monotonic': recovery.time.monotonic()}

    def latch(self, root):
        with patch.object(recovery, 'helper', side_effect=recovery.RecoveryError('read unavailable')):
            with self.assertRaises(recovery.RecoveryError):
                recovery.startup(root, None)
        return recovery.journal(root)

    def test_check_failure_can_resume_but_not_become_healthy_before_owner_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recovery.save(root, {'state': 'healthy', 'controllers': [{'uid': 'original'}]})
            previous = self.latch(root)
            self.assertEqual(previous['automatic_recheck']['failure_stage'], 'integrity-check')
            with patch.object(recovery, 'helper', return_value=self.healthy_report()) as helper, \
                 patch.object(recovery, 'assert_idle'), patch.object(recovery, 'recover_images') as repair:
                result = recovery.startup(root, None)
            self.assertEqual(result['status'], 'healthy')
            helper.assert_called_once_with('check'); repair.assert_not_called()
            current = recovery.journal(root)
            self.assertEqual(current['controllers'], previous['controllers'])
            self.assertEqual(current['state'], 'restored-awaiting-readiness')
            with patch.object(recovery, 'helper', side_effect=recovery.RecoveryError('owner not ready')):
                with self.assertRaises(recovery.RecoveryError): recovery.confirmed(root)
            self.assertEqual(recovery.journal(root), current)
            with patch.object(recovery, 'helper', return_value=self.healthy_report()): recovery.confirmed(root)
            self.assertEqual(recovery.journal(root)['state'], 'healthy')

    def test_bad_or_incomplete_recheck_stays_latched_and_does_not_restart(self):
        mutations = [{'status': 'corrupt'}, {'corrupt': [{'reference': 'bad'}]},
                     {'pending_repairs': None}, {'boot_id': 'old-boot'},
                     {'checked_references': []}, {'checked_images': 2},
                     {'checked_references': ['duplicate', 'duplicate'], 'checked_images': 2},
                     {'checked_monotonic': -1000}, {'checked_monotonic': recovery.time.monotonic() + 1000}]
        mutations += [{'pending_repairs': [{'phase': phase}]} for phase in
                      ('attempted', 'importing-archive', 'restored-awaiting-readiness')]
        for delta in mutations:
            with self.subTest(delta=delta), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.latch(root); calls = []
                def run(args, **kwargs): calls.append(args)
                with patch.object(recovery, 'assert_idle'), \
                     patch.object(recovery, 'helper', return_value={**self.healthy_report(), **delta}), \
                     patch.object(recovery, 'recover_images') as repair:
                    self.assertFalse(recovery.maintenance(root, run, 'retained.service'))
                self.assertEqual(recovery.journal(root)['state'], 'operator-required')
                self.assertEqual(recovery.journal(root)['automatic_recheck']['result'], 'blocked')
                self.assertEqual(calls, []); repair.assert_not_called()

    def test_failed_recheck_is_not_repeated_in_the_same_boot_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.latch(root)
            with patch.object(recovery, 'assert_idle'), \
                 patch.object(recovery, 'helper', side_effect=recovery.RecoveryError('read unavailable')) as helper:
                self.assertIsNone(recovery.recheck_latched(root, None))
                saved = recovery.journal(root)
                recovery.save(root, json.loads(json.dumps(saved)))
                self.assertIsNone(recovery.recheck_latched(root, None))
            helper.assert_called_once_with('check')
            # The persisted guard from an earlier boot permits one new check.
            saved['automatic_recheck']['attempted_boot_id'] = 'previous-boot'
            recovery.save(root, saved)
            with patch.object(recovery, 'assert_idle'), patch.object(recovery, 'helper', return_value=self.healthy_report()):
                self.assertIsNotNone(recovery.recheck_latched(root, None))

    def test_busy_owner_preserves_failure_and_unspent_recheck(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); previous = self.latch(root)
            with patch.object(recovery, 'assert_idle', side_effect=recovery.RecoveryDeferred('busy')), \
                 patch.object(recovery, 'helper') as helper:
                with self.assertRaises(recovery.RecoveryDeferred): recovery.startup(root, None)
            self.assertEqual(recovery.journal(root), previous); helper.assert_not_called()

    def test_failed_repair_does_not_gain_automatic_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(recovery, 'helper', return_value={'status': 'corrupt'}), \
                 patch.object(recovery, 'recover_images', side_effect=recovery.RecoveryError('uncertain import')):
                with self.assertRaises(recovery.RecoveryError): recovery.startup(root, None)
            self.assertNotIn('automatic_recheck', recovery.journal(root))
            with patch.object(recovery, 'helper') as helper:
                self.assertIsNone(recovery.recheck_latched(root, None))
            helper.assert_not_called()

    def test_check_failure_during_pending_recovery_cannot_be_reclassified(self):
        for state in ('repairing', 'quiescing', 'restored-awaiting-readiness', 'resume-requested'):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); recovery.save(root, {'state': state, 'controllers': [{'uid': 'original'}]})
                self.latch(root)
                self.assertNotIn('automatic_recheck', recovery.journal(root))
                self.assertEqual(recovery.journal(root)['controllers'], [{'uid': 'original'}])

    def test_frontend_failure_after_verified_recheck_cannot_reuse_old_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.latch(root)
            with patch.object(recovery, 'assert_idle'), patch.object(recovery, 'helper', return_value=self.healthy_report()), \
                 patch.object(recovery, 'frontend_restartable', side_effect=recovery.RecoveryError('bad frontend')):
                with self.assertRaises(recovery.RecoveryError): recovery.startup(root, None, revision='accepted')
            self.assertEqual(recovery.journal(root)['state'], 'operator-required')
            self.assertNotIn('automatic_recheck', recovery.journal(root))
            with patch.object(recovery, 'helper') as helper:
                self.assertIsNone(recovery.recheck_latched(root, None))
            helper.assert_not_called()

    def test_initial_frontend_failure_is_not_classified_as_an_image_check_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recovery.save(root, {'state': 'healthy'})
            with patch.object(recovery, 'frontend_restartable', side_effect=recovery.RecoveryError('bad frontend')):
                with self.assertRaises(recovery.RecoveryError): recovery.startup(root, None, revision='accepted')
            self.assertNotIn('automatic_recheck', recovery.journal(root))

    def test_recheck_uses_only_existing_retained_supervisor_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.latch(root); calls = []
            with patch.object(recovery, 'assert_idle'), patch.object(recovery, 'helper', return_value=self.healthy_report()):
                self.assertTrue(recovery.maintenance(root, lambda args: calls.append(args), 'retained.service'))
            self.assertEqual(calls, [['systemctl', '--user', '--no-block', 'restart', 'retained.service']])
            self.assertEqual(recovery.journal(root)['state'], 'resume-requested')
            self.assertEqual(recovery.journal(root)['automatic_recheck']['result'], 'verified-awaiting-readiness')

    def test_policy_can_disable_recheck_without_altering_the_latch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); previous = self.latch(root)
            policy = root / 'disabled.json'; policy.write_text('{"automatic_verification_resume": false}')
            with patch.object(recovery, 'POLICY', policy), patch.object(recovery, 'helper') as helper:
                self.assertIsNone(recovery.recheck_latched(root, None))
            self.assertEqual(recovery.journal(root), previous); helper.assert_not_called()

    def test_maintenance_check_failure_records_the_same_explicit_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def run(args, **kwargs): return subprocess.CompletedProcess(args, 0, '')
            with patch.object(recovery, 'runtime_fault', return_value=True), patch.object(recovery, 'assert_idle'), \
                 patch.object(recovery, 'helper', side_effect=recovery.RecoveryError('read unavailable')):
                with self.assertRaises(recovery.RecoveryError): recovery.maintenance(root, run, 'retained.service')
            value = recovery.journal(root)
            self.assertEqual(value['state'], 'operator-required')
            self.assertEqual(value['automatic_recheck']['result'], 'eligible')

    def test_successful_old_recheck_is_evidence_not_permission_to_clear_a_new_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.latch(root)
            with patch.object(recovery, 'assert_idle'), patch.object(recovery, 'helper', return_value=self.healthy_report()):
                recovery.recheck_latched(root, None)
            value = recovery.journal(root)
            value.update(state='operator-required', reason='new unrelated failure')
            value['automatic_recheck']['attempted_boot_id'] = 'previous-boot'
            recovery.save(root, value)
            with patch.object(recovery, 'helper') as helper:
                self.assertIsNone(recovery.recheck_latched(root, None))
            helper.assert_not_called()

    def test_new_check_failure_after_success_does_not_reset_the_same_boot_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.latch(root)
            with patch.object(recovery, 'assert_idle'), patch.object(recovery, 'helper', return_value=self.healthy_report()):
                recovery.recheck_latched(root, None)
                recovery.confirmed(root)
            self.latch(root)
            with patch.object(recovery, 'helper') as helper:
                self.assertIsNone(recovery.recheck_latched(root, None))
            helper.assert_not_called()

    def test_proven_cache_readback_resumes_existing_supervisor_without_image_replacement(self):
        for recovered in (False, True):
            with self.subTest(recovered=recovered), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); calls = []
                def run(args, **kwargs):
                    calls.append(args); return subprocess.CompletedProcess(args, 0, '')
                with patch.object(recovery, 'runtime_fault', return_value=True), \
                     patch.object(recovery, 'assert_idle') as idle, \
                     patch.object(recovery, 'helper', return_value={'status': 'healthy', 'cache_readbacks': [{'recovered': recovered}]}), \
                     patch.object(recovery, 'recover_images') as replace:
                    self.assertEqual(recovery.maintenance(root, run, 'retained.service'), recovered)
                idle.assert_called_once(); replace.assert_not_called()
                self.assertEqual(['systemctl', '--user', '--no-block', 'restart', 'retained.service'] in calls, recovered)
                self.assertEqual(recovery.journal(root)['state'], 'resume-requested' if recovered else 'unresolved-runtime-fault')

    def test_maintenance_never_replaces_a_pending_recovery_journal(self):
        for state in ('quiescing', 'repairing', 'restored-awaiting-readiness', 'resume-requested', 'operator-required'):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                original = {'state': state, 'controllers': [{'uid': 'original', 'replicas': 1}],
                            'corrupt': [{'reference': 'original'}], 'completed_pods': [['ns', 'pod', 'uid']]}
                recovery.save(root, original)
                with patch.object(recovery, 'runtime_fault') as fault, patch.object(recovery, 'helper') as helper:
                    self.assertFalse(recovery.maintenance(root, None, 'retained.service'))
                fault.assert_not_called(); helper.assert_not_called()
                self.assertEqual(recovery.journal(root), original)

    def test_unknown_fault_preserves_existing_recovery_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); retained = {'state': 'healthy', 'controllers': [{'uid': 'original'}],
                                               'inspected_resume': {'receipt': 'retained'}}
            recovery.save(root, retained)
            def run(args, **kwargs): return subprocess.CompletedProcess(args, 0, '')
            with patch.object(recovery, 'runtime_fault', return_value=True), patch.object(recovery, 'assert_idle'), \
                 patch.object(recovery, 'helper', return_value={'status': 'healthy'}):
                self.assertFalse(recovery.maintenance(root, run, 'retained.service'))
            current = recovery.journal(root)
            self.assertEqual(current['controllers'], retained['controllers'])
            self.assertEqual(current['inspected_resume'], retained['inspected_resume'])
            with patch.object(recovery, 'runtime_fault', return_value=False):
                self.assertFalse(recovery.maintenance(root, run, 'retained.service'))
            self.assertEqual(recovery.journal(root)['state'], 'healthy')
            self.assertEqual(recovery.journal(root)['inspected_resume'], retained['inspected_resume'])

    def test_corrupt_or_unknown_helper_result_cannot_be_confirmed_healthy(self):
        for state in ('corrupt', 'unexpected-state'):
            value = {'status': state, 'helper_sha256': recovery.digest(recovery.SOURCE), 'policy_sha256': recovery.digest(recovery.POLICY)}
            reply = subprocess.CompletedProcess([], 0, json.dumps(value))
            with self.subTest(state=state), patch.object(recovery.subprocess, 'run', return_value=reply), self.assertRaises(recovery.RecoveryError):
                recovery.helper('confirm')

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

    def test_distinct_image_preserves_original_consumer_and_prior_evidence(self):
        old = 'repo@sha256:' + 'a'*64; new = 'repo@sha256:' + 'b'*64
        controller = {'namespace':'devint-proof','resource':'deployment/store','uid':'same-owner','replicas':1}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            recovery.save(root, {'state':'restored-awaiting-readiness','corrupt':[{'reference':old}],
                'controllers':[controller], 'completed_pods':[['devint-proof','already-retired','original-uid']],
                'repaired':[old], 'started_at':100})
            calls=[]
            def run(args, **kwargs):
                calls.append(args)
                return subprocess.CompletedProcess(args,0,json.dumps({'metadata':{'uid':'same-owner'},'spec':{'replicas':0},'status':{'replicas':0}}))
            with patch.object(recovery,'assert_idle'), \
                 patch.object(recovery,'affected_controllers',return_value=([{**controller,'replicas':0}],[])), \
                 patch.object(recovery,'helper',return_value={'repaired':[new]}):
                recovery.recover_images(root,run,{'corrupt':[{'reference':new}]})
            value=recovery.journal(root)
            self.assertEqual(value['controllers'],[controller])
            self.assertEqual(value['started_at'],100)
            self.assertEqual({item['reference'] for item in value['corrupt']},{old,new})
            self.assertEqual(value['repaired'],[old,new])
            self.assertFalse(any('delete' in call for call in calls))
            with patch.object(recovery,'assert_idle'),patch.object(recovery,'helper') as helper,self.assertRaises(recovery.RecoveryError):
                recovery.recover_images(root,run,{'corrupt':[{'reference':new}]})
            helper.assert_not_called()

    def test_interrupted_archive_resume_requires_root_proof_for_same_attempt(self):
        reference='repo@sha256:'+'a'*64
        for resume in (False,True):
            with self.subTest(resume=resume),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);recovery.save(root,{'state':'repairing','corrupt':[{'reference':reference}],
                    'controllers':[],'completed_pods':[]})
                report={'corrupt':[{'reference':reference,'resume_from_archive':resume}]}
                with patch.object(recovery,'assert_idle'),patch.object(recovery,'affected_controllers',return_value=([],[])), \
                     patch.object(recovery,'helper',return_value={'repaired':[reference]}) as helper:
                    if resume:
                        recovery.recover_images(root,None,report)
                        self.assertEqual(recovery.journal(root)['state'],'restored-awaiting-readiness')
                    else:
                        with self.assertRaises(recovery.RecoveryError):recovery.recover_images(root,None,report)
                        helper.assert_not_called()

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
