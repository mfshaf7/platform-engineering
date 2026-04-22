# frozen_string_literal: true

require "json"
require_relative "openproject_delivery_art_custom_field_support"

target_epic_id = Integer(ENV.fetch("TARGET_EPIC_ID"))
target_pi = ENV["TARGET_PI"]&.strip&.presence
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)

required_field_names = [
  "Delivery Team",
  "Iteration",
  "Acceptance Criteria",
  "Definition of Ready",
  "Definition of Done",
  "PI Objective Type",
  "PI Objective Review Outcome",
  "Planned Business Value",
  "Actual Business Value"
]

project = Project.find_by!(identifier: delivery_project_identifier)
epic = WorkPackage.find(target_epic_id)

unless epic.project_id == project.id
  raise "Epic #{target_epic_id} is not in project #{delivery_project_identifier}"
end

custom_fields = project.work_package_custom_fields.where(name: required_field_names).index_by(&:name)
missing_fields = required_field_names.reject { |name| custom_fields.key?(name) }
raise "Missing PI objective custom fields: #{missing_fields.join(', ')}" if missing_fields.any?

work_packages = WorkPackage.where(project_id: project.id).includes(:type, :status, :version).to_a
children_by_parent_id = Hash.new { |hash, key| hash[key] = [] }
work_packages.each do |entry|
  children_by_parent_id[entry.parent_id] << entry if entry.parent_id
end

build_descendants = lambda do |parent_id|
  children_by_parent_id[parent_id]
    .sort_by { |child| [child.type&.position || 0, child.id] }
    .flat_map do |child|
      [child] + build_descendants.call(child.id)
    end
end

read_custom_field_value = lambda do |entry, field_name|
  field = custom_fields.fetch(field_name)
  OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: entry, field: field)
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

counts = lambda do |items, key|
  items.each_with_object(Hash.new(0)) do |item, result|
    value = item[key]
    value = "_none_" if value.nil? || value == ""
    result[value] += 1
  end.sort.to_h
end

objectives = build_descendants.call(epic.id)
  .select { |entry| entry.type&.name == "PI Objective" }
  .map do |entry|
    objective = {
      id: entry.id,
      record_ref: "openproject://work_packages/#{entry.id}",
      subject: entry.subject,
      status: entry.status&.name,
      target_pi: work_package_version_name.call(entry),
      assignee_login: work_package_assignee_login.call(entry),
      delivery_team: read_custom_field_value.call(entry, "Delivery Team"),
      iteration: read_custom_field_value.call(entry, "Iteration"),
      pi_objective_type: read_custom_field_value.call(entry, "PI Objective Type"),
      pi_objective_review_outcome: read_custom_field_value.call(entry, "PI Objective Review Outcome"),
      planned_business_value: read_custom_field_value.call(entry, "Planned Business Value"),
      actual_business_value: read_custom_field_value.call(entry, "Actual Business Value"),
      acceptance_criteria_present: read_custom_field_value.call(entry, "Acceptance Criteria").present?,
      definition_of_ready_present: read_custom_field_value.call(entry, "Definition of Ready").present?,
      definition_of_done_present: read_custom_field_value.call(entry, "Definition of Done").present?,
      attachment_count: entry.attachments.count,
      attachment_filenames: entry.attachments.order(:id).map(&:filename)
    }
    objective[:business_value_delta] =
      objective[:actual_business_value].to_i - objective[:planned_business_value].to_i
    objective
  end

objectives.select! { |objective| objective[:target_pi] == target_pi } if target_pi

result = {
  epic: {
    id: epic.id,
    record_ref: "openproject://work_packages/#{epic.id}",
    subject: epic.subject,
    status: epic.status&.name
  },
  summary: {
    target_pi: target_pi,
    objective_count: objectives.length,
    committed_count: objectives.count { |objective| objective[:pi_objective_type] == "Committed" },
    stretch_count: objectives.count { |objective| objective[:pi_objective_type] == "Stretch" },
    review_recorded_count: objectives.count { |objective| objective[:pi_objective_review_outcome].present? },
    review_missing_count: objectives.count { |objective| objective[:pi_objective_review_outcome].blank? },
    missing_acceptance_criteria_count: objectives.count { |objective| !objective[:acceptance_criteria_present] },
    missing_ready_contract_count: objectives.count do |objective|
      !objective[:definition_of_ready_present] || !objective[:definition_of_done_present]
    end,
    planned_business_value_total: objectives.sum { |objective| objective[:planned_business_value].to_i },
    actual_business_value_total: objectives.sum { |objective| objective[:actual_business_value].to_i },
    business_value_delta_total: objectives.sum { |objective| objective[:business_value_delta].to_i },
    by_status: counts.call(objectives, :status),
    by_pi_objective_type: counts.call(objectives, :pi_objective_type),
    by_review_outcome: counts.call(objectives, :pi_objective_review_outcome),
    by_target_pi: counts.call(objectives, :target_pi),
    by_delivery_team: counts.call(objectives, :delivery_team),
    by_iteration: counts.call(objectives, :iteration)
  },
  objectives: objectives
}

puts JSON.pretty_generate(result)
