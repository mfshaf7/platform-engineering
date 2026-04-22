# frozen_string_literal: true

require "json"
require_relative "openproject_delivery_art_custom_field_support"

include_done = ENV.fetch("INCLUDE_DONE", "true") == "true"
include_inactive = ENV.fetch("INCLUDE_INACTIVE", "false") == "true"
inactive_statuses = %w[retired].freeze
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)

project = Project.find_by!(identifier: delivery_project_identifier)

blocker_field_names = [
  "Blocker Statement",
  "Blocker Impact",
  "Blocker Owner",
  "Blocker Discovered On",
  "Blocker Decision Path",
  "Blocker Justification",
  "Blocker Follow-Up Owner",
  "Blocker Review Date"
]
inactive_field_names = [
  "Parking Decision",
  "Parking Reason",
  "Parking Review Date",
  "Retirement Reason"
]

governance_field_names = [
  "PM² Phase",
  "Sponsor",
  "Business Objective",
  "Success Criteria",
  "System Demo Evidence",
  "Inspect & Adapt Actions",
  "NFR Category"
]
ready_required_field_names_by_type = {
  "Feature" => ["Delivery Team", "Iteration", "Acceptance Criteria", "Definition of Ready", "Definition of Done"],
  "Enabler" => ["Delivery Team", "Iteration", "Acceptance Criteria", "Definition of Ready", "Definition of Done"],
  "User story" => ["Delivery Team", "Iteration", "Acceptance Criteria", "Definition of Ready", "Definition of Done"],
  "Task" => ["Delivery Team", "Iteration", "Acceptance Criteria", "Definition of Ready", "Definition of Done"],
  "PI Objective" => [
    "Delivery Team",
    "Iteration",
    "Acceptance Criteria",
    "Definition of Ready",
    "Definition of Done",
    "PI Objective Type",
    "Planned Business Value",
    "Actual Business Value"
  ],
  "Risk" => ["Delivery Team", "Iteration", "ROAM State", "Risk Owner", "Risk Review Date", "Risk Disposition"]
}
execution_field_names = [
  "Delivery Team",
  "Iteration",
  "Acceptance Criteria",
  "Definition of Ready",
  "Definition of Done",
  "NFR Category",
  "PI Objective Type",
  "PI Objective Review Outcome",
  "Planned Business Value",
  "Actual Business Value",
  "ROAM State",
  "Risk Owner",
  "Risk Review Date",
  "Risk Disposition"
]

custom_fields = project.work_package_custom_fields
  .where(name: blocker_field_names + inactive_field_names + governance_field_names + execution_field_names)
  .index_by(&:name)

work_packages = WorkPackage.where(project_id: project.id).includes(:type, :status, :version).to_a
by_id = work_packages.index_by(&:id)
children_by_parent_id = Hash.new { |hash, key| hash[key] = [] }
work_packages.each do |entry|
  children_by_parent_id[entry.parent_id] << entry if entry.parent_id
end
relation_records = Relation.where(relation_type: "follows")
  .where(from_id: by_id.keys, to_id: by_id.keys)
  .order(:id)
  .to_a
top_level_epic_id_by_work_package_id = {}
top_level_epic_id_for = lambda do |work_package_or_id|
  work_package_id = work_package_or_id.is_a?(WorkPackage) ? work_package_or_id.id : work_package_or_id
  return top_level_epic_id_by_work_package_id[work_package_id] if top_level_epic_id_by_work_package_id.key?(work_package_id)

  current = work_package_or_id.is_a?(WorkPackage) ? work_package_or_id : by_id[work_package_id]
  visited = {}
  while current && current.parent_id && !visited[current.id]
    visited[current.id] = true
    parent = by_id[current.parent_id]
    break if parent.nil?

    current = parent
  end

  top_level_epic_id_by_work_package_id[work_package_id] = current&.type&.name == "Epic" ? current.id : nil
end

work_package_version_name = lambda do |entry|
  if entry.respond_to?(:version)
    entry.version&.name
  elsif entry.respond_to?(:fixed_version)
    entry.fixed_version&.name
  end
end

work_package_assignee_login = lambda do |entry|
  if entry.respond_to?(:assigned_to)
    entry.assigned_to&.respond_to?(:login) ? entry.assigned_to.login : nil
  elsif entry.respond_to?(:assignee)
    entry.assignee&.respond_to?(:login) ? entry.assignee.login : nil
  end
end

read_blocker_fields = lambda do |entry|
  blocker_field_names.to_h do |field_name|
    field = custom_fields[field_name]
    value = OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: entry, field: field)
    [field_name, value]
  end
end

read_inactive_fields = lambda do |entry|
  inactive_field_names.to_h do |field_name|
    field = custom_fields[field_name]
    value = OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: entry, field: field)
    [field_name, value]
  end
end

read_governance_field = lambda do |entry, field_name|
  field = custom_fields[field_name]
  OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: entry, field: field)
end

read_custom_field_value = lambda do |entry, field_name|
  field = custom_fields[field_name]
  OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: entry, field: field)
end

ready_contract_state = lambda do |entry|
  required_field_names = ready_required_field_names_by_type.fetch(entry.type&.name, [])
  missing_field_names = required_field_names.reject do |field_name|
    read_custom_field_value.call(entry, field_name).present?
  end
  {
    applicable: required_field_names.any?,
    satisfied: missing_field_names.empty?,
    missing_fields: missing_field_names
  }
end

completion_headings = [
  "Completion Summary",
  "Changed Surfaces",
  "Test Result Evidence",
  "Validation Evidence"
]

description_headings = lambda do |entry|
  entry.description.to_s.scan(/^## ([^\n]+)$/).flatten
end

completion_evidence_state = lambda do |entry|
  rendered = entry.description.to_s
  section_map = completion_headings.to_h do |heading|
    match = rendered.match(/^## #{Regexp.escape(heading)}\n(.*?)(?=^## |\z)/m)
    body = match ? match[1].to_s.strip : nil
    substantive = body.present? && !body.match?(/\ANot yet complete\.?\z/i)
    [heading, {
      present: !body.nil?,
      substantive: substantive
    }]
  end
  {
    present: section_map.values.all? { |entry_state| entry_state[:substantive] },
    sections: section_map
  }
end

node_summary = lambda do |entry|
  blocker_fields = read_blocker_fields.call(entry)
  blocker_active = blocker_fields.values.any?(&:present?)
  inactive_fields = read_inactive_fields.call(entry)
  inactive_fields_present = inactive_fields.values.any?(&:present?)
  completion_state = completion_evidence_state.call(entry)
  ready_state = ready_contract_state.call(entry)
  {
    id: entry.id,
    record_ref: "openproject://work_packages/#{entry.id}",
    parent_id: entry.parent_id,
    subject: entry.subject,
    type: entry.type&.name,
    status: entry.status&.name,
    target_pi: work_package_version_name.call(entry),
    assignee_login: work_package_assignee_login.call(entry),
    delivery_team: read_custom_field_value.call(entry, "Delivery Team"),
    iteration: read_custom_field_value.call(entry, "Iteration"),
    start_date: entry.respond_to?(:start_date) ? entry.start_date&.iso8601 : nil,
    due_date: entry.respond_to?(:due_date) ? entry.due_date&.iso8601 : nil,
    estimated_work: entry.respond_to?(:estimated_hours) ? entry.estimated_hours : nil,
    remaining_work: entry.respond_to?(:remaining_hours) ? entry.remaining_hours : nil,
    percent_complete: entry.respond_to?(:done_ratio) ? entry.done_ratio : nil,
    nfr_category: read_custom_field_value.call(entry, "NFR Category"),
    pi_objective_type: read_custom_field_value.call(entry, "PI Objective Type"),
    pi_objective_review_outcome: read_custom_field_value.call(entry, "PI Objective Review Outcome"),
    planned_business_value: read_custom_field_value.call(entry, "Planned Business Value"),
    actual_business_value: read_custom_field_value.call(entry, "Actual Business Value"),
    roam_state: read_custom_field_value.call(entry, "ROAM State"),
    risk_owner: read_custom_field_value.call(entry, "Risk Owner"),
    risk_review_date: read_custom_field_value.call(entry, "Risk Review Date"),
    attachment_count: entry.attachments.count,
    attachment_filenames: entry.attachments.order(:id).map(&:filename),
    blocked: blocker_active || entry.status&.name == "blocked",
    ready_contract_applicable: ready_state[:applicable],
    ready_contract_satisfied: ready_state[:satisfied],
    ready_contract_missing_fields: ready_state[:missing_fields],
    completion_evidence_present: completion_state[:present],
    description_present: entry.description.to_s.strip.present?,
    description_headings: description_headings.call(entry),
    blocker_fields: blocker_active ? blocker_fields : nil,
    inactive_scope_fields: (inactive_fields_present || ["parked", *inactive_statuses].include?(entry.status&.name)) ? inactive_fields : nil
  }
end

flatten_tree = lambda do |node|
  [node] + node.fetch(:children).flat_map { |child| flatten_tree.call(child) }
end

build_tree = lambda do |entry|
  children = children_by_parent_id[entry.id]
    .sort_by { |child| [child.type&.position || 0, child.id] }
    .map { |child| build_tree.call(child) }

  summary = node_summary.call(entry)
  summary[:children] = children
  summary
end

counts = lambda do |nodes, key|
  nodes.each_with_object(Hash.new(0)) do |node, result|
    value = node[key]
    value = "_none_" if value.nil? || value == ""
    result[value] += 1
  end.sort.to_h
end

dependency_relation_summary = lambda do |relation|
  predecessor = by_id[relation.from_id]
  target = by_id[relation.to_id]
  return nil if predecessor.nil? || target.nil?

  {
    id: relation.id,
    relation_type: relation.relation_type,
    lag: relation.lag,
    description: relation.description.presence,
    unresolved: predecessor.status&.name != "done",
    depends_on: {
      id: predecessor.id,
      record_ref: "openproject://work_packages/#{predecessor.id}",
      subject: predecessor.subject,
      status: predecessor.status&.name,
      top_level_epic_id: top_level_epic_id_for.call(predecessor)
    },
    target: {
      id: target.id,
      record_ref: "openproject://work_packages/#{target.id}",
      subject: target.subject,
      status: target.status&.name,
      top_level_epic_id: top_level_epic_id_for.call(target)
    }
  }
end

top_level_epics = work_packages
  .select { |entry| entry.parent_id.nil? && entry.type&.name == "Epic" }
  .sort_by(&:id)

initiatives = top_level_epics.filter_map do |epic|
  root_tree = build_tree.call(epic)
  all_nodes = flatten_tree.call(root_tree)
  descendant_nodes = all_nodes.reject { |node| node[:id] == epic.id }
  subtree_ids = all_nodes.map { |node| node[:id] }
  parked_items = descendant_nodes.select { |node| node[:status] == "parked" }
  retired_items = descendant_nodes.select { |node| node[:status] == "retired" }
  open_descendants = descendant_nodes.reject { |node| ["done", *inactive_statuses].include?(node[:status]) }
  blocked_items = descendant_nodes.select { |node| node[:blocked] }
  ready_without_contract = descendant_nodes.select do |node|
    node[:status] == "ready" && node[:ready_contract_applicable] && !node[:ready_contract_satisfied]
  end
  completed_without_evidence = descendant_nodes.select do |node|
    node[:status] == "done" && !node[:completion_evidence_present]
  end
  pi_objectives = descendant_nodes.select { |node| node[:type] == "PI Objective" }
  risks = descendant_nodes.select { |node| node[:type] == "Risk" }
  dependency_relations = relation_records
    .select { |relation| subtree_ids.include?(relation.from_id) || subtree_ids.include?(relation.to_id) }
    .map { |relation| dependency_relation_summary.call(relation) }
    .compact
  internal_dependency_relations = dependency_relations.select do |relation|
    subtree_ids.include?(relation.dig(:depends_on, :id)) && subtree_ids.include?(relation.dig(:target, :id))
  end
  external_dependency_relations = dependency_relations - internal_dependency_relations
  unresolved_dependency_relations = dependency_relations.select { |relation| relation[:unresolved] }
  pm2_phase = read_governance_field.call(epic, "PM² Phase")
  sponsor = read_governance_field.call(epic, "Sponsor")
  business_objective = read_governance_field.call(epic, "Business Objective")
  success_criteria = read_governance_field.call(epic, "Success Criteria")
  system_demo_evidence = read_governance_field.call(epic, "System Demo Evidence")
  inspect_and_adapt_actions = read_governance_field.call(epic, "Inspect & Adapt Actions")
  initiative_nfr_category = read_governance_field.call(epic, "NFR Category")

  closeout_reasons = []
  closeout_reasons << "epic_not_done" unless epic.status&.name == "done"
  closeout_reasons << "open_descendants_present" if open_descendants.any?
  closeout_reasons << "blocked_items_present" if blocked_items.any?
  closeout_reasons << "completion_evidence_missing" if completed_without_evidence.any?
  closeout_ready = closeout_reasons.empty?

  next if !include_done && epic.status&.name == "done"
  next if !include_inactive && inactive_statuses.include?(epic.status&.name)

  {
    epic: node_summary.call(epic).merge(
      pm2_phase: pm2_phase,
      sponsor: sponsor,
      nfr_category: initiative_nfr_category,
      business_objective_present: business_objective.present?,
      success_criteria_present: success_criteria.present?,
      system_demo_evidence_present: system_demo_evidence.present?,
      inspect_and_adapt_actions_present: inspect_and_adapt_actions.present?
    ),
    execution_summary: {
      total_descendants: descendant_nodes.length,
      open_descendant_count: open_descendants.length,
      parked_count: parked_items.length,
      retired_count: retired_items.length,
      inactive_count: retired_items.length,
      blocked_count: blocked_items.length,
      ready_without_contract_count: ready_without_contract.length,
      completed_without_evidence_count: completed_without_evidence.length,
      pi_objective_count: pi_objectives.length,
      risk_count: risks.length,
      dependency_count: dependency_relations.length,
      unresolved_dependency_count: unresolved_dependency_relations.length,
      cross_initiative_dependency_count: external_dependency_relations.length,
      by_status: counts.call(descendant_nodes, :status),
      by_type: counts.call(descendant_nodes, :type),
      by_target_pi: counts.call(descendant_nodes, :target_pi),
      by_assignee: counts.call(descendant_nodes, :assignee_login),
      by_delivery_team: counts.call(descendant_nodes, :delivery_team),
      by_iteration: counts.call(descendant_nodes, :iteration),
      by_roam_state: counts.call(risks, :roam_state),
      pi_objectives_by_type: counts.call(pi_objectives, :pi_objective_type),
      pi_objectives_by_review_outcome: counts.call(pi_objectives, :pi_objective_review_outcome),
      planned_business_value_total: pi_objectives.sum { |node| node[:planned_business_value].to_i },
      actual_business_value_total: pi_objectives.sum { |node| node[:actual_business_value].to_i },
      estimated_work_total: descendant_nodes.sum { |node| node[:estimated_work].to_f }.round(2),
      remaining_work_total: descendant_nodes.sum { |node| node[:remaining_work].to_f }.round(2)
    },
    closeout_ready: closeout_ready,
    closeout_reasons: closeout_reasons,
    parked_items: parked_items,
    retired_items: include_inactive ? retired_items : [],
    blocked_items: blocked_items,
    ready_without_contract: ready_without_contract,
    pi_objectives: pi_objectives,
    risks: risks,
    dependency_summary: {
      internal_relations: internal_dependency_relations.length,
      cross_initiative_relations: external_dependency_relations.length,
      unresolved_relations: unresolved_dependency_relations.length
    },
    external_dependencies: external_dependency_relations,
    _descendant_nodes: descendant_nodes
  }
end

initiative_counts = lambda do |items, key_path|
  items.each_with_object(Hash.new(0)) do |entry, result|
    value = key_path.call(entry)
    value = "_none_" if value.nil? || value == ""
    result[value] += 1
  end.sort.to_h
end

portfolio_descendants = initiatives.flat_map { |entry| entry.delete(:_descendant_nodes) }
portfolio_pi_objectives = portfolio_descendants.select { |node| node[:type] == "PI Objective" }
portfolio_risks = portfolio_descendants.select { |node| node[:type] == "Risk" }

result = {
  project: {
    identifier: project.identifier,
    name: project.name
  },
  summary: {
    include_done: include_done,
    include_inactive: include_inactive,
    total_initiatives: initiatives.length,
    active_initiatives: initiatives.count { |entry| !(["done", "parked", *inactive_statuses].include?(entry.dig(:epic, :status))) },
    parked_initiatives: initiatives.count { |entry| entry.dig(:epic, :status) == "parked" },
    retired_initiatives: initiatives.count { |entry| entry.dig(:epic, :status) == "retired" },
    blocked_initiatives: initiatives.count { |entry| entry.dig(:execution_summary, :blocked_count).to_i.positive? },
    parked_descendant_total: initiatives.sum { |entry| entry.dig(:execution_summary, :parked_count).to_i },
    retired_descendant_total: initiatives.sum { |entry| entry.dig(:execution_summary, :retired_count).to_i },
    ready_without_contract_total: initiatives.sum { |entry| entry.dig(:execution_summary, :ready_without_contract_count).to_i },
    pi_objective_total: initiatives.sum { |entry| entry.dig(:execution_summary, :pi_objective_count).to_i },
    risk_total: initiatives.sum { |entry| entry.dig(:execution_summary, :risk_count).to_i },
    dependency_count: relation_records.length,
    unresolved_dependency_count: relation_records.count { |relation| by_id[relation.from_id]&.status&.name != "done" },
    cross_initiative_dependency_count: relation_records.count do |relation|
      top_level_epic_id_for.call(relation.from_id) != top_level_epic_id_for.call(relation.to_id)
    end,
    closeout_ready_count: initiatives.count { |entry| entry[:closeout_ready] },
    system_demo_recorded_count: initiatives.count { |entry| entry.dig(:epic, :system_demo_evidence_present) },
    inspect_and_adapt_recorded_count: initiatives.count { |entry| entry.dig(:epic, :inspect_and_adapt_actions_present) },
    by_status: initiative_counts.call(initiatives, ->(entry) { entry.dig(:epic, :status) }),
    by_pm2_phase: initiative_counts.call(initiatives, ->(entry) { entry.dig(:epic, :pm2_phase) }),
    by_target_pi: initiative_counts.call(initiatives, ->(entry) { entry.dig(:epic, :target_pi) }),
    by_delivery_team: initiative_counts.call(portfolio_descendants, ->(node) { node[:delivery_team] }),
    by_iteration: initiative_counts.call(portfolio_descendants, ->(node) { node[:iteration] }),
    by_roam_state: initiative_counts.call(portfolio_risks, ->(node) { node[:roam_state] }),
    pi_objectives_by_type: initiative_counts.call(portfolio_pi_objectives, ->(node) { node[:pi_objective_type] }),
    pi_objectives_by_review_outcome: initiative_counts.call(portfolio_pi_objectives, ->(node) { node[:pi_objective_review_outcome] }),
    planned_business_value_total: portfolio_pi_objectives.sum { |node| node[:planned_business_value].to_i },
    actual_business_value_total: portfolio_pi_objectives.sum { |node| node[:actual_business_value].to_i },
    estimated_work_total: portfolio_descendants.sum { |node| node[:estimated_work].to_f }.round(2),
    remaining_work_total: portfolio_descendants.sum { |node| node[:remaining_work].to_f }.round(2)
  },
  initiatives: initiatives
}

puts JSON.pretty_generate(result)
