"""Finite native release dispatch through existing GitHub owner workflows.

Provider records are the durable owner journal. No request is redispatched after
its write-ahead dispatch marker; uncertainty only reconciles the original run.
"""
from __future__ import annotations
from contextlib import nullcontext
from datetime import datetime,timezone,timedelta
import base64,hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import yaml
import console_release_identity as identity
from console_release_source import ReleaseSource,SourceView,SourceChanged
from console_dev_integration_profiles import committed_document,ProfileReadError

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from repository_provider_identity import ProviderClient,IdentityError,ProviderHttpError
sys.path.insert(0,str(ROOT/"products/openclaw/scripts"))
from gateway_contract import compute_source_bundle_ref
from prod_lifecycle import expected_prod_resources,lifecycle_configmap_payload,prod_verification_status_for_state
from stage_readiness import candidate_ref_for,verification_ref_for
REPOSITORY='mfshaf7/platform-engineering';REPOSITORY_ID=1195328534
PREFIX='/repos/'+REPOSITORY
SPECS={
 'readiness':{'filename':'confirm-stage-promotion-readiness.yaml','label':'Record stage verification and readiness','environment':'stage','action':'governed-release.execute-step','branch':'stage/approve-'},
 'promotion':{'filename':'promote-environment.yaml','label':'Request production promotion','environment':'prod','action':'governed-release.execute-step','branch':'promote/prod-'},
 'runtime':{'filename':'manage-prod-environment.yaml','label':'Request production runtime change','environment':'prod','action':'governed-release.change-runtime-lifecycle','branch':'prod/openclaw-'},
}
PHASES={'prepared','dispatching','uncertain','queued','awaiting-approval','in-progress','awaiting-review','applied','no-change','failed','cancelled'}
class ReleaseError(RuntimeError):
 def __init__(self,status,code,message):super().__init__(message);self.status=status;self.code=code

def digest(value):return identity.digest(value)
def now():return datetime.now(timezone.utc).isoformat()
def field(ident,label,description,*,required=True,options=None,default=''):
 return {'id':ident,'label':label,'description':description,'kind':'select' if options else 'text','required':required,'options':options or [],'default_value':default}
def options(values):return [{'label':value.replace('_',' ').replace('-',' ').capitalize(),'value':value} for value in values]

def selected(policy):return identity.selection_accepted(policy)

def source(policy,reader=committed_document):
 workspace=Path(policy['workspace_root']);registry,revision=reader(workspace,'workspace-governance','contracts/products.yaml')
 product=registry.get('products',{}).get('openclaw')
 if not isinstance(product,dict) or product.get('posture')!='active' or product.get('stage_supported')is not True or product.get('governed_prod_promotion')is not True:raise ReleaseError(409,'release_product_not_admitted','The current product contract does not admit this release path.')
 files={};platform_revision=None
 for key,path in [('candidate','environments/stage/release-candidate.yaml'),('verification','environments/stage/verification.yaml'),('readiness','environments/stage/promotion-readiness.yaml'),('runtime','environments/prod/openclaw-lifecycle.yaml'),('checks','products/openclaw/verification-catalog.yaml')]:
  doc,actual=reader(workspace,'platform-engineering',path)
  if platform_revision is not None and actual!=platform_revision:raise ReleaseError(409,'release_source_changed','Owner source changed during preparation. Refresh the product.')
  platform_revision=actual
  if not isinstance(doc,dict):raise ReleaseError(409,'release_source_invalid','The owner release contract is invalid.')
  files[key]=doc
 files.update({'registry_revision':revision,'platform_revision':platform_revision,'source_version':f'products:{revision}:{platform_revision}'})
 return files

def action_definition(policy,workflow_id,*,reader=committed_document):
 if workflow_id not in SPECS:raise ReleaseError(400,'release_workflow_invalid','Select a supported owner workflow.')
 spec=SPECS[workflow_id];data=source(policy,reader);fields=[]
 if workflow_id=='readiness':
  fields=[field('verification_evidence_ref','Verification evidence','Reference to the evidence for this exact candidate; recorded in the owner repository.'),field('verification_note','Verification note','Optional context recorded with the owner verification.',required=False),field('approval_note','Readiness note','Optional context for the protected readiness review.',required=False)]
  required=data['candidate'].get('candidate',{}).get('requiredChecks',[]);catalog=data['checks'].get('checks',{})
  if not isinstance(catalog,dict):raise ReleaseError(409,'release_checks_unavailable','The owner check catalog is invalid.')
  if not isinstance(required,list) or not 1<=len(required)<=20:raise ReleaseError(409,'release_checks_unavailable','The candidate verification catalog is incomplete.')
  for name in required:
   check=catalog.get(name,{})
   if not isinstance(name,str)or not re.fullmatch(r'[a-z0-9-]{1,100}',name) or not isinstance(check.get('acceptedReadinessStatuses'),list) or not check['acceptedReadinessStatuses']:raise ReleaseError(409,'release_checks_unavailable','A required candidate check has no accepted owner result contract.')
   fields.append(field('check:'+name,name.replace('-',' ').capitalize(),check.get('description','Record the actual verification result.'),options=options(check['acceptedReadinessStatuses'])))
 elif workflow_id=='promotion':
  fields=[field('promotion_note','Promotion note','Optional reason, recorded in the owner change.',required=False),field('suspend_stage_environment','After promotion','Choose whether the existing owner workflow suspends stage after preparing promotion.',options=[{'label':'Suspend stage','value':'true'},{'label':'Keep stage active','value':'false'}],default='true')]
 else:
  current=data['runtime'].get('state')
  if current not in {'live','traffic-stopped','suspended','quarantined'}:raise ReleaseError(409,'release_runtime_unknown','The current owner runtime contract is unavailable.')
  fields=[field('state','Target production state','The owner workflow changes desired GitOps state; observed resource health remains separate.',options=options([s for s in ['live','traffic-stopped','suspended','quarantined'] if s!=current])),field('reason','Reason','Explain the requested runtime change. This is recorded in the owner repository.'),field('incident_ref','Incident or follow-up reference','Required for quarantine or returning from quarantine to live.',required=False),field('operation_note','Operator note','Optional owner-record context.',required=False)]
 available=False;reason='Native release submission is not commissioned.'
 try:
  if not selected(policy):raise IdentityError('not selected or reviewed')
  identity.credential(policy)
  workflow,revision=reader(Path(policy['workspace_root']),'platform-engineering','.github/workflows/'+spec['filename'])
  inputs=(workflow.get('on')or workflow.get(True)or{}).get('workflow_dispatch',{}).get('inputs',{})
  if revision!=data['platform_revision'] or not {'console_request_id','console_intent'}.issubset(inputs):reason='The reviewed owner workflow does not yet contain the native request guard.'
  else:available=True;reason=None
 except (IdentityError,OSError,ValueError,KeyError,ProfileReadError):pass
 return {'schema_version':1,'workflow_id':workflow_id,'capability_id':'release.openclaw.'+workflow_id,'action':spec['action'],'available':available,'unavailable_reason':reason,'source_version':data['source_version'],'fields':fields}

def catalog_subjects(policy,reader=committed_document):
 definitions=[]
 try:data=source(policy,reader)
 except (ReleaseError,ProfileReadError):return []
 for key,spec in SPECS.items():
  try:definitions.append(action_definition(policy,key,reader=reader))
  except (ReleaseError,ProfileReadError):definitions.append({'workflow_id':key,'capability_id':'release.openclaw.'+key,'action':spec['action'],'available':False,'unavailable_reason':'Required inputs for this owner workflow are unavailable.','source_version':data['source_version']})
 if len({item['source_version']for item in definitions})!=1:return []
 return [{'kind':kind,'ref':'product:openclaw','owner':'platform-engineering','source_version':definitions[0]['source_version'],'capabilities':[{'capability_id':item['capability_id'],'action':item['action'],'available':item['available'],'unavailable_reason':item['unavailable_reason'],'required_capability':'platform.release.'+item['workflow_id'],'approval_required':True,'destructive':item['workflow_id']=='runtime'} for item in definitions if (item['workflow_id']=='runtime')==(kind=='product-runtime-lifecycle')]} for kind in ['product-release','product-runtime-lifecycle']]

def normalize_values(definition,values,data):
 if not isinstance(values,dict) or set(values)-{f['id'] for f in definition['fields']}:raise ReleaseError(400,'release_input_invalid','Use only fields declared by the selected owner workflow.')
 result={}
 for item in definition['fields']:
  value=values.get(item['id'],'')
  if not isinstance(value,str) or len(value)>2048 or item['required']and not value.strip() or item['options']and value not in [o['value'] for o in item['options']]:raise ReleaseError(400,'release_input_invalid','Complete the declared owner inputs and use supported choices.')
  result[item['id']]=value.strip()
 if definition['workflow_id']=='runtime' and (result['state']=='quarantined' or data['runtime']['state']=='quarantined'and result['state']=='live') and not result['incident_ref']:raise ReleaseError(400,'release_incident_required','This transition requires an incident or incident follow-up reference.')
 return result

def envelope(command,policy,definition,data):
 expected={'schema_version','command_id','idempotency_key','correlation_id','causation_id','actor_ref','subject','capability_id','action','input','requested_at','intent_digest','approval'}
 if not isinstance(command,dict) or set(command)!=expected or command['schema_version']!=1 or command['actor_ref']!=policy['platform_operation_provider']['operator_id']:raise ReleaseError(403,'release_command_forbidden','Release commands require the verified operator and exact owner intent.')
 for name in ['command_id','idempotency_key','correlation_id']:
  if not isinstance(command[name],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}',command[name]):raise ReleaseError(400,'release_command_invalid','Release request identity is invalid.')
 if command['causation_id']is not None and(not isinstance(command['causation_id'],str)or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}',command['causation_id'])):raise ReleaseError(400,'release_command_invalid','Release causation identity is invalid.')
 subject=command['subject'];kind='product-runtime-lifecycle' if definition['workflow_id']=='runtime' else 'product-release'
 if subject!={'kind':kind,'ref':'product:openclaw','expected_source_version':data['source_version']} or command['capability_id']!=definition['capability_id'] or command['action']!=definition['action']:raise ReleaseError(409,'release_review_stale','The reviewed product action or source differs from current owner preparation.')
 claims={key:value for key,value in command.items() if key not in {'intent_digest','approval'}};approved=command['approval']
 if digest(claims)!=command['intent_digest'] or not isinstance(approved,dict) or set(approved)!={'decision','operator_id','decision_ref','decided_at','intent_digest'} or approved['decision']!='approved' or approved['operator_id']!=command['actor_ref'] or approved['intent_digest']!=command['intent_digest']:raise ReleaseError(403,'release_approval_invalid','Review and explicitly authorize this exact release request.')
 if not isinstance(approved['decision_ref'],str)or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}',approved['decision_ref']):raise ReleaseError(400,'release_approval_invalid','The exact review decision reference is invalid.')
 try:datetime.fromisoformat(command['requested_at'].replace('Z','+00:00'));datetime.fromisoformat(approved['decided_at'].replace('Z','+00:00'))
 except (ValueError,TypeError,AttributeError):raise ReleaseError(400,'release_command_invalid','Release request timestamps are invalid.') from None

def validate_original(command,policy):
 payload=command.get('input')if isinstance(command,dict)else None
 version=command.get('subject',{}).get('expected_source_version')if isinstance(command,dict)and isinstance(command.get('subject'),dict)else None
 if not isinstance(payload,dict)or set(payload)!={'workflow_id','values'}or not isinstance(payload['workflow_id'],str)or payload['workflow_id']not in SPECS or not isinstance(payload['values'],dict)or len(payload['values'])>24 or any(not isinstance(key,str)or not isinstance(value,str)or len(value)>2048 for key,value in payload['values'].items())or not isinstance(version,str)or not re.fullmatch('products:[0-9a-f]{40}:[0-9a-f]{40}',version):raise ReleaseError(400,'release_command_invalid','Release command fields are invalid.')
 kind=payload['workflow_id'];envelope(command,policy,{'workflow_id':kind,'capability_id':'release.openclaw.'+kind,'action':SPECS[kind]['action']},{'source_version':version})

def rejected(command):
 _,registry,platform=command['subject']['expected_source_version'].split(':')
 return {'workflow_id':command['input']['workflow_id'],'values':{key:value.strip()for key,value in command['input']['values'].items()},'registry_revision':registry,'platform_revision':platform,'phase':'failed','run_id':None,'run_url':None,'pull_request_url':None,'branch':None,'merge_commit':None,'desired_state_verified':False}

class ReleaseDispatcher:
 def __init__(self,policy,store,*,reader=committed_document,client=None,credential_reader=identity.credential,owner_source=None):
  self.policy=policy;self.store=store;self.reader=reader;self.client=client or ProviderClient('https://api.github.com',api_version='2026-03-10');self.credential_reader=credential_reader
  self.source_client=client or ProviderClient('https://api.github.com',api_version='2026-03-10',request_timeout=3);self.owner_source=owner_source
 def call(self,method,route,body=None):
  with (identity.lease(self.policy)if self.credential_reader is identity.credential else nullcontext(self.credential_reader(self.policy)))as cred:
   return self.client.call(method,PREFIX+route,bearer=cred['token'],body=body)
 def source_call(self,method,route):
  with (identity.lease(self.policy)if self.credential_reader is identity.credential else nullcontext(self.credential_reader(self.policy)))as cred:
   return self.source_client.call(method,PREFIX+route,bearer=cred['token'])
 def source_view(self,*,force=False,require_current=False):
  if self.owner_source is None and self.reader is not committed_document:return SourceView(self.reader,'owner-main',datetime.now(timezone.utc))
  if self.owner_source is None:self.owner_source=ReleaseSource(self.policy,self.source_call,local_reader=self.reader)
  return self.owner_source.view(force=force,require_current=require_current)
 def prepare(self,command):
  payload=command.get('input')if isinstance(command,dict)else None
  if not isinstance(payload,dict) or set(payload)!={'workflow_id','values'}:raise ReleaseError(400,'release_input_invalid','Review a supported product workflow and its declared fields.')
  view=self.source_view();definition=action_definition(self.policy,payload['workflow_id'],reader=view.reader);data=source(self.policy,view.reader);envelope(command,self.policy,definition,data)
  if not selected(self.policy):raise ReleaseError(403,'release_not_selected','Native release submission has not been explicitly selected and reviewed.')
  values=normalize_values(definition,payload['values'],data)
  return {'workflow_id':payload['workflow_id'],'values':values,'platform_revision':data['platform_revision'],'registry_revision':data['registry_revision'],'candidate':data['candidate'].get('candidate',{}),'runtime_state':data['runtime'].get('state'),'dispatch_actor_id':None,'phase':'prepared','run_id':None,'run_url':None,'pull_request_url':None,'branch':None,'merge_commit':None,'desired_state_verified':False,'dispatch_started_at':None}
 def protect(self,spec,cred):
  repo=self.call('GET','')
  if not isinstance(repo,dict)or repo.get('id')!=REPOSITORY_ID or repo.get('full_name')!=REPOSITORY:raise ReleaseError(403,'release_repository_mismatch','The provider repository identity differs from its admitted target.')
  env=self.call('GET','/environments/'+spec['environment']);rules=env.get('protection_rules',[])
  reviewers=[r.get('reviewer',{}).get('id')for rule in rules if rule.get('type')=='required_reviewers'for r in rule.get('reviewers',[])]
  if identity.definition()['identity']['account_id']not in reviewers or cred['bot_id']in reviewers or env.get('deployment_branch_policy',{}).get('protected_branches')is not True:raise ReleaseError(403,'release_approval_gate_missing','The existing protected environment must retain the accountable human reviewer and protected-branch policy.')
 def dispatch(self,record,emit,receipt):
  self.assert_retained(record)
  release=record['release'];spec=SPECS[release['workflow_id']]
  if release.get('dispatch_started_at')is not None or release['phase']!='prepared':return self.reconcile(record,emit,receipt)
  try:view=self.source_view(force=True,require_current=True)
  except SourceChanged as exc:raise ReleaseError(409,'release_workflow_source_changed',str(exc))from None
  except ProfileReadError:raise ReleaseError(503,'release_source_unavailable','Current owner source is unavailable; refresh this original request after restoring its connection.')from None
  if source(self.policy,view.reader)['source_version']!=record['source_version']:raise ReleaseError(409,'release_source_changed','Owner data changed after review. Refresh and review the new record before another request.')
  if not action_definition(self.policy,release['workflow_id'],reader=view.reader)['available']:raise ReleaseError(503,'release_not_commissioned','The reviewed release connection is unavailable; recover this original prepared request after restoring it.')
  cred=self.credential_reader(self.policy);self.protect(spec,cred)
  branch=self.call('GET','/git/ref/heads/main')
  if branch.get('object',{}).get('sha')!=release['platform_revision']:raise ReleaseError(409,'release_source_changed','The owner main revision changed. Refresh and review the new source before submitting again.')
  values=release['values'];inputs={key:value for key,value in values.items()if not key.startswith('check:')}
  if release['workflow_id']=='readiness':inputs['verification_results']=','.join(key[6:]+'='+value for key,value in values.items()if key.startswith('check:'))
  if release['workflow_id']=='promotion':inputs.update({'source_environment':'stage','target_environment':'prod'})
  correlation=record['command']['intent_digest'][7:]
  intent={'schema_version':1,'command_id':record['command']['command_id'],'intent_digest':record['command']['intent_digest'],'operator_id':record['command']['actor_ref'],'platform_revision':release['platform_revision'],'registry_revision':release['registry_revision'],'workflow_id':release['workflow_id'],'inputs_digest':digest(inputs)}
  inputs.update({'console_request_id':correlation,'console_intent':json.dumps(intent,sort_keys=True,separators=(',',':'))})
  release.update({'phase':'dispatching','dispatch_actor_id':cred['bot_id'],'dispatch_started_at':now()});emit(record,'queued','Platform retained the exact release intent before dispatch.');self.store.write(record)
  try:
   response=self.call('POST','/actions/workflows/'+spec['filename']+'/dispatches',{'ref':'main','inputs':inputs})
   if isinstance(response,dict)and type(response.get('workflow_run_id'))is int and response['workflow_run_id']>0:
    release.update({'run_id':response['workflow_run_id'],'run_url':f'https://github.com/{REPOSITORY}/actions/runs/{response["workflow_run_id"]}','phase':'queued'})
   else:release['phase']='uncertain'
  except ProviderHttpError as exc:
   if exc.status_code in {401,403,404,409,422,429}:
    release['phase']='failed';record.update(retryable=False,cancel_available=False,blocker=None,failure={'code':'release-dispatch-rejected','owner':'platform-engineering','detail':'GitHub rejected the original dispatch before starting a workflow. Inspect its connection and reviewed source before a new request.'})
    record['receipt']=receipt(record,'failed','none');emit(record,'failed','GitHub rejected the retained dispatch; no release effect was performed.');self.store.write(record);return record
   release['phase']='uncertain'
  except (IdentityError,OSError,ValueError):release['phase']='uncertain'
  self.store.write(record)
  return self.reconcile(record,emit,receipt)
 def _verify_run(self,record,run):
  rel=record['release'];spec=SPECS[rel['workflow_id']]
  if not isinstance(run,dict)or run.get('id')!=rel['run_id']or run.get('run_attempt')!=1 or run.get('event')!='workflow_dispatch'or run.get('head_sha')!=rel['platform_revision']or run.get('repository',{}).get('id')!=REPOSITORY_ID or run.get('actor',{}).get('id')!=rel['dispatch_actor_id']or str(run.get('path','')).split('@')[0]!='.github/workflows/'+spec['filename']or run.get('display_title')!='Console release '+record['command']['intent_digest'][7:]:raise ReleaseError(409,'release_run_binding_invalid','The original workflow run does not match this reviewed command and dedicated App identity.')
 def _find_run(self,record):
  rel=record['release'];spec=SPECS[rel['workflow_id']];matches=[]
  after=(datetime.fromisoformat(rel['dispatch_started_at'])-timedelta(seconds=120)).isoformat()
  for page in range(1,5):
   result=self.call('GET','/actions/workflows/'+spec['filename']+'/runs?event=workflow_dispatch&per_page=50&page='+str(page)+'&created='+quote('>='+after,safe=''))
   rows=result.get('workflow_runs')
   if not isinstance(rows,list)or len(rows)>50:raise ReleaseError(502,'release_run_read_invalid','Original workflow discovery returned invalid owner data.')
   for run in rows:
    if run.get('display_title')=='Console release '+record['command']['intent_digest'][7:]:matches.append(run)
   if len(rows)<50:break
  if len(matches)>1:raise ReleaseError(409,'release_run_ambiguous','More than one owner run matches the original request. Inspect its original history; no dispatch retry is allowed.')
  if matches:rel.update({'run_id':matches[0]['id'],'run_url':f'https://github.com/{REPOSITORY}/actions/runs/{matches[0]["id"]}'});self._verify_run(record,matches[0]);return matches[0]
  return None
 def _contents(self,path,ref):
  value=self.call('GET','/contents/'+path+'?ref='+quote(ref,safe=''))
  if not isinstance(value,dict)or value.get('encoding')!='base64'or not isinstance(value.get('content'),str)or len(value['content'])>1_000_000:raise ReleaseError(502,'release_readback_invalid','Owner desired-state readback is invalid.')
  return yaml.safe_load(base64.b64decode(value['content'],validate=False))
 def _desired(self,record,ref):
  rel=record['release'];values=rel['values'];kind=rel['workflow_id']
  # Bind original candidate data to its immutable reviewed source, not mutable journal metadata.
  candidate_document=self._contents('environments/stage/release-candidate.yaml',rel['platform_revision']);candidate=candidate_document.get('candidate',{})
  if candidate!=rel['candidate']:raise ReleaseError(409,'release_candidate_binding_invalid','The retained candidate differs from the original immutable owner source.')
  actor=record['command']['actor_ref'].removeprefix('operator:')
  if kind=='runtime':
   doc=self._contents('environments/prod/openclaw-lifecycle.yaml',ref)
   matches=doc.get('state')==values['state']and doc.get('reason')==values['reason']and(doc.get('incidentRef')or'')==values['incident_ref']and doc.get('changedBy')==actor and(not values['operation_note']or doc.get('note')==values['operation_note'])
   if not matches:return False
   resources=self._contents('environments/prod/argocd/kustomization.yaml',ref).get('resources')
   configmap=self._contents('environments/prod/argocd/openclaw-prod-lifecycle-configmap.yaml',ref)
   verification=self._contents('environments/prod/verification.yaml',ref)
   return resources==expected_prod_resources(values['state'])and configmap==lifecycle_configmap_payload(doc)and verification.get('status')==prod_verification_status_for_state(values['state'])
  doc=self._contents('environments/stage/promotion-readiness.yaml'if kind=='readiness'else'environments/prod/versions.yaml',ref)
  if kind=='readiness':
   verification=self._contents('environments/stage/verification.yaml',ref);checks={item.get('id'):item.get('status')for item in verification.get('checks',[])}
   expected={key[6:]:value for key,value in values.items()if key.startswith('check:')}
   return doc.get('status')=='approved'and doc.get('approvedBy')==actor and doc.get('approvedCandidate')==candidate and doc.get('candidateRef')==candidate_ref_for(candidate_document)and verification.get('candidateRef')==candidate_ref_for(candidate_document)and doc.get('verificationRef')==verification_ref_for(verification)and verification.get('verifiedBy')==actor and verification.get('evidenceRef')==values['verification_evidence_ref']and checks==expected and(not values['verification_note']or verification.get('note')==values['verification_note'])and(not values['approval_note']or doc.get('note')==values['approval_note'])
  correct=compute_source_bundle_ref(doc)==candidate.get('sourceBundleRef')and doc.get('gateway',{}).get('image',{}).get('digest')==candidate.get('image',{}).get('digest')
  resources=self._contents('environments/stage/argocd/kustomization.yaml',ref).get('resources')
  if values['suspend_stage_environment']=='true':correct=correct and resources==['suspend-sentinel-configmap.yaml']
  else:correct=correct and isinstance(resources,list)and bool(resources)and resources!=['suspend-sentinel-configmap.yaml']and self._contents('environments/stage/verification.yaml',ref).get('status')=='pending'and self._contents('environments/stage/promotion-readiness.yaml',ref).get('status')=='pending'
  return correct
 def assert_retained(self,record):
  validate_original(record['command'],self.policy)
  if record.get('command_digest')!=digest(record['command']):raise ReleaseError(409,'release_journal_binding_invalid','The original command journal binding is invalid.')
  if record['release']['values']!={key:record['command']['input']['values'].get(key,'').strip()for key in record['release']['values']} or record['command']['input']['workflow_id']!=record['release']['workflow_id']or record['command']['subject']['expected_source_version']!=f"products:{record['release']['registry_revision']}:{record['release']['platform_revision']}":raise ReleaseError(409,'release_journal_binding_invalid','The original release parameters differ from their canonical command.')
 def reconcile(self,record,emit,receipt):
  self.assert_retained(record)
  if record['state']in {'succeeded','failed','cancelled'}:return record
  rel=record['release'];spec=SPECS[rel['workflow_id']];record.update({'retryable':False,'cancel_available':False,'blocker':None,'failure':None})
  run=self.call('GET','/actions/runs/'+str(rel['run_id']))if rel['run_id']else self._find_run(record)
  if run is None:
   rel['phase']='uncertain';record['blocker']={'code':'release-dispatch-uncertain','owner':'platform-engineering','reason':'Original dispatch acknowledgement is unknown. Refresh this original request; it will not be redispatched.','supported_dispositions':['remove','defer'],'next_action':'reconcile-original-release'};emit(record,'blocked','The original workflow has not yet been recovered; dispatch retry is disabled.');self.store.write(record);return record
  self._verify_run(record,run);record['safe_log_ref']=rel['run_url'];status=run.get('status');conclusion=run.get('conclusion')
  if status!='completed':
   rel['phase']='awaiting-approval'if status in {'waiting','pending'}else'in-progress'if status=='in_progress'else'queued';record['cancel_available']=True
   emit(record,'queued'if rel['phase']in {'queued','awaiting-approval'}else'running','Owner workflow: '+rel['phase']+'. Protected approval remains with the human reviewer.');self.store.write(record);return record
  branch=spec['branch']+(rel['values']['state']+'-'if rel['workflow_id']=='runtime'else'')+str(rel['run_id']);rel['branch']=branch
  pulls=self.call('GET','/pulls?state=all&base=main&head='+quote('mfshaf7:'+branch,safe='')+'&per_page=10')
  if not isinstance(pulls,list)or len(pulls)>10:raise ReleaseError(502,'release_review_read_invalid','Owner source-review readback is invalid.')
  matching=[p for p in pulls if p.get('head',{}).get('ref')==branch and p.get('base',{}).get('ref')=='main'and p.get('base',{}).get('repo',{}).get('id')==REPOSITORY_ID and p.get('head',{}).get('repo',{}).get('id')==REPOSITORY_ID]
  if len(matching)>1:raise ReleaseError(409,'release_review_ambiguous','The original release branch has ambiguous source reviews.')
  pull=matching[0]if matching else None
  if pull:
   rel['pull_request_url']=f'https://github.com/{REPOSITORY}/pull/{pull["number"]}'
   if pull.get('merged_at'):
    sha=pull.get('merge_commit_sha');head=pull.get('head',{}).get('sha')
    if not isinstance(sha,str)or not re.fullmatch('[0-9a-f]{40}',sha)or not isinstance(head,str)or not re.fullmatch('[0-9a-f]{40}',head):raise ReleaseError(502,'release_merge_read_invalid','Owner merge identity is invalid.')
    compare=self.call('GET','/compare/'+sha+'...main')
    if compare.get('merge_base_commit',{}).get('sha')!=sha or not self._desired(record,sha):raise ReleaseError(409,'release_effect_unverified','The approved merge and exact desired-state effect are not proven on owner main.')
    rel.update({'phase':'applied','merge_commit':sha,'desired_state_verified':True});record['receipt']=receipt(record,'succeeded','verified');emit(record,'succeeded','The reviewed source change is merged and its exact desired-state effect is verified. Observed runtime health remains separate.')
   elif pull.get('state')=='closed':
    rel['phase']='failed';record['failure']={'code':'release-review-rejected','owner':'operator','detail':'The original source review was closed without merge.'};record['receipt']=receipt(record,'failed','partial');emit(record,'failed','The original source change was not merged.')
   else:rel['phase']='awaiting-review';emit(record,'running','The source change awaits human review and merge; workflow completion is not release completion.')
  elif self._retained_branch(branch):
   rel['phase']='awaiting-review';record['blocker']={'code':'release-source-branch-retained','owner':'operator','reason':'The original source branch exists but its review is not yet discovered. Open its comparison, complete the source review and refresh this original operation.','supported_dispositions':['remove','defer'],'next_action':'inspect-owner-source-review'};emit(record,'blocked','The original source branch is retained; workflow failure does not erase its effects or create a replacement request.')
  elif conclusion=='success' and self._desired(record,'main'):
   rel.update({'phase':'no-change','desired_state_verified':True});record['receipt']=receipt(record,'succeeded','none');emit(record,'succeeded','The owner workflow needed no source change and exact desired state is already recorded. This is not observed health.')
  elif conclusion in {'cancelled','failure','timed_out','action_required','startup_failure','stale'}:
   state='cancelled'if conclusion=='cancelled'else'failed';rel['phase']=state;record['failure']=None if state=='cancelled'else{'code':'release-workflow-failed','owner':'platform-engineering','detail':'The original workflow did not complete; inspect its run and retained source effects.'};record['receipt']=receipt(record,state,'partial');emit(record,state,'The original GitHub run ended without a proven completed source change. Inspect retained effects before another request.')
  else:
   rel['phase']='awaiting-review';record['blocker']={'code':'release-review-not-discovered','owner':'operator','reason':'The workflow ended but its source review is not yet discovered. Inspect the original run/branch and refresh it.','supported_dispositions':['remove','defer'],'next_action':'inspect-owner-source-review'};emit(record,'blocked','The original source review is not yet proven; no replacement workflow is dispatched.')
  if rel['phase']in {'applied','no-change'}and self.owner_source is not None:self.owner_source.invalidate()
  self.store.write(record);return record
 def _retained_branch(self,branch):
  try:return bool(self.call('GET','/git/ref/heads/'+quote(branch,safe='')).get('object',{}).get('sha'))
  except ProviderHttpError as exc:
   if exc.status_code==404:return False
   raise
 def cancel(self,record,control,emit,receipt):
  self.reconcile(record,emit,receipt)
  if not record.get('cancel_available')or not record['release']['run_id']:raise ReleaseError(409,'release_cancel_unavailable','Only this exact in-flight GitHub run can be cancelled. Source effects are retained.')
  controls=record.setdefault('controls',{});key=control['idempotency_key'];value=digest(control)
  if key in controls and controls[key]!=value:raise ReleaseError(409,'release_control_conflict','Cancellation identity is already bound to another intent.')
  if key not in controls:
   controls[key]=value;self.store.write(record);self.call('POST','/actions/runs/'+str(record['release']['run_id'])+'/cancel',{})
  return self.reconcile(record,emit,receipt)

def public_evidence(record):
 rel=record['release'];return {'schema_version':1,'workflow_id':rel['workflow_id'],'phase':rel['phase'],'run_id':rel['run_id'],'run_url':rel['run_url'],'pull_request_url':rel['pull_request_url'],'branch':rel['branch'],'merge_commit':rel['merge_commit'],'desired_state_verified':rel['desired_state_verified']}
