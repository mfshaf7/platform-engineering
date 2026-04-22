# frozen_string_literal: true

require "json"
require "date"
require_relative "openproject_delivery_art_custom_field_support"

parent_work_package_id = Integer(ENV.fetch("PARENT_WORK_PACKAGE_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
type_name = ENV.fetch("TYPE").strip
subject = ENV.fetch("SUBJECT").strip
status_name = ENV["STATUS"]&.strip&.presence
target_pi = ENV["TARGET_PI"]&.strip&.presence
assignee_login = ENV["ASSIGNEE_LOGIN"]&.strip&.presence
description = ENV["DESCRIPTION"]&.strip&.presence
start_date_raw = ENV["START_DATE"]&.strip&.presence
due_date_raw = ENV["DUE_DATE"]&.strip&.presence
estimated_work_raw = ENV["ESTIMATED_WORK"]&.strip&.presence
remaining_work_raw = ENV["REMAINING_WORK"]&.strip&.presence
percent_complete_raw = ENV["PERCENT_COMPLETE"]&.strip&.presence

CUSTOM_FIELD_ENV_SPECS = [
  { env: "DELIVERY_TEAM", field: "Delivery Team", kind: :string },
  { env: "ITERATION", field: "Iteration", kind: :string },
  { env: "ACCEPTANCE_CRITERIA", field: "Acceptance Criteria", kind: :text },
  { env: "DEFINITION_OF_READY", field: "Definition of Ready", kind: :text },
  { env: "DEFINITION_OF_DONE", field: "Definition of Done", kind: :text },
  { env: "NFR_CATEGORY", field: "NFR Category", kind: :list },
  { env: "PI_OBJECTIVE_TYPE", field: "PI Objective Type", kind: :list },
  { env: "PLANNED_BUSINESS_VALUE", field: "Planned Business Value", kind: :int },
  { env: "ACTUAL_BUSINESS_VALUE", field: "Actual Business Value", kind: :int },
  { env: "ROAM_STATE", field: "ROAM State", kind: :list },
  { env: "RISK_OWNER", field: "Risk Owner", kind: :string },
  { env: "RISK_REVIEW_DATE", field: "Risk Review Date", kind: :date },
  { env: "RISK_DISPOSITION", field: "Risk Disposition", kind: :text },
  { env: "WSJF_USER_BUSINESS_VALUE", field: "WSJF User-Business Value", kind: :int },
  { env: "WSJF_TIME_CRITICALITY", field: "WSJF Time Criticality", kind: :int },
  { env: "WSJF_RR_OE", field: "WSJF Risk Reduction / Opportunity Enablement", kind: :int },
  { env: "WSJF_JOB_SIZE", field: "WSJF Job Size", kind: :int }
].freeze

WSJF_COMPONENT_FIELDS = [
  "WSJF User-Business Value",
  "WSJF Time Criticality",
  "WSJF Risk Reduction / Opportunity Enablement",
  "WSJF Job Size"
].freeze
WSJF_SCORE_FIELD = "WSJF Score"
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
parent = WorkPackage.find(parent_work_package_id)

unless parent.project_id == project.id
  raise "Parent work package #{parent_work_package_id} is not in project #{delivery_project_identifier}"
end

author = User.admin.active.first || User.active.first
raise "No active author user is available for work package creation" unless author

type = Type.all.find { |entry| entry.name.casecmp?(type_name) }
raise "Unknown work package type #{type_name.inspect}" unless type

status =
  if status_name
    Status.find_by(name: status_name).tap do |entry|
      raise "Unknown status #{status_name.inspect}" unless entry
    end
  else
    Status.find_by!(name: "new")
  end

if status.name == "done"
  raise "Create the work item first, then use openproject-complete-delivery-work-item to mark it done with evidence"
end

duplicate = WorkPackage
  .where(project_id: project.id, parent_id: parent.id, type_id: type.id)
  .find { |candidate| candidate.subject.to_s.casecmp?(subject) }

if duplicate
  raise "A sibling work package already exists with parent #{parent.id}, type #{type.name}, and subject #{subject.inspect}"
end

default_priority = IssuePriority.where(is_default: true).first || IssuePriority.order(:position).first
raise "No default priority is available for work package creation" unless default_priority

priority = parent.priority || default_priority

version =
  if target_pi
    project.versions.find_or_initialize_by(name: target_pi).tap do |entry|
      entry.status = "open" if entry.respond_to?(:status=)
      entry.sharing = "none" if entry.respond_to?(:sharing=) && entry.sharing.blank?
      entry.save!
    end
  elsif parent.respond_to?(:version)
    parent.version
  elsif parent.respond_to?(:fixed_version)
    parent.fixed_version
  end

assignee =
  if assignee_login
    User.active.find_by(login: assignee_login).tap do |entry|
      raise "Unknown ASSIGNEE_LOGIN #{assignee_login.inspect}" unless entry
    end
  end

provided_custom_fields = CUSTOM_FIELD_ENV_SPECS.filter_map do |spec|
  value = ENV[spec[:env]]&.strip&.presence
  next if value.nil?

  [spec, value]
end

project_custom_fields = project.work_package_custom_fields.index_by(&:name)
target_pi_field = project_custom_fields["Target PI"]
raise "Missing delivery-art custom field \"Target PI\"" if target_pi_field.nil?

assign_custom_value = lambda do |entry, field, value, kind = nil|
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: entry, field: field, value: value, kind: kind)
end

custom_value_present = lambda do |entry, field|
  OpenprojectDeliveryArtCustomFieldSupport.custom_value_present?(entry: entry, field: field)
end

parse_date_value = lambda do |raw_value, label|
  Date.iso8601(raw_value)
rescue ArgumentError
  raise "#{label} must be an ISO date (YYYY-MM-DD)"
end

parse_hours_value = lambda do |raw_value, label|
  value = Float(raw_value)
  raise "#{label} must be greater than or equal to zero" if value.negative?

  value
rescue ArgumentError
  raise "#{label} must be a numeric value"
end

parse_percent_complete = lambda do |raw_value|
  value = Integer(raw_value)
  raise "PERCENT_COMPLETE must be between 0 and 100" if value.negative? || value > 100

  value
rescue ArgumentError
  raise "PERCENT_COMPLETE must be an integer between 0 and 100"
end

work_package = WorkPackage.new(
  author: author,
  parent: parent,
  priority: priority,
  project: project,
  status: status,
  subject: subject,
  type: type
)
work_package.description = description if description
if start_date_raw
  unless work_package.respond_to?(:start_date=)
    raise "This OpenProject runtime does not support start date updates through the current creation path"
  end
  work_package.start_date = parse_date_value.call(start_date_raw, "START_DATE")
end
if due_date_raw
  unless work_package.respond_to?(:due_date=)
    raise "This OpenProject runtime does not support due date updates through the current creation path"
  end
  work_package.due_date = parse_date_value.call(due_date_raw, "DUE_DATE")
end
if estimated_work_raw
  unless work_package.respond_to?(:estimated_hours=)
    raise "This OpenProject runtime does not support estimated work updates through the current creation path"
  end
  work_package.estimated_hours = parse_hours_value.call(estimated_work_raw, "ESTIMATED_WORK")
end
if remaining_work_raw
  unless work_package.respond_to?(:remaining_hours=)
    raise "This OpenProject runtime does not support remaining work updates through the current creation path"
  end
  work_package.remaining_hours = parse_hours_value.call(remaining_work_raw, "REMAINING_WORK")
end
if percent_complete_raw
  unless work_package.respond_to?(:done_ratio=)
    raise "This OpenProject runtime does not support percent complete updates through the current creation path"
  end
  work_package.done_ratio = parse_percent_complete.call(percent_complete_raw)
end
if work_package.respond_to?(:version=)
  work_package.version = version if version
elsif work_package.respond_to?(:fixed_version=)
  work_package.fixed_version = version if version
end
assign_custom_value.call(work_package, target_pi_field, version&.name) if version || target_pi
if work_package.respond_to?(:assigned_to=)
  work_package.assigned_to = assignee if assignee
elsif work_package.respond_to?(:assignee=)
  work_package.assignee = assignee if assignee
end

provided_custom_fields.each do |spec, raw_value|
  field = project_custom_fields[spec[:field]]
  raise "Missing delivery-art custom field #{spec[:field].inspect}" if field.nil?
  unless field.types.include?(type)
    raise "Custom field #{spec[:field].inspect} is not available for work package type #{type.name.inspect}"
  end

  assign_custom_value.call(work_package, field, raw_value, spec[:kind])
end

if provided_custom_fields.any? { |spec, _| WSJF_COMPONENT_FIELDS.include?(spec[:field]) }
  missing = WSJF_COMPONENT_FIELDS.reject { |field_name| project_custom_fields.key?(field_name) }
  raise "Missing WSJF custom fields: #{missing.join(', ')}" if missing.any?

  wsjf_values = WSJF_COMPONENT_FIELDS.map do |field_name|
    field = project_custom_fields.fetch(field_name)
    value = OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: field)
    raise "WSJF component #{field_name.inspect} must be provided for #{type.name}" if value.empty?
    Integer(value)
  end

  job_size = wsjf_values.last
  raise "WSJF Job Size must be greater than zero" if job_size <= 0

  wsjf_score = ((wsjf_values[0] + wsjf_values[1] + wsjf_values[2]).to_f / job_size).round(2)
  score_field = project_custom_fields[WSJF_SCORE_FIELD]
  raise "Missing delivery-art custom field #{WSJF_SCORE_FIELD.inspect}" if score_field.nil?
  raise "Custom field #{WSJF_SCORE_FIELD.inspect} is not available for work package type #{type.name.inspect}" unless score_field.types.include?(type)
  assign_custom_value.call(work_package, score_field, wsjf_score.to_s, :float)
end

if work_package.status&.name == "ready"
  required_field_names = READY_REQUIRED_FIELD_NAMES_BY_TYPE.fetch(type.name, [])
  missing_field_names = required_field_names.reject do |field_name|
    custom_value_present.call(work_package, project_custom_fields[field_name])
  end
  if missing_field_names.any?
    raise "Work package cannot be created in ready while required fields are missing: #{missing_field_names.join(', ')}"
  end
end

work_package.save!
work_package.reload

version_name =
  if work_package.respond_to?(:version)
    work_package.version&.name
  elsif work_package.respond_to?(:fixed_version)
    work_package.fixed_version&.name
  end

assignee_login_value =
  if work_package.respond_to?(:assigned_to)
    work_package.assigned_to&.respond_to?(:login) ? work_package.assigned_to.login : nil
  elsif work_package.respond_to?(:assignee)
    work_package.assignee&.respond_to?(:login) ? work_package.assignee.login : nil
  end

result = {
  work_package: {
    id: work_package.id,
    parent_id: parent.id,
    record_ref: "openproject://work_packages/#{work_package.id}",
    subject: work_package.subject,
    type: work_package.type&.name,
    status: work_package.status&.name,
    target_pi: version_name,
    assignee_login: assignee_login_value,
    start_date: work_package.respond_to?(:start_date) ? work_package.start_date&.iso8601 : nil,
    due_date: work_package.respond_to?(:due_date) ? work_package.due_date&.iso8601 : nil,
    estimated_work: work_package.respond_to?(:estimated_hours) ? work_package.estimated_hours : nil,
    remaining_work: work_package.respond_to?(:remaining_hours) ? work_package.remaining_hours : nil,
    percent_complete: work_package.respond_to?(:done_ratio) ? work_package.done_ratio : nil,
    description_present: work_package.description.to_s.strip.length.positive?,
    custom_fields: provided_custom_fields.to_h do |spec, _|
      field = project_custom_fields.fetch(spec[:field])
      [field.name, OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: field)]
    end
  }
}

puts JSON.pretty_generate(result)
