# frozen_string_literal: true

require "date"
require "json"

ITEM_FIELD_SPECS = [
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

EPIC_UPDATE_FIELD_SPECS = [
  { key: "pm2_phase", field: "PM² Phase", kind: :list },
  { key: "sponsor", field: "Sponsor", kind: :string },
  { key: "business_objective", field: "Business Objective", kind: :text },
  { key: "success_criteria", field: "Success Criteria", kind: :text },
  { key: "system_demo_evidence", field: "System Demo Evidence", kind: :text },
  { key: "inspect_and_adapt_actions", field: "Inspect & Adapt Actions", kind: :text },
  { key: "nfr_category", field: "NFR Category", kind: :list }
].freeze

WSJF_COMPONENT_KEYS = [
  "wsjf_user_business_value",
  "wsjf_time_criticality",
  "wsjf_rr_oe",
  "wsjf_job_size"
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

plan_path = ARGV.fetch(0)
target_epic_id = Integer(ENV.fetch("TARGET_EPIC_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
reconcile_missing = ENV.fetch("RECONCILE_MISSING", "ignore").strip
reconcile_decision = ENV.fetch("RECONCILE_DECISION", "retire").strip
reconcile_retirement_reason = ENV.fetch("RECONCILE_RETIREMENT_REASON", "superseded").strip
reconcile_reason = ENV["RECONCILE_REASON"]&.strip&.presence || "Removed by delivery plan reconciliation"
reconcile_review_date = ENV["RECONCILE_REVIEW_DATE"]&.strip&.presence

unless %w[ignore park].include?(reconcile_missing)
  raise "RECONCILE_MISSING must be ignore or park"
end

unless %w[retire defer].include?(reconcile_decision)
  raise "RECONCILE_DECISION must be retire or defer"
end

if reconcile_missing == "park" && reconcile_decision == "defer"
  raise "RECONCILE_REVIEW_DATE is required when RECONCILE_DECISION=defer" if reconcile_review_date.nil?

  begin
    Date.iso8601(reconcile_review_date)
  rescue ArgumentError
    raise "RECONCILE_REVIEW_DATE must be an ISO date (YYYY-MM-DD)"
  end
end

if reconcile_missing == "park" && reconcile_decision == "retire" && !reconcile_review_date.nil?
  raise "RECONCILE_REVIEW_DATE must not be set when RECONCILE_DECISION=retire"
end

plan = JSON.parse(File.read(plan_path))

unless plan.is_a?(Hash) && plan["schema_version"] == 1 && plan["items"].is_a?(Array)
  raise "Delivery plan must be a JSON object with schema_version=1 and an items array"
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
  raise "#{path} must be an integer-compatible value when provided"
end

def validate_item_shape!(item, path)
  raise "#{path} must be an object" unless item.is_a?(Hash)

  supported_keys = [
    "type",
    "subject",
    "status",
    "description",
    "target_pi",
    "start_date",
    "due_date",
    "estimated_work",
    "remaining_work",
    "percent_complete",
    "children"
  ] + ITEM_FIELD_SPECS.map { |spec| spec.fetch(:key) }
  unknown_keys = item.keys - supported_keys
  raise "#{path} contains unsupported keys: #{unknown_keys.join(', ')}" if unknown_keys.any?

  type = item["type"]
  subject = item["subject"]
  status = item["status"]
  description = item["description"]
  target_pi = item["target_pi"]
  children = item["children"]

  raise "#{path}.type must be a non-empty string" unless type.is_a?(String) && !type.strip.empty?
  raise "#{path}.subject must be a non-empty string" unless subject.is_a?(String) && !subject.strip.empty?

  if item.key?("status")
    raise "#{path}.status must be a non-empty string when provided" unless status.is_a?(String) && !status.strip.empty?
    if status.casecmp("done").zero?
      raise "#{path}.status cannot be done in a delivery plan; use the supported completion workflow after the item exists"
    end
  end

  if item.key?("description") && !description.nil? && !description.is_a?(String)
    raise "#{path}.description must be a string or null when provided"
  end

  if item.key?("target_pi") && !target_pi.nil? && (!target_pi.is_a?(String) || target_pi.strip.empty?)
    raise "#{path}.target_pi must be a non-empty string or null when provided"
  end

  if children && !children.is_a?(Array)
    raise "#{path}.children must be an array when provided"
  end

  ITEM_FIELD_SPECS.each do |spec|
    next unless item.key?(spec.fetch(:key))

    validate_custom_shape!(
      value: item[spec.fetch(:key)],
      spec: spec,
      path: "#{path}.#{spec.fetch(:key)}",
    )
  end

  Array(children).each_with_index do |child, index|
    validate_item_shape!(child, "#{path}.children[#{index}]")
  end

  if item.key?("start_date") && !item["start_date"].nil?
    raise "#{path}.start_date must be a non-empty string when provided" unless item["start_date"].is_a?(String) && !item["start_date"].strip.empty?
    Date.iso8601(item["start_date"])
  end

  if item.key?("due_date") && !item["due_date"].nil?
    raise "#{path}.due_date must be a non-empty string when provided" unless item["due_date"].is_a?(String) && !item["due_date"].strip.empty?
    Date.iso8601(item["due_date"])
  end

  if item.key?("estimated_work") && !item["estimated_work"].nil?
    value = Float(item["estimated_work"])
    raise "#{path}.estimated_work must be greater than or equal to zero" if value.negative?
  end

  if item.key?("remaining_work") && !item["remaining_work"].nil?
    value = Float(item["remaining_work"])
    raise "#{path}.remaining_work must be greater than or equal to zero" if value.negative?
  end

  if item.key?("percent_complete")
    raise "#{path}.percent_complete must not be null when provided" if item["percent_complete"].nil?

    value = Integer(item["percent_complete"])
    raise "#{path}.percent_complete must be between 0 and 100" if value.negative? || value > 100
  end
rescue ArgumentError
  raise "#{path} contains invalid schedule or progress values"
end

def validate_epic_updates_shape!(epic_updates)
  raise "epic_updates must be an object when provided" unless epic_updates.is_a?(Hash)

  supported_keys = ["description", "status", "target_pi"] + EPIC_UPDATE_FIELD_SPECS.map { |spec| spec.fetch(:key) }
  unknown_keys = epic_updates.keys - supported_keys
  raise "epic_updates contains unsupported keys: #{unknown_keys.join(', ')}" if unknown_keys.any?

  if epic_updates.key?("description") && !epic_updates["description"].nil? && !epic_updates["description"].is_a?(String)
    raise "epic_updates.description must be a string or null when provided"
  end

  if epic_updates.key?("status")
    status = epic_updates["status"]
    raise "epic_updates.status must be a non-empty string when provided" unless status.is_a?(String) && !status.strip.empty?
    if status.casecmp("done").zero?
      raise "epic_updates.status cannot be done in a delivery plan; use the supported closeout workflow after execution is complete"
    end
  end

  if epic_updates.key?("target_pi")
    target_pi = epic_updates["target_pi"]
    if !target_pi.nil? && (!target_pi.is_a?(String) || target_pi.strip.empty?)
      raise "epic_updates.target_pi must be a non-empty string or null when provided"
    end
  end

  EPIC_UPDATE_FIELD_SPECS.each do |spec|
    next unless epic_updates.key?(spec.fetch(:key))

    validate_custom_shape!(
      value: epic_updates[spec.fetch(:key)],
      spec: spec,
      path: "epic_updates.#{spec.fetch(:key)}",
    )
  end
end

def count_plan_items(items)
  items.sum do |item|
    1 + count_plan_items(Array(item["children"]))
  end
end

def normalize_custom_value(spec:, raw_value:, field:)
  return nil if raw_value.nil?

  case spec.fetch(:kind)
  when :int
    Integer(raw_value).to_s
  when :date
    Date.iso8601(raw_value.to_s).iso8601
  when :list
    possible_values =
      if field.respond_to?(:custom_options)
        field.custom_options.map { |entry| entry.value.to_s.strip }.reject(&:empty?)
      else
        Array(field.possible_values).map { |entry| entry.to_s.strip }.reject(&:empty?)
      end
    string_value = raw_value.to_s.strip
    raise "Invalid #{field.name.inspect} value #{raw_value.inspect}" if possible_values.any? && !possible_values.include?(string_value)

    string_value
  else
    raw_value.to_s.strip.presence
  end
end

def custom_value_present?(work_package, field)
  return false if field.nil?

  work_package.custom_value_for(field)&.value.to_s.strip.present?
end

plan["items"].each_with_index do |item, index|
  validate_item_shape!(item, "items[#{index}]")
end
validate_epic_updates_shape!(plan["epic_updates"]) if plan["epic_updates"]

project = Project.find_by!(identifier: delivery_project_identifier)
epic = WorkPackage.find(target_epic_id)

unless epic.project_id == project.id
  raise "Epic #{target_epic_id} is not in project #{delivery_project_identifier}"
end

author = User.admin.active.first || User.active.first
raise "No active author user is available for work package creation" unless author
User.current = author if User.respond_to?(:current=)

types_by_name = Type.all.index_by { |entry| entry.name.downcase }
statuses_by_name = Status.all.index_by { |entry| entry.name.downcase }
default_priority = IssuePriority.where(is_default: true).first || IssuePriority.order(:position).first
raise "No default priority is available for work package creation" unless default_priority

versions_by_name = project.versions.index_by { |entry| entry.name.to_s.downcase }
project_custom_fields = project.work_package_custom_fields.index_by(&:name)
target_pi_field = project_custom_fields["Target PI"]
raise "Missing delivery-art custom field \"Target PI\"" if target_pi_field.nil?

resolve_version = lambda do |version_name|
  normalized = version_name.to_s.strip
  return nil if normalized.empty?

  key = normalized.downcase
  version = versions_by_name[key]
  return version if version

  version = project.versions.find_or_initialize_by(name: normalized)
  version.status = "open" if version.respond_to?(:status=)
  version.sharing = "none" if version.respond_to?(:sharing=) && version.sharing.blank?
  version.save!
  versions_by_name[key] = version
  version
end

work_package_version_name = lambda do |work_package|
  if work_package.respond_to?(:version)
    work_package.version&.name
  elsif work_package.respond_to?(:fixed_version)
    work_package.fixed_version&.name
  end
end

assign_work_package_version = lambda do |work_package, version|
  if work_package.respond_to?(:version=)
    work_package.version = version
  elsif work_package.respond_to?(:fixed_version=)
    work_package.fixed_version = version
  end
end

assign_custom_value = lambda do |work_package, field, value|
  custom_value = work_package.custom_value_for(field)
  custom_value = work_package.custom_values.build(custom_field: field) if custom_value.nil?
  custom_value.value = value
end

record_has_pending_changes = lambda do |work_package|
  work_package.changed? || work_package.custom_values.any?(&:changed?)
end

apply_schedule_and_progress = lambda do |work_package:, container:, changes:|
  if container.key?("start_date")
    unless work_package.respond_to?(:start_date) && work_package.respond_to?(:start_date=)
      raise "This OpenProject runtime does not support start date updates through the current plan path"
    end

    desired_start_date = container["start_date"] ? Date.iso8601(container["start_date"].to_s) : nil
    current_start_date = work_package.start_date
    if current_start_date != desired_start_date
      changes[:start_date] = {
        from: current_start_date&.iso8601,
        to: desired_start_date&.iso8601
      }
      work_package.start_date = desired_start_date
    end
  end

  if container.key?("due_date")
    unless work_package.respond_to?(:due_date) && work_package.respond_to?(:due_date=)
      raise "This OpenProject runtime does not support due date updates through the current plan path"
    end

    desired_due_date = container["due_date"] ? Date.iso8601(container["due_date"].to_s) : nil
    current_due_date = work_package.due_date
    if current_due_date != desired_due_date
      changes[:due_date] = {
        from: current_due_date&.iso8601,
        to: desired_due_date&.iso8601
      }
      work_package.due_date = desired_due_date
    end
  end

  if container.key?("estimated_work")
    unless work_package.respond_to?(:estimated_hours) && work_package.respond_to?(:estimated_hours=)
      raise "This OpenProject runtime does not support estimated work updates through the current plan path"
    end

    desired_estimated_work = container["estimated_work"].nil? ? nil : Float(container["estimated_work"])
    current_estimated_work = work_package.estimated_hours&.to_f
    current_estimated_work = nil if work_package.estimated_hours.nil?
    if current_estimated_work != desired_estimated_work
      changes[:estimated_work] = {
        from: current_estimated_work,
        to: desired_estimated_work
      }
      work_package.estimated_hours = desired_estimated_work
    end
  end

  if container.key?("remaining_work")
    unless work_package.respond_to?(:remaining_hours) && work_package.respond_to?(:remaining_hours=)
      raise "This OpenProject runtime does not support remaining work updates through the current plan path"
    end

    desired_remaining_work = container["remaining_work"].nil? ? nil : Float(container["remaining_work"])
    current_remaining_work = work_package.remaining_hours&.to_f
    current_remaining_work = nil if work_package.remaining_hours.nil?
    if current_remaining_work != desired_remaining_work
      changes[:remaining_work] = {
        from: current_remaining_work,
        to: desired_remaining_work
      }
      work_package.remaining_hours = desired_remaining_work
    end
  end

  if container.key?("percent_complete")
    unless work_package.respond_to?(:done_ratio) && work_package.respond_to?(:done_ratio=)
      raise "This OpenProject runtime does not support percent complete updates through the current plan path"
    end

    desired_percent_complete = Integer(container["percent_complete"])
    current_percent_complete = work_package.done_ratio&.to_i
    if current_percent_complete != desired_percent_complete
      changes[:percent_complete] = {
        from: current_percent_complete,
        to: desired_percent_complete
      }
      work_package.done_ratio = desired_percent_complete
    end
  end
end

apply_spec_values = lambda do |work_package:, container:, specs:, changes:, field_store:, change_prefix: nil|
  specs.each do |spec|
    key = spec.fetch(:key)
    next unless container.key?(key)

    field = field_store[spec.fetch(:field)]
    raise "Missing delivery-art custom field #{spec.fetch(:field).inspect}" if field.nil?
    unless field.types.include?(work_package.type)
      raise "Custom field #{spec.fetch(:field).inspect} is not available for work package type #{work_package.type&.name.inspect}"
    end

    desired_value = normalize_custom_value(spec: spec, raw_value: container[key], field: field)
    current_value = work_package.custom_value_for(field)&.value.to_s.strip.presence
    next if current_value == desired_value

    changes_key = [change_prefix, key].compact.join("_").to_sym
    changes[changes_key] = { from: current_value, to: desired_value }
    assign_custom_value.call(work_package, field, desired_value)
  end
end

sync_wsjf_score = lambda do |work_package:, container:, changes:, field_store:|
  return unless WSJF_COMPONENT_KEYS.any? { |key| container.key?(key) }

  wsjf_values = WSJF_COMPONENT_KEYS.map do |key|
    field_name = ITEM_FIELD_SPECS.find { |spec| spec.fetch(:key) == key }.fetch(:field)
    field = field_store[field_name]
    raise "Missing delivery-art custom field #{field_name.inspect}" if field.nil?
    unless field.types.include?(work_package.type)
      raise "Custom field #{field_name.inspect} is not available for work package type #{work_package.type&.name.inspect}"
    end

    value = work_package.custom_value_for(field)&.value.to_s.strip
    raise "WSJF component #{field_name.inspect} must be set before computing WSJF Score" if value.empty?

    Integer(value)
  end

  job_size = wsjf_values.last
  raise "WSJF Job Size must be greater than zero" if job_size <= 0

  wsjf_score = ((wsjf_values[0] + wsjf_values[1] + wsjf_values[2]).to_f / job_size).round(2).to_s
  score_field = field_store[WSJF_SCORE_FIELD]
  raise "Missing delivery-art custom field #{WSJF_SCORE_FIELD.inspect}" if score_field.nil?
  unless score_field.types.include?(work_package.type)
    raise "Custom field #{WSJF_SCORE_FIELD.inspect} is not available for work package type #{work_package.type&.name.inspect}"
  end

  current_score = work_package.custom_value_for(score_field)&.value.to_s.strip.presence
  return if current_score == wsjf_score

  changes[:wsjf_score] = { from: current_score, to: wsjf_score }
  assign_custom_value.call(work_package, score_field, wsjf_score)
end

validate_ready_contract = lambda do |work_package:, field_store:|
  required_field_names = READY_REQUIRED_FIELD_NAMES_BY_TYPE.fetch(work_package.type&.name, [])
  missing_field_names = required_field_names.reject do |field_name|
    custom_value_present?(work_package, field_store[field_name])
  end
  return if missing_field_names.empty?

  raise "Work package #{work_package.id || work_package.subject.inspect} cannot move to ready while required fields are missing: #{missing_field_names.join(', ')}"
end

parking_field_names = [
  "Parking Decision",
  "Parking Reason",
  "Parking Review Date",
  "Retirement Reason"
]
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
parking_fields =
  if reconcile_missing == "park"
    project.work_package_custom_fields.where(name: parking_field_names).index_by(&:name)
  else
    {}
  end
blocker_fields =
  if reconcile_missing == "park"
    project.work_package_custom_fields.where(name: blocker_field_names).index_by(&:name)
  else
    {}
  end

if reconcile_missing == "park"
  missing_fields = parking_field_names.reject { |name| parking_fields.key?(name) }
  raise "Missing delivery parking custom fields: #{missing_fields.join(', ')}" if missing_fields.any?
end

if reconcile_missing == "park" && reconcile_decision == "retire" && reconcile_retirement_reason.empty?
  raise "RECONCILE_RETIREMENT_REASON must be a non-empty string when RECONCILE_DECISION=retire"
end

parked_status = statuses_by_name["parked"] if reconcile_missing == "park"
retired_status = statuses_by_name["retired"] if reconcile_missing == "park"
raise "Missing parked status for reconciliation" if reconcile_missing == "park" && parked_status.nil?
raise "Missing retired status for reconciliation" if reconcile_missing == "park" && retired_status.nil?

work_package_summary = lambda do |work_package, parent_id:, changes: nil|
  summary = {
    id: work_package.id,
    parent_id: parent_id,
    record_ref: "openproject://work_packages/#{work_package.id}",
    status: work_package.status&.name,
    subject: work_package.subject,
    type: work_package.type&.name,
    target_pi: work_package_version_name.call(work_package),
    start_date: work_package.respond_to?(:start_date) ? work_package.start_date&.iso8601 : nil,
    due_date: work_package.respond_to?(:due_date) ? work_package.due_date&.iso8601 : nil,
    estimated_work: work_package.respond_to?(:estimated_hours) ? work_package.estimated_hours : nil,
    remaining_work: work_package.respond_to?(:remaining_hours) ? work_package.remaining_hours : nil,
    percent_complete: work_package.respond_to?(:done_ratio) ? work_package.done_ratio : nil
  }
  summary[:changes] = changes if changes && !changes.empty?
  summary
end

epic_updates = plan["epic_updates"]
epic_changes = {}

if epic_updates.is_a?(Hash)
  if epic_updates.key?("status")
    desired_status = statuses_by_name.fetch(epic_updates.fetch("status").downcase) do
      raise "Unknown status #{epic_updates['status'].inspect}"
    end
    if epic.status_id != desired_status.id
      epic_changes[:status] = { from: epic.status&.name, to: desired_status.name }
      epic.status = desired_status
    end
  end

  if epic_updates.key?("description")
    desired_description = epic_updates["description"]&.to_s&.strip&.presence
    current_description = epic.description.to_s.strip.presence
    if current_description != desired_description
      epic_changes[:description] = {
        from_present: current_description.present?,
        to_present: desired_description.present?
      }
      epic.description = desired_description
    end
  end

  if epic_updates.key?("target_pi")
    desired_version = resolve_version.call(epic_updates["target_pi"])
    desired_version_name = desired_version&.name
    current_version_name = work_package_version_name.call(epic)
    if current_version_name != desired_version_name
      epic_changes[:target_pi] = { from: current_version_name, to: desired_version_name }
      assign_work_package_version.call(epic, desired_version)
    end

    current_custom_target_pi = epic.custom_value_for(target_pi_field)&.value.to_s.strip.presence
    if current_custom_target_pi != desired_version_name
      assign_custom_value.call(epic, target_pi_field, desired_version_name)
    end
  end

  apply_spec_values.call(
    work_package: epic,
    container: epic_updates,
    specs: EPIC_UPDATE_FIELD_SPECS,
    changes: epic_changes,
    field_store: project_custom_fields,
  )

  epic.save! if record_has_pending_changes.call(epic)
  epic.reload
end

created = []
updated = []
reused = []
deferred = []
retired = []

apply_items = lambda do |items, parent|
  planned_keys = []

  items.each do |item|
    type = types_by_name.fetch(item["type"].downcase) do
      raise "Unknown work package type #{item['type'].inspect}"
    end
    planned_keys << [type.id, item["subject"].strip.downcase]

    requested_status =
      if item.key?("status")
        statuses_by_name.fetch(item["status"].downcase) do
          raise "Unknown status #{item['status'].inspect}"
        end
      end
    create_status = requested_status || statuses_by_name.fetch("new")

    subject = item["subject"].strip
    description_specified = item.key?("description")
    desired_description =
      description_specified ? item["description"]&.to_s&.strip&.presence : nil
    target_pi_specified = item.key?("target_pi")
    desired_version =
      if target_pi_specified
        resolve_version.call(item["target_pi"])
      else
        nil
      end

    work_package = WorkPackage
      .where(project_id: project.id, parent_id: parent.id, type_id: type.id)
      .find { |candidate| candidate.subject.to_s.casecmp?(subject) }

    if work_package
      changes = {}

      if requested_status && work_package.status_id != requested_status.id
        changes[:status] = {
          from: work_package.status&.name,
          to: requested_status.name
        }
        work_package.status = requested_status
      end

      if description_specified
        current_description = work_package.description.to_s.strip.presence
        if current_description != desired_description
          changes[:description] = {
            from_present: current_description.present?,
            to_present: desired_description.present?
          }
          work_package.description = desired_description
        end
      end

      if target_pi_specified
        current_version_name = work_package_version_name.call(work_package)
        desired_version_name = desired_version&.name
        if current_version_name != desired_version_name
          changes[:target_pi] = {
            from: current_version_name,
            to: desired_version_name
          }
          assign_work_package_version.call(work_package, desired_version)
        end

        current_custom_target_pi = work_package.custom_value_for(target_pi_field)&.value.to_s.strip.presence
        if current_custom_target_pi != desired_version_name
          assign_custom_value.call(work_package, target_pi_field, desired_version_name)
        end
      end

      apply_spec_values.call(
        work_package: work_package,
        container: item,
        specs: ITEM_FIELD_SPECS,
        changes: changes,
        field_store: project_custom_fields,
      )
      apply_schedule_and_progress.call(
        work_package: work_package,
        container: item,
        changes: changes,
      )
      sync_wsjf_score.call(
        work_package: work_package,
        container: item,
        changes: changes,
        field_store: project_custom_fields,
      )

      if work_package.status&.name == "ready"
        validate_ready_contract.call(
          work_package: work_package,
          field_store: project_custom_fields,
        )
      end

      if record_has_pending_changes.call(work_package)
        work_package.save!
        work_package.reload
        updated << work_package_summary.call(
          work_package,
          parent_id: parent.id,
          changes: changes,
        )
      else
        reused << work_package_summary.call(work_package, parent_id: parent.id)
      end
    else
      priority = parent.priority || default_priority
      inherited_version =
        if target_pi_specified
          desired_version
        elsif parent.respond_to?(:version)
          parent.version
        elsif parent.respond_to?(:fixed_version)
          parent.fixed_version
        end

      work_package = WorkPackage.new(
        author: author,
        parent: parent,
        priority: priority,
        project: project,
        status: create_status,
        subject: subject,
        type: type
      )
      work_package.description = desired_description if description_specified
      assign_work_package_version.call(work_package, inherited_version) if target_pi_specified || inherited_version
      assign_custom_value.call(work_package, target_pi_field, inherited_version&.name) if target_pi_specified || inherited_version

      apply_spec_values.call(
        work_package: work_package,
        container: item,
        specs: ITEM_FIELD_SPECS,
        changes: {},
        field_store: project_custom_fields,
      )
      apply_schedule_and_progress.call(
        work_package: work_package,
        container: item,
        changes: {},
      )
      sync_wsjf_score.call(
        work_package: work_package,
        container: item,
        changes: {},
        field_store: project_custom_fields,
      )

      if work_package.status&.name == "ready"
        validate_ready_contract.call(
          work_package: work_package,
          field_store: project_custom_fields,
        )
      end

      work_package.save!
      work_package.reload

      created << work_package_summary.call(work_package, parent_id: parent.id)
    end

    next unless item["children"].is_a?(Array) && !item["children"].empty?

    apply_items.call(item["children"], work_package)
  end

  next unless reconcile_missing == "park"

  WorkPackage.where(project_id: project.id, parent_id: parent.id).find_each do |child|
    next if planned_keys.include?([child.type_id, child.subject.to_s.strip.downcase])
    target_inactive_status = reconcile_decision == "retire" ? retired_status : parked_status
    next if child.status&.name == target_inactive_status.name

    previous_status_name = child.status&.name
    child.status = target_inactive_status
    assign_custom_value.call(child, parking_fields.fetch("Parking Decision"), reconcile_decision)
    assign_custom_value.call(child, parking_fields.fetch("Parking Reason"), reconcile_reason)
    assign_custom_value.call(
      child,
      parking_fields.fetch("Parking Review Date"),
      reconcile_decision == "defer" ? reconcile_review_date : nil,
    )
    assign_custom_value.call(
      child,
      parking_fields.fetch("Retirement Reason"),
      reconcile_decision == "retire" ? reconcile_retirement_reason : nil,
    )
    blocker_fields.each_value do |field|
      assign_custom_value.call(child, field, nil)
    end
    child.save!
    child.reload

    destination = reconcile_decision == "retire" ? retired : deferred
    destination << work_package_summary.call(
      child,
      parent_id: parent.id,
      changes: {
        status: {
          from: previous_status_name,
          to: target_inactive_status.name
        },
        parking_decision: reconcile_decision,
        retirement_reason: reconcile_decision == "retire" ? reconcile_retirement_reason : nil
      }
    )
  end
end

apply_items.call(plan["items"], epic)

result = {
  epic: {
    id: epic.id,
    record_ref: "openproject://work_packages/#{epic.id}",
    subject: epic.subject,
    updated: epic_changes.any?,
    changes: epic_changes,
    target_pi: work_package_version_name.call(epic)
  },
  created: created,
  updated: updated,
  reused: reused,
  deferred: deferred,
  retired: retired,
  summary: {
    created_count: created.length,
    updated_count: updated.length,
    reused_count: reused.length,
    deferred_count: deferred.length,
    retired_count: retired.length,
    total_requested: count_plan_items(plan["items"])
  }
}

puts JSON.pretty_generate(result)
