# frozen_string_literal: true

require "json"
require_relative "openproject_delivery_art_custom_field_support"

target_epic_id = Integer(ENV.fetch("TARGET_EPIC_ID"))
include_done = ENV.fetch("INCLUDE_DONE", "false") == "true"
include_inactive = ENV.fetch("INCLUDE_INACTIVE", "false") == "true"
inactive_statuses = %w[retired].freeze
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)

READY_REQUIRED_FIELD_NAMES_BY_TYPE = {
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
}.freeze

project = Project.find_by!(identifier: delivery_project_identifier)
epic = WorkPackage.find(target_epic_id)

unless epic.project_id == project.id
  raise "Epic #{target_epic_id} is not in project #{delivery_project_identifier}"
end

field_names = [
  "Delivery Team",
  "Iteration",
  "Acceptance Criteria",
  "Definition of Ready",
  "Definition of Done",
  "PI Objective Type",
  "Planned Business Value",
  "Actual Business Value",
  "ROAM State",
  "Risk Owner",
  "Risk Review Date",
  "Risk Disposition"
]
custom_fields = project.work_package_custom_fields.where(name: field_names).index_by(&:name)

work_packages = WorkPackage.where(project_id: project.id).includes(:type, :status, :version).to_a
by_id = work_packages.index_by(&:id)
children_by_parent_id = Hash.new { |hash, key| hash[key] = [] }
work_packages.each do |entry|
  children_by_parent_id[entry.parent_id] << entry if entry.parent_id
end

read_custom_field_value = lambda do |entry, field_name|
  field = custom_fields[field_name]
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

ready_contract_state = lambda do |entry|
  required_field_names = READY_REQUIRED_FIELD_NAMES_BY_TYPE.fetch(entry.type&.name, [])
  missing_field_names = required_field_names.reject do |field_name|
    read_custom_field_value.call(entry, field_name).present?
  end
  {
    applicable: required_field_names.any?,
    satisfied: missing_field_names.empty?,
    missing_fields: missing_field_names
  }
end

build_descendants = lambda do |parent_id|
  children_by_parent_id[parent_id]
    .sort_by { |child| [child.type&.position || 0, child.id] }
    .flat_map do |child|
      [child] + build_descendants.call(child.id)
    end
end

counts = lambda do |items, key|
  items.each_with_object(Hash.new(0)) do |item, result|
    value = item[key]
    value = "_none_" if value.nil? || value == ""
    result[value] += 1
  end.sort.to_h
end

round_average = lambda do |items, key|
  values = items.filter_map do |item|
    value = item[key]
    next nil if value.nil?

    value.to_f
  end
  return nil if values.empty?

  (values.sum / values.length.to_f).round(2)
end

sum_metric = lambda do |items, key|
  items.sum { |item| item[key].to_f }.round(2)
end

descendants = build_descendants.call(epic.id)
descendants = descendants.reject { |entry| entry.status&.name == "done" } unless include_done
descendants = descendants.reject { |entry| inactive_statuses.include?(entry.status&.name) } unless include_inactive

planning_items = descendants.map do |entry|
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
    estimated_work: entry.respond_to?(:estimated_hours) ? entry.estimated_hours : nil,
    remaining_work: entry.respond_to?(:remaining_hours) ? entry.remaining_hours : nil,
    percent_complete: entry.respond_to?(:done_ratio) ? entry.done_ratio : nil,
    start_date: entry.respond_to?(:start_date) ? entry.start_date&.iso8601 : nil,
    due_date: entry.respond_to?(:due_date) ? entry.due_date&.iso8601 : nil,
    ready_contract_applicable: ready_state[:applicable],
    ready_contract_satisfied: ready_state[:satisfied],
    ready_contract_missing_fields: ready_state[:missing_fields]
  }
end

group_summary = lambda do |items|
  {
    count: items.length,
    by_status: counts.call(items, :status),
    by_type: counts.call(items, :type),
    by_target_pi: counts.call(items, :target_pi),
    estimated_work_total: sum_metric.call(items, :estimated_work),
    remaining_work_total: sum_metric.call(items, :remaining_work),
    average_percent_complete: round_average.call(items, :percent_complete),
    ready_without_contract_count: items.count do |item|
      item[:status] == "ready" && item[:ready_contract_applicable] && !item[:ready_contract_satisfied]
    end,
    items: items.map do |item|
      {
        id: item[:id],
        record_ref: item[:record_ref],
        subject: item[:subject],
        type: item[:type],
        status: item[:status],
        target_pi: item[:target_pi],
        assignee_login: item[:assignee_login],
        estimated_work: item[:estimated_work],
        remaining_work: item[:remaining_work],
        percent_complete: item[:percent_complete]
      }
    end
  }
end

by_delivery_team = planning_items
  .group_by { |item| item[:delivery_team].presence || "_none_" }
  .sort
  .to_h do |team_name, items|
    [team_name, group_summary.call(items)]
  end

by_iteration = planning_items
  .group_by { |item| item[:iteration].presence || "_none_" }
  .sort
  .to_h do |iteration_name, items|
    [iteration_name, group_summary.call(items)]
  end

team_iteration_matrix = planning_items
  .group_by { |item| [item[:delivery_team].presence || "_none_", item[:iteration].presence || "_none_"] }
  .sort_by { |(team_name, iteration_name), _| [team_name, iteration_name] }
  .map do |(team_name, iteration_name), items|
    {
      delivery_team: team_name,
      iteration: iteration_name
    }.merge(group_summary.call(items))
  end

result = {
  epic: {
    id: epic.id,
    record_ref: "openproject://work_packages/#{epic.id}",
    subject: epic.subject,
    status: epic.status&.name,
    target_pi: work_package_version_name.call(epic)
  },
  summary: {
    include_done: include_done,
    include_inactive: include_inactive,
    total_items: planning_items.length,
    by_status: counts.call(planning_items, :status),
    by_type: counts.call(planning_items, :type),
    by_target_pi: counts.call(planning_items, :target_pi),
    by_assignee: counts.call(planning_items, :assignee_login),
    ready_without_contract_count: planning_items.count do |item|
      item[:status] == "ready" && item[:ready_contract_applicable] && !item[:ready_contract_satisfied]
    end,
    estimated_work_total: sum_metric.call(planning_items, :estimated_work),
    remaining_work_total: sum_metric.call(planning_items, :remaining_work),
    average_percent_complete: round_average.call(planning_items, :percent_complete)
  },
  by_delivery_team: by_delivery_team,
  by_iteration: by_iteration,
  team_iteration_matrix: team_iteration_matrix
}

puts JSON.pretty_generate(result)
