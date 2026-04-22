# frozen_string_literal: true

require "json"
require "set"

require_relative "openproject_delivery_art_custom_field_support"

PROJECT_IDENTIFIER = ENV.fetch("OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER", "workspace-delivery-art")
TARGET_EPIC_ID = ENV["TARGET_EPIC_ID"]&.strip&.then { |value| Integer(value) }

PLATFORM_ENGINEERING_IDS = Set[
  68, 74, 82, 83, 84, 85, 86,
  171, 172, 173, 174, 175, 176, 177, 178, 179, 180
].freeze
SECURITY_ARCHITECTURE_IDS = Set[49, 71].freeze
OPERATOR_ORCHESTRATION_IDS = Set[
  51, 52, 53, 54, 55, 56, 57,
  59, 60, 61, 62, 63, 64, 65, 66, 67, 70, 72, 75
].freeze
WORKSPACE_GOVERNANCE_IDS = Set[
  38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 50,
  58, 76, 77, 78, 79, 80, 81
].freeze

ACTIVE_OR_OPEN_STATUSES = Set[%w[ready in-progress blocked parked done]].freeze
DONE_STATUS = "done"
BACKLOG_ITERATION = "Not committed to a PI iteration yet."
COMPLETION_HEADINGS = Set[
  "Completion Summary",
  "Changed Surfaces",
  "Test Result Evidence",
  "Validation Evidence",
  "Residual Follow-Up"
].freeze
PRESERVED_NON_DONE_HEADINGS = Set["Operator work notes"].freeze
PRESERVED_DONE_HEADINGS = COMPLETION_HEADINGS + PRESERVED_NON_DONE_HEADINGS
LEGACY_COMPLETION_HEADING_MAP = {
  "Completed Output" => "Completion Summary",
  "Completed Scope" => "Changed Surfaces",
  "Acceptance Evidence" => "Test Result Evidence",
  "Verification" => "Validation Evidence",
  "Result" => "Completion Summary"
}.freeze

project = Project.find_by!(identifier: PROJECT_IDENTIFIER)
author = User.find_by(login: "admin") || User.admin.active.first || User.active.first
raise "No active OpenProject user is available for normalization" unless author

User.current = author if User.respond_to?(:current=)

field_names = [
  "Owner Repo",
  "Sponsor",
  "Delivery Team",
  "Iteration",
  "Acceptance Criteria",
  "Definition of Ready",
  "Definition of Done"
]
custom_fields = project.work_package_custom_fields.where(name: field_names).index_by(&:name)

all_work_packages = WorkPackage.where(project_id: project.id).includes(:type, :status, :version, :parent).order(:id).to_a
by_id = all_work_packages.index_by(&:id)

def section_pairs(markdown)
  markdown.to_s.scan(/^## ([^\n]+)\n(.*?)(?=^## |\z)/m).map do |heading, body|
    [heading, body.to_s.strip]
  end
end

def first_body(section_map, *headings)
  headings.each do |heading|
    body = section_map[heading]
    return body if body.present?
  end
  nil
end

def execution_context_owner_repo(entry)
  sections = section_pairs(entry.description).to_h
  context = sections["Execution Context"].to_s
  return nil if context.blank?

  context.each_line do |line|
    match = line.strip.match(/\A-\s*Owner repo:\s*`?([A-Za-z0-9._-]+)`?\s*\z/i)
    return match[1] if match
  end

  nil
end

def clean_subject(subject)
  subject.to_s.sub(/\A(?:Enabler|Feature|Task|User story|Risk|Improvement|Defect|Milestone|PI Objective):\s*/i, "")
end

def top_epic_for(entry, by_id)
  current = entry
  visited = {}
  while current && current.parent_id && !visited[current.id]
    visited[current.id] = true
    current = by_id[current.parent_id]
  end
  current if current&.type&.name == "Epic"
end

def current_target_pi(entry)
  if entry.respond_to?(:version)
    entry.version&.name
  elsif entry.respond_to?(:fixed_version)
    entry.fixed_version&.name
  end
end

def field_value(entry, field)
  OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: entry, field: field)
end

def set_field!(entry, field, value, kind: nil)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: entry, field: field, value: value, kind: kind)
end

def owner_repo_for(entry, top_epic)
  explicit_owner_repo = execution_context_owner_repo(entry)
  return explicit_owner_repo if explicit_owner_repo.present?
  return "security-architecture" if top_epic&.id == 87
  return "platform-engineering" if PLATFORM_ENGINEERING_IDS.include?(entry.id)
  return "security-architecture" if SECURITY_ARCHITECTURE_IDS.include?(entry.id)
  return "operator-orchestration-service" if OPERATOR_ORCHESTRATION_IDS.include?(entry.id)
  return "workspace-governance" if WORKSPACE_GOVERNANCE_IDS.include?(entry.id)

  "platform-engineering"
end

def default_delivery_team(owner_repo)
  {
    "workspace-governance" => "Workspace Governance",
    "platform-engineering" => "Platform Engineering",
    "operator-orchestration-service" => "Operator Orchestration Service",
    "security-architecture" => "Security Architecture"
  }.fetch(owner_repo, "Platform Engineering")
end

def default_iteration(entry)
  target_pi = current_target_pi(entry)
  target_pi.present? ? "#{target_pi} / Iteration 1" : BACKLOG_ITERATION
end

def default_acceptance_criteria(entry)
  item = clean_subject(entry.subject)
  case entry.type&.name
  when "PI Objective"
    "The objective outcome for #{item} is explicit in the ART, linked to the right child work, and reviewable in the current PI."
  else
    "The outcome for #{item} is explicit in the owner repo and the ART record is clear enough for the next operator to execute without reconstruction."
  end
end

def default_definition_of_ready(entry)
  "#{entry.type&.name || 'Work item'} ownership, narrative, execution context, and evidence path are explicit enough to start work without further scope reconstruction."
end

def default_definition_of_done(entry)
  if entry.type&.name == "PI Objective"
    "Delivered child work supports the stated outcome, the PI review fields are recorded at review time, and the ART reflects the final review result."
  else
    "Required fields remain populated, the narrative matches the delivered outcome, and completion evidence is recorded through the ART workflow when the item moves to done."
  end
end

def default_scope_boundaries(entry)
  "This #{entry.type&.name.to_s.downcase} covers the capability described above and its directly attached child work. It does not, by itself, claim that the full initiative is complete."
end

def default_benefit(entry, top_epic)
  if top_epic&.id == 87
    "Making this workstream explicit and owner-backed reduces ambiguity in the cybersecurity program and gives later implementation and audit work a stable planning surface."
  else
    "Making this slice explicit and owner-backed reduces ambiguity in the governed AI agent platform initiative and makes later delivery work easier to sequence and verify."
  end
end

def default_why_now(entry, top_epic)
  if top_epic&.id == 87
    "This task sharpens the cybersecurity baseline before implementation starts, so later delivery and assurance work can proceed from explicit control intent."
  else
    "This task turns the named delivery slice into an inspectable, owner-backed result so the next implementation tranche can move without reconstructing intent."
  end
end

def default_evidence_expectation(entry, top_epic)
  if top_epic&.id == 87
    "Planning-grade control text, references, or review surfaces exist in the owner repo and are sufficient to keep this item ready for later implementation."
  else
    "The owner repo, platform surface, or linked review artifact contains enough proof to show this delivery slice is ready for execution and later closeout."
  end
end

def default_risk_handling
  "The ART keeps this risk visible and expects the owning repo to reduce, mitigate, or explicitly accept it through later delivery work."
end

def execution_context_body(entry, owner_repo, top_epic, field_team, field_iteration)
  lines = []
  lines << "- Owner repo: `#{owner_repo}`"
  lines << "- Work package: `##{entry.id}` #{entry.subject}"
  if top_epic && top_epic.id != entry.id
    lines << "- Initiative: `##{top_epic.id}` #{top_epic.subject}"
  end
  if entry.parent_id
    parent = entry.parent
    lines << "- Parent item: `##{parent.id}` #{parent.subject}" if parent
  end
  target_pi = current_target_pi(entry)
  lines << "- Target PI: `#{target_pi}`" if target_pi.present?
  lines << "- Delivery team: `#{field_team}`" if field_team.present?
  lines << "- Iteration: `#{field_iteration}`" if field_iteration.present?
  lines.join("\n")
end

def render_sections(sections)
  sections.filter_map do |heading, body|
    rendered = body.to_s.strip
    next if rendered.empty?

    "## #{heading}\n\n#{rendered}"
  end.join("\n\n").strip
end

def preserved_sections_for(entry, preserve_done_sections)
  sections = section_pairs(entry.description)
  preserved = []

  sections.each do |heading, body|
    next if body.blank?

    if preserve_done_sections
      canonical_heading = LEGACY_COMPLETION_HEADING_MAP.fetch(heading, heading)
      next unless PRESERVED_DONE_HEADINGS.include?(canonical_heading)

      preserved << [canonical_heading, body] unless preserved.any? { |existing_heading, _| existing_heading == canonical_heading }
    else
      preserved << [heading, body] if PRESERVED_NON_DONE_HEADINGS.include?(heading)
    end
  end

  preserved
end

def normalize_description(entry, owner_repo:, top_epic:, delivery_team:, iteration:, preserve_done_sections:)
  sections = section_pairs(entry.description).to_h
  preserved = preserved_sections_for(entry, preserve_done_sections)

  type_name = entry.type&.name
  normalized_sections =
    case type_name
    when "Epic"
      [
        [
          "What This Initiative Achieves",
          first_body(sections, "What This Initiative Achieves", "Initiative Outcome", "What This Achieves", "Current State")
        ],
        [
          "Current PI Focus",
          first_body(sections, "Current PI Focus", "Current State")
        ],
        [
          "Scope Boundaries",
          first_body(sections, "Scope Boundaries", "Scope") || default_scope_boundaries(entry)
        ],
        [
          "Execution Context",
          first_body(sections, "Execution Context") || execution_context_body(entry, owner_repo, top_epic, delivery_team, iteration)
        ]
      ]
    when "PI Objective"
      [
        [
          "Outcome",
          first_body(sections, "Outcome", "Outcome Statement", "Objective Intent") || clean_subject(entry.subject)
        ],
        [
          "Why This PI",
          first_body(sections, "Why This PI", "Current Purpose") || default_why_now(entry, top_epic)
        ],
        [
          "Success Signal",
          first_body(sections, "Success Signal", "Evidence Expectation", "Ready Condition") || default_evidence_expectation(entry, top_epic)
        ],
        [
          "Execution Context",
          first_body(sections, "Execution Context") || execution_context_body(entry, owner_repo, top_epic, delivery_team, iteration)
        ]
      ]
    when "Risk"
      [
        [
          "Risk Event",
          first_body(sections, "Risk Event", "Trigger", "Risk Statement") || clean_subject(entry.subject)
        ],
        [
          "Impact",
          first_body(sections, "Impact") || "If this risk materializes, it will slow delivery, weaken assurance, or leave the current initiative with less explicit control than intended."
        ],
        [
          "Current Handling",
          first_body(sections, "Current Handling", "Disposition", "Mitigation Strategy") || default_risk_handling
        ],
        [
          "Execution Context",
          first_body(sections, "Execution Context") || execution_context_body(entry, owner_repo, top_epic, delivery_team, iteration)
        ]
      ]
    when "Feature"
      [
        [
          "What This Achieves",
          first_body(sections, "What This Achieves", "Delivery Outcome", "Feature Outcome", "Purpose") || clean_subject(entry.subject)
        ],
        [
          "Benefit Hypothesis",
          first_body(sections, "Benefit Hypothesis", "Current Purpose", "Runway Need") || default_benefit(entry, top_epic)
        ],
        [
          "Scope Boundaries",
          first_body(sections, "Scope Boundaries", "Scope") || default_scope_boundaries(entry)
        ],
        [
          "Execution Context",
          first_body(sections, "Execution Context") || execution_context_body(entry, owner_repo, top_epic, delivery_team, iteration)
        ]
      ]
    when "Enabler"
      [
        [
          "What This Enables",
          first_body(sections, "What This Enables", "Delivery Outcome", "Purpose") || clean_subject(entry.subject)
        ],
        [
          "Benefit Hypothesis",
          first_body(sections, "Benefit Hypothesis", "Runway Need", "Current Purpose") || default_benefit(entry, top_epic)
        ],
        [
          "Scope Boundaries",
          first_body(sections, "Scope Boundaries", "Scope") || default_scope_boundaries(entry)
        ],
        [
          "Execution Context",
          first_body(sections, "Execution Context") || execution_context_body(entry, owner_repo, top_epic, delivery_team, iteration)
        ]
      ]
    when "Milestone"
      [
        [
          "Exit Condition",
          first_body(sections, "Exit Condition", "Evidence Expectation", "Ready Condition") || default_evidence_expectation(entry, top_epic)
        ],
        [
          "Execution Context",
          first_body(sections, "Execution Context") || execution_context_body(entry, owner_repo, top_epic, delivery_team, iteration)
        ]
      ]
    else
      [
        [
          "What This Achieves",
          first_body(sections, "What This Achieves", "Concrete Output", "Expected Output", "Purpose") || clean_subject(entry.subject)
        ],
        [
          "Why This Matters Now",
          first_body(sections, "Why This Matters Now", "Current Purpose", "Ready Condition") || default_why_now(entry, top_epic)
        ],
        [
          "Evidence Expectation",
          first_body(sections, "Evidence Expectation", "Exit Condition") || default_evidence_expectation(entry, top_epic)
        ],
        [
          "Execution Context",
          first_body(sections, "Execution Context") || execution_context_body(entry, owner_repo, top_epic, delivery_team, iteration)
        ]
      ]
    end

  render_sections(normalized_sections + preserved)
end

work_packages = all_work_packages.select do |entry|
  next true if TARGET_EPIC_ID.nil?

  top_epic = top_epic_for(entry, by_id)
  entry.id == TARGET_EPIC_ID || top_epic&.id == TARGET_EPIC_ID
end

changes = []

work_packages.each do |entry|
  top_epic = top_epic_for(entry, by_id)
  owner_repo = owner_repo_for(entry, top_epic)
  owner_repo_field = custom_fields.fetch("Owner Repo")
  current_owner_repo = field_value(entry, owner_repo_field)

  delivery_team_field = custom_fields["Delivery Team"]
  iteration_field = custom_fields["Iteration"]
  acceptance_field = custom_fields["Acceptance Criteria"]
  dor_field = custom_fields["Definition of Ready"]
  dod_field = custom_fields["Definition of Done"]

  current_delivery_team = delivery_team_field ? field_value(entry, delivery_team_field) : nil
  current_iteration = iteration_field ? field_value(entry, iteration_field) : nil

  changed = {}

  if owner_repo_field.types.include?(entry.type) && current_owner_repo != owner_repo
    set_field!(entry, owner_repo_field, owner_repo)
    changed[:owner_repo] = { from: current_owner_repo, to: owner_repo }
  end

  if entry.id == 87
    sponsor_field = custom_fields.fetch("Sponsor")
    current_sponsor = field_value(entry, sponsor_field)
    if current_sponsor.blank?
      set_field!(entry, sponsor_field, "Dev Integration Admin")
      changed[:sponsor] = { from: current_sponsor, to: "Dev Integration Admin" }
    end
  end

  if ACTIVE_OR_OPEN_STATUSES.include?(entry.status&.name)
    current_assignee = entry.respond_to?(:assigned_to) ? entry.assigned_to : entry.try(:assignee)
    if current_assignee.nil?
      if entry.respond_to?(:assigned_to_id=)
        entry.assigned_to_id = author.id
      elsif entry.respond_to?(:assigned_to=)
        entry.assigned_to = author
      elsif entry.respond_to?(:assignee=)
        entry.assignee = author
      end
      changed[:assignee] = { from: nil, to: author.login }
      current_assignee = author
    end

    if entry.respond_to?(:responsible) && entry.responsible.nil?
      if entry.respond_to?(:responsible_id=)
        entry.responsible_id = current_assignee&.id || author.id
      else
        entry.responsible = current_assignee || author
      end
      changed[:responsible] = { from: nil, to: current_assignee&.login }
    end
  end

  if entry.status&.name.in?(OpenprojectDeliveryArtCustomFieldSupport::ACTIVE_EXECUTION_CONTRACT_STATUSES)
    if delivery_team_field&.types&.include?(entry.type) && current_delivery_team.blank?
      desired_delivery_team = default_delivery_team(owner_repo)
      set_field!(entry, delivery_team_field, desired_delivery_team)
      current_delivery_team = desired_delivery_team
      changed[:delivery_team] = { from: nil, to: desired_delivery_team }
    end

    if iteration_field&.types&.include?(entry.type) && current_iteration.blank?
      desired_iteration = default_iteration(entry)
      set_field!(entry, iteration_field, desired_iteration)
      current_iteration = desired_iteration
      changed[:iteration] = { from: nil, to: desired_iteration }
    end

    if acceptance_field&.types&.include?(entry.type) && field_value(entry, acceptance_field).blank?
      desired = default_acceptance_criteria(entry)
      set_field!(entry, acceptance_field, desired)
      changed[:acceptance_criteria] = { from: nil, to: desired }
    end

    if dor_field&.types&.include?(entry.type) && field_value(entry, dor_field).blank?
      desired = default_definition_of_ready(entry)
      set_field!(entry, dor_field, desired)
      changed[:definition_of_ready] = { from: nil, to: desired }
    end

    if dod_field&.types&.include?(entry.type) && field_value(entry, dod_field).blank?
      desired = default_definition_of_done(entry)
      set_field!(entry, dod_field, desired)
      changed[:definition_of_done] = { from: nil, to: desired }
    end
  end

  current_headings = OpenprojectDeliveryArtCustomFieldSupport.description_headings(entry: entry)
  desired_description = normalize_description(
    entry,
    owner_repo: owner_repo,
    top_epic: top_epic,
    delivery_team: current_delivery_team,
    iteration: current_iteration,
    preserve_done_sections: entry.status&.name == DONE_STATUS
  )

  current_description = entry.description.to_s.strip
  if desired_description.present? && current_description != desired_description
    entry.description = desired_description
    changed[:description] = {
      from_headings: current_headings,
      to_headings: section_pairs(desired_description).map(&:first)
    }
  end

  next unless entry.changed? || entry.custom_values.any?(&:changed?)

  entry.save!
  entry.reload
  changes << {
    id: entry.id,
    subject: entry.subject,
    status: entry.status&.name,
    owner_repo: field_value(entry, owner_repo_field),
    description_headings: OpenprojectDeliveryArtCustomFieldSupport.description_headings(entry: entry),
    changed: changed.keys.sort
  }
end

puts JSON.pretty_generate(
  summary: {
    project: project.identifier,
    target_epic_id: TARGET_EPIC_ID,
    changed_count: changes.length
  },
  changed_work_packages: changes
)
