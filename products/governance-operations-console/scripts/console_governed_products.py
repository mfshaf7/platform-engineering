"""Bounded committed product/readiness projection; never executes a release."""
from datetime import datetime, timezone
from pathlib import Path
import re
from console_dev_integration_profiles import committed_document, ProfileReadError

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FILES = (
    ("candidate", "Release candidate", "environments/stage/release-candidate.yaml", "recordedAt"),
    ("stage-verification", "Stage verification", "environments/stage/verification.yaml", "verifiedAt"),
    ("readiness", "Production readiness", "environments/stage/promotion-readiness.yaml", "approvedAt"),
    ("production", "Production verification", "environments/prod/verification.yaml", "verifiedAt"),
)
WORKFLOWS = (
    ("readiness", "Review stage readiness", "confirm-stage-promotion-readiness.yaml", "stage"),
    ("promotion", "Promote approved candidate", "promote-environment.yaml", "prod"),
    ("runtime", "Change production runtime state", "manage-prod-environment.yaml", "prod"),
)

def read_products(policy, *, query=None, reader=committed_document, observed=None):
    query = query or {}
    if set(query) - {"limit", "offset", "q", "maturity", "endpoint", "product_id"}:
        raise ProfileReadError("Unsupported product filter.")
    try:
        limit, offset = int(query.get("limit", 20)), int(query.get("offset", 0))
    except (ValueError, TypeError):
        raise ProfileReadError("Product pagination must use integers.") from None
    if not 1 <= limit <= 25 or not 0 <= offset <= 10000 or any(not isinstance(v, str) or len(v) > 200 for k,v in query.items() if k not in {"limit", "offset"}):
        raise ProfileReadError("Product query exceeds its bounds.")
    if query.get("endpoint", "all") not in {"all", "production", "stage", "unavailable"}:
        raise ProfileReadError("Unsupported endpoint filter.")
    if query.get("maturity", "all") not in {"all", "fully-governed", "platform-integrated", "owner-managed"}:
        raise ProfileReadError("Unsupported maturity filter.")
    workspace = Path(policy["workspace_root"])
    registry, revision = reader(workspace, "workspace-governance", "contracts/products.yaml")
    entries = registry.get("products")
    if not isinstance(entries, dict) or len(entries) > 10000:
        raise ProfileReadError("Product registry is invalid.")
    # Include the Platform revision even for a page with no product-specific adapter.
    _, platform_revision = reader(workspace, "platform-engineering", "environments/prod/openclaw-lifecycle.yaml")
    def platform_read(relative):
        value, actual = reader(workspace, "platform-engineering", relative)
        if actual != platform_revision:
            raise ProfileReadError("Product owner source changed during read; refresh it.")
        return value
    selected = []
    for product_id, entry in sorted(entries.items()):
        if not SLUG.fullmatch(product_id) or not isinstance(entry, dict):
            raise ProfileReadError("Invalid product identity.")
        if entry.get("posture") == "retired":
            continue
        maturity = entry.get("maturity")
        if maturity not in {"fully-governed", "platform-integrated", "owner-managed"} or any(not isinstance(entry.get(k), bool) for k in ("stage_supported", "governed_prod_promotion")):
            raise ProfileReadError("Product capability contract is invalid.")
        endpoint = "production" if entry["governed_prod_promotion"] else "stage" if entry["stage_supported"] else "unavailable"
        if query.get("product_id") and query["product_id"] != product_id: continue
        if query.get("maturity", "all") not in {"all", maturity}: continue
        if query.get("endpoint", "all") not in {"all", endpoint}: continue
        if query.get("q", "").casefold() not in f"{product_id} {entry.get('platform_owner','')} {entry.get('highest_real_endpoint','')}".casefold(): continue
        selected.append((product_id, entry))
    products = []
    for product_id, entry in selected[offset:offset+limit]:
        if any(not isinstance(entry.get(k), str) or not SLUG.fullmatch(entry[k]) for k in ("platform_owner", "security_owner", "highest_real_endpoint")):
            raise ProfileReadError("Product ownership or endpoint is invalid.")
        item = {"product_id":product_id, "label":{"openclaw":"OpenClaw", "openproject":"OpenProject", "governance-operations-console":"Governance Operations Console"}.get(product_id,product_id.replace('-', ' ').title()),
            "maturity":entry["maturity"], "platform_owner":entry["platform_owner"], "security_owner":entry["security_owner"],
            "highest_real_endpoint":entry["highest_real_endpoint"], "stage_supported":entry["stage_supported"], "production_supported":entry["governed_prod_promotion"],
            "evidence":[], "runtime":None, "workflows":[], "guidance_url":f"https://github.com/mfshaf7/workspace-governance/blob/{revision}/contracts/products.yaml",
            "execution":"unavailable", "unavailable_reason":"No Console release execution adapter is commissioned for this product."}
        if product_id == "openclaw":
            item["execution"] = "owner-workflow"
            item["guidance_url"] = f"https://github.com/mfshaf7/platform-engineering/blob/{platform_revision}/products/openclaw/runbooks/release-governance.md"
            for ident, label, relative, time_key in FILES:
                doc = platform_read(relative)
                if doc.get("product") != product_id:
                    raise ProfileReadError("Release evidence belongs to another product.")
                status = doc.get("status")
                if not isinstance(status, str) or not status or len(status) > 100:
                    raise ProfileReadError("Release record status is invalid.")
                candidate = doc.get("candidateRef") or doc.get("candidate") or {}
                image = candidate.get("image") or {}
                item["evidence"].append({"id":ident,"label":label,"status":status,"recorded_at":doc.get(time_key),
                    "source_bundle":candidate.get("sourceBundleRef"), "image_digest":candidate.get("imageDigest") or image.get("digest"),
                    "evidence_ref":doc.get("evidenceRef"),"url":f"https://github.com/mfshaf7/platform-engineering/blob/{platform_revision}/{relative}"})
            state = platform_read("environments/prod/openclaw-lifecycle.yaml")
            if state.get("product") != product_id or state.get("state") not in {"live","traffic-stopped","suspended","quarantined"}:
                raise ProfileReadError("Product runtime contract is invalid.")
            item["runtime"] = {"state":state["state"],"recorded_at":state.get("changedAt"),"url":f"https://github.com/mfshaf7/platform-engineering/blob/{platform_revision}/environments/prod/openclaw-lifecycle.yaml"}
            for ident,label,filename,environment in WORKFLOWS:
                # committed_document requires a regular Git blob; YAML parsing also proves the route exists.
                workflow = platform_read(f".github/workflows/{filename}")
                if not isinstance(workflow.get("jobs"),dict): raise ProfileReadError("Owner workflow is unavailable.")
                item["workflows"].append({"id":ident,"label":label,"environment":environment,"url":f"https://github.com/mfshaf7/platform-engineering/actions/workflows/{filename}"})
                if "governed_release" in policy:
                    from console_release_dispatch import action_definition, ReleaseError, SPECS
                    try:
                        item["workflows"][-1]["native"] = action_definition(policy, ident, reader=reader)
                    except (ReleaseError, ProfileReadError):
                        # Executability must never determine whether existing
                        # products/evidence can still be inspected.
                        item["workflows"][-1]["native"] = {"schema_version":1,"workflow_id":ident,"capability_id":"release.openclaw."+ident,"action":SPECS[ident]["action"],"available":False,"unavailable_reason":"Current owner release inputs are unavailable; inspect its existing records and workflow.","source_version":f"products:{revision}:{platform_revision}","fields":[]}
        elif not item["stage_supported"] and not item["production_supported"]:
            item["execution"] = "unsupported"
            item["unavailable_reason"] = "This product has no governed stage-to-production release path. Its current endpoint remains available for inspection."
        products.append(item)
    return {"schema_version":1,"workflow_id":"governed-product-projection","source_version":f"products:{revision}:{platform_revision}",
        "observed_at":(observed or datetime.now(timezone.utc)).isoformat(),"products":products,
        "page":{"offset":offset,"limit":limit,"total":len(selected),"next_offset":offset+limit if offset+limit < len(selected) else None}}
