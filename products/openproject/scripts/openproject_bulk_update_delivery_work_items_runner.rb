# frozen_string_literal: true

require "date"
require "json"
require "time"

CUSTOM_FIELD_UPDATE_SPECS = [
  { key: "delivery_team", field: "Delivery Team", kind: :string },
  { key: "iteration", field: "Iteration", kind: :string },
  { key: "acceptance_criteria", field: "Acceptance Criteria", kind: :text },
  { key: "definition_of_ready", field: "Definition of Ready", kind: :text },
  { key: "definition_of_done", field: "Definition of Done", kind: :text },
  { key: "nfr_category", field: "NFR Category", kind: :list },
  { key: "pi_objective_type", field: "PI Objective Type", kind: :list },
  { key: "planned_business_value", field: "Planned Business Value", kind: :int },
  { key: "actual_business_value", field: "Actual Business Value", kind: :int },
  { key: "roam_state", field: "ROAM State", kind: :list },
  { key: "risk_owner", field: "Risk Owner", kind: :string },
  { key: "risk_review_date", field: "Risk Review Date", kind: :date },
  { key: "risk_disposition", field: "Risk Disposition", kind: :text },
  { key: "wsjf_user_business_value", field: "WSJF User-Business Value", kind: :int },
  { key: "wsjf_time_criticality", field: "WSJF Time Criticality", kind: :int },
  { key: "wsjf_rr_oe", field: "WSJF Risk Reduction / Opportunity Enablement", kind: :int },
  { key: "wsjf_job_size", field: "WSJF Job Size", kind: :int }
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

updates_path = ARGV.fetch(0)
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)

updates_payload = JSON.parse(File.read(updates_path))
unless updates_payload.is_a?(Hash) &&
       updates_payload["schema_version"] == 1 &&
       updates_payload["updates"].is_a?(Array)
  raise "Bulk update payload must be a JSON object with schema_version=1 and an updates array"
end

def validate_custom_shape!(value:, spec:, path:)
  return if value.nil?

  case spec.fetch(:kind)
  when :string, :text, :list, :date
    raise "#{path} must be a non-empty string when provided" unless value.is_a?(String) && !value.strip.empty?
  when :int
    Integer(value)
  else
    raise "Unsupported custom field kind #{spec.fetch(:kind).inspect} at #{path}"
  end
rescue ArgumentError
  raise "#{path} must match the expected #{spec.fetch(:kind)} shape"
end

def validate_update_shape!(update, path)
  raise "#{path} must be an object" unless update.is_a?(Hash)

  supported_keys = [
    "target_work_package_id",
    "status",
    "target_pi",
    "clear_target_pi",
    "assignee_login",
    "clear_assignee",
    "description",
    "clear_description",
    "work_note",
    "start_date",
    "clear_start_date",
    "due_date",
    "clear_due_date",
    "estimated_work",
    "clear_estimated_work",
    "remaining_work",
    "clear_remaining_work",
    "percent_complete"
  ] + CUSTOM_FIELD_UPDATE_SPECS.map { |spec| spec.fetch(:key) }

  unknown_keys = update.keys - supported_keys
  raise "#{path} contains unsupported keys: #{unknown_keys.join(', ')}" if unknown_keys.any?

  Integer(update.fetch("target_work_package_id"))

  if update.key?("status")
    status = update["status"]
    raise "#{path}.status must be a non-empty string when provided" unless status.is_a?(String) && !status.strip.empty?
    raise "#{path}.status cannot be done; use the supported completion workflow" if status.casecmp("done").zero?
  end

  if update.key?("target_pi")
    target_pi = update["target_pi"]
    raise "#{path}.target_pi must be a non-empty string when provided" unless target_pi.is_a?(String) && !target_pi.strip.empty?
  end

  if update.key?("assignee_login")
    assignee_login = update["assignee_login"]
    raise "#{path}.assignee_login must be a non-empty string when provided" unless assignee_login.is_a?(String) && !assignee_login.strip.empty?
  end

  if update.key?("description") && !update["description"].nil? && !update["description"].is_a?(String)
    raise "#{path}.description must be a string or null when provided"
  end

  if update.key?("work_note")
    work_note = update["work_note"]
    raise "#{path}.work_note must be a non-empty string when provided" unless work_note.is_a?(String) && !work_note.strip.empty?
  end

  %w[
    clear_target_pi
    clear_assignee
    clear_description
    clear_start_date
    clear_due_date
    clear_estimated_work
    clear_remaining_work
  ].each do |field_name|
    next unless update.key?(field_name)

    raise "#{path}.#{field_name} must be true or false when provided" unless [true, false].include?(update[field_name])
  end

  raise "#{path} cannot set target_pi and clear_target_pi=true" if update["target_pi"] && update["clear_target_pi"] == true
  raise "#{path} cannot set assignee_login and clear_assignee=true" if update["assignee_login"] && update["clear_assignee"] == true
  raise "#{path} cannot set description and clear_description=true" if update.key?("description") && update["clear_description"] == true
  raise "#{path} cannot set start_date and clear_start_date=true" if update.key?("start_date") && update["start_date"] && update["clear_start_date"] == true
  raise "#{path} cannot set due_date and clear_due_date=true" if update.key?("due_date") && update["due_date"] && update["clear_due_date"] == true
  raise "#{path} cannot set estimated_work and clear_estimated_work=true" if update.key?("estimated_work") && !update["estimated_work"].nil? && update["clear_estimated_work"] == true
  raise "#{path} cannot set remaining_work and clear_remaining_work=true" if update.key?("remaining_work") && !update["remaining_work"].nil? && update["clear_remaining_work"] == true

  if update.key?("start_date") && !update["start_date"].nil?
    raise "#{path}.start_date must be a non-empty string when provided" unless update["start_date"].is_a?(String) && !update["start_date"].strip.empty?
    Date.iso8601(update["start_date"])
  end

  if update.key?("due_date") && !update["due_date"].nil?
    raise "#{path}.due_date must be a non-empty string when provided" unless update["due_date"].is_a?(String) && !update["due_date"].strip.empty?
    Date.iso8601(update["due_date"])
  end

  if update.key?("estimated_work") && !update["estimated_work"].nil?
    value = Float(update["estimated_work"])
    raise "#{path}.estimated_work must be greater than or equal to zero" if value.negative?
  end

  if update.key?("remaining_work") && !update["remaining_work"].nil?
    value = Float(update["remaining_work"])
    raise "#{path}.remaining_work must be greater than or equal to zero" if value.negative?
  end

  if update.key?("percent_complete")
    raise "#{path}.percent_complete must not be null when provided" if update["percent_complete"].nil?

    value = Integer(update["percent_complete"])
    raise "#{path}.percent_complete must be between 0 and 100" if value.negative? || value > 100
  end

  CUSTOM_FIELD_UPDATE_SPECS.each do |spec|
    next unless update.key?(spec.fetch(:key))

    validate_custom_shape!(
      value: update[spec.fetch(:key)],
      spec: spec,
      path: "#{path}.#{spec.fetch(:key)}",
    )
  end
rescue ArgumentError
  raise "#{path} contains invalid numeric or date values"
end

updates_payload["updates"].each_with_index do |update, index|
  validate_update_shape!(update, "updates[#{index}]")
end

project = Project.find_by!(identifier: delivery_project_identifier)
author = User.admin.active.first || User.active.first
raise "No active author user is available for bulk delivery updates" unless author
User.current = author if User.respond_to?(:current=)

field_names = ["Target PI"] + CUSTOM_FIELD_UPDATE_SPECS.map { |spec| spec[:field] } + [WSJF_SCORE_FIELD]
custom_fields = project.work_package_custom_fields.where(name: field_names).index_by(&:name)
missing_fields = ["Target PI"].reject { |name| custom_fields.key?(name) }
raise "Missing delivery-art custom fields: #{missing_fields.join(', ')}" if missing_fields.any?

def assign_custom_value!(work_package, field, value)
  custom_value = work_package.custom_value_for(field)
  custom_value = work_package.custom_values.build(custom_field: field) if custom_value.nil?
  custom_value.value = value
end

def custom_value_present?(work_package, field)
  return false if field.nil?

  work_package.custom_value_for(field)&.value.to_s.strip.present?
end

def parse_custom_value(spec:, raw_value:, field:)
  case spec[:kind]
  when :int
    Integer(raw_value).to_s
  when :date
    Date.iso8601(raw_value).iso8601
  when :list
    possible_values =
      if field.respond_to?(:custom_options)
        field.custom_options.map { |entry| entry.value.to_s.strip }.reject(&:empty?)
      else
        Array(field.possible_values).map { |entry| entry.to_s.strip }.reject(&:empty?)
      end
    raise "Invalid #{field.name.inspect} value #{raw_value.inspect}" if possible_values.any? && !possible_values.include?(raw_value)

    raw_value
  else
    raw_value
  end
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
  raise "percent_complete must be between 0 and 100" if value.negative? || value > 100

  value
rescue ArgumentError
  raise "percent_complete must be an integer between 0 and 100"
end

def validate_ready_contract!(work_package:, custom_fields:)
  required_field_names = READY_REQUIRED_FIELD_NAMES_BY_TYPE.fetch(work_package.type&.name, [])
  missing_field_names = required_field_names.reject do |field_name|
    custom_value_present?(work_package, custom_fields[field_name])
  end
  return if missing_field_names.empty?

  raise "Work package #{work_package.id} cannot move to ready while required fields are missing: #{missing_field_names.join(', ')}"
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
    raise "This OpenProject runtime does not support assignee updates through the current bulk-update path"
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

record_has_pending_changes = lambda do |work_package|
  work_package.changed? || work_package.custom_values.any?(&:changed?)
end

updated = []
reused = []

updates_payload["updates"].each do |update|
  work_package = WorkPackage.find(Integer(update.fetch("target_work_package_id")))
  unless work_package.project_id == project.id
    raise "Work package #{work_package.id} is not in project #{delivery_project_identifier}"
  end

  changes = {}
  note_applied = nil

  if update.key?("status")
    status = Status.find_by(name: update.fetch("status"))
    raise "Unknown status #{update['status'].inspect}" unless status

    if work_package.status_id != status.id
      changes[:status] = { from: work_package.status&.name, to: status.name }
      work_package.status = status
    end
  end

  current_description = work_package.description.to_s.strip.presence
  if update["clear_description"] == true
    if current_description.present?
      changes[:description] = { from_present: true, to_present: false }
      work_package.description = nil
    end
  elsif update.key?("description")
    desired_description = update["description"]&.to_s&.strip&.presence
    if current_description != desired_description
      changes[:description] = {
        from_present: current_description.present?,
        to_present: desired_description.present?
      }
      work_package.description = desired_description
    end
  end

  target_pi_field = custom_fields.fetch("Target PI")
  if update["clear_target_pi"] == true
    current_version_name = work_package_version_name.call(work_package)
    if current_version_name.present?
      changes[:target_pi] = { from: current_version_name, to: nil }
      assign_work_package_version.call(work_package, nil)
      assign_custom_value!(work_package, target_pi_field, nil)
    end
  elsif update.key?("target_pi")
    desired_version = resolve_version.call(update.fetch("target_pi"))
    desired_version_name = desired_version&.name
    current_version_name = work_package_version_name.call(work_package)
    if current_version_name != desired_version_name
      changes[:target_pi] = { from: current_version_name, to: desired_version_name }
      assign_work_package_version.call(work_package, desired_version)
    end

    current_custom_target_pi = work_package.custom_value_for(target_pi_field)&.value.to_s.strip.presence
    assign_custom_value!(work_package, target_pi_field, desired_version_name) if current_custom_target_pi != desired_version_name
  end

  CUSTOM_FIELD_UPDATE_SPECS.each do |spec|
    next unless update.key?(spec.fetch(:key))

    field = custom_fields[spec[:field]]
    raise "Missing delivery-art custom field #{spec[:field].inspect}" if field.nil?
    unless field.types.include?(work_package.type)
      raise "Custom field #{spec[:field].inspect} is not available for work package type #{work_package.type&.name.inspect}"
    end

    desired_value = parse_custom_value(spec: spec, raw_value: update[spec.fetch(:key)], field: field)
    current_value = work_package.custom_value_for(field)&.value.to_s.strip.presence
    next if current_value == desired_value

    changes[spec[:key].to_sym] = { from: current_value, to: desired_value }
    assign_custom_value!(work_package, field, desired_value)
  end

  if CUSTOM_FIELD_UPDATE_SPECS.any? { |spec| update.key?(spec.fetch(:key)) && WSJF_COMPONENT_FIELDS.include?(spec[:field]) }
    wsjf_values = WSJF_COMPONENT_FIELDS.map do |field_name|
      field = custom_fields[field_name]
      raise "Missing delivery-art custom field #{field_name.inspect}" if field.nil?
      raise "Custom field #{field_name.inspect} is not available for work package type #{work_package.type&.name.inspect}" unless field.types.include?(work_package.type)

      value = work_package.custom_value_for(field)&.value.to_s.strip
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
      changes[:wsjf_score] = { from: current_score, to: wsjf_score }
      assign_custom_value!(work_package, score_field, wsjf_score)
    end
  end

  if update["clear_start_date"] == true || update.key?("start_date")
    unless work_package.respond_to?(:start_date) && work_package.respond_to?(:start_date=)
      raise "This OpenProject runtime does not support start date updates through the current bulk-update path"
    end

    desired_start_date = update["clear_start_date"] == true ? nil : parse_date_value(update.fetch("start_date"), "start_date")
    current_start_date = work_package.start_date
    if current_start_date != desired_start_date
      changes[:start_date] = { from: current_start_date&.iso8601, to: desired_start_date&.iso8601 }
      work_package.start_date = desired_start_date
    end
  end

  if update["clear_due_date"] == true || update.key?("due_date")
    unless work_package.respond_to?(:due_date) && work_package.respond_to?(:due_date=)
      raise "This OpenProject runtime does not support due date updates through the current bulk-update path"
    end

    desired_due_date = update["clear_due_date"] == true ? nil : parse_date_value(update.fetch("due_date"), "due_date")
    current_due_date = work_package.due_date
    if current_due_date != desired_due_date
      changes[:due_date] = { from: current_due_date&.iso8601, to: desired_due_date&.iso8601 }
      work_package.due_date = desired_due_date
    end
  end

  if update["clear_estimated_work"] == true || update.key?("estimated_work")
    unless work_package.respond_to?(:estimated_hours) && work_package.respond_to?(:estimated_hours=)
      raise "This OpenProject runtime does not support estimated work updates through the current bulk-update path"
    end

    desired_estimated_work = update["clear_estimated_work"] == true ? nil : parse_hours_value(update.fetch("estimated_work"), "estimated_work")
    current_estimated_work = work_package.estimated_hours&.to_f
    current_estimated_work = nil if work_package.estimated_hours.nil?
    if current_estimated_work != desired_estimated_work
      changes[:estimated_work] = { from: current_estimated_work, to: desired_estimated_work }
      work_package.estimated_hours = desired_estimated_work
    end
  end

  if update["clear_remaining_work"] == true || update.key?("remaining_work")
    unless work_package.respond_to?(:remaining_hours) && work_package.respond_to?(:remaining_hours=)
      raise "This OpenProject runtime does not support remaining work updates through the current bulk-update path"
    end

    desired_remaining_work = update["clear_remaining_work"] == true ? nil : parse_hours_value(update.fetch("remaining_work"), "remaining_work")
    current_remaining_work = work_package.remaining_hours&.to_f
    current_remaining_work = nil if work_package.remaining_hours.nil?
    if current_remaining_work != desired_remaining_work
      changes[:remaining_work] = { from: current_remaining_work, to: desired_remaining_work }
      work_package.remaining_hours = desired_remaining_work
    end
  end

  if update.key?("percent_complete")
    unless work_package.respond_to?(:done_ratio) && work_package.respond_to?(:done_ratio=)
      raise "This OpenProject runtime does not support percent complete updates through the current bulk-update path"
    end

    desired_percent_complete = parse_percent_complete(update.fetch("percent_complete"))
    current_percent_complete = work_package.done_ratio&.to_i
    if current_percent_complete != desired_percent_complete
      changes[:percent_complete] = { from: current_percent_complete, to: desired_percent_complete }
      work_package.done_ratio = desired_percent_complete
    end
  end

  current_assignee_login = work_package_assignee_login.call(work_package)
  if update["clear_assignee"] == true
    if current_assignee_login.present?
      changes[:assignee] = { from: current_assignee_login, to: nil }
      assign_work_package_assignee.call(work_package, nil)
    end
  elsif update.key?("assignee_login")
    assignee = User.active.find_by(login: update.fetch("assignee_login"))
    raise "Unknown assignee_login #{update['assignee_login'].inspect}" unless assignee

    if current_assignee_login != assignee.login
      changes[:assignee] = { from: current_assignee_login, to: assignee.login }
      assign_work_package_assignee.call(work_package, assignee)
    end
  end

  if update.key?("work_note")
    note = update.fetch("work_note")
    if work_package.respond_to?(:notes=)
      work_package.notes = note
      note_applied = "journal"
    else
      latest_description = work_package.description.to_s.strip.presence
      work_package.description = append_work_note_to_description.call(
        latest_description,
        note,
        author.login,
      )
      note_applied = "description_section"
      unless changes.key?(:description)
        changes[:description] = {
          from_present: latest_description.present?,
          to_present: true
        }
      end
    end
  end

  validate_ready_contract!(work_package: work_package, custom_fields: custom_fields) if work_package.status&.name == "ready"

  if record_has_pending_changes.call(work_package) || note_applied
    work_package.save!
    work_package.reload
    updated << {
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
        percent_complete: work_package.respond_to?(:done_ratio) ? work_package.done_ratio : nil
      },
      changes: changes,
      note_applied: note_applied
    }
  else
    reused << {
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
        percent_complete: work_package.respond_to?(:done_ratio) ? work_package.done_ratio : nil
      }
    }
  end
end

result = {
  summary: {
    total_requested: updates_payload["updates"].length,
    updated_count: updated.length,
    reused_count: reused.length
  },
  updated: updated,
  reused: reused
}

puts JSON.pretty_generate(result)
