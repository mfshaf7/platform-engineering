# frozen_string_literal: true

require "date"
require "json"
require "time"

action = ENV.fetch("ACTION").strip
target_work_package_id = Integer(ENV.fetch("TARGET_WORK_PACKAGE_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
resume_status_name = ENV["RESUME_STATUS"]&.strip
park_decision = ENV["PARK_DECISION"]&.strip
park_reason = ENV["PARK_REASON"]&.strip
park_review_date = ENV["PARK_REVIEW_DATE"]&.strip
work_note = ENV["WORK_NOTE"]&.strip&.presence

project = Project.find_by!(identifier: delivery_project_identifier)
work_package = WorkPackage.find(target_work_package_id)

unless work_package.project_id == project.id
  raise "Work package #{target_work_package_id} is not in project #{delivery_project_identifier}"
end

author = User.admin.active.first || User.active.first
raise "No active author user is available for work package updates" unless author

User.current = author if User.respond_to?(:current=)

parking_field_names = [
  "Parking Decision",
  "Parking Reason",
  "Parking Review Date"
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

custom_fields = project.work_package_custom_fields
  .where(name: parking_field_names + blocker_field_names)
  .index_by(&:name)

missing_fields = parking_field_names.reject { |name| custom_fields.key?(name) }
raise "Missing delivery parking custom fields: #{missing_fields.join(', ')}" if missing_fields.any?

decision_field = custom_fields.fetch("Parking Decision")
decision_values =
  if decision_field.respond_to?(:custom_options)
    decision_field.custom_options.map { |entry| entry.value.to_s.strip }.reject(&:empty?)
  elsif decision_field.respond_to?(:possible_values)
    Array(decision_field.possible_values).map { |entry| entry.to_s.strip }.reject(&:empty?)
  else
    []
  end

def parse_iso_date!(value, field_name)
  Date.iso8601(value)
  value
rescue ArgumentError
  raise "#{field_name} must be an ISO date (YYYY-MM-DD)"
end

def assign_custom_value!(work_package, field, value)
  custom_value = work_package.custom_value_for(field)
  custom_value = work_package.custom_values.build(custom_field: field) if custom_value.nil?
  custom_value.value = value
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
note_applied = nil

case action
when "park"
  missing = []
  missing << "PARK_DECISION" if park_decision.nil? || park_decision.empty?
  missing << "PARK_REASON" if park_reason.nil? || park_reason.empty?
  raise "Missing parking fields for ACTION=park: #{missing.join(', ')}" if missing.any?

  if decision_values.any? && !decision_values.include?(park_decision)
    raise "Unknown PARK_DECISION #{park_decision.inspect}"
  end

  if park_decision == "defer"
    raise "PARK_REVIEW_DATE is required for PARK_DECISION=defer" if park_review_date.nil? || park_review_date.empty?
    parse_iso_date!(park_review_date, "PARK_REVIEW_DATE")
  elsif park_review_date && !park_review_date.empty?
    parse_iso_date!(park_review_date, "PARK_REVIEW_DATE")
  end

  parked_status = Status.find_by!(name: "parked")
  if work_package.status&.name != parked_status.name
    changes[:status] = {
      from: work_package.status&.name,
      to: parked_status.name
    }
    work_package.status = parked_status
  end

  assign_custom_value!(work_package, custom_fields.fetch("Parking Decision"), park_decision)
  assign_custom_value!(work_package, custom_fields.fetch("Parking Reason"), park_reason)
  assign_custom_value!(work_package, custom_fields.fetch("Parking Review Date"), park_review_date.presence)

  blocker_field_names.each do |field_name|
    field = custom_fields[field_name]
    next unless field

    assign_custom_value!(work_package, field, nil)
  end
when "resume"
  if resume_status_name.nil? || resume_status_name.empty?
    raise "RESUME_STATUS is required for ACTION=resume"
  end

  resume_status = Status.find_by(name: resume_status_name)
  raise "Unknown RESUME_STATUS #{resume_status_name.inspect}" unless resume_status
  raise "RESUME_STATUS must not be parked" if resume_status.name == "parked"

  if work_package.status&.name != resume_status.name
    changes[:status] = {
      from: work_package.status&.name,
      to: resume_status.name
    }
    work_package.status = resume_status
  end

  parking_field_names.each do |field_name|
    field = custom_fields.fetch(field_name)
    assign_custom_value!(work_package, field, nil)
  end
else
  raise "ACTION must be park or resume"
end

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

work_package.save!
work_package.reload

parking_result = parking_field_names.to_h do |field_name|
  field = custom_fields.fetch(field_name)
  [field_name, work_package.custom_value_for(field)&.value]
end

blocker_result = blocker_field_names.filter_map do |field_name|
  field = custom_fields[field_name]
  next unless field

  [field_name, work_package.custom_value_for(field)&.value]
end.to_h

result = {
  action: action,
  work_package: {
    id: work_package.id,
    record_ref: "openproject://work_packages/#{work_package.id}",
    subject: work_package.subject,
    type: work_package.type&.name,
    status: work_package.status&.name
  },
  changes: changes,
  note_applied: note_applied,
  parking_fields: parking_result,
  blocker_fields: blocker_result
}

puts JSON.pretty_generate(result)
