# frozen_string_literal: true

require "json"
require_relative "openproject_delivery_art_custom_field_support"

target_epic_id = Integer(ENV.fetch("TARGET_EPIC_ID"))
include_done = ENV.fetch("INCLUDE_DONE", "true") == "true"
include_inactive = ENV.fetch("INCLUDE_INACTIVE", "false") == "true"
inactive_statuses = %w[retired].freeze
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)

project = Project.find_by!(identifier: delivery_project_identifier)
epic = WorkPackage.find(target_epic_id)

unless epic.project_id == project.id
  raise "Epic #{target_epic_id} is not in project #{delivery_project_identifier}"
end

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
  "WSJF Score",
  "PI Objective Type",
  "PI Objective Review Outcome",
  "Planned Business Value",
  "Actual Business Value",
  "ROAM State",
  "Risk Owner",
  "Risk Review Date",
  "Risk Disposition"
]

custom_fields = project.work_package_custom_fields.where(name: blocker_field_names + inactive_field_names + execution_field_names).index_by(&:name)

work_packages = WorkPackage.where(project_id: project.id).to_a
by_id = work_packages.index_by(&:id)
children_by_parent_id = Hash.new { |hash, key| hash[key] = [] }
work_packages.each do |entry|
  children_by_parent_id[entry.parent_id] << entry if entry.parent_id
end
relation_records = Relation.where(relation_type: "follows")
  .where(from_id: by_id.keys, to_id: by_id.keys)
  .order(:id)
  .to_a
depends_on_ids_by_target_id = Hash.new { |hash, key| hash[key] = [] }
required_by_ids_by_source_id = Hash.new { |hash, key| hash[key] = [] }
unresolved_dependency_ids_by_target_id = Hash.new { |hash, key| hash[key] = [] }

relation_records.each do |relation|
  depends_on_ids_by_target_id[relation.to_id] << relation.from_id
  required_by_ids_by_source_id[relation.from_id] << relation.to_id

  predecessor = by_id[relation.from_id]
  next if predecessor&.status&.name == "done"

  unresolved_dependency_ids_by_target_id[relation.to_id] << relation.from_id
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
      status: predecessor.status&.name
    },
    target: {
      id: target.id,
      record_ref: "openproject://work_packages/#{target.id}",
      subject: target.subject,
      status: target.status&.name
    }
  }
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
  unresolved_dependency_ids = unresolved_dependency_ids_by_target_id[entry.id].uniq.sort
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
    wsjf_score: read_custom_field_value.call(entry, "WSJF Score"),
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
    completion_evidence_sections: completion_state[:sections],
    description_present: entry.description.to_s.strip.present?,
    description_headings: description_headings.call(entry),
    dependency_blocked: unresolved_dependency_ids.any?,
    depends_on_work_package_ids: depends_on_ids_by_target_id[entry.id].uniq.sort,
    required_by_work_package_ids: required_by_ids_by_source_id[entry.id].uniq.sort,
    unresolved_dependency_work_package_ids: unresolved_dependency_ids,
    blocker_fields: blocker_active ? blocker_fields : nil,
    inactive_scope_fields: (inactive_fields_present || ["parked", *inactive_statuses].include?(entry.status&.name)) ? inactive_fields : nil
  }
end

build_tree = lambda do |entry|
  children = children_by_parent_id[entry.id]
    .sort_by { |child| [child.type&.position || 0, child.id] }
    .map { |child| build_tree.call(child) }

  summary = node_summary.call(entry)
  summary[:children] = children
  summary
end

filter_tree = lambda do |node|
  return nil if node[:id] != epic.id && !include_done && node[:status] == "done"
  return nil if node[:id] != epic.id && !include_inactive && inactive_statuses.include?(node[:status])

  filtered_children = node.fetch(:children)
    .map { |child| filter_tree.call(child) }
    .compact

  node.merge(children: filtered_children)
end

full_tree = build_tree.call(epic)
root_tree = filter_tree.call(full_tree)

flatten_tree = lambda do |node|
  [node] + node.fetch(:children).flat_map { |child| flatten_tree.call(child) }
end

all_nodes = flatten_tree.call(full_tree)
descendant_nodes = all_nodes.reject { |node| node[:id] == epic.id }

counts = lambda do |nodes, key|
  nodes.each_with_object(Hash.new(0)) do |node, result|
    value = node[key]
    value = "_none_" if value.nil? || value == ""
    result[value] += 1
  end.sort.to_h
end

blocked_items = descendant_nodes.select { |node| node[:blocked] }
parked_items = descendant_nodes.select { |node| node[:status] == "parked" }
retired_items = descendant_nodes.select { |node| node[:status] == "retired" }
inactive_items = descendant_nodes.select { |node| inactive_statuses.include?(node[:status]) }
completed_without_evidence = descendant_nodes.select do |node|
  node[:status] == "done" && !node[:completion_evidence_present]
end
ready_without_contract = descendant_nodes.select do |node|
  node[:status] == "ready" && node[:ready_contract_applicable] && !node[:ready_contract_satisfied]
end
pi_objectives = descendant_nodes.select { |node| node[:type] == "PI Objective" }
risks = descendant_nodes.select { |node| node[:type] == "Risk" }
dependency_relations = relation_records.map { |relation| dependency_relation_summary.call(relation) }.compact
unresolved_dependency_relations = dependency_relations.select { |relation| relation[:unresolved] }

result = {
  epic: node_summary.call(epic),
  summary: {
    include_done: include_done,
    include_inactive: include_inactive,
    total_items: descendant_nodes.length,
    parked_count: parked_items.length,
    retired_count: retired_items.length,
    inactive_count: retired_items.length,
    blocked_count: blocked_items.length,
    ready_without_contract_count: ready_without_contract.length,
    completed_without_evidence_count: completed_without_evidence.length,
    pi_objective_count: pi_objectives.length,
    risk_count: risks.length,
    dependency_count: dependency_relations.length,
    dependency_blocked_count: descendant_nodes.count { |node| node[:dependency_blocked] },
    unresolved_dependency_count: unresolved_dependency_relations.length,
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
  parked_items: parked_items,
  retired_items: retired_items,
  blocked_items: blocked_items,
  ready_without_contract: ready_without_contract,
  completed_without_evidence: completed_without_evidence,
  pi_objectives: pi_objectives,
  risks: risks,
  dependency_relations: dependency_relations,
  unresolved_dependency_relations: unresolved_dependency_relations,
  execution_tree: root_tree
}

puts JSON.pretty_generate(result)
