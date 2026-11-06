"""Finite Console adapter for the existing Platform profile lifecycle.

Preparation reads source contracts, never the AI gateway. Execution accepts a
real OOS request identity, not a browser-supplied target policy or shell command.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, HTTPRedirectHandler, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import model_profile_lifecycle as native

INTENTS = {"create", "amend", "activate", "suspend", "retire", "exception"}
ENVIRONMENT = "dev-integration"


class ProfileError(RuntimeError):
    pass


def digest(value):
    return native.digest_value(value)


def utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def prepare(repo: Path, body: dict, *, workspace: Path | None = None):
    if not isinstance(body, dict) or set(body) != {"request_id", "intent", "profile_id", "environment", "changes"}:
        raise ProfileError("Choose a profile action and review its current settings.")
    if subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip() or subprocess.check_output(['git','-C',str(repo),'branch','--show-current'],text=True).strip()!='main':
        raise ProfileError('The current Platform policy must come from clean accepted main before preparing a request.')
    intent, profile_id = body["intent"], body["profile_id"]
    if intent not in INTENTS or body["environment"] != ENVIRONMENT or not re.fullmatch(r"model-profile-request:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", body["request_id"]):
        raise ProfileError("This installation supports profile changes in dev-integration only.")
    registry = native.read_yaml(repo / native.REGISTRY)
    profiles = registry["model_profiles"]
    if not isinstance(profile_id, str) or profile_id not in profiles:
        raise ProfileError("The selected profile is no longer present. Refresh the profile list.")
    current = profiles[profile_id]
    if current["status"] == "retired":
        raise ProfileError("Retired profiles retain their history and cannot be changed. Create a replacement instead.")
    if ENVIRONMENT not in current["selected_binding_by_environment"]:
        raise ProfileError("The profile has no reviewed binding for this environment.")
    changes = body["changes"]
    if not isinstance(changes, dict) or set(changes) - {"allowed_data_scope", "runtime_limits", "display_name"} or intent not in {"amend", "create", "exception"} and changes:
        raise ProfileError("Only a policy amendment, new profile or exception can change the listed operating limits.")
    target = copy.deepcopy(current)
    if intent == "create":
        target["capability_id"] = current.get("capability_id", profile_id)
        target["display_name"] = current.get("display_name", profile_id) + " copy"
    if "display_name" in changes:
        name = changes["display_name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 160 or any(ord(c) < 32 for c in name):
            raise ProfileError("Use a profile name of at most 160 characters.")
        target["display_name"] = name.strip()
    if "allowed_data_scope" in changes:
        scope = changes["allowed_data_scope"]
        if not isinstance(scope, list) or not 1 <= len(scope) <= 20 or any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in scope):
            raise ProfileError("Describe the allowed input in one to twenty short rules.")
        target["allowed_data_scope"] = scope
    if "runtime_limits" in changes:
        limits = changes["runtime_limits"]
        bounds = {"max_request_bytes": (1024, 1000000), "max_output_tokens": (1, 32768), "timeout_seconds": (1, 300), "retry_count": (0, 3), "max_concurrency": (1, 8)}
        if not isinstance(limits, dict) or set(limits) - set(bounds):
            raise ProfileError("Choose one of the existing operating limits.")
        for key, value in limits.items():
            if type(value) is not int or not bounds[key][0] <= value <= bounds[key][1]:
                raise ProfileError("An operating limit is outside the supported range.")
        target["runtime_limits"].update(limits)
    assigned_id = "purpose-" + hashlib.sha256(body["request_id"].encode()).hexdigest()[:24] if intent == "create" else profile_id
    if intent in {"activate", "suspend", "retire", "exception"} and current["status"] == {"activate": "active", "suspend": "suspended", "retire": "retired", "exception": "exception"}[intent]:
        raise ProfileError("The profile already has the requested state.")
    target["status"] = {"create": "suspended", "amend": "suspended", "activate": "active", "exception": "exception"}.get(intent, current["status"])
    for binding in target["bindings"].values():
        if binding["status"] != "retired":
            binding["status"] = "active" if intent == "activate" else "selected-not-active"
    if intent == "activate":
        selected = target["bindings"][target["selected_binding_by_environment"][ENVIRONMENT]]
        if selected["status"] == "retired":
            raise ProfileError("The selected model binding is retired. Amend the profile first.")
    target = None if intent in {"suspend", "retire"} else target
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    source = native.source_state(repo, source_version=head)
    output = current["provider_output_schema_ref"]
    # Resolve only the owner-recorded schema, never a browser path.
    output_root = repo if output["repo"] == "platform-engineering" else (workspace or repo.parent) / output["repo"]
    output_path = (output_root / output["path"]).resolve()
    if not output_path.is_relative_to(output_root.resolve()) or not output_path.is_file():
        raise ProfileError("The output contract is unavailable from its recorded owner.")
    callers = [{"caller_id": caller, "owner_repo": caller.split("/", 1)[0]} for caller in current["allowed_callers"]]
    if any("/" not in row["caller_id"] for row in callers):
        raise ProfileError("The profile has an unresolved workflow registration.")
    candidate = {"profile_id": assigned_id, "intent": intent, "expected_sources": source, "target_profile": target,
                 "activation_environment": ENVIRONMENT if intent == "activate" else None}
    candidate["candidate_digest"] = digest(candidate)
    documents = [native.read_yaml(repo / path) for path in (native.REGISTRY, native.ACCESS_PLANE, native.RUNTIME_ASSIST)]
    native.mutate_sources(*documents, {**candidate, "decision_id": "platform-model-profile-decision:preparation"})
    native.validate_candidate(repo, *(native.render_yaml(document) for document in documents))
    changes_for_review=[]
    if target:
        if target['allowed_data_scope']!=current['allowed_data_scope']:
            changes_for_review.append({'field':'allowed_data_scope','label':'Allowed input','before':current['allowed_data_scope'],'after':target['allowed_data_scope']})
        labels={'max_request_bytes':'Request size limit (bytes)','max_output_tokens':'Response token limit','timeout_seconds':'Time limit (seconds)','retry_count':'Retries after failure','max_concurrency':'Simultaneous requests'}
        for key,label in labels.items():
            if target['runtime_limits'].get(key)!=current['runtime_limits'].get(key):changes_for_review.append({'field':key,'label':label,'before':current['runtime_limits'].get(key),'after':target['runtime_limits'].get(key)})
    return {"schema_version": 1, "preparation_digest": digest({"input": body, "candidate": candidate}), "candidate": candidate,
            "profile_id": profile_id, "intent": intent, "current_state": 'not created' if intent=='create' else current["status"],
            "result_state": {"suspend": "suspended", "retire": "retired"}.get(intent, (target or {}).get("status")),
            "affected_workflows": current["allowed_callers"], "security_acceptance_required": intent in {"activate", "exception"},"policy_changes":changes_for_review,"can_submit":intent!='amend' or bool(changes_for_review),
            "impact": "Creates a separate suspended profile using this template's workflow contracts. Activation and selecting it for the AI capability are separate steps." if intent=='create' else "Current settings were read without changing permission. Change an operating rule or limit before submitting an amendment." if intent=='amend' and not changes_for_review else "Policy changes suspend this profile until separately reviewed activation." if intent=='amend' else "Running permission changes only after reviewed source is applied and the runtime is checked.",
            "profile_setup": {"profile_id": None if intent == "create" else profile_id,
                "source": None if intent == "create" else {"registry_ref": {"uri": "repo://platform-engineering/" + native.REGISTRY.as_posix(), "digest": source["registry_digest"]}, "source_version": head},
                "requesting_owner": callers[0]["owner_repo"], "registered_callers": callers,
                "requested_environments": [ENVIRONMENT], "required_output_schema_ref": {**output, "version": native.digest_bytes(output_path.read_bytes())},
                "human_approval_required": True, "operational_expectations": copy.deepcopy(current["allowed_data_scope"])},
            "editable_policy": {"allowed_data_scope": copy.deepcopy(current["allowed_data_scope"]), "runtime_limits": copy.deepcopy(current["runtime_limits"])}}


class OwnerClient:
    """Distinct Platform fulfiller identity; no operator review authority."""
    def __init__(self, base, caller, secret):
        self.base, self.caller, self.secret = base.rstrip("/"), caller, secret

    def request(self, path, body=None):
        request = Request(self.base + path, data=None if body is None else native.canonical_json(body),
                          headers={"content-type": "application/json", "x-oos-caller-id": self.caller, "x-oos-caller-secret": self.secret}, method="GET" if body is None else "POST")
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*_args,**_kwargs):raise ProfileError('The accepted owner connection cannot redirect credentials.')
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            payload = response.read(1048577)
        if len(payload) > 1048576:
            raise ProfileError("The request owner returned oversized evidence.")
        return json.loads(payload)

    def lifecycle(self, request_id):
        return self.request("/v1/model-profile-requests/" + quote(request_id, safe="") + "/lifecycle")

    def fulfill(self, projection, state):
        key = projection["request_id"] + ":implement:" + str(projection["revision"])
        return self.request("/v1/model-profile-requests/" + quote(projection["request_id"], safe="") + "/fulfillment", {
            "schema_version": 1, "fulfillment_id": key, "request_id": projection["request_id"], "expected_revision": projection["revision"],
            "state": state, "actor_id": native.ACTOR_ID, "recorded_at": utc(), "source": None, "receipt_ref": None, "failure": None, "idempotency_key": key})


class ProfileOperations:
    """One durable operation per real request, in the existing operation store."""
    def __init__(self, policy, store, *, owner=None, run=None):
        self.policy, self.store = policy, store
        self.workspace = Path(policy["workspace_root"])
        self.repo = self.workspace / "platform-engineering"
        self.oos = self.workspace / "operator-orchestration-service"
        self.settings = policy.get("purpose_profiles", {}).get("lifecycle", {})
        self.enabled = self.settings.get("enabled") is True
        self.run = run or self._run
        self.owner = owner

    def require(self):
        if not self.enabled:
            raise ProfileError("Profile lifecycle implementation is not commissioned. No operation was started.")
        if self.owner is None:
            from urllib.parse import urlsplit
            base = self.settings.get("oos_base_url", "")
            parsed = urlsplit(base)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
                raise ProfileError("The accepted request-owner connection is unavailable.")
            credential = Path(self.policy["runtime_state_root"]) / "private/model-profile-requests/fulfillment-caller-secret"
            if credential.is_symlink() or not credential.is_file() or credential.stat().st_mode & 0o077 or credential.stat().st_uid != os.geteuid():
                raise ProfileError("The distinct Platform fulfillment credential is unavailable.")
            secret=credential.read_text().strip()
            if len(secret)<32 or '\n' in secret or '\r' in secret:raise ProfileError('The distinct fulfillment credential is invalid.')
            self.owner = OwnerClient(base, native.ACTOR_ID, secret)

    @staticmethod
    def _run(argv, *, cwd=None):
        result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=600)
        if result.returncode:
            # Provider output can contain credentials or private source data.
            # Keep it out of the Console and operation journal.
            raise ProfileError("The owning command did not succeed; resume this original operation after resolving its prerequisite.")
        return result.stdout.rstrip('\n')

    @staticmethod
    def key(request_id):
        if not isinstance(request_id, str) or not re.fullmatch(r"model-profile-request:[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", request_id):
            raise ProfileError("Select a real profile request.")
        return "model-profile-lifecycle:" + hashlib.sha256(request_id.encode()).hexdigest()

    def inspect(self, request_id):
        self.require()
        # Prove this is still an approved request via the distinct fulfiller.
        handoff=self.owner.lifecycle(request_id)
        record = self.store.read(self.key(request_id))
        if record is None and handoff['request']['fulfillment_state'] in {'applied','implementing'}:
            return {'request_id':request_id,'state':'previous-implementation','source_applied':False,'runtime_state':'not-checked','next_action':'complete','history':[],'operation_digest':None,'review':None,'error':'This request records an earlier Platform implementation. Inspect its retained implementation evidence; no new operation has been started.'}
        return self.view(record) if record else {"request_id": request_id, "state": "not-started", "source_applied": False, "runtime_state": "not-checked", "next_action": "implement", "history": [], "operation_digest": None, "review": None, "error": None}

    @staticmethod
    def view(record):
        fields = ("request_id", "state", "source_applied", "runtime_state", "next_action", "history", "review", "error")
        value = {key: copy.deepcopy(record.get(key)) for key in fields}
        value["operation_digest"] = digest(value)
        value['rollback_available']=record['source_applied'] and not record['restore'] and record['state']=='verified'
        return value

    def save(self, record, state, next_action, detail):
        record.update(state=state, next_action=next_action, error=None)
        record["history"].append({"state": state, "recorded_at": utc(), "detail": detail})
        self.store.write(record)

    def control(self, body):
        # Policy documents share a single source/rollback boundary. Serialize
        # their writer without involving model invocation or another service.
        with self.store.lock('model-profile-policy-writer'):
            return self._control(body)

    def writer_available(self,request_id):
        for path in self.store.operations.glob('*.json'):
            value=json.loads(path.read_text())
            if value.get('command',{}).get('command_id','').startswith('model-profile-lifecycle:') and value.get('request_id')!=request_id and not value.get('source_applied') and value.get('state') in {'authoring','awaiting-review','merged','cleanup'}:
                raise ProfileError('Finish or decline the other pending policy source change before starting another.')

    def _control(self, body):
        self.require()
        if not isinstance(body, dict) or set(body) != {"request_id", "action", "expected_operation_digest"} or body["action"] not in {"implement", "continue", "approve-merge", "decline-source", "reconcile", "restore"}:
            raise ProfileError("Choose an available action on the original request.")
        request_id = body["request_id"]
        key = self.key(request_id)
        with self.store.lock(key):
            record = self.store.read(key)
            if record is None:
                self.writer_available(request_id)
                if body["action"] != "implement" or body["expected_operation_digest"] is not None:
                    raise ProfileError("Read the original operation before continuing it.")
                handoff = self.owner.lifecycle(request_id)
                projection, context = handoff["request"], handoff["context"]
                if projection["review_state"] != "approved" or not context or not context.get("candidate"):
                    raise ProfileError("An approved owner-prepared policy is required. For an older manual request, create a new request from the current profile.")
                if projection['fulfillment_state']!='not-started':
                    raise ProfileError('This request already records a Platform implementation. Recover its retained evidence instead of starting another operation.')
                record = {"command": {"command_id": key}, "request_id": request_id, "state": "queued", "source_applied": False,
                          "runtime_state": "not-checked", "next_action": "continue", "history": [], "review": None, "error": None,
                          "context": context, "request": projection, "security_acceptance": handoff.get("security_acceptance"), "restore": False}
                self.save(record, "queued", "continue", "Platform accepted this exact approved profile request.")
            elif body["action"] == "implement":
                # Unknown acknowledgement recovers the same original operation.
                return self.view(record)
            elif body["expected_operation_digest"] != self.view(record)["operation_digest"]:
                raise ProfileError("The operation changed. Read it again before acting.")
            try:
                self.advance(record, body["action"])
            except Exception:
                record["error"] = "The owner step did not complete. Check the original operation and resume it; no active state has been inferred."
                self.store.write(record)
                raise
            return self.view(record)

    def paths(self, record):
        root = self.store.root / "model-profiles" / self.store.key(record["command"]["command_id"])
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink() or root.parent.is_symlink() or not root.resolve().is_relative_to(self.store.root.resolve()):
            raise ProfileError("The operation directory is not a private owner directory.")
        return root

    def source(self, record, action):
        args = ["node", str(self.oos / "scripts/owner_source_cli.mjs"), "maintenance", action, "--repo-root", record["checkout"],
                "--landing-unit-id", record["landing_unit"], "--base-commit", record["base"], "--tracking-ref", "oos://model-profile-requests/" + record["request_id"]]
        return json.loads(self.run(args))

    def identity(self, record, action):
        root = self.paths(record)
        args = ["make", "--no-print-directory", "-C", str(self.repo), "agent-source-identity", "ACTION=" + action,
                "ARGS=--landing-unit-id " + record["landing_unit"] + " --repository mfshaf7/platform-engineering" +
                (" --branch " + record["branch"] + " --fetched-base " + record["base"] + " --human-reviewer-id " + self.reviewer() if action == "deliver" else "") +
                " --receipt " + str(root / ("identity-" + action + ".json")) + " --workspace-repo-inventory " + str(self.workspace / "workspace-governance/contracts/repos.yaml")]
        self.run(args)

    def reviewer(self):
        value = self.policy["platform_operation_provider"]["operator_id"].removeprefix("operator:")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,38}", value):
            raise ProfileError("The accountable human reviewer is not configured.")
        return value

    def advance(self, record, action):
        root = self.paths(record)
        if action=='decline-source':
            self.decline(record)
        if action == "restore":
            if not record["source_applied"] or record["restore"]:
                raise ProfileError("Rollback requires the original applied receipt and exact unchanged source.")
            self.begin_restore(record)
        if record["state"] == "queued":
            self.begin(record)
        if record["state"] == "authoring":
            self.author(record)
        if record["state"] == "awaiting-review":
            if action != "approve-merge":
                return
            self.merge(record)
        if record["state"] == "merged":
            self.readback(record)
        if record["state"] in {"source-applied", "runtime-unverified"}:
            self.reconcile(record)
        if record['state']=='cleanup':
            self.cleanup(record)
            self.save(record,'declined' if record.get('declined') else 'verified','complete','Source review declined; running policy unchanged.' if record.get('declined') else 'Running policy verified and the owned source branches and worktrees retired.')

    def begin(self, record):
        candidate = record["context"]["candidate"]
        self.run(['git','-C',str(self.repo),'fetch','origin','main'])
        if self.run(['git','-C',str(self.repo),'rev-parse','origin/main'])!=candidate['expected_sources']['source_version']:
            raise ProfileError('The accepted Platform base changed. Decline this stale operation and create a new request from the current profile.')
        if candidate["candidate_digest"] != digest({key: value for key, value in candidate.items() if key != "candidate_digest"}):
            raise ProfileError("The owner-prepared policy changed after review.")
        if native.source_state(self.repo, source_version=self.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"])) != candidate["expected_sources"]:
            raise ProfileError("Platform source changed after preparation. Revise and review the request against current source.")
        projection = self.owner.lifecycle(record["request_id"])["request"]
        reference=projection.get('decision_ref') or {}
        if reference.get('uri')!='oos://model-profile-requests/'+quote(record['request_id'],safe='')+'/decisions/'+quote(reference.get('digest',''),safe=''):
            raise ProfileError('Automatic implementation requires a decision recorded by the request owner.')
        approval=self.owner.request('/v1/model-profile-requests/'+quote(record['request_id'],safe='')+'/decisions/'+quote(reference['digest'],safe=''))
        if approval.get('request_id')!=record['request_id'] or approval.get('decision')!='approve' or digest({k:v for k,v in approval.items() if k!='digest'})!=reference['digest']:
            raise ProfileError('The exact saved operator decision could not be verified.')
        record['approval']=approval
        if projection["fulfillment_state"] in {"not-started","failed"}:
            projection = self.owner.fulfill(projection, "implementing")
        if projection["review_state"] != "approved" or projection["fulfillment_state"] != "implementing":
            raise ProfileError("The exact request is not approved for Platform implementation.")
        record["request"] = projection
        acceptance = record.get("security_acceptance")
        if projection["request"]["intent"] in {"activate", "exception"}:
            if not acceptance or acceptance.get("candidate_digest") != candidate["candidate_digest"] or acceptance.get("source") != projection["request"]["profile_intent"]["source"] or acceptance.get("digest") != digest({k: v for k, v in acceptance.items() if k != "digest"}):
                raise ProfileError("Separate Security acceptance for this exact source and candidate is required.")
        record["base"] = candidate["expected_sources"]["source_version"]
        suffix = self.store.key(record["command"]["command_id"])[:24]
        record.update(branch="maintenance/profile-" + suffix, landing_unit="model-profile-" + suffix,
                      checkout=str(self.paths(record) / "checkout"))
        self.save(record, "authoring", "continue", "The approved source and implementation identity are bound to this operation.")

    def author(self, record):
        checkout = Path(record["checkout"])
        root = self.paths(record)
        current=self.owner.lifecycle(record['request_id'])['request']
        if not record['restore'] and (current['review_state']!='approved' or current['fulfillment_state']!='implementing' or current['latest_receipt']['digest']!=record['request']['latest_receipt']['digest']):
            raise ProfileError('The original approval or fulfillment changed. Source authoring has stopped.')
        if not checkout.exists():
            self.run(["git", "-C", str(self.repo), "worktree", "add", "-b", record["branch"], str(checkout), record["base"]])
        self.identity(record, "deliver")
        self.source(record, "prepare")
        candidate, projection = record["context"]["candidate"], record["request"]
        decision = {"schema_version": 1, "decision_id": "platform-model-profile-decision:" + self.store.key(record["command"]["command_id"])[:24],
            "request_id": record["request_id"], "request_revision": projection["revision"], "request_receipt_digest": projection["latest_receipt"]["digest"],
            "intent": candidate["intent"], "actor_id": native.ACTOR_ID, "recorded_at": record.setdefault("decision_at", utc()),
            "expected_sources": candidate["expected_sources"], "profile_id": candidate["profile_id"], "target_profile": candidate["target_profile"],
            "activation_environment": candidate["activation_environment"], "security_decision_ref": None,
            "idempotency_key": record["command"]["command_id"]}
        acceptance = record.get("security_acceptance")
        if acceptance:
            decision["security_decision_ref"] = {"uri": "oos://model-profile-requests/"+quote(record["request_id"],safe="")+"/decisions/"+quote(acceptance["digest"],safe=""), "digest": acceptance["digest"]}
        self.store.write(record)
        for name, value in (("request.json", projection), ("decision.json", decision)):
            native.write_atomic(root / name, native.canonical_json(value))
        native_command = [sys.executable, str(checkout / "scripts/model_profile_lifecycle.py"), "--repo-root", str(checkout), "--oos-repo-root", str(self.oos)]
        if record["restore"]:
            self.run(native_command + ["restore", "--receipt", str(root / "receipt.json"), "--rollback-bundle", str(root / "rollback.json"), "--recorded-at", record['decision_at'], "--output", str(root / "restore.json")])
        else:
            self.run(native_command + ["apply", "--request-projection", str(root / "request.json"), "--decision", str(root / "decision.json"), "--receipt", str(root / "receipt.json"), "--rollback-bundle", str(root / "rollback.json")])
        status = self.run(["git", "-C", str(checkout), "status", "--porcelain"])
        allowed = {str(native.REGISTRY), str(native.ACCESS_PLANE), str(native.RUNTIME_ASSIST)}
        if any(line[3:] not in allowed for line in status.splitlines()):
            raise ProfileError("The source operation contains a file outside the three approved policy documents.")
        if status:
            self.run(["git", "-C", str(checkout), "add", "--", *sorted(allowed)])
            self.run(["git", "-C", str(checkout), "commit", "-m", ("Restore" if record["restore"] else "Apply") + " reviewed purpose profile lifecycle"])
        publication = self.source(record, "publish")
        pr = publication["pull_request"]
        if pr.get("author") not in {None, "mfshaf7-agent-gary[bot]", "app/mfshaf7-agent-gary"}:
            raise ProfileError("The published source does not have the admitted Gary author.")
        record["review"] = {"url": pr["url"], "number": pr["number"], "head": publication["pushed_head"]}
        self.save(record, "awaiting-review", "approve-merge", "Gary published the exact policy change for accountable human review.")
        self.identity(record,'revoke')

    def merge(self, record):
        pr = record["review"]
        observed = json.loads(self.run(["gh", "pr", "view", str(pr["number"]), "--repo", "mfshaf7/platform-engineering", "--json", "url,author,headRefOid,baseRefName,state,mergeCommit,statusCheckRollup"]))
        if observed["url"] != pr["url"] or observed["author"]["login"] != "app/mfshaf7-agent-gary" or observed["headRefOid"] != pr["head"] or observed["baseRefName"] != "main":
            raise ProfileError("The reviewed source changed. Inspect the exact current pull request before approval.")
        if observed["state"] == "OPEN":
            if self.run(["gh", "api", "user", "--jq", ".login"]) != self.reviewer():
                raise ProfileError("The delegated accountable human identity is unavailable.")
            self.run(["gh", "pr", "checks", str(pr["number"]), "--repo", "mfshaf7/platform-engineering"])
            self.run(["gh", "pr", "review", str(pr["number"]), "--repo", "mfshaf7/platform-engineering", "--approve", "--body", "Explicit Console approval of exact policy head " + pr["head"]])
            self.run(["gh", "pr", "merge", str(pr["number"]), "--repo", "mfshaf7/platform-engineering", "--squash", "--admin", "--match-head-commit", pr["head"]])
            observed = json.loads(self.run(["gh", "pr", "view", str(pr["number"]), "--repo", "mfshaf7/platform-engineering", "--json", "state,mergeCommit,headRefOid"]))
        if observed["state"] != "MERGED" or observed["headRefOid"] != pr["head"]:
            raise ProfileError("The exact source merge is not confirmed.")
        record["merge_commit"] = observed["mergeCommit"]["oid"]
        self.save(record, "merged", "continue", "The human-approved exact source head is merged.")

    def readback(self, record):
        root = self.paths(record)
        self.run(["git", "-C", str(self.repo), "fetch", "origin", "main"])
        merged = root / ('restore-merged' if record['restore'] else 'merged')
        if not merged.exists():
            self.run(["git", "-C", str(self.repo), "worktree", "add", "--detach", str(merged), record["merge_commit"]])
        record['merged_checkout']=str(merged)
        retained=record.setdefault('merged_checkouts',{})
        retained[str(merged)]=record['merge_commit']
        if record["restore"]:
            if any((merged / path).read_bytes() != __import__('base64').b64decode(native.read_json(root / "rollback.json")["documents"][str(path)]) for path in (native.REGISTRY, native.ACCESS_PLANE, native.RUNTIME_ASSIST)):
                raise ProfileError("Merged rollback source does not match the original bundle.")
        else:
            review_digest = digest(record["review"])
            record.setdefault('readback_at',utc());self.store.write(record)
            self.run([sys.executable, str(merged / "scripts/model_profile_lifecycle.py"), "--repo-root", str(merged), "--oos-repo-root", str(self.oos), "readback",
                "--receipt", str(root / "receipt.json"), "--source-version", record["merge_commit"], "--review-uri", record["review"]["url"], "--review-digest", review_digest,
                "--recorded-at", record.setdefault("readback_at", utc()), "--output", str(root / "readback.json"), "--request-history-root", str(Path(self.policy["runtime_state_root"]) / "private/model-profile-requests/request-history")])
            result = native.read_json(root / "readback.json")
            current = self.owner.lifecycle(record["request_id"])["request"]
            if current["fulfillment_state"] != "applied":
                self.owner.request("/v1/model-profile-requests/" + quote(record["request_id"], safe="") + "/fulfillment", result["oos_fulfillment"])
        record["source_applied"] = True
        if self.run(['git','-C',str(self.repo),'branch','--show-current'])!='main' or self.run(['git','-C',str(self.repo),'status','--porcelain']):
            raise ProfileError('Merged source is retained; the accepted Platform checkout must be clean main before reconciliation.')
        self.run(['git','-C',str(self.repo),'merge','--ff-only','origin/main'])
        expected=native.source_state(merged,source_version=record['merge_commit'])
        if native.source_state(self.repo,source_version=record['merge_commit'])!=expected:
            raise ProfileError('Newer policy source superseded this operation. Running state has not been overwritten.')
        self.run([sys.executable,str(merged/'scripts/model_profile_lifecycle.py'),'--repo-root',str(merged),'project','--source-version',record['merge_commit'],'--output',str(Path(self.policy['runtime_state_root'])/'private/model-profile-requests/current-registry.json')])
        self.save(record, "source-applied", "reconcile", "Platform read back the merged source; running state still needs verification.")

    def reconcile(self, record):
        # Reuse the profile runner. It retains its normal admission gates and
        # reports failure rather than treating merged source as live activation.
        root=self.paths(record)
        merged = Path(record['merged_checkout'])
        self.run(['git','-C',str(self.repo),'fetch','origin','main'])
        for path in (native.REGISTRY,native.ACCESS_PLANE,native.RUNTIME_ASSIST):
            if self.run(['git','-C',str(self.repo),'show','origin/main:'+str(path)])!=(merged/path).read_text().rstrip('\n'):
                raise ProfileError('Newer policy source superseded this operation. Running state has not been overwritten.')
        # Preserve the already commissioned management image, account slots,
        # private journal and credentials. A policy update does not reinstall a
        # provider or downgrade the gateway to its unmanaged baseline.
        overlay_path=Path(self.policy['runtime_state_root'])/'private/model-management/overlay.json'
        if overlay_path.is_symlink() or not overlay_path.is_file() or overlay_path.stat().st_uid!=os.geteuid() or overlay_path.stat().st_mode & 0o077:
            record['runtime_state']='unverified'
            self.save(record,'runtime-unverified','reconcile','Source is applied; the commissioned model-management overlay is unavailable and was preserved.')
            return
        import console_model_management as management
        overlay=native.read_json(overlay_path)
        if set(overlay)!={'image','owner_policy','memory_limit','cpu_limit'}:
            raise ProfileError('The commissioned model-management overlay is invalid.')
        overlay['owner_policy']=management.owner_policy(merged,'operator:'+self.reviewer(),lifecycle_policy=self.policy)
        current_overlay=root/'model-management-overlay.json'
        native.write_atomic(current_overlay,native.canonical_json(overlay))
        try:
            self.run(['env','DEVINT_GAI_MODEL_MANAGEMENT_OVERLAY='+str(current_overlay),sys.executable,str(self.repo/'scripts/dev_integration.py'),'up','--workspace-root',str(self.workspace),'--profile','governed-ai-gateway','--operator',self.reviewer(),'--repo-path','platform-engineering='+str(merged)])
        except ProfileError:
            record["runtime_state"] = "unverified"
            self.save(record, "runtime-unverified", "reconcile", "Source is applied; the running gateway has not confirmed the policy.")
            return
        # A runner completion alone is not profile readback.
        script = "import json,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8080/readyz',timeout=10))))"
        namespace = "devint-governed-ai-gateway-" + self.reviewer()
        observed = json.loads(self.run(["k3s", "kubectl", "-n", namespace, "exec", "deployment/governed-ai-gateway", "--", "python3", "-c", script]))
        profile_id = record["context"]["candidate"]["profile_id"]
        profiles = observed.get("profiles", {})
        state = profiles.get(profile_id, {}) if isinstance(profiles, dict) else {}
        expected = record["context"]["candidate"]["target_profile"]
        expected_state = "retired" if record["context"]["candidate"]["intent"] == "retire" else "suspended" if expected is None else expected["status"]
        if record['restore']:
            prior=native.read_json(root/'receipt.json')['lifecycle_before']
            expected_state=prior
        source=native.source_state(merged)
        binding=observed.get('selected_binding') or {}
        if binding.get('profile_registry_digest')!=source['registry_digest'] or binding.get('access_plane_digest')!=source['access_plane_digest'] or state.get("status") != expected_state or (expected_state=='active' and (state.get('activation_eligible') is not True or state.get('ready') is not True)):
            record["runtime_state"] = "unverified"
            self.save(record, "runtime-unverified", "reconcile", "Running profile evidence does not yet match the merged policy.")
            return
        record["runtime_state"] = expected_state or 'removed'
        record["runtime_evidence"] = observed
        self.save(record, "cleanup", "continue", "Merged source and observed running profile state match; source cleanup remains.")

    def cleanup(self,record):
        if not record.get('landing_unit'):return
        self.identity(record,'revoke')
        checkout=Path(record['checkout'])
        source_head=record['review']['head'] if record.get('review') else record.get('source_head')
        if checkout.exists():
            if self.run(['git','-C',str(checkout),'status','--porcelain']) or self.run(['git','-C',str(checkout),'rev-parse','HEAD'])!=source_head:
                raise ProfileError('Source cleanup found changed or unique work and preserved it.')
            self.run(['git','-C',str(self.repo),'worktree','remove',str(checkout)])
        # The human owns branch deletion; Gary never receives this authority.
        if self.run(['gh','api','user','--jq','.login'])!=self.reviewer():
            raise ProfileError('Human branch-cleanup authority is unavailable.')
        refs=self.run(['git','-C',str(self.repo),'ls-remote','--heads','origin',record['branch']])
        if refs:
            if refs.split()[0]!=source_head:
                raise ProfileError('The remote branch changed after merge and has been preserved.')
            self.run(['gh','api','--method','DELETE','repos/mfshaf7/platform-engineering/git/refs/heads/'+record['branch']])
        local=self.run(['git','-C',str(self.repo),'for-each-ref','--format=%(objectname)','refs/heads/'+record['branch']])
        if local:
            if local!=source_head:
                raise ProfileError('The local source branch changed and has been preserved.')
            self.run(['git','-C',str(self.repo),'update-ref','-d','refs/heads/'+record['branch'],source_head])
        self.run(['git','-C',str(self.repo),'fetch','--prune','origin'])
        for path,head in record.get('merged_checkouts',{}).items():
            detached=Path(path)
            if detached.exists():
                if detached.parent!=self.paths(record) or self.run(['git','-C',str(detached),'status','--porcelain']) or self.run(['git','-C',str(detached),'rev-parse','HEAD'])!=head:
                    raise ProfileError('Readback cleanup found changed source and preserved it.')
                self.run(['git','-C',str(self.repo),'worktree','remove',str(detached)])

    def decline(self,record):
        if record['state'] not in {'queued','authoring','awaiting-review'} or record['source_applied']:
            raise ProfileError('Only an unmerged source review can be declined.')
        pr=record['review'];root=self.paths(record)
        if not pr:
            if self.run(['gh','api','user','--jq','.login'])!=self.reviewer():raise ProfileError('The accountable human rejection identity is unavailable.')
            if not record.get('checkout'):return self.record_decline(record)
            checkout=Path(record['checkout']);record['source_head']=record.get('base')
            if checkout.exists():
                status=self.run(['git','-C',str(checkout),'status','--porcelain'])
                allowed={str(native.REGISTRY),str(native.ACCESS_PLANE),str(native.RUNTIME_ASSIST)}
                if any(line[3:] not in allowed for line in status.splitlines()):raise ProfileError('Unexpected source was preserved; resolve it before retiring this operation.')
                for name,args in [('declined-committed.patch',['diff','--binary',record['base'],'HEAD']),('declined-working.patch',['diff','--binary','HEAD'])]:
                    native.write_atomic(root/name,self.run(['git','-C',str(checkout),*args]).encode())
                record['source_head']=self.run(['git','-C',str(checkout),'rev-parse','HEAD'])
                if status:self.run(['git','-C',str(checkout),'restore','--source=HEAD','--staged','--worktree','--',*sorted(allowed)])
            return self.record_decline(record)
        current=json.loads(self.run(['gh','pr','view',str(pr['number']),'--repo','mfshaf7/platform-engineering','--json','url,author,headRefOid,baseRefName,state']))
        if current.get('url')!=pr['url'] or current.get('headRefOid')!=pr['head'] or current.get('author',{}).get('login')!='app/mfshaf7-agent-gary' or current.get('baseRefName')!='main' or current.get('state') not in {'OPEN','CLOSED'} or self.run(['gh','api','user','--jq','.login'])!=self.reviewer():
            raise ProfileError('The exact unmerged Gary source review could not be verified.')
        if current['state']=='OPEN':
            self.run(['gh','pr','close',str(pr['number']),'--repo','mfshaf7/platform-engineering','--comment','Explicit Console rejection of exact source head '+pr['head']])
        current=json.loads(self.run(['gh','pr','view',str(pr['number']),'--repo','mfshaf7/platform-engineering','--json','url,author,headRefOid,baseRefName,state']))
        if current.get('state')!='CLOSED' or current.get('headRefOid')!=pr['head']:
            raise ProfileError('Source review rejection is not confirmed.')
        # Preserve the rejected unique patch privately before retiring its branch.
        patch=self.run(['git','-C',record['checkout'],'format-patch','--stdout','-1',pr['head']])
        native.write_atomic(root/'declined-source.patch',patch.encode())
        self.record_decline(record)

    def record_decline(self,record):
        root=self.paths(record);pr=record.get('review')
        original=self.owner.lifecycle(record['request_id'])['request']
        if original['fulfillment_state']=='not-started':original=self.owner.fulfill(original,'implementing')
        artifact=record.setdefault('decline_decision',{'request_id':record['request_id'],'decision':'declined','review':pr,'actor_id':'operator:'+self.reviewer(),'recorded_at':utc()})
        artifact['digest']=digest({k:v for k,v in artifact.items() if k!='digest'})
        native.write_atomic(root/'decline.json',native.canonical_json(artifact));self.store.write(record)
        if record['restore']:
            record.update(restore_declined=True,source_applied=True)
        elif original['fulfillment_state']=='implementing':
            update=record.setdefault('decline_fulfillment',{'schema_version':1,'fulfillment_id':'model-profile-declined:'+self.store.key(record['command']['command_id'])[:24],'request_id':record['request_id'],'expected_revision':original['revision'],'state':'failed','actor_id':native.ACTOR_ID,'recorded_at':artifact['recorded_at'],'source':None,'receipt_ref':native.artifact_ref(root/'decline.json',artifact['digest']),'failure':{'code':'source-review-declined','summary':'The accountable human declined the exact source change; running policy is unchanged.','retryable':False},'idempotency_key':'model-profile-declined:'+self.store.key(record['command']['command_id'])[:24]})
            self.store.write(record)
            self.owner.request('/v1/model-profile-requests/'+quote(record['request_id'],safe='')+'/fulfillment',update)
        elif original['fulfillment_state']!='failed' or original.get('fulfillment',{}).get('receipt_ref')!=native.artifact_ref(root/'decline.json',artifact['digest']):
            raise ProfileError('The original rejection outcome does not match this operation.')
        record.update(declined=True,runtime_state='unchanged')
        self.save(record,'cleanup','continue','The human declined source; its exact patch and failure receipt are retained.')

    def begin_restore(self, record):
        root = self.paths(record)
        self.writer_available(record['request_id'])
        receipt = native.load_valid_receipt(self.repo, root / "receipt.json")
        current_head = self.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"])
        current = native.source_state(self.repo, source_version=receipt["result_source"]["source_version"])
        if current != receipt["result_source"]:
            raise ProfileError("Platform policy changed after this operation. Rollback cannot overwrite it.")
        record['original_merge_commit']=record['merge_commit']
        record['restore_base']=current_head
        record.update(restore=True, source_applied=False, runtime_state="not-checked", base=current_head,
                      branch=record["branch"] + "-restore", landing_unit=record["landing_unit"] + "-restore", checkout=str(root / "restore-checkout"), review=None)
        record.pop('decision_at',None)
        self.save(record, "authoring", "continue", "Rollback is bound to the original receipt and unchanged policy source.")


def admitted_policy_source(policy, repo: Path, *, store_root: Path | None = None):
    """Reuse exact-source admission for receipted policy-only descendants.

    Executable acceptance is unchanged. Every three-document transition must
    form an unbroken native receipt/readback chain from the accepted tree.
    Missing, corrupt, unrelated or unreviewed changes return False.
    """
    if policy.get('purpose_profiles',{}).get('lifecycle',{}).get('enabled') is not True:
        return False
    git=lambda *args:subprocess.check_output(['git','-C',str(repo),*args],text=True,stderr=subprocess.DEVNULL).strip()
    try:
        if git('status','--porcelain') or git('branch','--show-current')!='main':return False
        current=git('rev-parse','HEAD');accepted_tree=policy['security']['platform_tree']
        if git('rev-parse','HEAD^{tree}')==accepted_tree:return False
        anchor=next((line.split()[0] for line in git('log','-1000','--format=%H %T','HEAD').splitlines() if line.split()[1]==accepted_tree),None)
        if not anchor:return False
        allowed={str(native.REGISTRY),str(native.ACCESS_PLANE),str(native.RUNTIME_ASSIST)}
        if not set(git('diff','--name-only',anchor,current).splitlines()).issubset(allowed):return False
        fields=('registry_digest','access_plane_digest','runtime_assist_digest')
        sources=lambda commit:{key:native.digest_bytes(subprocess.check_output(['git','-C',str(repo),'show',commit+':'+str(path)],stderr=subprocess.DEVNULL)) for key,path in zip(fields,(native.REGISTRY,native.ACCESS_PLANE,native.RUNTIME_ASSIST))}
        initial=sources(anchor);target=sources(current);edges=[]
        root=store_root or Path(policy['runtime_state_root'])/'provider'
        for path in (root/'operations').glob('*.json'):
            record=json.loads(path.read_text());command=record.get('command',{}).get('command_id','')
            if not command.startswith('model-profile-lifecycle:'):continue
            private=root/'model-profiles'/hashlib.sha256(command.encode()).hexdigest()
            if private.is_symlink():return False
            receipt_path,readback_path=private/'receipt.json',private/'readback.json'
            if not receipt_path.exists() or not readback_path.exists():continue
            receipt=native.load_valid_receipt(repo,receipt_path);readback=native.read_json(readback_path)
            if readback.get('digest')!=digest({k:v for k,v in readback.items() if k!='digest'}) or readback.get('lifecycle_receipt_ref')!=native.artifact_ref(receipt_path,receipt['digest']):return False
            approval=record.get('approval',{});request=record.get('request',{})
            if approval.get('decision')!='approve' or approval.get('request_id')!=receipt['request_id'] or approval.get('digest')!=digest({k:v for k,v in approval.items() if k!='digest'}) or request.get('decision_ref',{}).get('digest')!=approval['digest']:return False
            candidate=record['context']['candidate']
            if candidate.get('candidate_digest')!=digest({k:v for k,v in candidate.items() if k!='candidate_digest'}):return False
            if receipt['intent'] in {'activate','exception'}:
                security=record.get('security_acceptance') or {}
                if security.get('candidate_digest')!=candidate['candidate_digest'] or security.get('digest')!=digest({k:v for k,v in security.items() if k!='digest'}):return False
            base,result=receipt['base_source']['source_version'],readback['source_version']
            before={k:receipt['base_source'][k] for k in fields};after={k:receipt['result_source'][k] for k in fields}
            if sources(base)!=before or sources(result)!=after:return False
            edges.append((base,result,before,after))
            if record.get('restore') and not record.get('restore_declined') and record.get('merge_commit')!=record.get('original_merge_commit') and (private/'restore.json').exists():
                restored=native.read_json(private/'restore.json')
                if restored.get('digest')!=digest({k:v for k,v in restored.items() if k!='digest'}) or restored.get('lifecycle_receipt_ref')!=native.artifact_ref(receipt_path,receipt['digest']):return False
                restore_base,restore_head=record['restore_base'],record['merge_commit']
                if sources(restore_base)!=after or sources(restore_head)!={k:restored['restored_source'][k] for k in fields}:return False
                edges.append((restore_base,restore_head,after,{k:restored['restored_source'][k] for k in fields}))
        reachable={(anchor,tuple(initial[k] for k in fields))}
        for _ in range(len(edges)+1):
            old=len(reachable)
            for base,result,before,after in edges:
                if (base,tuple(before[k] for k in fields)) in reachable:
                    reachable.add((result,tuple(after[k] for k in fields)))
            if len(reachable)==old:break
        return (current,tuple(target[k] for k in fields)) in reachable
    except (OSError,ValueError,KeyError,IndexError,StopIteration,native.LifecycleError,subprocess.CalledProcessError):
        return False
