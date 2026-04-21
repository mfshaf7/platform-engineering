# frozen_string_literal: true

require "json"
require "time"

target_work_package_id = Integer(ENV.fetch("TARGET_WORK_PACKAGE_ID"))
new_parent_work_package_id = Integer(ENV.fetch("NEW_PARENT_WORK_PACKAGE_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
work_note = ENV["WORK_NOTE"]&.strip&.presence

project = Project.find_by!(identifier: delivery_project_identifier)
work_package = WorkPackage.find(target_work_package_id)
new_parent = WorkPackage.find(new_parent_work_package_id)

unless work_package.project_id == project.id
  raise "Work package #{target_work_package_id} is not in project #{delivery_project_identifier}"
end

unless new_parent.project_id == project.id
  raise "New parent work package #{new_parent_work_package_id} is not in project #{delivery_project_identifier}"
end

author = User.admin.active.first || User.active.first
raise "No active author user is available for work package updates" unless author

User.current = author if User.respond_to?(:current=)

if work_package.id == new_parent.id
  raise "A work package cannot become its own parent"
end

ancestor = new_parent
while ancestor
  if ancestor.id == work_package.id
    raise "Cannot move work package #{work_package.id} under one of its descendants"
  end
  ancestor = ancestor.parent
end

duplicate = WorkPackage
  .where(project_id: project.id, parent_id: new_parent.id, type_id: work_package.type_id)
  .where.not(id: work_package.id)
  .find { |candidate| candidate.subject.to_s.casecmp?(work_package.subject.to_s) }

if duplicate
  raise "A sibling work package already exists with parent #{new_parent.id}, type #{work_package.type&.name}, and subject #{work_package.subject.inspect}"
end

old_parent = work_package.parent
old_parent_id = old_parent&.id
old_parent_ref = old_parent ? "openproject://work_packages/#{old_parent.id}" : nil

note_applied = nil
changes = {}

if old_parent_id != new_parent.id
  changes[:parent] = {
    from: old_parent_id,
    to: new_parent.id
  }
  work_package.parent = new_parent
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

current_version_name =
  if work_package.respond_to?(:version)
    work_package.version&.name
  elsif work_package.respond_to?(:fixed_version)
    work_package.fixed_version&.name
  end

current_assignee_login =
  if work_package.respond_to?(:assigned_to)
    work_package.assigned_to&.respond_to?(:login) ? work_package.assigned_to.login : nil
  elsif work_package.respond_to?(:assignee)
    work_package.assignee&.respond_to?(:login) ? work_package.assignee.login : nil
  end

result = {
  work_package: {
    id: work_package.id,
    record_ref: "openproject://work_packages/#{work_package.id}",
    subject: work_package.subject,
    type: work_package.type&.name,
    status: work_package.status&.name,
    parent_id: work_package.parent_id,
    parent_ref: "openproject://work_packages/#{work_package.parent_id}",
    target_pi: current_version_name,
    assignee_login: current_assignee_login,
    description_present: work_package.description.to_s.strip.length.positive?
  },
  previous_parent: {
    id: old_parent_id,
    record_ref: old_parent_ref
  },
  changes: changes,
  note_applied: note_applied
}

puts JSON.pretty_generate(result)
