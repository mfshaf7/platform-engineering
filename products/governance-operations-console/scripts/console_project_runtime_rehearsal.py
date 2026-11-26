"""Run the paired project through the broker and protected Platform owner on local K3s."""

from contextlib import contextmanager
from hashlib import sha256
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from threading import Thread
import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

import platform_operation_provider as platform
from agent_source_identity import write_json_atomic
from agent_source_instance import digest
from console_project_runtime_driver import K3sProjectClient
from console_project_runtime_provider import ProjectRuntimeProvider
from console_project_runtime_sandbox import ProjectSandbox, SandboxRecipe, WorkloadLimits
from console_project_runtime_setup import CommittedSource, ProjectSetupStore, scope_key


HERE = Path(__file__).resolve().parent
IMAGE = 'docker.io/library/node:22.22.0-bookworm-slim@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94'
BUILD = dict(cpu_millis=200,memory_mib=192,temporary_mib=256,deadline_seconds=100)
SERVE = dict(cpu_millis=100,memory_mib=96,temporary_mib=64,deadline_seconds=100)
AGGREGATE = dict(cpu_millis=420,memory_mib=480,temporary_mib=416,deadline_seconds=100)
RECIPE_KEY = 'node-frontend-api'
FRONTEND = """import http from 'node:http';
import {readFileSync} from 'node:fs';
const build = readFileSync('built.txt','utf8').trim();
http.createServer(async (_req,res) => {
  try {
    const api = await fetch(new URL('/project-info',process.env.PROJECT_API_ORIGIN),{signal:AbortSignal.timeout(1800)});
    if (!api.ok) throw new Error('api unavailable');
    res.end(JSON.stringify({frontend:build,api:await api.text()}));
  } catch { res.writeHead(503).end('API unavailable'); }
}).listen(Number(process.env.PORT),'0.0.0.0');
"""
API = """import http from 'node:http';
import {readFileSync} from 'node:fs';
const version=readFileSync('built.txt','utf8').trim();
http.createServer((_,res)=>res.end(version)).listen(Number(process.env.PORT),'0.0.0.0');
"""


@contextmanager
def restarted_owner(configuration, root):
    child = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--serve-owner'],stdin=subprocess.PIPE,text=True,
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        child.stdin.write(json.dumps(configuration))
        child.stdin.close()
        port = root / 'fresh-owner-port.json'
        deadline=time.monotonic()+12
        while not port.exists() and child.poll() is None and time.monotonic()<deadline:
            time.sleep(0.1)
        assert child.poll() is None and port.exists(), 'The isolated Platform owner did not restart'
        yield f'http://127.0.0.1:{json.loads(port.read_text())["port"]}'
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def serve_owner():
    input = json.load(sys.stdin)
    policy = input['policy']
    store = platform.OperationStore(Path(input['store']))
    provider = ProjectRuntimeProvider.from_policy(policy,store)
    fixture=SimpleNamespace(policy=policy,source_version='disposable',project_runtime=provider)
    with patch.object(platform,'activation_is_current',return_value=True), \
            patch.object(platform.artifact_recovery,'blocked',return_value=None), \
            ThreadingHTTPServer(('127.0.0.1',0),platform.handler_for(fixture,'isolated-broker',input['secret'])) as server:
        write_json_atomic(Path(input['port_file']),{'port':server.server_port})
        server.serve_forever()


def exercise(broker, *, failed_update=False, capacity=False, retained_data=False):
    if not __debug__:
        raise RuntimeError('The rehearsal requires enabled runtime assertions.')
    with TemporaryDirectory(prefix='1384-paired-run-') as tmp:
        root = Path(tmp)
        repo = root / 'repository'
        app = repo / 'app'
        app.mkdir(parents=True)
        package = {'name':'paired-proof','version':'1.0.0','scripts':{
            'build':'node build.mjs','start:frontend':'node frontend.mjs','start':'node api.mjs'}}
        lock = b'{"name":"paired-proof","version":"1.0.0","lockfileVersion":3,"requires":true,"packages":{"":{"name":"paired-proof","version":"1.0.0"}}}'
        files = {'package.json':json.dumps(package), 'package-lock.json':lock.decode(), 'frontend.mjs':FRONTEND,
                 'api.mjs':API,'version.txt':'base\n','build.mjs':"import {copyFileSync,readFileSync} from 'node:fs'; if (readFileSync('version.txt','utf8').trim()==='fails') throw Error('rehearsal failure'); copyFileSync('version.txt','built.txt');"}
        for name, value in files.items():
            (app / name).write_text(value)
        def git(*args):
            return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
        git('init','-q')
        git('add','--all')
        git('-c','user.name=Disposable Project','-c','user.email=proof@example.invalid','commit','-qm','Pinned application')
        base=git('rev-parse','HEAD')
        scope={'installation_id':f'isolated:{uuid4().hex}','project_custody_ref':'project:paired-rehearsal',
               'repository_id':42,'app_root':'app','dependency_paths':[],'environment_ref':'devint:paired-rehearsal'}
        subject={'kind':'delivery','ref':'work-item-42'}
        scope_digest='sha256:'+scope_key(scope)
        namespace='devint-project-'+scope_digest[7:39]
        owner=root / 'owner'
        private=owner / 'project-runtime'
        for folder in ('snapshots','admitted-scopes','approved-dependencies','dependency-approvals'):
            (private/folder).mkdir(parents=True,mode=0o700)
        private.chmod(0o700)
        store=platform.OperationStore(owner / 'store')
        setup=ProjectSetupStore(store).save(scope,requested_app_root='app',recipe_id=RECIPE_KEY,expected_revision=None,
                                            source=CommittedSource(repo,base))['setup']
        security='sha256:'+secrets.token_hex(32)
        write_json_atomic(private/'admitted-scopes'/f'{scope_key(scope)}.json',{
            'scope':scope,'project_ref':scope['project_custody_ref'],'subject':subject,'security_decision_digest':security,
            'visibility':'internal','lane':'local-dev-integration','data_mib':64 if retained_data else 0,
        })
        (root/'_cacache').mkdir()
        archive=root/'cache.tar'
        with tarfile.open(archive,'w') as bundle:
            bundle.add(root/'_cacache',arcname='_cacache')
        data=archive.read_bytes()
        cache_digest=sha256(data).hexdigest()
        (private/'approved-dependencies'/cache_digest).write_bytes(data)
        approval=digest({'recipe':RECIPE_KEY,'image':IMAGE,'lock_digest':'sha256:'+sha256(lock).hexdigest()})
        write_json_atomic(private/'dependency-approvals'/f'{approval[7:]}.json',{
            'identity':approval,'digest':'sha256:'+cache_digest,'bytes':len(data),'security_decision_digest':security,
        })
        aggregate={**AGGREGATE,'cpu_millis':300} if capacity else AGGREGATE
        recipe={'image':IMAGE,'transfer_image':IMAGE,'build':BUILD,'serve':SERVE,'aggregate':aggregate,
                'storage_mib':2048,'output_mib':128,'run_port':3000}
        settings={'enabled':True,'security_decision_digest':security,'recipe':recipe,
                  'source_limits':{'max_files':32,'max_bytes':65536,'max_manifest_bytes':65536},
                  'input_mib':128,'cache_mib':128,'cache_bytes':65536,'cache_expanded_bytes':65536}
        policy={'runtime_state_root':str(owner),'security':{'decision_digest':security},'project_runtime':settings}
        provider=ProjectRuntimeProvider.from_policy(policy,store)
        kube=K3sProjectClient()
        assert kube.get('namespace',namespace) is None
        fixture=SimpleNamespace(policy=policy,source_version='disposable',project_runtime=provider)
        secret=secrets.token_hex(24)
        peer_digest='sha256:'+secrets.token_hex(32)
        peer_operation='project-operation:'+secrets.token_hex(32)
        peer=ProjectSandbox(peer_digest,peer_operation,SandboxRecipe(IMAGE,IMAGE,WorkloadLimits(**BUILD),WorkloadLimits(**SERVE),
                            WorkloadLimits(**AGGREGATE),2048,128))
        assert kube.get('namespace',peer.namespace) is None

        def read_http(space,pod,url):
            js="""const u=process.argv[1];
            fetch(u,{signal:AbortSignal.timeout(2900)}).then(async r=>process.stdout.write(await r.text())).catch(()=>process.stdout.write('denied'))"""
            return kube._call('-n',space,'exec',pod,'--','node','-e',js,url,timeout=12).decode()

        def get_run(result, version):
            binding=result['acknowledgement']
            receipt_path=private/'operations/sandbox-receipts'/f"{binding['operation_id'].split(':',1)[1]}.json"
            receipt=json.loads(receipt_path.read_text())
            assert receipt['state']=='ready' and receipt['api_pod_uid']
            assert receipt['manifest_digest'] == result['confirmed']['manifest_digest']
            assert receipt['configuration_revision'] == setup['configuration_revision']
            assert result['confirmed']['instance_ref'] == f"project-runtime:{namespace}/{receipt['pod_name']}"
            for name in (receipt['pod_name'], receipt['api_pod_name']):
                pod = kube.get('pod', name, namespace)
                assert pod['spec']['containers'][0]['image'] == IMAGE
            return_status = provider.lifecycle.inspect(scope)
            assert return_status['last_qualified']['source_manifest_digest'] == receipt['manifest_digest']
            assert json.loads(read_http(namespace,receipt['pod_name'],'http://127.0.0.1:3000/'))=={'frontend':version,'api':version}
            return receipt

        with patch.object(platform,'activation_is_current',return_value=True), \
                patch.object(platform.artifact_recovery,'blocked',return_value=None), \
                ThreadingHTTPServer(('127.0.0.1',0),platform.handler_for(fixture,'isolated-broker',secret)) as server:
            thread=Thread(target=server.serve_forever,daemon=True)
            thread.start()
            provider_url = f'http://127.0.0.1:{server.server_port}'
            def command(action,expected,version='102',run_state=None):
                inputs={'broker':str(broker),'journal':str(root/'broker-state'),'action':action,'expected':expected,
                        'version':version,'runState':run_state,
                        'base':base,'scope':scope,'subject':subject,'project':scope['project_custody_ref'],'setup':setup,
                        'repository':str(repo),'snapshots':str(private/'snapshots'),'url':provider_url,'secret':secret}
                result=subprocess.run(['node',str(HERE/'console_project_runtime_rehearsal.mjs')],input=json.dumps(inputs),text=True,capture_output=True,timeout=255)
                if result.returncode:
                    for failure in (private/'operations/sandbox-receipts').glob('*.json'):
                        receipt=json.loads(failure.read_text())
                        if receipt.get('state')=='failed':
                            print(json.dumps({k:receipt.get(k) for k in ('state','failure_kind','failure_detail')}),file=sys.stderr)
                    raise AssertionError(result.stderr)
                return json.loads(result.stdout)

            def post(route, values):
                request=Request(provider_url+'/v1/console-operations/project-runtime/'+route,
                    data=json.dumps(values).encode(),method='POST',headers={'Content-Type':'application/json',
                    'X-Platform-Caller-Id':'isolated-broker','X-Platform-Caller-Secret':secret})
                try:
                    with urlopen(request,timeout=10) as response:
                        return response.status,json.load(response)
                except HTTPError as error:
                    return error.code,json.load(error)

            def exec_js(pod, source, *args):
                return kube._call('-n', namespace, 'exec', pod, '--', 'node', '-e', source, *args, timeout=12).decode()

            def verify_boundaries(runtime):
                runtime_policy = yaml.safe_load((HERE.parent / 'complete-runtime-policy.yaml').read_text())
                approved_operator = runtime_policy['platform_operation_provider']['operator_id'].removeprefix('operator:')
                live_namespace = runtime_policy['runtime']['namespace_pattern'].format(operator=approved_operator)
                broker_service = runtime_policy['runtime']['oos_deployment']
                protected = [
                    kube.get('service', 'kubernetes', 'default'),
                    kube.get('service', broker_service, live_namespace),
                ]
                assert all(protected), 'Expected the active Console Broker and Kubernetes services'
                for name in (runtime['pod_name'], runtime['api_pod_name']):
                    spec = kube.get('pod', name, namespace)['spec']
                    assert spec['automountServiceAccountToken'] is False
                    assert all(not spec.get(field) for field in ('hostNetwork', 'hostPID', 'hostIPC'))
                    assert all(set(volume) <= {'name', 'persistentVolumeClaim', 'emptyDir'} for volume in spec['volumes'])
                    container = spec['containers'][0]
                    assert not container.get('envFrom')
                    declared = {'HOME', 'PORT', 'HOST', 'NODE_ENV'}
                    if name == runtime['pod_name']:
                        declared.add('PROJECT_API_ORIGIN')
                    assert {entry['name'] for entry in container.get('env', [])} == declared
                    assert all('valueFrom' not in entry for entry in container.get('env', []))
                    assert exec_js(name, "const fs=require('fs'); console.log(fs.existsSync('/var/run/secrets/kubernetes.io/serviceaccount/token'))").strip() == 'false'
                    for service in protected:
                        host = service['spec']['clusterIP']
                        port = service['spec']['ports'][0]['port']
                        with socket.create_connection((host, port), timeout=3):
                            pass
                        check = (
                            "const s=require('node:net').createConnection({host:process.argv[1],port:Number(process.argv[2])});"
                            "s.on('connect',()=>{console.log('connected');s.destroy()});"
                            "s.on('error',()=>{console.log('denied');s.destroy()});"
                            "s.setTimeout(2400,()=>{console.log('denied');s.destroy()});"
                        )
                        assert exec_js(name, check, host, str(port)).strip() == 'denied'

            try:
                started=command('run',0,'101')
                old=get_run(started,'101')
                if capacity:
                    next_operation='project-operation:'+secrets.token_hex(32)
                    proposed=ProjectSandbox(scope_digest,next_operation,
                        SandboxRecipe(IMAGE,IMAGE,WorkloadLimits(**BUILD),WorkloadLimits(**SERVE),
                                      WorkloadLimits(**aggregate),2048,128))
                    response=subprocess.run(['k3s','kubectl','create','--dry-run=server','-f','-'],
                        input=json.dumps(proposed.transfer_pod()),text=True,capture_output=True,timeout=15)
                    assert response.returncode!=0 and 'exceeded quota' in response.stderr and 'cpu' in response.stderr, response.stderr
                    invalid=command('run',1,'102',run_state='failed')
                    assert invalid['confirmed']['state']=='failed' and 'instance_ref' not in invalid['confirmed']
                    assert invalid['dispatches']==1
                    qualified=provider.lifecycle.inspect(scope)['last_qualified']
                    assert qualified['source_manifest_digest']==old['manifest_digest']
                    assert qualified['artifact_digest']==old['artifact_digest']
                    assert qualified['instance_ref']==old['instance_ref']
                    assert json.loads(read_http(namespace,old['pod_name'],'http://127.0.0.1:3000/'))=={'frontend':'101','api':'101'}
                    assert {pod['metadata']['name'] for pod in kube.list('pod',namespace)}=={old['pod_name'],old['api_pod_name']}
                    proof={'nativeCpuQuotaRefusedConcurrentTransfer':True,'configuredCpuMilli':aggregate['cpu_millis'],
                        'overBudgetRunState':invalid['confirmed']['state'],'previousPairStayedReady':True,'strayPods':0,
                        'preservedManifest':old['manifest_digest']}
                elif retained_data:
                    api=old['api_pod_name']
                    claim=old['data_claim']
                    claim_before=kube.get('persistentvolumeclaim',claim,namespace)
                    assert claim_before is not None
                    written=exec_js(api,"const fs=require('fs');fs.writeFileSync('/project-data/witness.txt','approved data');fs.writeFileSync('/tmp/scratch-witness.txt','throw away');console.log('written')")
                    assert written.strip()=='written'
                    assert exec_js(old['pod_name'],"console.log(require('fs').existsSync('/project-data'))").strip()=='false'
                    checkpoint=provider.lifecycle.inspect(scope)
                    reset_id='project-operation:'+secrets.token_hex(32)
                    reset={'command_id':'control:unconfirmed-reset','operation_id':reset_id,'action':'reset',
                           'scope':scope,'expected_revision':checkpoint['revision']}
                    status,_=post('control',reset)
                    assert status==409
                    assert provider.lifecycle.inspect(scope)==checkpoint
                    assert exec_js(api,"console.log(require('fs').readFileSync('/project-data/witness.txt','utf8'))").strip()=='approved data'
                    stop = {'scope': scope, 'command_id': 'control:interrupted-stop',
                            'operation_id': 'project-operation:' + secrets.token_hex(32),
                            'action': 'stop', 'expected_revision': checkpoint['revision']}
                    # Commit normal owner acceptance, then end this rehearsal process's
                    # dispatch opportunity before starting a fresh owner against its store.
                    with patch.object(provider, '_start_retained', side_effect=lambda _, result: result):
                        status, accepted = post('control', stop)
                    assert status == 202 and accepted['state'] == 'preparing'
                    assert accepted['revision'] == checkpoint['revision'] + 1
                    read = {key: stop[key] for key in ('scope', 'command_id', 'operation_id')}
                    server.shutdown()
                    thread.join(timeout=5)
                    with restarted_owner({'policy':policy,'store':str(store.root),'secret':secret,
                                          'port_file':str(root/'fresh-owner-port.json')},root) as address:
                        provider_url = address
                        status, interrupted = post('read', read)
                        assert status == 200 and interrupted['state'] == 'unknown'
                        assert interrupted['revision'] == accepted['revision']
                        status, retried = post('control', stop)
                        assert status == 202 and retried['operation_id'] == accepted['operation_id']
                        deadline = time.monotonic() + 120
                        while time.monotonic() < deadline:
                            status, reconciled = post('read', read)
                            if status == 200 and reconciled['state'] == 'stopped':
                                break
                            time.sleep(1)
                        assert status == 200 and reconciled['state'] == 'stopped'
                        assert reconciled['revision'] == accepted['revision']
                        assert not kube.list('pods', namespace)
                        assert kube.get('persistentvolumeclaim', claim, namespace)['metadata']['uid'] == claim_before['metadata']['uid']
                        assert {p['metadata']['name'] for p in kube.list('networkpolicy', namespace)} == {'project-deny'}
                        failed = command('run', started['acknowledgement']['scope_revision'], 'fails')
                        assert failed['confirmed']['state'] == 'failed' and 'instance_ref' not in failed['confirmed']
                        qualified = provider.lifecycle.inspect(scope)['last_qualified']
                        assert qualified['artifact_digest'] == old['artifact_digest']
                        assert qualified['source_manifest_digest'] == old['manifest_digest']
                        (private/'approved-dependencies'/cache_digest).unlink()
                        resumed=command('resume',failed['confirmed']['revision'])
                        again=get_run(resumed,'101')
                        assert again['manifest_digest']==old['manifest_digest']
                        assert again['artifact_digest']==old['artifact_digest']
                        assert again['configuration_revision']==old['configuration_revision']
                        assert again['api_pod_uid']!=old['api_pod_uid']
                        assert again['data_claim']==claim
                        result=exec_js(again['api_pod_name'],"const fs=require('fs');console.log(JSON.stringify({data:fs.readFileSync('/project-data/witness.txt','utf8'), scratch:fs.existsSync('/tmp/scratch-witness.txt')}))")
                        assert json.loads(result)=={'data':'approved data','scratch':False}
                    proof={'stopReleasedBothPods':True,'originalStopReadBackAfterOwnerRestart':True,
                        'resumeReusedOriginalArtifactAndSetup':True,'pairedApiReadSameData':True,
                        'scratchDisposed':True,'resumeWorkedWithoutBuildCache':True,'unconfirmedResetHttp':409,
                        'resetAttemptLeftStateAndDataUntouched':True,'volumeUidPreserved':True,
                        'interruptedStopReadAsUnknown': True, 'failedUpdateRetainedData': True}
                elif failed_update:
                    invalid=command('run',1,'fails')
                    assert invalid['confirmed']['state']=='failed'
                    assert 'instance_ref' not in invalid['confirmed']
                    assert invalid['confirmed']['manifest_digest']!=old['manifest_digest']
                    assert invalid['dispatches']==1
                    qualified=provider.lifecycle.inspect(scope)['last_qualified']
                    assert qualified['source_manifest_digest']==old['manifest_digest']
                    assert qualified['artifact_digest']==old['artifact_digest']
                    assert qualified['instance_ref']==old['instance_ref']
                    assert kube.get('pod',old['api_pod_name'],namespace)['metadata']['uid']==old['api_pod_uid']
                    assert json.loads(read_http(namespace,old['pod_name'],'http://127.0.0.1:3000/'))=={'frontend':'101','api':'101'}
                    assert {pod['metadata']['name'] for pod in kube.list('pod',namespace)}=={old['pod_name'],old['api_pod_name']}
                    proof={'failedUpdateKeptPreviousFrontendAndApi':True,'failedUpdateHasNoReadyInstance':True,
                           'previousManifest':old['manifest_digest'],'refusedManifest':invalid['confirmed']['manifest_digest']}
                else:
                    verify_boundaries(old)
                    pair_generation=old['operation_id'].split(':',1)[1][:32]
                    for document in peer.policy():
                        kube.create(document)
                    peer_policy={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy',
                        'metadata':peer._metadata('peer-test-receiver'),
                        'spec':{'podSelector':{'matchLabels':{'platform.project/role':'api'}},'policyTypes':['Ingress'],
                            'ingress':[{'from':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':namespace}},
                                                'podSelector':{'matchLabels':{'platform.project/role':'frontend',
                                                                             'platform.project/generation':pair_generation}}}],
                                        'ports':[{'protocol':'TCP','port':3000}]}]}}
                    kube.create(peer_policy)
                    peer_pod=peer._pod('api',image=IMAGE,limits=WorkloadLimits(**SERVE),mounts=[],port=3000,
                        command=['node','-e',"require('node:http').createServer((_,r)=>r.end('peer')).listen(3000,'0.0.0.0')"])
                    peer_pod['metadata']['labels']['platform.project/generation']=pair_generation
                    peer_name=peer_pod['metadata']['name']
                    kube.create(peer_pod)
                    kube.wait_ready(peer.namespace,peer_name,80)
                    peer_ip=kube.get('pod',peer_name,peer.namespace)['status']['podIP']
                    assert read_http(peer.namespace,peer_name,'http://127.0.0.1:3000/')=='peer'
                    assert read_http(namespace,old['pod_name'],f'http://{peer_ip}:3000/')=='denied'
                    cache_files_before = sorted(cache_root.name for cache_root in (private/'approved-dependencies').iterdir())
                    assert cache_files_before == [cache_digest]
                    updated=command('run',1,'102')
                    assert sorted(item.name for item in (private/'approved-dependencies').iterdir()) == cache_files_before
                    assert sha256((private/'approved-dependencies'/cache_digest).read_bytes()).hexdigest() == cache_digest
                    current=get_run(updated,'102')
                    assert current['manifest_digest']!=old['manifest_digest']
                    assert started['dispatches']==updated['dispatches']==1
                    assert kube.get('pod',old['pod_name'],namespace) is None and kube.get('pod',old['api_pod_name'],namespace) is None
                    current_network=kube.list('networkpolicy',namespace)
                    current_generation=current['operation_id'].split(':',1)[1][:32]
                    assert {p['metadata']['name'] for p in current_network}=={
                        'project-deny',f'project-api-ingress-{current_generation}',f'project-frontend-egress-{current_generation}'}
                    stopped=command('stop',updated['confirmed']['revision'])
                    assert kube.list('pods',namespace)==[]
                    assert {p['metadata']['name'] for p in kube.list('networkpolicy',namespace)}=={'project-deny'}
                    resumed=command('resume',stopped['confirmed']['revision'])
                    again=get_run(resumed,'102')
                    assert again['artifact_digest']==current['artifact_digest']
                    assert again['api_pod_uid']!=current['api_pod_uid']
                    proof={'projectNamespace':namespace,'peerNamespace':peer.namespace,'recipe':RECIPE_KEY,
                           'firstSave':old['manifest_digest'],'updatedSave':current['manifest_digest'],
                           'servedSameProjectFrontendAndApi':True,'foreignNamespaceWithPermittingIngressDenied':True,
                           'sameLockCacheDigest':cache_digest,'previousPairRetired':True,'stopRemovedBothPods':True,
                           'readBackExactRun':True,'reusedApprovedDependencyCache':True,
                           'protectedServicesDenied':True,'noInheritedAccess':True,
                           'resumePreservedArtifact':again['artifact_digest'],'ownerState':resumed['confirmed']['state']}
            finally:
                server.shutdown()
                thread.join(timeout=5)
                for target,target_scope in ((namespace,scope_digest),(peer.namespace,peer_digest)):
                    metadata=kube.get('namespace',target)
                    if metadata is not None:
                        assert metadata['metadata']['annotations']['platform.project/scope']==target_scope
                        subprocess.run(['k3s','kubectl','delete','namespace',target,'--timeout=120s'],check=True,capture_output=True)
        assert kube.get('namespace',namespace) is None and kube.get('namespace',peer.namespace) is None
        proof['disposableNamespacesRemoved']=True
        return proof


if __name__=='__main__':
    if sys.argv[1]=='--serve-owner':
        serve_owner()
    else:
        raise SystemExit("Use console_project_runtime_evidence.py to run the owner rehearsal.")
