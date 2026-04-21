# frozen_string_literal: true

require "date"
require "json"
require "set"

reviews_path = ARGV.fetch(0)
target_epic_id = Integer(ENV.fetch("TARGET_EPIC_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
target_pi = ENV["TARGET_PI"]&.strip&.presence
pi_review_date = ENV["PI_REVIEW_DATE"]&.strip&.presence || Date.current.iso8601

reviews_payload = JSON.parse(File.read(reviews_path))
unless reviews_payload.is_a?(Hash) &&
       reviews_payload["schema_version"] == 1 &&
       reviews_payload["reviews"].is_a?(Array)
  raise "PI review payload must be a JSON object with schema_version=1 and a reviews array"
end

def validate_review_shape!(review, path)
  raise "#{path} must be an object" unless review.is_a?(Hash)

  supported_keys = [
    "target_work_package_id",
    "actual_business_value",
    "review_outcome",
    "review_note"
  ]
  unknown_keys = review.keys - supported_keys
  raise "#{path} contains unsupported keys: #{unknown_keys.join(', ')}" if unknown_keys.any?

  Integer(review.fetch("target_work_package_id"))
  Integer(review.fetch("actual_business_value"))

  review_outcome = review.fetch("review_outcome")
  raise "#{path}.review_outcome must be a non-empty string" unless review_outcome.is_a?(String) && !review_outcome.strip.empty?

  if review.key?("review_note")
    review_note = review["review_note"]
    raise "#{path}.review_note must be a non-empty string when provided" unless review_note.is_a?(String) && !review_note.strip.empty?
  end
rescue KeyError => e
  raise "#{path} is missing required key #{e.message}"
rescue ArgumentError
  raise "#{path} contains invalid numeric values"
end

reviews_payload["reviews"].each_with_index do |review, index|
  validate_review_shape!(review, "reviews[#{index}]")
end

project = Project.find_by!(identifier: delivery_project_identifier)
epic = WorkPackage.find(target_epic_id)
unless epic.project_id == project.id
  raise "Epic #{target_epic_id} is not in project #{delivery_project_identifier}"
end

author = User.admin.active.first || User.active.first
raise "No active author user is available for PI review recording" unless author
User.current = author if User.respond_to?(:current=)

objective_type = Type.all.find { |entry| entry.name == "PI Objective" }
raise "PI Objective type is missing from this OpenProject runtime" if objective_type.nil?

custom_fields = project.work_package_custom_fields.where(
  name: ["Actual Business Value", "PI Objective Review Outcome"]
).index_by(&:name)
missing_fields = ["Actual Business Value", "PI Objective Review Outcome"].reject { |name| custom_fields.key?(name) }
raise "Missing PI review custom fields: #{missing_fields.join(', ')}" if missing_fields.any?

review_outcome_field = custom_fields.fetch("PI Objective Review Outcome")
actual_business_value_field = custom_fields.fetch("Actual Business Value")
possible_review_outcomes =
  if review_outcome_field.respond_to?(:custom_options)
    review_outcome_field.custom_options.map { |entry| entry.value.to_s.strip }.reject(&:empty?)
  else
    Array(review_outcome_field.possible_values).map { |entry| entry.to_s.strip }.reject(&:empty?)
  end

work_packages = WorkPackage.where(project_id: project.id).to_a
by_id = work_packages.index_by(&:id)
children_by_parent_id = Hash.new { |hash, key| hash[key] = [] }
work_packages.each do |entry|
  children_by_parent_id[entry.parent_id] << entry if entry.parent_id
end

build_descendants = lambda do |parent_id|
  children_by_parent_id[parent_id].flat_map do |child|
    [child.id] + build_descendants.call(child.id)
  end
end
allowed_objective_ids = build_descendants.call(epic.id).select do |work_package_id|
  by_id[work_package_id]&.type_id == objective_type.id
end.to_set

work_package_version_name = lambda do |entry|
  if entry.respond_to?(:version)
    entry.version&.name
  elsif entry.respond_to?(:fixed_version)
    entry.fixed_version&.name
  end
end

append_review_note = lambda do |current_description, review_entry|
  heading = "## PI Review Notes"
  rendered = current_description.to_s.strip

  if rendered.empty?
    [heading, "", review_entry].join("\n")
  elsif rendered.include?(heading)
    [rendered, review_entry].join("\n")
  else
    [rendered, "", heading, "", review_entry].join("\n")
  end
end

updated = []

reviews_payload["reviews"].each do |review|
  objective_id = Integer(review.fetch("target_work_package_id"))
  raise "Work package #{objective_id} is not a descendant PI Objective of epic #{epic.id}" unless allowed_objective_ids.include?(objective_id)

  WorkPackage.transaction do
    objective = WorkPackage.lock.find(objective_id)
    raise "Work package #{objective_id} is not in project #{delivery_project_identifier}" unless objective.project_id == project.id
    raise "Work package #{objective_id} is not a PI Objective" unless objective.type&.name == "PI Objective"
    raise "\"Actual Business Value\" is not available on #{objective.type&.name}" unless actual_business_value_field.types.include?(objective.type)
    raise "\"PI Objective Review Outcome\" is not available on #{objective.type&.name}" unless review_outcome_field.types.include?(objective.type)

    if target_pi && work_package_version_name.call(objective) != target_pi
      raise "Work package #{objective_id} does not belong to target PI #{target_pi.inspect}"
    end

    review_outcome = review.fetch("review_outcome").strip
    if possible_review_outcomes.any? && !possible_review_outcomes.include?(review_outcome)
      raise "Invalid review_outcome #{review_outcome.inspect}"
    end

    changes = {}

    actual_value = Integer(review.fetch("actual_business_value")).to_s
    current_actual_value = objective.custom_value_for(actual_business_value_field)&.value.to_s.strip.presence
    if current_actual_value != actual_value
      changes[:actual_business_value] = { from: current_actual_value, to: actual_value }
      custom_value = objective.custom_value_for(actual_business_value_field)
      custom_value = objective.custom_values.build(custom_field: actual_business_value_field) if custom_value.nil?
      custom_value.value = actual_value
    end

    current_review_outcome = objective.custom_value_for(review_outcome_field)&.value.to_s.strip.presence
    if current_review_outcome != review_outcome
      changes[:review_outcome] = { from: current_review_outcome, to: review_outcome }
      custom_value = objective.custom_value_for(review_outcome_field)
      custom_value = objective.custom_values.build(custom_field: review_outcome_field) if custom_value.nil?
      custom_value.value = review_outcome
    end

    review_note = review["review_note"]&.strip&.presence
    note_applied = false
    if review_note
      review_entry_lines = [
        "### #{pi_review_date}",
        "- Outcome: #{review_outcome}",
        "- Actual Business Value: #{actual_value}",
        "- Note: #{review_note}"
      ]
      objective.description = append_review_note.call(objective.description, review_entry_lines.join("\n"))
      note_applied = true
    end

    objective.save! if objective.changed? || objective.custom_values.any?(&:changed?) || note_applied
    objective.reload

    updated << {
      work_package: {
        id: objective.id,
        record_ref: "openproject://work_packages/#{objective.id}",
        subject: objective.subject,
        status: objective.status&.name,
        target_pi: work_package_version_name.call(objective),
        review_outcome: objective.custom_value_for(review_outcome_field)&.value,
        actual_business_value: objective.custom_value_for(actual_business_value_field)&.value
      },
      changes: changes,
      review_note_recorded: note_applied
    }
  end
end

updated_objectives = updated.map { |entry| entry.fetch(:work_package) }
counts = updated_objectives.each_with_object(Hash.new(0)) do |entry, result|
  value = entry[:review_outcome].presence || "_none_"
  result[value] += 1
end.sort.to_h

result = {
  epic: {
    id: epic.id,
    record_ref: "openproject://work_packages/#{epic.id}",
    subject: epic.subject
  },
  summary: {
    target_pi: target_pi,
    review_date: pi_review_date,
    updated_count: updated.length,
    by_review_outcome: counts,
    actual_business_value_total: updated_objectives.sum { |entry| entry[:actual_business_value].to_i }
  },
  updated: updated
}

puts JSON.pretty_generate(result)
