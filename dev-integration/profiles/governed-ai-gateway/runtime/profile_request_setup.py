"""Bounded request setup from the already resolved owner workflow contracts."""
from __future__ import annotations
import re
from model_configuration import ConfigurationError, digest


GUIDES = {
    "agent-console-assistant-v1": ("Helps answer operator questions in Agent Console.", "Your message and admitted session context", "An advisory reply; no final decision or direct mutation"),
    "delivery-work-design-advisor-v1": ("Helps draft a delivery brief and work breakdown.", "Admitted planning context and the operator's request", "Suggested context answers or a draft work tree for review"),
    "delivery-refinement-advisor-v1": ("Helps refine delivery items before execution.", "Selected delivery metadata and admitted context", "Suggested metadata changes for review"),
    "intake-classifier-v1": ("Suggests how to classify a workspace entrant.", "Operator-supplied intake notes", "A proposed classification and confidence; operator acceptance remains separate"),
    "source-realization-v1": ("Drafts bounded source changes for Delivery.", "An accepted objective, repository binding and admitted source context", "A structured change set for human review"),
    "prototype-source-authoring-v1": ("Drafts bounded source changes for a Prototype.", "A real Prototype session, accepted objective and admitted source context", "A structured change set for human review"),
}

def profile_request_options(profiles, allowed_tasks):
    workflows = []
    for profile_id, profile in sorted(profiles.items()):
        if profile.get("capability_id", profile_id) != profile_id:
            continue
        for kind, task in sorted(profile["task_contracts"].items()):
            if kind != profile.get("default_task_kind", kind):
                continue
            workflow_id = profile_id + "/" + kind
            if workflow_id not in allowed_tasks:
                continue
            output = task["provider_output_schema"]
            owner = task["instruction_owner_repo"]
            callers = []
            for caller in profile["allowed_callers"]:
                if "/" not in caller:
                    raise ConfigurationError("profile-setup-invalid", "The workflow caller has no recorded repository binding.")
                caller_owner = caller.split("/", 1)[0]
                if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", caller_owner):
                    raise ConfigurationError("profile-setup-invalid", "The workflow caller has no recorded repository binding.")
                callers.append({"caller_id": caller, "owner_repo": caller_owner})
            if not callers or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", owner):
                raise ConfigurationError("profile-setup-invalid", "The workflow has no recorded responsible repository.")
            setup = {"workflow_id": workflow_id, "requesting_owner": owner,
                     "registered_callers": callers, "environments": [profile["environment"]],
                     "output_schema_ref": {**output, "version": task["provider_output_schema_digest"]},
                     "operational_expectations": ["Use only the admitted workflow, context and output contract.",
                                                  "Require the recorded human review before activation."]}
            guide = GUIDES.get(profile_id)
            if guide:
                setup["guide"] = {"behavior": guide[0], "input": guide[1], "output": guide[2],
                                  "instructions": "Task instructions are implemented by the registered integration. Profile descriptions and review notes do not change that behavior."}
            if profile.get("allowed_data_scope"):
                setup["policy_defaults"] = {"allowed_data_scope": profile["allowed_data_scope"], "runtime_limits": profile["runtime_limits"]}
            # Bind only request-relevant setup. Provider/model changes do not
            # unnecessarily invalidate an otherwise identical request draft.
            setup["setup_digest"] = digest(setup)
            label = re.sub(r"-v[0-9]+$", "", profile_id).replace("-", " ").capitalize()
            workflows.append({**setup, "label": label,
                              "purpose": profile["purpose"]})
    return {"schema_version": 1, "workflows": workflows}
