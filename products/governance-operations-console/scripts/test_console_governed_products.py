import copy,unittest
from datetime import datetime,timezone
import console_governed_products as products
from console_dev_integration_profiles import ProfileReadError
A='a'*40;B='b'*40
class ProductReadTests(unittest.TestCase):
 def setUp(self):
  self.registry={'products':{name:{'maturity':maturity,'platform_owner':'platform-engineering','security_owner':'security-architecture','highest_real_endpoint':endpoint,'stage_supported':stage,'governed_prod_promotion':stage,'posture':'active'} for name,maturity,endpoint,stage in [('openclaw','fully-governed','governed-prod',True),('owner-app','owner-managed','owner-managed-source',False),('openproject','platform-integrated','platform-integrated-runtime',False)]}}
  self.calls=[]
 def reader(self,workspace,owner,relative):
  self.calls.append((owner,relative))
  if owner=='workspace-governance':return copy.deepcopy(self.registry),A
  if relative.startswith('.github/workflows/'):return {'jobs':{'review':{}}},B
  if relative.endswith('openclaw-lifecycle.yaml'):return {'product':'openclaw','state':'suspended','changedAt':'2026-01-01T00:00:00Z'},B
  return {'product':'openclaw','status':'pending','candidateRef':{'sourceBundleRef':'bundle-one','imageDigest':'sha256:'+'c'*64},'evidenceRef':None},B
 def read(self,query=None,reader=None):return products.read_products({'workspace_root':'/synthetic'},query=query,reader=reader or self.reader,observed=datetime(2026,1,1,tzinfo=timezone.utc))
 def test_registry_visibility_and_owner_routes(self):
  result=self.read();self.assertEqual(len(result['products']),3)
  source=next(p for p in result['products'] if p['product_id']=='owner-app');self.assertEqual(source['execution'],'unsupported');self.assertEqual(source['workflows'],[]);self.assertIsNone(source['runtime'])
  claw=next(p for p in result['products'] if p['product_id']=='openclaw');self.assertEqual(len(claw['workflows']),3);self.assertEqual(claw['runtime']['state'],'suspended');self.assertIsNone(claw['evidence'][0]['recorded_at']);self.assertTrue(all('/blob/'+B+'/' in e['url'] for e in claw['evidence']))
 def test_bounded_filters(self):
  result=self.read({'limit':'1','offset':'1'});self.assertEqual(result['page']['total'],3);self.assertEqual(len(result['products']),1)
  result=self.read({'maturity':'owner-managed'});self.assertEqual([p['product_id'] for p in result['products']],['owner-app'])
  for query in [{'limit':'200'},{'offset':'-1'},{'path':'/etc/passwd'},{'endpoint':'anything'}]:
   with self.assertRaises(ProfileReadError):self.read(query)
 def test_drift_and_identity_fail_closed(self):
  def drift(w,o,p):
   doc,rev=self.reader(w,o,p);return doc,'d'*40 if p.endswith('verification.yaml') else rev
  with self.assertRaises(ProfileReadError):self.read(reader=drift)
  def mismatch(w,o,p):
   doc,rev=self.reader(w,o,p)
   if p.endswith('verification.yaml'):doc['product']='another-product'
   return doc,rev
  with self.assertRaises(ProfileReadError):self.read(reader=mismatch)
 def test_unsupported_does_not_adopt_openclaw(self):
  result=self.read({'product_id':'owner-app'});self.assertEqual(result['products'][0]['evidence'],[]);self.assertTrue(all(p in {'contracts/products.yaml','environments/prod/openclaw-lifecycle.yaml'} for _,p in self.calls))
if __name__=='__main__':unittest.main()
