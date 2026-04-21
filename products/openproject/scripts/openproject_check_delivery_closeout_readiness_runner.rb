# frozen_string_literal: true

require "json"

$stdout.sync = true

target_epic_id = Integer(ENV.fetch("TARGET_EPIC_ID"))
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

custom_fields = project.work_package_custom_fields.where(name: blocker_field_names + inactive_field_names).index_by(&:name)
inactive_statuses = %w[parked retired].freeze

work_packages = WorkPackage.where(project_id: project.id).to_a
children_by_parent_id = Hash.new { |hash, key| hash[key] = [] }
work_packages.each do |entry|
  children_by_parent_id[entry.parent_id] << entry if entry.parent_id
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
    value = field ? entry.custom_value_for(field)&.value.presence : nil
    [field_name, value]
  end
end

read_inactive_fields = lambda do |entry|
  inactive_field_names.to_h do |field_name|
    field = custom_fields[field_name]
    value = field ? entry.custom_value_for(field)&.value.presence : nil
    [field_name, value]
  end
end

completion_headings = [
  "Completion Summary",
  "Changed Surfaces",
  "Test Result Evidence",
  "Validation Evidence"
]

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
  {
    id: entry.id,
    record_ref: "openproject://work_packages/#{entry.id}",
    parent_id: entry.parent_id,
    subject: entry.subject,
    type: entry.type&.name,
    status: entry.status&.name,
    target_pi: work_package_version_name.call(entry),
    assignee_login: work_package_assignee_login.call(entry),
    attachment_count: entry.attachments.count,
    attachment_filenames: entry.attachments.order(:id).map(&:filename),
    blocked: blocker_active || entry.status&.name == "blocked",
    completion_evidence_present: completion_state[:present],
    completion_evidence_sections: completion_state[:sections],
    blocker_fields: blocker_active ? blocker_fields : nil,
    inactive_scope_fields: (inactive_fields_present || inactive_statuses.include?(entry.status&.name)) ? inactive_fields : nil
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

flatten_tree = lambda do |node|
  [node] + node.fetch(:children).flat_map { |child| flatten_tree.call(child) }
end

root_tree = build_tree.call(epic)
all_nodes = flatten_tree.call(root_tree)
descendant_nodes = all_nodes.reject { |node| node[:id] == epic.id }

parked_items = descendant_nodes.select { |node| node[:status] == "parked" }
retired_items = descendant_nodes.select { |node| node[:status] == "retired" }
active_open_items = descendant_nodes.reject { |node| ["done", *inactive_statuses].include?(node[:status]) }
blocked_items = descendant_nodes.select { |node| node[:blocked] }
completed_without_evidence = descendant_nodes.select do |node|
  node[:status] == "done" && !node[:completion_evidence_present]
end
reasons = []
reasons << "epic_not_done" if epic.status&.name != "done"
reasons << "open_descendants_present" if active_open_items.any?
reasons << "blocked_items_present" if blocked_items.any?
reasons << "completion_evidence_missing" if completed_without_evidence.any?

counts = lambda do |nodes, key|
  nodes.each_with_object(Hash.new(0)) do |node, result|
    value = node[key]
    value = "_none_" if value.nil? || value == ""
    result[value] += 1
  end.sort.to_h
end

result = {
  epic: node_summary.call(epic),
  ready_for_closeout: reasons.empty?,
  reasons: reasons,
  summary: {
    total_descendants: descendant_nodes.length,
    open_descendant_count: active_open_items.length,
    parked_count: parked_items.length,
    retired_count: retired_items.length,
    blocked_count: blocked_items.length,
    completed_without_evidence_count: completed_without_evidence.length,
    by_status: counts.call(descendant_nodes, :status),
    by_type: counts.call(descendant_nodes, :type),
    by_target_pi: counts.call(descendant_nodes, :target_pi),
    by_assignee: counts.call(descendant_nodes, :assignee_login)
  },
  open_descendants: active_open_items,
  parked_items: parked_items,
  retired_items: retired_items,
  blocked_items: blocked_items,
  completed_without_evidence: completed_without_evidence
}

puts JSON.pretty_generate(result)
exit 2 unless result[:ready_for_closeout]
