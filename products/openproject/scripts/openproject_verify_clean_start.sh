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

echo "Checking OpenProject clean-start readiness for ${PROPOSAL_PROJECT_IDENTIFIER} and ${DELIVERY_PROJECT_IDENTIFIER}"

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

result = {
  proposal_plane: proposal,
  delivery_plane: delivery,
  demo_projects_present: demo_projects,
  clean_start_ready: configured && empty_projects && demo_absent,
  checks: {
    configured: configured,
    proposal_plane_empty: proposal[:exists] ? proposal[:work_packages].to_i.zero? : false,
    delivery_plane_empty: delivery[:exists] ? delivery[:work_packages].to_i.zero? : false,
    demo_projects_absent: demo_absent
  },
  guidance: [
    "this gate applies to initial production activation only",
    "clean start requires both canonical projects to exist",
    "clean start requires zero work packages in both canonical projects",
    "clean start requires upstream demo projects to stay absent",
    "delivery versions are reported for visibility only; they are not treated as data pollution by this check",
    "once production is live, keep only production-created history there; do not carry over dev-integration or stage rehearsal data"
  ]
}

puts JSON.pretty_generate(result)

if require_empty && !result[:clean_start_ready]
  warn "OpenProject clean-start verification failed."
  exit 1
end
RUBY
