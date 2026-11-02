"""Dedicated Platform release identity; reuses existing App/Vault custody primitives."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib,json,os,stat,subprocess,sys,tempfile,fcntl,re
from pathlib import Path
from types import SimpleNamespace
import yaml
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from repository_provider_identity import ProviderClient,ProviderHttpError,IdentityError,create_app_jwt,verify_installation,verify_token
PERMISSIONS={'metadata':'read','contents':'read','actions':'write','pull_requests':'read'}
DEFAULT_CONTRACT=ROOT/'security/governed-release-identity.yaml'

def digest(value):return 'sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def selection_accepted(policy):
 selection=policy.get('governed_release',{})
 return selection.get('permitted') is True and selection.get('security_accepted') is True and selection.get('security_review_ref')=='docs/reviews/components/2026-11-02-console-native-governed-release.md' and bool(re.fullmatch('sha256:[0-9a-f]{64}',str(selection.get('security_decision_digest')))) and selection['security_decision_digest']==policy.get('security',{}).get('decision_digest')

def resolve_selection(policy,decision,review):
 """Derive authority from the existing external exact-source decision.

 No decision digest is hand-pinned into tracked Platform source. Missing native
 acceptance withholds this optional connection without blocking core startup.
 """
 selection=policy.get('governed_release',{})
 result={**selection,'security_accepted':False,'security_decision_digest':None}
 if selection.get('permitted')is not True or decision.get('status')!='accepted':return result
 try:
  if not review.startswith('---\n'):return result
  header=yaml.safe_load(review.split('---',2)[1])
  acceptance=header.get('native_release_activation',{})
  if set(acceptance)!={'status','gate_id','reviewed_revisions','reviewed_platform_tree'}or acceptance['status']!='accepted'or acceptance['gate_id']!=decision['gate_id']or acceptance['reviewed_revisions']!=decision['reviewed_revisions']or acceptance['reviewed_platform_tree']!=decision['reviewed_trees']['platform-engineering']:return result
  result.update(security_accepted=True,security_decision_digest=digest(decision))
 except (ValueError,KeyError,TypeError,AttributeError,yaml.YAMLError):pass
 return result
def definition(path=DEFAULT_CONTRACT):
 value=yaml.safe_load(Path(path).read_text());identity=value.get('identity',{}) if isinstance(value,dict) else {}
 if value.get('schema_version')!=1 or identity.get('id')!='governed-release-dispatch-github-app-v1' or identity.get('api_base_url')!='https://api.github.com' or identity.get('api_version')!='2026-03-10' or identity.get('required_permissions')!=PERMISSIONS or identity.get('repository_selection')!='selected' or identity.get('events')!=[]:
  raise IdentityError('Release identity definition does not match its finite authority.')
 if identity.get('repository')!='mfshaf7/platform-engineering' or identity.get('repository_id')!=1195328534 or identity.get('account_id')!=244414185 or identity.get('app_slug')!='mfshaf7-governed-releases':raise IdentityError('Release identity target is not admitted.')
 if value.get('execution',{}).get('automatic_environment_approval') is not False or value['execution'].get('automatic_source_merge') is not False or value['execution'].get('ambiguous_dispatch_retry') is not False:raise IdentityError('Release identity must retain approvals and uncertain-write recovery.')
 if value.get('secret_custody',{}).get('path')!='components/governance-operations-console/governed-release-dispatch' or value['secret_custody'].get('property')!='privateKey':raise IdentityError('Release custody must use its separate Vault path.')
 return value

def bundle_path(policy):return Path(policy['runtime_state_root'])/'governed-release/credential.json'
def private_json(path):
 path=Path(path)
 if path.is_symlink():raise IdentityError('Release credential bundle must be a regular private file.')
 info=path.stat()
 if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077 or info.st_size>32768:raise IdentityError('Release credential bundle permissions or bounds are invalid.')
 return json.loads(path.read_text())
def credential(policy,*,now=None):
 contract=definition();value=private_json(bundle_path(policy));identity=contract['identity'];now=now or datetime.now(timezone.utc)
 expected={'schema_version','identity_id','app_id','installation_id','repository_id','bot_id','bot_login','permissions','expires_at','contract_digest','security_digest','token','token_digest'}
 if set(value)!=expected or value['identity_id']!=identity['id'] or value['repository_id']!=identity['repository_id'] or value['permissions']!=PERMISSIONS or value['contract_digest']!=digest(contract) or value['security_digest']!=policy.get('security',{}).get('decision_digest'):raise IdentityError('Release credential binding is stale or differs from its contract.')
 if any(type(value[k]) is not int or value[k]<=0 for k in ('app_id','installation_id','repository_id','bot_id')) or value['bot_login']!=identity['app_slug']+'[bot]':raise IdentityError('Release App identity binding is invalid.')
 if not isinstance(value['token'],str) or len(value['token'])<20 or 'sha256:'+hashlib.sha256(value['token'].encode()).hexdigest()!=value['token_digest']:raise IdentityError('Release credential digest is invalid.')
 remaining=(datetime.fromisoformat(value['expires_at'].replace('Z','+00:00'))-now).total_seconds()
 if not 120<remaining<=3660:raise IdentityError('Release credential is expired or outside its admitted lifetime.')
 return value

def atomic_json(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 if path.parent.is_symlink() or path.is_symlink():raise IdentityError('Release credential custody cannot use symlinks.')
 os.chmod(path.parent,0o700);fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.release-')
 try:
  with os.fdopen(fd,'w') as stream:os.fchmod(stream.fileno(),0o600);json.dump(value,stream,separators=(',',':'),sort_keys=True);stream.flush();os.fsync(stream.fileno())
  os.replace(temp,path);parent=os.open(path.parent,os.O_DIRECTORY);os.fsync(parent);os.close(parent)
 finally:
  if os.path.exists(temp):os.unlink(temp)

@contextmanager
def vault_key(contract):
 custody=contract['secret_custody']
 result=subprocess.run(['vault','kv','get','-mount=kv',f"-field={custody['property']}",custody['path']],capture_output=True,text=True,check=False,timeout=30)
 if result.returncode or 'PRIVATE KEY' not in result.stdout:raise IdentityError('Dedicated release key is unavailable from Platform Vault custody.')
 with tempfile.TemporaryDirectory(prefix='platform-release-key-') as directory:
  path=Path(directory)/'key.pem';path.write_text(result.stdout);os.chmod(path,0o600);yield path

@contextmanager
def custody_lock(policy, *, shared=False):
 root=bundle_path(policy).parent;root.mkdir(parents=True,exist_ok=True,mode=0o700)
 if root.is_symlink():raise IdentityError('Release custody must be a private regular directory.')
 descriptor=os.open(root/'credential.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  os.fchmod(descriptor,0o600);fcntl.flock(descriptor,fcntl.LOCK_SH if shared else fcntl.LOCK_EX);yield
 finally:fcntl.flock(descriptor,fcntl.LOCK_UN);os.close(descriptor)

@contextmanager
def lease(policy):
 with custody_lock(policy,shared=True):yield credential(policy)

def commission(policy,app_id,installation_id,*,client=None,key_context=None):
 with custody_lock(policy):return _commission(policy,app_id,installation_id,client=client,key_context=key_context)

def _commission(policy,app_id,installation_id,*,client=None,key_context=None):
 contract=definition();identity=contract['identity'];client=client or ProviderClient(identity['api_base_url'],api_version=identity['api_version'])
 if not selection_accepted(policy):raise IdentityError('Release commissioning requires the accepted native boundary in the existing resolved Platform policy.')
 with (key_context(contract) if key_context else vault_key(contract)) as key:
  jwt=create_app_jwt(app_id,key);app=client.authenticated_app(jwt);owner=app.get('owner')or{}
  if app.get('id')!=app_id or app.get('slug')!=identity['app_slug'] or owner.get('id')!=identity['account_id'] or owner.get('login')!=identity['account_login']:raise IdentityError('Dedicated release App identity does not match its contract.')
  installation=client.installation(installation_id,jwt)
  verify_installation(installation,app_id=app_id,installation_id=installation_id,required_permissions=PERMISSIONS)
  if (installation.get('account')or{}).get('id')!=identity['account_id']or(installation.get('account')or{}).get('login')!=identity['account_login']:raise IdentityError('Dedicated release installation account differs from its contract.')
  # Inspect the installation's whole selected inventory with Metadata read only;
  # a one-repo runtime token alone would hide a broader App installation.
  inspection=client.issue_token(installation_id,jwt,None,{'metadata':'read'})
  try:
   inventory=verify_token(inspection,client.accessible_repositories(inspection.token),[identity['repository']],SimpleNamespace(required_permissions={'metadata':'read'},maximum_token_lifetime_seconds=3600))
   if len(inventory)!=1 or inventory[0].provider_repository_id!=identity['repository_id']:raise IdentityError('Dedicated release installation includes an unadmitted repository.')
  finally:client.revoke_token(inspection.token)
  if bundle_path(policy).exists():
   previous=private_json(bundle_path(policy))
   if previous.get('identity_id')!=identity['id']or previous.get('repository_id')!=identity['repository_id']or previous.get('permissions')!=PERMISSIONS:raise IdentityError('The previous release lease has an invalid binding.')
   # Lease users hold the shared custody lock. Retire the previous token before
   # issuing a replacement so explicit revocation has no overlapping old lease.
   try:client.revoke_token(previous['token'])
   except ProviderHttpError as exc:
    if exc.status_code!=401:raise
   previous['expires_at']=datetime.now(timezone.utc).isoformat();atomic_json(bundle_path(policy),previous)
  token=client.issue_token(installation_id,jwt,['platform-engineering'],PERMISSIONS)
  try:
   repos=verify_token(token,client.accessible_repositories(token.token),[identity['repository']],SimpleNamespace(required_permissions=PERMISSIONS,maximum_token_lifetime_seconds=3600))
   if len(repos)!=1 or repos[0].provider_repository_id!=identity['repository_id']:raise IdentityError('Release token repository identity differs from the contract.')
   bot=client.call('GET','/users/'+identity['app_slug']+'%5Bbot%5D',bearer=token.token)
   if not isinstance(bot,dict) or type(bot.get('id'))is not int or bot.get('login')!=identity['app_slug']+'[bot]':raise IdentityError('Release App actor readback is invalid.')
   bundle={'schema_version':1,'identity_id':identity['id'],'app_id':app_id,'installation_id':installation_id,'repository_id':identity['repository_id'],'bot_id':bot['id'],'bot_login':bot['login'],'permissions':PERMISSIONS,'expires_at':token.expires_at,'contract_digest':digest(contract),'security_digest':policy['security']['decision_digest'],'token':token.token,'token_digest':'sha256:'+hashlib.sha256(token.token.encode()).hexdigest()}
   atomic_json(bundle_path(policy),bundle)
  except Exception:
   try:client.revoke_token(token.token)
   except Exception:pass
   raise
 return {key:value for key,value in bundle.items() if key!='token'}

def maintain(policy):
 if not selection_accepted(policy):return {'state':'not-selected'}
 current=private_json(bundle_path(policy));remaining=(datetime.fromisoformat(current['expires_at'].replace('Z','+00:00'))-datetime.now(timezone.utc)).total_seconds()
 if remaining>900:
  credential(policy);return {'state':'current','expires_at':current['expires_at']}
 return {'state':'renewed',**commission(policy,current['app_id'],current['installation_id'])}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['validate','status','commission','refresh','revoke']);parser.add_argument('--policy',type=Path,required=True);parser.add_argument('--app-id',type=int);parser.add_argument('--installation-id',type=int);args=parser.parse_args()
 policy=yaml.safe_load(args.policy.read_text())
 try:
  if args.action=='validate':result={'state':'definition-valid','contract_digest':digest(definition())}
  elif args.action=='status':result={k:v for k,v in credential(policy).items() if k!='token'}
  elif args.action=='commission':
   if not args.app_id or not args.installation_id:raise IdentityError('Dedicated App and installation IDs are required.')
   result=commission(policy,args.app_id,args.installation_id)
  elif args.action=='refresh':result=maintain(policy)
  else:
   with custody_lock(policy):
    value=private_json(bundle_path(policy))
    try:ProviderClient('https://api.github.com',api_version='2026-03-10').revoke_token(value['token'])
    except ProviderHttpError as exc:
     if exc.status_code!=401:raise
    bundle_path(policy).unlink()
   result={'state':'revoked'}
  print(json.dumps(result,sort_keys=True));return 0
 except (IdentityError,OSError,ValueError,KeyError,subprocess.SubprocessError):print(json.dumps({'state':'unavailable','error':'Dedicated release identity is unavailable; inspect its Platform custody and reviewed selection.'}));return 1
if __name__=='__main__':raise SystemExit(main())
