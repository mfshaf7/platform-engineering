# frozen_string_literal: true

require "date"
require "json"

target_epic_id = Integer(ENV.fetch("TARGET_EPIC_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
demo_date = ENV["DEMO_DATE"]&.strip&.presence || Date.current.iso8601
demo_outcome = ENV["DEMO_OUTCOME"]&.strip&.presence || "reviewed"
demo_summary = ENV.fetch("DEMO_SUMMARY").strip
demo_evidence = ENV.fetch("DEMO_EVIDENCE").strip
demo_follow_up = ENV["DEMO_FOLLOW_UP"]&.strip&.presence

raise "DEMO_SUMMARY must not be empty" if demo_summary.empty?
raise "DEMO_EVIDENCE must not be empty" if demo_evidence.empty?

project = Project.find_by!(identifier: delivery_project_identifier)
epic = WorkPackage.find(target_epic_id)

unless epic.project_id == project.id
  raise "Epic #{target_epic_id} is not in project #{delivery_project_identifier}"
end

raise "System demo records apply only to Epic initiatives" unless epic.type&.name == "Epic"

author = User.admin.active.first || User.active.first
raise "No active author user is available for system demo recording" unless author

User.current = author if User.respond_to?(:current=)

field = project.work_package_custom_fields.find_by!(name: "System Demo Evidence")
raise "\"System Demo Evidence\" is not available on #{epic.type&.name}" unless field.types.include?(epic.type)

custom_value = epic.custom_value_for(field)
entry_lines = [
  "### #{demo_date}",
  "- Outcome: #{demo_outcome}",
  "- Summary: #{demo_summary}",
  "- Evidence: #{demo_evidence}"
]
entry_lines << "- Follow-up: #{demo_follow_up}" if demo_follow_up
entry = entry_lines.join("\n")

saved_epic = nil
field_length = nil

WorkPackage.transaction do
  locked_epic = WorkPackage.lock.find(target_epic_id)
  custom_value = locked_epic.custom_value_for(field)
  custom_value = locked_epic.custom_values.build(custom_field: field) if custom_value.nil?

  current_value = custom_value.value.to_s.strip
  updated_value =
    if current_value.empty?
      entry
    else
      [current_value, entry].join("\n\n")
    end

  custom_value.value = updated_value
  locked_epic.save!
  locked_epic.reload
  saved_epic = locked_epic
  field_length = locked_epic.custom_value_for(field)&.value.to_s.length
end

result = {
  epic: {
    id: saved_epic.id,
    record_ref: "openproject://work_packages/#{saved_epic.id}",
    subject: saved_epic.subject
  },
  recorded_entry: {
    date: demo_date,
    outcome: demo_outcome,
    summary: demo_summary,
    evidence: demo_evidence,
    follow_up: demo_follow_up
  },
  field_length: field_length
}

puts JSON.pretty_generate(result)
