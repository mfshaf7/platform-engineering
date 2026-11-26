import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const proof = JSON.parse(readFileSync(0,"utf8"));
const load = name => import(path.join(proof.broker,"src",name));
const { canonicalDigest } = await load("delivery-art/canonical-json.js");
const { captureSavedProjectSource } = await load("project-runtime/saved-source.js");
const { createSavedProjectRuntimeCommands } = await load("project-runtime/commands.js");
const { createPlatformOperationProviderClient } = await load("platform-operation/provider-client.js");
const digest = value => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const changeSet = {session_id:"proof:paired-project",base_commit:proof.base,operations:[
  {path:"app/version.txt",action:"replace",expected_digest:digest("base\n"),content:proof.version+"\n"},
]};
const saved = { revision:`saved:paired:${proof.version}`, change_set:changeSet };
const source = { kind:"saved-draft",base_commit:proof.base,session_id:changeSet.session_id,revision:saved.revision,
  change_set_digest:canonicalDigest(changeSet) };
const selection = { project_ref:proof.project,subject:proof.subject,scope:proof.scope,setup:proof.setup,source };
const api = createPlatformOperationProviderClient({allowHttp:true,baseUrl:proof.url,callerId:"isolated-broker",callerSecret:proof.secret});
const callerId="origin:isolated",operatorId="operator:paired-proof";
let dispatches=0;
const broker=createSavedProjectRuntimeCommands({ root:proof.journal, authority:{
  resolve:async()=>selection,
  capture:async({commandId})=>captureSavedProjectSource({repository:proof.repository,snapshotRoot:proof.snapshots,
    scope:proof.scope,source,setup:proof.setup,commandId,saved,limits:{max_files:32,max_bytes:65536,max_tree_bytes:65536}}),
  withCurrentScope:async (_binding,effect)=>effect(),
}, platform:{submit:async binding=>{dispatches++; return api.submitProjectRuntime(binding);},read:api.readProjectRuntime}});
const control=proof.action!=="run";
let acknowledgement, observation;
if (!control) {
  const commandId=`run:paired:${proof.version}`;
  const input={callerId,operatorId,commandId};
  acknowledgement=await broker.accept({...input,request:{
    command_id:commandId,project_ref:proof.project,expected_revision:proof.expected,
    source_revision:source.revision,source_digest:source.change_set_digest,configuration_revision:proof.setup.configuration_revision,
  }});
  assert.equal(dispatches,0);
  observation=(await broker.advance(input)).observation;
  const expected=proof.runState ?? (proof.version==="fails"?"failed":"ready");
  const deadline=Date.now()+240_000;
  while (observation?.state!==expected && Date.now()<deadline) {
    if (observation?.state==="failed") break;
    await sleep(1500);
    const value=await broker.advance(input);
    assert.deepEqual(value.acknowledgement,acknowledgement);
    observation=value.observation;
  }
  assert.equal(dispatches,1);
  if (observation?.state!==expected) throw Error(JSON.stringify({state:observation?.state,accepted:acknowledgement.operation_id}));
} else {
  const commandId=`control:${proof.action}`;
  const operationId="project-operation:"+digest(`${proof.project}:${commandId}`).slice(7);
  const input={scope:proof.scope,command_id:commandId,operation_id:operationId};
  const accepted=await api.controlProjectRuntime({...input,action:proof.action,expected_revision:proof.expected});
  acknowledgement={command_id:commandId,operation_id:accepted.operation_id};
  const expected=proof.action==="stop"?"stopped":"ready";
  observation=accepted;
  const deadline=Date.now()+145_000;
  while (observation.state!==expected && Date.now()<deadline) {
    if (observation.state==="failed") break;
    await sleep(1500);
    observation=await api.readProjectRuntime(input);
  }
  assert.equal(observation.state,expected,JSON.stringify(observation));
}
const confirmed=await api.readProjectRuntime({scope:proof.scope,command_id:acknowledgement.command_id,operation_id:acknowledgement.operation_id});
assert.equal(confirmed.state,observation.state);
assert.equal(confirmed.configuration_revision,proof.setup.configuration_revision);
if (!control) assert.equal(confirmed.manifest_digest,acknowledgement.snapshot.manifest_digest);
console.log(JSON.stringify({acknowledgement,confirmed,dispatches}));
