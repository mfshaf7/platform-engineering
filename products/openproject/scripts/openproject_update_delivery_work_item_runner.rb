# frozen_string_literal: true

require "json"
require "time"
require "date"
require_relative "openproject_delivery_art_custom_field_support"

target_work_package_id = Integer(ENV.fetch("TARGET_WORK_PACKAGE_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)

status_name = ENV["STATUS"]&.strip&.presence
target_pi = ENV["TARGET_PI"]&.strip&.presence
clear_target_pi = ENV.fetch("CLEAR_TARGET_PI", "false") == "true"
assignee_login = ENV["ASSIGNEE_LOGIN"]&.strip&.presence
clear_assignee = ENV.fetch("CLEAR_ASSIGNEE", "false") == "true"
description = ENV["DESCRIPTION"]&.strip&.presence
clear_description = ENV.fetch("CLEAR_DESCRIPTION", "false") == "true"
work_note = ENV["WORK_NOTE"]&.strip&.presence
start_date_raw = ENV["START_DATE"]&.strip&.presence
clear_start_date = ENV.fetch("CLEAR_START_DATE", "false") == "true"
due_date_raw = ENV["DUE_DATE"]&.strip&.presence
clear_due_date = ENV.fetch("CLEAR_DUE_DATE", "false") == "true"
estimated_work_raw = ENV["ESTIMATED_WORK"]&.strip&.presence
clear_estimated_work = ENV.fetch("CLEAR_ESTIMATED_WORK", "false") == "true"
remaining_work_raw = ENV["REMAINING_WORK"]&.strip&.presence
clear_remaining_work = ENV.fetch("CLEAR_REMAINING_WORK", "false") == "true"
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

if status_name&.casecmp("done")&.zero?
  raise "Use openproject-complete-delivery-work-item to mark a delivery work item done with completion evidence"
end

if target_pi && clear_target_pi
  raise "TARGET_PI and CLEAR_TARGET_PI=true cannot be used together"
end

if assignee_login && clear_assignee
  raise "ASSIGNEE_LOGIN and CLEAR_ASSIGNEE=true cannot be used together"
end

if start_date_raw && clear_start_date
  raise "START_DATE and CLEAR_START_DATE=true cannot be used together"
end

if due_date_raw && clear_due_date
  raise "DUE_DATE and CLEAR_DUE_DATE=true cannot be used together"
end

if estimated_work_raw && clear_estimated_work
  raise "ESTIMATED_WORK and CLEAR_ESTIMATED_WORK=true cannot be used together"
end

if remaining_work_raw && clear_remaining_work
  raise "REMAINING_WORK and CLEAR_REMAINING_WORK=true cannot be used together"
end

project = Project.find_by!(identifier: delivery_project_identifier)
work_package = WorkPackage.find(target_work_package_id)

unless work_package.project_id == project.id
  raise "Work package #{target_work_package_id} is not in project #{delivery_project_identifier}"
end

author = User.admin.active.first || User.active.first
raise "No active author user is available for work package updates" unless author

User.current = author if User.respond_to?(:current=)

field_names = ["Target PI"] + CUSTOM_FIELD_ENV_SPECS.map { |spec| spec[:field] } + [WSJF_SCORE_FIELD]
custom_fields = project.work_package_custom_fields.where(name: field_names).index_by(&:name)
missing_fields = ["Target PI"].reject { |name| custom_fields.key?(name) }
raise "Missing delivery-art custom fields: #{missing_fields.join(', ')}" if missing_fields.any?

def custom_value_present?(work_package, field)
  OpenprojectDeliveryArtCustomFieldSupport.custom_value_present?(entry: work_package, field: field)
end

def validate_ready_contract!(work_package:, custom_fields:)
  required_field_names = READY_REQUIRED_FIELD_NAMES_BY_TYPE.fetch(work_package.type&.name, [])
  missing_field_names = required_field_names.reject do |field_name|
    custom_value_present?(work_package, custom_fields[field_name])
  end
  return if missing_field_names.empty?

  raise "Work package #{work_package.id} cannot move to ready while required fields are missing: #{missing_field_names.join(', ')}"
end

def parse_custom_value(spec:, raw_value:, field:)
  OpenprojectDeliveryArtCustomFieldSupport.normalize_input_value!(field: field, value: raw_value, kind: spec[:kind])
end

def parse_date_value(raw_value, label)
  Date.iso8601(raw_value)
rescue ArgumentError
  raise "#{label} must be an ISO date (YYYY-MM-DD)"
end

def parse_hours_value(raw_value, label)
  value = Float(raw_value)
  raise "#{label} must be greater than or equal to zero" if value.negative?

  value
rescue ArgumentError
  raise "#{label} must be a numeric value"
end

def parse_percent_complete(raw_value)
  value = Integer(raw_value)
  raise "PERCENT_COMPLETE must be between 0 and 100" if value.negative? || value > 100

  value
rescue ArgumentError
  raise "PERCENT_COMPLETE must be an integer between 0 and 100"
end

project_versions = project.versions.index_by { |entry| entry.name.to_s.downcase }

resolve_version = lambda do |version_name|
  normalized = version_name.to_s.strip
  return nil if normalized.empty?

  key = normalized.downcase
  version = project_versions[key]
  return version if version

  version = project.versions.find_or_initialize_by(name: normalized)
  version.status = "open" if version.respond_to?(:status=)
  version.sharing = "none" if version.respond_to?(:sharing=) && version.sharing.blank?
  version.save!
  project_versions[key] = version
  version
end

work_package_version_name = lambda do |entry|
  if entry.respond_to?(:version)
    entry.version&.name
  elsif entry.respond_to?(:fixed_version)
    entry.fixed_version&.name
  end
end

assign_work_package_version = lambda do |entry, version|
  if entry.respond_to?(:version=)
    entry.version = version
  elsif entry.respond_to?(:fixed_version=)
    entry.fixed_version = version
  end
end

work_package_assignee_login = lambda do |entry|
  if entry.respond_to?(:assigned_to)
    entry.assigned_to&.respond_to?(:login) ? entry.assigned_to.login : nil
  elsif entry.respond_to?(:assignee)
    entry.assignee&.respond_to?(:login) ? entry.assignee.login : nil
  end
end

assign_work_package_assignee = lambda do |entry, assignee|
  if entry.respond_to?(:assigned_to=)
    entry.assigned_to = assignee
  elsif entry.respond_to?(:assignee=)
    entry.assignee = assignee
  else
    raise "This OpenProject runtime does not support assignee updates through the current update path"
  end
end

append_work_note_to_description = lambda do |current_description, note, author_login|
  note_heading = "## Operator work notes"
  note_entry = "- #{Time.now.utc.iso8601} @#{author_login}: #{note}"
  rendered = current_description.to_s.strip

  if rendered.empty?
    [note_heading, "", note_entry].join("\n")
  elsif rendered.include?(note_heading)
    [rendered, note_entry].join("\n")
  else
    [rendered, "", note_heading, "", note_entry].join("\n")
  end
end

changes = {}

if status_name
  status = Status.find_by(name: status_name)
  raise "Unknown status #{status_name.inspect}" unless status

  if work_package.status_id != status.id
    changes[:status] = {
      from: work_package.status&.name,
      to: status.name
    }
    work_package.status = status
  end
end

if clear_start_date || start_date_raw
  unless work_package.respond_to?(:start_date) && work_package.respond_to?(:start_date=)
    raise "This OpenProject runtime does not support start date updates through the current update path"
  end

  current_start_date = work_package.start_date
  desired_start_date = clear_start_date ? nil : parse_date_value(start_date_raw, "START_DATE")
  if current_start_date != desired_start_date
    changes[:start_date] = {
      from: current_start_date&.iso8601,
      to: desired_start_date&.iso8601
    }
    work_package.start_date = desired_start_date
  end
end

if clear_due_date || due_date_raw
  unless work_package.respond_to?(:due_date) && work_package.respond_to?(:due_date=)
    raise "This OpenProject runtime does not support due date updates through the current update path"
  end

  current_due_date = work_package.due_date
  desired_due_date = clear_due_date ? nil : parse_date_value(due_date_raw, "DUE_DATE")
  if current_due_date != desired_due_date
    changes[:due_date] = {
      from: current_due_date&.iso8601,
      to: desired_due_date&.iso8601
    }
    work_package.due_date = desired_due_date
  end
end

if clear_estimated_work || estimated_work_raw
  unless work_package.respond_to?(:estimated_hours) && work_package.respond_to?(:estimated_hours=)
    raise "This OpenProject runtime does not support estimated work updates through the current update path"
  end

  current_estimated_work = work_package.estimated_hours&.to_f
  current_estimated_work = nil if current_estimated_work.nil?
  desired_estimated_work = clear_estimated_work ? nil : parse_hours_value(estimated_work_raw, "ESTIMATED_WORK")
  if current_estimated_work != desired_estimated_work
    changes[:estimated_work] = {
      from: current_estimated_work,
      to: desired_estimated_work
    }
    work_package.estimated_hours = desired_estimated_work
  end
end

if clear_remaining_work || remaining_work_raw
  unless work_package.respond_to?(:remaining_hours) && work_package.respond_to?(:remaining_hours=)
    raise "This OpenProject runtime does not support remaining work updates through the current update path"
  end

  current_remaining_work = work_package.remaining_hours&.to_f
  current_remaining_work = nil if current_remaining_work.nil?
  desired_remaining_work = clear_remaining_work ? nil : parse_hours_value(remaining_work_raw, "REMAINING_WORK")
  if current_remaining_work != desired_remaining_work
    changes[:remaining_work] = {
      from: current_remaining_work,
      to: desired_remaining_work
    }
    work_package.remaining_hours = desired_remaining_work
  end
end

if percent_complete_raw
  unless work_package.respond_to?(:done_ratio) && work_package.respond_to?(:done_ratio=)
    raise "This OpenProject runtime does not support percent complete updates through the current update path"
  end

  desired_percent_complete = parse_percent_complete(percent_complete_raw)
  current_percent_complete = work_package.done_ratio&.to_i
  if current_percent_complete != desired_percent_complete
    changes[:percent_complete] = {
      from: current_percent_complete,
      to: desired_percent_complete
    }
    work_package.done_ratio = desired_percent_complete
  end
end

current_description = work_package.description.to_s.strip.presence
if clear_description
  if current_description.present?
    changes[:description] = {
      from_present: true,
      to_present: false
    }
    work_package.description = nil
  end
elsif description
  if current_description != description
    changes[:description] = {
      from_present: current_description.present?,
      to_present: true
    }
    work_package.description = description
  end
end

current_version_name = work_package_version_name.call(work_package)
target_pi_field = custom_fields.fetch("Target PI")
if clear_target_pi
  if current_version_name.present?
    changes[:target_pi] = {
      from: current_version_name,
      to: nil
    }
    assign_work_package_version.call(work_package, nil)
    OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: target_pi_field, value: nil)
  end
elsif target_pi
  desired_version = resolve_version.call(target_pi)
  desired_version_name = desired_version&.name
  if current_version_name != desired_version_name
    changes[:target_pi] = {
      from: current_version_name,
      to: desired_version_name
    }
    assign_work_package_version.call(work_package, desired_version)
  end

  current_custom_target_pi = OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: target_pi_field)
  if current_custom_target_pi != desired_version_name
    OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: target_pi_field, value: desired_version_name)
  end
end

provided_custom_fields = CUSTOM_FIELD_ENV_SPECS.filter_map do |spec|
  value = ENV[spec[:env]]&.strip&.presence
  next if value.nil?

  [spec, value]
end

provided_custom_fields.each do |spec, raw_value|
  field = custom_fields[spec[:field]]
  raise "Missing delivery-art custom field #{spec[:field].inspect}" if field.nil?
  unless field.types.include?(work_package.type)
    raise "Custom field #{spec[:field].inspect} is not available for work package type #{work_package.type&.name.inspect}"
  end

  desired_value = parse_custom_value(spec: spec, raw_value: raw_value, field: field)
  current_value = OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: field)
  next if current_value == desired_value

  changes[spec[:env].downcase.to_sym] = {
    from: current_value,
    to: desired_value
  }
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: field, value: desired_value, kind: spec[:kind])
end

if provided_custom_fields.any? { |spec, _| WSJF_COMPONENT_FIELDS.include?(spec[:field]) }
  wsjf_values = WSJF_COMPONENT_FIELDS.map do |field_name|
    field = custom_fields[field_name]
    raise "Missing delivery-art custom field #{field_name.inspect}" if field.nil?
    raise "Custom field #{field_name.inspect} is not available for work package type #{work_package.type&.name.inspect}" unless field.types.include?(work_package.type)

    value = OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: field)
    raise "WSJF component #{field_name.inspect} must be set before computing WSJF Score" if value.empty?

    Integer(value)
  end

  job_size = wsjf_values.last
  raise "WSJF Job Size must be greater than zero" if job_size <= 0

  wsjf_score = ((wsjf_values[0] + wsjf_values[1] + wsjf_values[2]).to_f / job_size).round(2).to_s
  score_field = custom_fields[WSJF_SCORE_FIELD]
  raise "Missing delivery-art custom field #{WSJF_SCORE_FIELD.inspect}" if score_field.nil?
  raise "Custom field #{WSJF_SCORE_FIELD.inspect} is not available for work package type #{work_package.type&.name.inspect}" unless score_field.types.include?(work_package.type)

  current_score = work_package.custom_value_for(score_field)&.value.to_s.strip.presence
  if current_score != wsjf_score
    changes[:wsjf_score] = {
      from: current_score,
      to: wsjf_score
    }
    OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: score_field, value: wsjf_score, kind: :float)
  end
end

current_assignee_login = work_package_assignee_login.call(work_package)
if clear_assignee
  if current_assignee_login.present?
    changes[:assignee] = {
      from: current_assignee_login,
      to: nil
    }
    assign_work_package_assignee.call(work_package, nil)
  end
elsif assignee_login
  assignee = User.active.find_by(login: assignee_login)
  raise "Unknown ASSIGNEE_LOGIN #{assignee_login.inspect}" unless assignee

  if current_assignee_login != assignee.login
    changes[:assignee] = {
      from: current_assignee_login,
      to: assignee.login
    }
    assign_work_package_assignee.call(work_package, assignee)
  end
end

note_applied = nil
if work_note
  if work_package.respond_to?(:notes=)
    work_package.notes = work_note
    note_applied = "journal"
  else
    current_description = work_package.description.to_s.strip.presence
    work_package.description = append_work_note_to_description.call(
      current_description,
      work_note,
      author.login,
    )
    note_applied = "description_section"

    unless changes.key?(:description)
      changes[:description] = {
        from_present: current_description.present?,
        to_present: true
      }
    end
  end
end

validate_ready_contract!(work_package: work_package, custom_fields: custom_fields) if work_package.status&.name == "ready"

work_package.save!
work_package.reload

result = {
  work_package: {
    id: work_package.id,
    record_ref: "openproject://work_packages/#{work_package.id}",
    subject: work_package.subject,
    type: work_package.type&.name,
    status: work_package.status&.name,
    target_pi: work_package_version_name.call(work_package),
    assignee_login: work_package_assignee_login.call(work_package),
    start_date: work_package.respond_to?(:start_date) ? work_package.start_date&.iso8601 : nil,
    due_date: work_package.respond_to?(:due_date) ? work_package.due_date&.iso8601 : nil,
    estimated_work: work_package.respond_to?(:estimated_hours) ? work_package.estimated_hours : nil,
    remaining_work: work_package.respond_to?(:remaining_hours) ? work_package.remaining_hours : nil,
    percent_complete: work_package.respond_to?(:done_ratio) ? work_package.done_ratio : nil,
    description_present: work_package.description.to_s.strip.length.positive?,
    custom_fields: provided_custom_fields.to_h do |spec, _|
      field = custom_fields.fetch(spec[:field])
      [field.name, OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: field)]
    end
  },
  changes: changes,
  note_applied: note_applied
}

puts JSON.pretty_generate(result)
