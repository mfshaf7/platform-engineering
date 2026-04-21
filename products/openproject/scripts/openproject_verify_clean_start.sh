#!/usr/bin/env bash
set -euo pipefail

KUBECTL="${KUBECTL:-k3s kubectl}"
OPENPROJECT_NAMESPACE="${OPENPROJECT_NAMESPACE:-openproject}"
OPENPROJECT_DEPLOYMENT="${OPENPROJECT_DEPLOYMENT:-openproject-web}"
REQUIRE_EMPTY="${REQUIRE_EMPTY:-false}"
PROPOSAL_PROJECT_IDENTIFIER="${PROPOSAL_PROJECT_IDENTIFIER:-workspace-proposals}"
DELIVERY_PROJECT_IDENTIFIER="${DELIVERY_PROJECT_IDENTIFIER:-workspace-delivery-art}"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

kubectl_cmd() {
  ${KUBECTL} "$@"
}

need_cmd "${KUBECTL%% *}"

echo "Checking OpenProject production activation hygiene for ${PROPOSAL_PROJECT_IDENTIFIER} and ${DELIVERY_PROJECT_IDENTIFIER}"

kubectl_cmd -n "${OPENPROJECT_NAMESPACE}" exec -i "deploy/${OPENPROJECT_DEPLOYMENT}" -- \
  env \
    REQUIRE_EMPTY="${REQUIRE_EMPTY}" \
    PROPOSAL_PROJECT_IDENTIFIER="${PROPOSAL_PROJECT_IDENTIFIER}" \
    DELIVERY_PROJECT_IDENTIFIER="${DELIVERY_PROJECT_IDENTIFIER}" \
    sh -lc '
set -euo pipefail
tmp_script="/tmp/openproject_verify_clean_start.rb"
cat > "${tmp_script}"
bundle exec ruby "${tmp_script}"
rm -f "${tmp_script}"
' <<'RUBY'
require "json"

proposal_identifier = ENV.fetch("PROPOSAL_PROJECT_IDENTIFIER")
delivery_identifier = ENV.fetch("DELIVERY_PROJECT_IDENTIFIER")
require_empty = ENV.fetch("REQUIRE_EMPTY", "false") == "true"

require "/app/config/environment"

def summarize_project(identifier)
  project = Project.find_by(identifier: identifier)
  unless project
    return {
      identifier: identifier,
      exists: false,
      work_packages: nil,
      versions: nil
    }
  end

  {
    identifier: project.identifier,
    name: project.name,
    exists: true,
    work_packages: project.work_packages.count,
    versions: project.versions.count
  }
end

proposal = summarize_project(proposal_identifier)
delivery = summarize_project(delivery_identifier)
demo_projects = Project.where(identifier: ["demo-project", "your-scrum-project"]).order(:identifier).pluck(:identifier)

configured = proposal[:exists] && delivery[:exists]
empty_projects =
  configured &&
  proposal[:work_packages].to_i.zero? &&
  delivery[:work_packages].to_i.zero?
demo_absent = demo_projects.empty?
activation_hygiene_ready = configured && demo_absent
existing_records_present =
  configured &&
  (proposal[:work_packages].to_i.positive? || delivery[:work_packages].to_i.positive?)

result = {
  proposal_plane: proposal,
  delivery_plane: delivery,
  demo_projects_present: demo_projects,
  activation_mode: require_empty ? "empty-plane-required" : "noise-free-history-allowed",
  production_activation_hygiene_ready: activation_hygiene_ready,
  empty_plane_ready: activation_hygiene_ready && empty_projects,
  clean_start_ready: activation_hygiene_ready && empty_projects,
  checks: {
    configured: configured,
    existing_records_present: existing_records_present,
    provenance_review_required: existing_records_present,
    proposal_plane_empty: proposal[:exists] ? proposal[:work_packages].to_i.zero? : false,
    delivery_plane_empty: delivery[:exists] ? delivery[:work_packages].to_i.zero? : false,
    demo_projects_absent: demo_absent
  },
  guidance: [
    "this gate applies to production activation only",
    "production activation hygiene requires both canonical projects to exist",
    "production activation hygiene requires upstream demo projects to stay absent",
    "existing records are allowed only when they are real production history, vetted imports, or an explicitly approved promoted ART baseline with explicit provenance",
    "dev-integration or stage-originated ART history may seed production only when it is intentionally promoted as the canonical baseline rather than left as disposable rehearsal data",
    "REQUIRE_EMPTY=true is the stricter first-activation mode when an empty plane is still required",
    "delivery versions are reported for visibility only; they are not treated as data pollution by this check",
    "once production is live, keep only production-created history or explicitly promoted baseline history there; do not carry over smoke, demo, or rehearsal-only data"
  ]
}

puts JSON.pretty_generate(result)

required_ready =
  if require_empty
    result[:empty_plane_ready]
  else
    result[:production_activation_hygiene_ready]
  end

if !required_ready
  warn "OpenProject production activation hygiene verification failed."
  exit 1
end
RUBY
