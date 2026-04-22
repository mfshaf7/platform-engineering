# frozen_string_literal: true

require "date"
require "json"
require "time"
require_relative "openproject_delivery_art_custom_field_support"

action = ENV.fetch("ACTION").strip
target_work_package_id = Integer(ENV.fetch("TARGET_WORK_PACKAGE_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
resume_status_name = ENV["RESUME_STATUS"]&.strip
park_decision = ENV["PARK_DECISION"]&.strip
retirement_reason = ENV["RETIREMENT_REASON"]&.strip
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

custom_fields = project.work_package_custom_fields
  .where(name: parking_field_names + blocker_field_names)
  .index_by(&:name)

missing_fields = parking_field_names.reject { |name| custom_fields.key?(name) }
raise "Missing delivery parking custom fields: #{missing_fields.join(', ')}" if missing_fields.any?

decision_field = custom_fields.fetch("Parking Decision")
decision_values = OpenprojectDeliveryArtCustomFieldSupport.list_allowed_values(decision_field)
retirement_reason_field = custom_fields.fetch("Retirement Reason")
retirement_reason_values = OpenprojectDeliveryArtCustomFieldSupport.list_allowed_values(retirement_reason_field)

def parse_iso_date!(value, field_name)
  Date.iso8601(value)
  value
rescue ArgumentError
  raise "#{field_name} must be an ISO date (YYYY-MM-DD)"
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
    raise "RETIREMENT_REASON must not be set for PARK_DECISION=defer" if retirement_reason&.present?
  elsif park_review_date && !park_review_date.empty?
    parse_iso_date!(park_review_date, "PARK_REVIEW_DATE")
  end

  if park_decision == "retire"
    raise "RETIREMENT_REASON is required for PARK_DECISION=retire" if retirement_reason.nil? || retirement_reason.empty?
    raise "PARK_REVIEW_DATE must not be set for PARK_DECISION=retire" if park_review_date&.present?
    if retirement_reason_values.any? && !retirement_reason_values.include?(retirement_reason)
      raise "Unknown RETIREMENT_REASON #{retirement_reason.inspect}"
    end
  end

  target_status_name = park_decision == "retire" ? "retired" : "parked"
  target_status = Status.find_by!(name: target_status_name)
  if work_package.status&.name != target_status.name
    changes[:status] = {
      from: work_package.status&.name,
      to: target_status.name
    }
    work_package.status = target_status
  end

  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Parking Decision"), value: park_decision, kind: :list)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Parking Reason"), value: park_reason, kind: :string)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Parking Review Date"), value: park_review_date.presence, kind: :date)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Retirement Reason"), value: park_decision == "retire" ? retirement_reason : nil, kind: :list)

  blocker_field_names.each do |field_name|
    field = custom_fields[field_name]
    next unless field

    OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field:, value: nil)
  end
when "resume"
  if resume_status_name.nil? || resume_status_name.empty?
    raise "RESUME_STATUS is required for ACTION=resume"
  end

  resume_status = Status.find_by(name: resume_status_name)
  raise "Unknown RESUME_STATUS #{resume_status_name.inspect}" unless resume_status
  raise "RESUME_STATUS must not be parked or retired" if %w[parked retired].include?(resume_status.name)

  if work_package.status&.name != resume_status.name
    changes[:status] = {
      from: work_package.status&.name,
      to: resume_status.name
    }
    work_package.status = resume_status
  end

  parking_field_names.each do |field_name|
    field = custom_fields.fetch(field_name)
    OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field:, value: nil)
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
  [field_name, OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: field)]
end

blocker_result = blocker_field_names.filter_map do |field_name|
  field = custom_fields[field_name]
  next unless field

  [field_name, OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: field)]
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
