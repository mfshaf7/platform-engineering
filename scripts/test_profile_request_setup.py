import copy
import sys
import unittest
import json
import tempfile
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dev-integration/profiles/governed-ai-gateway/runtime'))
from profile_request_setup import profile_request_options
from model_configuration import ConfigurationError

class ProfileRequestSetupTests(unittest.TestCase):
    def profile(self):
        return {'environment':'dev-integration','purpose':'planning-assist','allowed_callers':['service/planning'],
                'provider':'private-provider-must-not-leak','task_contracts':{'planning':{
                'instruction_owner_repo':'service','provider_output_schema':{'repo':'platform-engineering','path':'security/schemas/planning.json'},
                'provider_output_schema_digest':'sha256:'+'a'*64,'provider_output_schema_document':{'private':'not projected'}}}}
    def test_uses_owner_contracts_and_only_admitted_tasks(self):
        profiles={'planning-v1':self.profile()}
        self.assertEqual(profile_request_options(profiles,set())['workflows'],[])
        row=profile_request_options(profiles,{'planning-v1/planning'})['workflows'][0]
        self.assertEqual(row['registered_callers'],[{'caller_id':'service/planning','owner_repo':'service'}])
        self.assertEqual(row['output_schema_ref']['version'],'sha256:'+'a'*64)
        self.assertNotIn('private',str(row));self.assertNotIn('provider',row)
        self.assertEqual(row['environments'],['dev-integration'])
    def test_setup_changes_bind_schema_but_not_provider_selection(self):
        profile=self.profile();before=profile_request_options({'planning-v1':profile},{'planning-v1/planning'})['workflows'][0]['setup_digest']
        profile['provider']='another-provider'
        self.assertEqual(before,profile_request_options({'planning-v1':profile},{'planning-v1/planning'})['workflows'][0]['setup_digest'])
        profile['task_contracts']['planning']['provider_output_schema_digest']='sha256:'+'b'*64
        self.assertNotEqual(before,profile_request_options({'planning-v1':profile},{'planning-v1/planning'})['workflows'][0]['setup_digest'])
    def test_missing_caller_binding_fails_instead_of_inventing_one(self):
        for callers in [[],['opaque-caller']]:
            profile=self.profile();profile['allowed_callers']=callers
            with self.assertRaises(ConfigurationError):profile_request_options({'planning-v1':profile},{'planning-v1/planning'})

class ProfileRequestHttpTests(unittest.TestCase):
    def test_catalogue_uses_the_existing_management_authentication(self):
        from gateway_app import Handler
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'token';token.write_text('synthetic-token')
            runtime=SimpleNamespace(profiles={'planning-v1':ProfileRequestSetupTests().profile()},management=SimpleNamespace(authority={'token_file':str(token),'caller_id':'service','operator_id':'operator:sample'},configuration=SimpleNamespace(tasks={'planning-v1/planning'})))
            class TestHandler(Handler):
                def log_message(self,*args): pass
            TestHandler.runtime=runtime
            server=ThreadingHTTPServer(('127.0.0.1',0),TestHandler)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:
                url=f'http://127.0.0.1:{server.server_port}/v1/model-management/profile-request-options'
                for headers in [{},{'Authorization':'Bearer synthetic-token','X-Platform-Caller':'service','X-Platform-Operator':'operator:other'}]:
                    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=2)
                    self.assertEqual(error.exception.code,403)
                headers={'Authorization':'Bearer synthetic-token','X-Platform-Caller':'service','X-Platform-Operator':'operator:sample'}
                value=json.load(urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=2))
                self.assertEqual(value['workflows'][0]['workflow_id'],'planning-v1/planning')
                self.assertNotIn('token',str(value));self.assertNotIn('private',str(value))
            finally:server.shutdown();worker.join();server.server_close()

if __name__=='__main__':unittest.main()
