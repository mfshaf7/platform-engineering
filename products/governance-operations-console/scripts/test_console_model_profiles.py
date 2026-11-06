"""Controlled native-source tests: disposable repositories, no live grants."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'scripts'))
import console_model_profiles as profiles
import platform_operation_provider as provider
import test_model_profile_lifecycle as native_tests
OOS_ROOT,PROFILE_ID=native_tests.OOS_ROOT,native_tests.PROFILE_ID


class RequestOwner:
    def __init__(self,projection,context):
        self.projection,self.context=copy.deepcopy(projection),copy.deepcopy(context)
        self.approval={'request_id':projection['request_id'],'request_revision':3,'decision':'approve','reason':'Synthetic explicit approval','operator_id':'operator:workspace-owner'}
        self.approval['digest']=profiles.digest(self.approval)
        self.projection['decision_ref']={'uri':'oos://model-profile-requests/'+profiles.quote(projection['request_id'],safe='')+'/decisions/'+profiles.quote(self.approval['digest'],safe=''),'digest':self.approval['digest']}
    def lifecycle(self,request_id):
        assert request_id==self.projection['request_id']
        return {'request':copy.deepcopy(self.projection),'context':copy.deepcopy(self.context),'security_acceptance':None}
    def request(self,path,body=None):
        if '/decisions/' in path:return copy.deepcopy(self.approval)
        assert path.endswith('/fulfillment') and body['state'] in {'applied','failed'}
        self.projection['fulfillment_state']=body['state'];self.projection['fulfillment']=copy.deepcopy(body);return copy.deepcopy(self.projection)
    def fulfill(self,original,state):
        assert original['fulfillment_state']=='not-started' and state=='implementing'
        self.projection['revision']+=1;self.projection['fulfillment_state']=state
        receipt=self.projection['latest_receipt'];receipt['request_revision']=self.projection['revision'];receipt['fulfillment_state']=state;receipt['recorded_at']=profiles.utc()
        receipt['digest']=profiles.digest({k:v for k,v in receipt.items() if k!='digest'})
        key=original['request_id']+':implement:'+str(original['revision'])
        self.projection['fulfillment']={'schema_version':1,'fulfillment_id':key,'request_id':original['request_id'],'expected_revision':original['revision'],'state':state,'actor_id':profiles.native.ACTOR_ID,'recorded_at':receipt['recorded_at'],'source':None,'receipt_ref':None,'failure':None,'idempotency_key':key}
        event=self.projection['history'][-1];event['fulfillment_state_after']=state;event['occurred_at']=receipt['recorded_at'];event['receipt_ref']['digest']=receipt['digest'];event['command_id']=key
        return copy.deepcopy(self.projection)


class ProfileConsoleTests(unittest.TestCase):
    def setUp(self):
        self.fixture=native_tests.ModelProfileLifecycleTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root=self.fixture.root;self.workspace=self.root.parent
        subprocess.run(['git','-C',str(self.root),'branch','-m','main'],check=True)
        # The native CLI and validator run against the disposable source.
        (self.root/'scripts').mkdir()
        (self.root/'.gitignore').write_text('__pycache__/\n')
        for name in ('model_profile_lifecycle.py','validate_ai_model_profiles.py'):
            shutil.copy2(ROOT/'scripts'/name,self.root/'scripts'/name)
        composition=self.root/'products/governance-operations-console/complete-runtime-policy.yaml'
        composition.parent.mkdir(parents=True);shutil.copy2(ROOT/'products/governance-operations-console/complete-runtime-policy.yaml',composition)
        subprocess.run(['git','-C',str(self.root),'add','scripts','.gitignore','products'],check=True)
        subprocess.run(['git','-C',str(self.root),'commit','-qm','Native implementation'],check=True)
        self.fixture.base_version=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip()
        (self.workspace/'operator-orchestration-service').symlink_to(OOS_ROOT,target_is_directory=True)
        self.store=provider.OperationStore(self.workspace/'private-state/provider')
        self.policy={'workspace_root':str(self.workspace),'runtime_state_root':str(self.workspace/'private-state'),
          'purpose_profiles':{'lifecycle':{'enabled':True}},'platform_operation_provider':{'operator_id':'operator:workspace-owner'},
          'security':{'platform_revision':self.fixture.base_version,'platform_tree':subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD^{tree}'],text=True).strip()}}
        self.calls=[];self.pr=None;self.provider_online=True
        overlay=Path(self.policy['runtime_state_root'])/'private/model-management/overlay.json'
        overlay.parent.mkdir(parents=True)
        profiles.native.write_atomic(overlay,profiles.native.canonical_json({'image':'synthetic-commissioned-image','owner_policy':{},'memory_limit':'1Gi','cpu_limit':'1'}))
        self.input={'request_id':'model-profile-request:test-amend','intent':'amend','profile_id':PROFILE_ID,'environment':'dev-integration','changes':{'runtime_limits':{'max_output_tokens':4000}}}

    def run_owner(self,argv,*,cwd=None):
        self.calls.append(argv)
        if argv[0]=='make':return '{}'
        if argv[0]=='node':
            if 'publish' not in argv:return '{}'
            checkout=Path(argv[argv.index('--repo-root')+1]);head=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
            self.pr={'url':'https://github.com/mfshaf7/platform-engineering/pull/42','number':42,'head':head}
            return json.dumps({'pull_request':{'url':self.pr['url'],'number':42},'pushed_head':head})
        if argv[:3]==['gh','api','user']:return 'workspace-owner'
        if argv[:3]==['gh','pr','view']:
            return json.dumps({'url':self.pr['url'],'author':{'login':'app/mfshaf7-agent-gary'},'headRefOid':self.pr['head'],'baseRefName':'main','state':'MERGED' if self.pr.get('merged') else 'CLOSED' if self.pr.get('closed') else 'OPEN','mergeCommit':{'oid':self.pr['head']}})
        if argv[:3]==['gh','pr','merge']:
            subprocess.run(['git','-C',str(self.root),'merge','--ff-only',self.pr['head']],check=True,capture_output=True);self.pr['merged']=True;return ''
        if argv[:3]==['gh','pr','close']:self.pr['closed']=True;return ''
        if argv[0]=='gh':return ''
        if any(str(arg).endswith('scripts/dev_integration.py') for arg in argv):
            self.assertEqual('env',argv[0]);self.assertTrue(argv[1].startswith('DEVINT_GAI_MODEL_MANAGEMENT_OVERLAY='))
            if not self.provider_online:raise profiles.ProfileError('Synthetic provider offline')
            return ''
        if argv[:2]==['k3s','kubectl']:
            source=profiles.native.source_state(self.root)
            states={key:{'status':value['status'],'activation_eligible':value['status']=='active','ready':value['status']=='active'} for key,value in profiles.native.read_yaml(self.root/profiles.native.REGISTRY)['model_profiles'].items()}
            return json.dumps({'selected_binding':{'profile_registry_digest':source['registry_digest'],'access_plane_digest':source['access_plane_digest']},'profiles':states})
        if argv[0]=='git' and ('fetch' in argv or 'ls-remote' in argv):return ''
        if argv[0]=='git' and argv[-1]=='origin/main':
            if 'rev-parse' in argv:return self.fixture.base_version
            return ''
        if argv[0]=='git' and 'show' in argv and argv[-1].startswith('origin/main:'):
            return (self.root/argv[-1].split(':',1)[1]).read_text().rstrip('\n')
        result=subprocess.run(argv,cwd=cwd,text=True,capture_output=True,timeout=30)
        self.assertEqual(0,result.returncode,result.stderr[:3000])
        return result.stdout.rstrip('\n')

    def flow(self):
        prepared=profiles.prepare(self.root,self.input,workspace=self.workspace)
        projection=self.fixture.projection(intent=self.input['intent'])
        projection.update(fulfillment_state='not-started',fulfillment=None)
        projection['latest_receipt']['fulfillment_state']='not-started';projection['history'][-1]['fulfillment_state_after']='not-started'
        if self.input['intent']=='create':
            projection['request']['profile_intent'].update(profile_id=None,source=None)
            receipt=projection['latest_receipt'];receipt.update(profile_id=None,source_ref=None);receipt['digest']=profiles.digest({k:v for k,v in receipt.items() if k!='digest'})
            projection['history'][0]['receipt_ref']['digest']=receipt['digest']
        projection['latest_receipt']['digest']=profiles.digest({k:v for k,v in projection['latest_receipt'].items() if k!='digest'})
        projection['history'][0]['receipt_ref']['digest']=projection['latest_receipt']['digest']
        self.owner=RequestOwner(projection,{'candidate':prepared['candidate'],'candidate_digest':prepared['candidate']['candidate_digest']})
        return profiles.ProfileOperations(self.policy,self.store,owner=self.owner,run=self.run_owner)

    def test_six_actions_derive_exact_source_and_policy_without_model_access(self):
        for intent in ('create','amend','suspend','retire','exception'):
            value=profiles.prepare(self.root,{**self.input,'intent':intent,'changes':self.input['changes'] if intent=='amend' else {}},workspace=self.workspace)
            self.assertEqual(intent,value['intent']);self.assertEqual(self.fixture.base_version,value['candidate']['expected_sources']['source_version'])
            self.assertEqual(intent in {'activate','exception'},value['security_acceptance_required'])
            self.assertEqual(value['candidate']['candidate_digest'],profiles.digest({k:v for k,v in value['candidate'].items() if k!='candidate_digest'}))
        registry=profiles.native.read_yaml(self.root/profiles.native.REGISTRY);registry['model_profiles'][PROFILE_ID]['status']='suspended'
        profiles.native.write_atomic(self.root/profiles.native.REGISTRY,profiles.native.render_yaml(registry))
        subprocess.run(['git','-C',str(self.root),'add',str(profiles.native.REGISTRY)],check=True)
        subprocess.run(['git','-C',str(self.root),'commit','-qm','Controlled suspended source'],check=True)
        value=profiles.prepare(self.root,{**self.input,'intent':'activate','changes':{}},workspace=self.workspace)
        self.assertTrue(value['security_acceptance_required']);self.assertEqual('active',value['result_state'])

    def test_rejects_raw_policy_paths_shells_unreviewed_fields_and_noop(self):
        for changes in ({'command':'anything'},{'runtime_limits':{'max_concurrency':True}},{'runtime_limits':{'max_output_tokens':999999}}):
            with self.assertRaises(profiles.ProfileError):profiles.prepare(self.root,{**self.input,'changes':changes},workspace=self.workspace)
        with self.assertRaises(profiles.ProfileError):profiles.prepare(self.root,{**self.input,'intent':'suspend','changes':self.input['changes']},workspace=self.workspace)
        unchanged=profiles.prepare(self.root,{**self.input,'changes':{}},workspace=self.workspace)
        self.assertFalse(unchanged['can_submit']);self.assertTrue(unchanged['editable_policy']['allowed_data_scope'])

    def test_real_native_apply_review_readback_and_restart_recovery(self):
        flow=self.flow();request_id=self.input['request_id']
        before=(self.root/profiles.native.REGISTRY).read_bytes()
        result=flow.control({'request_id':request_id,'action':'implement','expected_operation_digest':None})
        self.assertEqual('awaiting-review',result['state']);self.assertEqual(before,(self.root/profiles.native.REGISTRY).read_bytes());self.assertFalse(result['source_applied'])
        self.assertEqual(result,flow.control({'request_id':request_id,'action':'implement','expected_operation_digest':None}))
        restarted=profiles.ProfileOperations(self.policy,self.store,owner=self.owner,run=self.run_owner)
        result=restarted.control({'request_id':request_id,'action':'approve-merge','expected_operation_digest':result['operation_digest']})
        self.assertEqual('verified',result['state']);self.assertTrue(result['source_applied']);self.assertEqual('suspended',result['runtime_state'])
        self.assertEqual('applied',self.owner.projection['fulfillment_state'])
        self.assertFalse(Path(self.store.read(flow.key(request_id))['checkout']).exists())
        self.assertTrue(profiles.admitted_policy_source(self.policy,self.root,store_root=self.store.root))

    def test_only_receipted_policy_descendants_keep_control_acceptance(self):
        flow=self.flow();result=flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        result=flow.control({'request_id':self.input['request_id'],'action':'approve-merge','expected_operation_digest':result['operation_digest']})
        self.assertTrue(profiles.admitted_policy_source(self.policy,self.root,store_root=self.store.root))
        # Unrelated source is never admitted through a policy receipt.
        (self.root/'scripts/unreviewed.py').write_text('unexpected = True\n')
        subprocess.run(['git','-C',str(self.root),'add','scripts/unreviewed.py'],check=True)
        subprocess.run(['git','-C',str(self.root),'commit','-qm','Unrelated source'],check=True)
        self.assertFalse(profiles.admitted_policy_source(self.policy,self.root,store_root=self.store.root))

    def test_receipt_rollback_reuses_source_review_and_restores_exact_policy(self):
        before={str(p):(self.root/p).read_bytes() for p in (profiles.native.REGISTRY,profiles.native.ACCESS_PLANE,profiles.native.RUNTIME_ASSIST)}
        flow=self.flow();result=flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        result=flow.control({'request_id':self.input['request_id'],'action':'approve-merge','expected_operation_digest':result['operation_digest']})
        restored=flow.control({'request_id':self.input['request_id'],'action':'restore','expected_operation_digest':result['operation_digest']})
        self.assertEqual('awaiting-review',restored['state'])
        restored=flow.control({'request_id':self.input['request_id'],'action':'approve-merge','expected_operation_digest':restored['operation_digest']})
        self.assertEqual('verified',restored['state']);self.assertFalse(restored['rollback_available'])
        for path,content in before.items():self.assertEqual(content,(self.root/path).read_bytes())

    def test_rollback_cannot_overwrite_later_policy(self):
        flow=self.flow();result=flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        result=flow.control({'request_id':self.input['request_id'],'action':'approve-merge','expected_operation_digest':result['operation_digest']})
        path=self.root/profiles.native.REGISTRY;path.write_text(path.read_text()+'\n# Later policy\n')
        with self.assertRaises(profiles.ProfileError):flow.control({'request_id':self.input['request_id'],'action':'restore','expected_operation_digest':result['operation_digest']})

    def test_declining_source_preserves_patch_and_releases_the_policy_writer(self):
        before=(self.root/profiles.native.REGISTRY).read_bytes()
        flow=self.flow();result=flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        with self.assertRaises(profiles.ProfileError):flow.writer_available('model-profile-request:another')
        result=flow.control({'request_id':self.input['request_id'],'action':'decline-source','expected_operation_digest':result['operation_digest']})
        self.assertEqual('declined',result['state']);self.assertFalse(result['source_applied']);self.assertEqual('failed',self.owner.projection['fulfillment_state'])
        self.assertEqual(before,(self.root/profiles.native.REGISTRY).read_bytes());flow.writer_available('model-profile-request:another')
        record=self.store.read(flow.key(self.input['request_id']))
        self.assertTrue((flow.paths(record)/'declined-source.patch').is_file())
        self.assertFalse(Path(record['checkout']).exists())

    def test_aborting_interrupted_authoring_preserves_unique_source(self):
        flow=self.flow();original_run=flow.run
        def stopped(argv,**kwargs):
            if argv[0]=='node' and 'publish' in argv:raise profiles.ProfileError('Synthetic publication interruption')
            return original_run(argv,**kwargs)
        flow.run=stopped
        with self.assertRaises(profiles.ProfileError):flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        flow.run=original_run;current=flow.inspect(self.input['request_id'])
        result=flow.control({'request_id':self.input['request_id'],'action':'decline-source','expected_operation_digest':current['operation_digest']})
        self.assertEqual('declined',result['state'])
        record=self.store.read(flow.key(self.input['request_id']))
        self.assertTrue((flow.paths(record)/'declined-committed.patch').read_text())

    def test_new_profile_extends_only_the_receipted_management_task_catalog(self):
        self.input.update(intent='create',changes={})
        flow=self.flow();result=flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        result=flow.control({'request_id':self.input['request_id'],'action':'approve-merge','expected_operation_digest':result['operation_digest']})
        self.assertEqual('verified',result['state'])
        record=self.store.read(flow.key(self.input['request_id']));created=record['context']['candidate']['profile_id']
        overlay=profiles.native.read_json(flow.paths(record)/'model-management-overlay.json')
        self.assertFalse(any(task.startswith(created+'/') for task in overlay['owner_policy']['backends']['managed-codex']['allowed_tasks']))
        resolved = native_tests.resolve_model_profile_registry(self.root/profiles.native.REGISTRY, self.root/profiles.native.ACCESS_PLANE, environment='dev-integration')
        self.assertEqual(PROFILE_ID, resolved['profiles'][created]['capability_id'])
        self.assertIn(PROFILE_ID+'/metadata_advice', overlay['owner_policy']['backends']['managed-codex']['allowed_tasks'])
        self.assertEqual('suspended',profiles.native.read_yaml(self.root/profiles.native.REGISTRY)['model_profiles'][created]['status'])
        # Ordinary exact composed acceptance may advance the anchor after this
        # change; a restart must retain the newly accepted task catalog.
        import console_model_management as management
        qualified=copy.deepcopy(self.policy);qualified['security'].update(status='accepted',platform_revision=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip(),platform_tree=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD^{tree}'],text=True).strip())
        self.assertIn(PROFILE_ID+'/metadata_advice', management.owner_policy(self.root,'operator:workspace-owner',lifecycle_policy=qualified)['backends']['managed-codex']['allowed_tasks'])

    def test_no_active_profile_can_keep_only_accepted_management_controls_online(self):
        documents=[profiles.native.read_yaml(self.root/path) for path in (profiles.native.REGISTRY,profiles.native.ACCESS_PLANE,profiles.native.RUNTIME_ASSIST)]
        for profile_id in list(documents[0]['model_profiles']):
            profiles.native.mutate_sources(*documents,{'intent':'retire','profile_id':profile_id,'target_profile':None,'activation_environment':None,'decision_id':'synthetic-retirement'})
        profiles.native.validate_candidate(self.root,*(profiles.native.render_yaml(d) for d in documents))
        for path,document in zip((profiles.native.REGISTRY,profiles.native.ACCESS_PLANE,profiles.native.RUNTIME_ASSIST),documents):profiles.native.write_atomic(self.root/path,profiles.native.render_yaml(document))
        path=self.workspace/'control-only.json';profiles.native.write_atomic(path,profiles.native.canonical_json({'image':'synthetic','owner_policy':{'schema_version':1,'caller_id':'operator-orchestration-service','operator_id':'operator:sample','token_file':'/run/model-management/management-token'},'memory_limit':'1Gi','cpu_limit':'1'}))
        command=['bash','-c','source dev-integration/profiles/governed-ai-gateway/scripts/common.sh; require_active_model_binding']
        import os
        env={**os.environ,'DEVINT_PROFILE_LIFECYCLE':'active'}
        self.assertEqual(2,subprocess.run(command,cwd=self.root,env=env,capture_output=True).returncode)
        env['DEVINT_GAI_MODEL_MANAGEMENT_OVERLAY']=str(path)
        self.assertEqual(0,subprocess.run(command,cwd=self.root,env=env,capture_output=True).returncode)
        path.chmod(0o644)
        self.assertEqual(2,subprocess.run(command,cwd=self.root,env=env,capture_output=True).returncode)

    def test_provider_failure_never_turns_merged_source_into_verified_runtime(self):
        flow=self.flow();result=flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        self.provider_online=False
        result=flow.control({'request_id':self.input['request_id'],'action':'approve-merge','expected_operation_digest':result['operation_digest']})
        self.assertEqual('runtime-unverified',result['state']);self.assertTrue(result['source_applied']);self.assertEqual('unverified',result['runtime_state']);self.assertEqual('reconcile',result['next_action'])

    def test_stale_operation_and_source_are_denied_before_source_authoring(self):
        flow=self.flow();result=flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        with self.assertRaises(profiles.ProfileError):flow.control({'request_id':self.input['request_id'],'action':'approve-merge','expected_operation_digest':'sha256:'+'0'*64})
        self.assertEqual('awaiting-review',flow.inspect(self.input['request_id'])['state'])

    def test_default_off_does_not_create_any_operation(self):
        flow=profiles.ProfileOperations({**self.policy,'purpose_profiles':{}},self.store,owner=object(),run=self.run_owner)
        with self.assertRaises(profiles.ProfileError):flow.control({'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None})
        self.assertFalse(list(self.store.operations.glob('*.json')))

    def test_existing_runtime_recovery_guard_prevents_policy_control_effects(self):
        service=SimpleNamespace(policy=self.policy,store=self.store,source_version=self.fixture.base_version)
        handler=provider.handler_for(service,'synthetic-caller','synthetic-secret')
        request=object.__new__(handler);request.path='/v1/console-operations/model-profiles/control';request.command='POST'
        request.authenticated=lambda:True
        request.body=lambda **kwargs:{'request_id':self.input['request_id'],'action':'implement','expected_operation_digest':None}
        responses=[];request.respond=lambda status,value:responses.append((status,value))
        flow=mock.Mock()
        with mock.patch.object(provider,'activation_is_current',return_value=True),mock.patch.object(provider.model_profiles,'ProfileOperations',return_value=flow),mock.patch.object(provider.artifact_recovery,'owner_guard',side_effect=provider.artifact_recovery.RecoveryDeferred('Controlled recovery')):
            request.dispatch()
        self.assertEqual(503,responses[0][0]);self.assertEqual('platform_profile_recovery_busy',responses[0][1]['code'])
        flow.control.assert_not_called()


if __name__=='__main__':unittest.main()
