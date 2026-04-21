# frozen_string_literal: true

require "json"
require "time"

target_work_package_id = Integer(ENV.fetch("TARGET_WORK_PACKAGE_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
completion_summary = ENV.fetch("COMPLETION_SUMMARY").strip
changed_surfaces = ENV.fetch("CHANGED_SURFACES").strip
test_result_evidence = ENV.fetch("TEST_RESULT_EVIDENCE").strip
test_result_artifact_path = ENV["TEST_RESULT_ARTIFACT_PATH"]&.strip&.presence
test_result_artifact_name = ENV["TEST_RESULT_ARTIFACT_NAME"]&.strip&.presence
test_result_artifact_description = ENV["TEST_RESULT_ARTIFACT_DESCRIPTION"]&.strip&.presence
validation_evidence = ENV.fetch("VALIDATION_EVIDENCE").strip
completion_note = ENV["COMPLETION_NOTE"]&.strip&.presence
COMPLETION_REQUIRED_FIELD_NAMES_BY_TYPE = {
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
  ]
}.freeze

raise "COMPLETION_SUMMARY must not be empty" if completion_summary.empty?
raise "CHANGED_SURFACES must not be empty" if changed_surfaces.empty?
raise "TEST_RESULT_EVIDENCE must not be empty" if test_result_evidence.empty?
raise "VALIDATION_EVIDENCE must not be empty" if validation_evidence.empty?

if test_result_artifact_path && !File.file?(test_result_artifact_path)
  raise "TEST_RESULT_ARTIFACT_PATH does not exist: #{test_result_artifact_path}"
end

project = Project.find_by!(identifier: delivery_project_identifier)
work_package = WorkPackage.find(target_work_package_id)

unless work_package.project_id == project.id
  raise "Work package #{target_work_package_id} is not in project #{delivery_project_identifier}"
end

author = User.admin.active.first || User.active.first
raise "No active author user is available for work package completion" unless author

User.current = author if User.respond_to?(:current=)

done_status = Status.find_by!(name: "done")
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
blocker_fields = project.work_package_custom_fields.where(name: blocker_field_names).index_by(&:name)
completion_required_fields = project.work_package_custom_fields
  .where(name: COMPLETION_REQUIRED_FIELD_NAMES_BY_TYPE.values.flatten.uniq)
  .index_by(&:name)

read_blocker_fields = lambda do |entry|
  blocker_field_names.to_h do |field_name|
    field = blocker_fields[field_name]
    value = field ? entry.custom_value_for(field)&.value.presence : nil
    [field_name, value]
  end
end

blocker_values = read_blocker_fields.call(work_package)
if work_package.status&.name == "blocked" || blocker_values.values.any?(&:present?)
  raise "Work package #{target_work_package_id} still has active blocker state; clear it before completion"
end

required_field_names = COMPLETION_REQUIRED_FIELD_NAMES_BY_TYPE.fetch(work_package.type&.name, [])
missing_field_names = required_field_names.reject do |field_name|
  completion_required_fields[field_name] && work_package.custom_value_for(completion_required_fields[field_name])&.value.to_s.strip.present?
end
if missing_field_names.any?
  raise "Work package #{target_work_package_id} cannot complete while required execution fields are missing: #{missing_field_names.join(', ')}"
end

def normalize_markdown_sections(markdown)
  markdown.to_s
    .gsub(/([^\n])## /, "\\1\n\n## ")
    .gsub(/\n{3,}/, "\n\n")
    .strip
end

def remove_section(markdown, heading)
  rendered = normalize_markdown_sections(markdown)
  pattern = /^## #{Regexp.escape(heading)}\n.*?(?=^## |\z)/m
  rendered.gsub(pattern, "").gsub(/\n{3,}/, "\n\n").strip
end

def replace_or_append_section(markdown, heading, body)
  rendered = remove_section(markdown, heading)
  section = "## #{heading}\n#{body.strip}"

  if rendered.empty?
    section
  else
    [rendered, section].join("\n\n")
  end
end

def append_work_note_to_description(current_description, note, author_login)
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

current_description = work_package.description.to_s
updated_description = current_description.dup
legacy_completion_headings = [
  "Completed Output",
  "Completed Scope",
  "Acceptance Evidence",
  "Verification",
  "Result"
]
legacy_completion_headings.each do |heading|
  updated_description = remove_section(updated_description, heading)
end
test_result_section_body = test_result_evidence.dup
if test_result_artifact_path
  artifact_display_name = test_result_artifact_name || File.basename(test_result_artifact_path)
  artifact_lines = ["Attached test artifact:", "- #{artifact_display_name}"]
  test_result_section_body = [test_result_section_body, artifact_lines.join("\n")].join("\n\n")
end
updated_description = replace_or_append_section(
  updated_description,
  "Completion Summary",
  completion_summary,
)
updated_description = replace_or_append_section(
  updated_description,
  "Changed Surfaces",
  changed_surfaces,
)
updated_description = replace_or_append_section(
  updated_description,
  "Test Result Evidence",
  test_result_section_body,
)
updated_description = replace_or_append_section(
  updated_description,
  "Validation Evidence",
  validation_evidence,
)

changes = {}

if work_package.status_id != done_status.id
  changes[:status] = {
    from: work_package.status&.name,
    to: done_status.name
  }
  work_package.status = done_status
end

if work_package.respond_to?(:remaining_hours) && work_package.remaining_hours.to_f != 0.0
  changes[:remaining_work] = {
    from: work_package.remaining_hours,
    to: 0.0
  }
  work_package.remaining_hours = 0.0
end

if work_package.respond_to?(:done_ratio) && work_package.done_ratio.to_i != 100
  changes[:percent_complete] = {
    from: work_package.done_ratio,
    to: 100
  }
  work_package.done_ratio = 100
end

if work_package.description.to_s.strip != updated_description.strip
  changes[:description] = {
    from_present: work_package.description.to_s.strip.present?,
    to_present: true
  }
  work_package.description = updated_description
end

added_attachments = []
replaced_attachments = []

note_applied = nil
if completion_note
  if work_package.respond_to?(:notes=)
    work_package.notes = completion_note
    note_applied = "journal"
  else
    work_package.description = append_work_note_to_description(
      work_package.description.to_s,
      completion_note,
      author.login,
    )
    note_applied = "description_section"
  end
end

work_package.save!

if test_result_artifact_path
  artifact_name = test_result_artifact_name || File.basename(test_result_artifact_path)
  work_package.attachments.select { |existing_attachment| existing_attachment.filename == artifact_name }.each do |existing_attachment|
    replaced_attachments << {
      id: existing_attachment.id,
      filename: existing_attachment.filename
    }
    existing_attachment.destroy!
  end
  content_type = Attachment.content_type_for(test_result_artifact_path)
  uploaded_file = OpenProject::Files.create_uploaded_file(
    name: artifact_name,
    content_type: content_type,
    content: File.binread(test_result_artifact_path),
    binary: true,
  )
  attachment = Attachment.new(
    container: work_package,
    author: author,
    description: test_result_artifact_description,
    file: uploaded_file,
  )
  attachment.save!
  added_attachments << {
    id: attachment.id,
    filename: attachment.filename,
    content_type: attachment.content_type,
    filesize: attachment.filesize,
    description: attachment.description
  }
end

work_package.reload

result = {
  work_package: {
    id: work_package.id,
    record_ref: "openproject://work_packages/#{work_package.id}",
    subject: work_package.subject,
    type: work_package.type&.name,
    status: work_package.status&.name,
    remaining_work: work_package.respond_to?(:remaining_hours) ? work_package.remaining_hours : nil,
    percent_complete: work_package.respond_to?(:done_ratio) ? work_package.done_ratio : nil,
    attachment_count: work_package.attachments.count,
    attachment_filenames: work_package.attachments.order(:id).map(&:filename),
    completion_evidence_sections: {
      completion_summary: work_package.description.to_s.include?("## Completion Summary"),
      changed_surfaces: work_package.description.to_s.include?("## Changed Surfaces"),
      test_result_evidence: work_package.description.to_s.include?("## Test Result Evidence"),
      validation_evidence: work_package.description.to_s.include?("## Validation Evidence")
    }
  },
  changes: changes,
  note_applied: note_applied,
  attachments_replaced: replaced_attachments,
  attachments_added: added_attachments
}

puts JSON.pretty_generate(result)
