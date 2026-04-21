# frozen_string_literal: true

require "json"

action = ENV.fetch("ACTION").strip
target_work_package_id = Integer(ENV.fetch("TARGET_WORK_PACKAGE_ID"))
depends_on_work_package_id = Integer(ENV.fetch("DEPENDS_ON_WORK_PACKAGE_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
lag_input = ENV["LAG"]&.strip
clear_lag = ENV.fetch("CLEAR_LAG", "false") == "true"
description = ENV["DESCRIPTION"]&.strip&.presence
clear_description = ENV.fetch("CLEAR_DESCRIPTION", "false") == "true"

if lag_input&.present? && clear_lag
  raise "LAG and CLEAR_LAG=true cannot be used together"
end

if description && clear_description
  raise "DESCRIPTION and CLEAR_DESCRIPTION=true cannot be used together"
end

project = Project.find_by!(identifier: delivery_project_identifier)
target = WorkPackage.find(target_work_package_id)
depends_on = WorkPackage.find(depends_on_work_package_id)

if target.id == depends_on.id
  raise "A work package cannot depend on itself"
end

[target, depends_on].each do |work_package|
  next if work_package.project_id == project.id

  raise "Work package #{work_package.id} is not in project #{delivery_project_identifier}"
end

parse_optional_integer = lambda do |value, field_name|
  return nil if value.nil? || value.empty?

  Integer(value)
rescue ArgumentError
  raise "#{field_name} must be an integer"
end

relation_scope = lambda do
  Relation.where(
    from_id: depends_on.id,
    to_id: target.id,
    relation_type: "follows",
  ).order(:id)
end

relation_summary = lambda do |relation|
  {
    id: relation.id,
    relation_type: relation.relation_type,
    lag: relation.lag,
    description: relation.description.presence,
    depends_on: {
      id: depends_on.id,
      record_ref: "openproject://work_packages/#{depends_on.id}",
      subject: depends_on.subject,
      status: depends_on.status&.name
    },
    target: {
      id: target.id,
      record_ref: "openproject://work_packages/#{target.id}",
      subject: target.subject,
      status: target.status&.name
    }
  }
end

result =
  case action
  when "set"
    lag = parse_optional_integer.call(lag_input, "LAG")
    relations = relation_scope.call.to_a
    relation = relations.shift || Relation.new(
      from: depends_on,
      to: target,
      relation_type: "follows",
    )
    created = relation.new_record?
    changes = {}

    if clear_lag
      if relation.lag.present?
        changes[:lag] = {
          from: relation.lag,
          to: nil
        }
        relation.lag = nil
      end
    elsif !lag_input.nil? && relation.lag != lag
      changes[:lag] = {
        from: relation.lag,
        to: lag
      }
      relation.lag = lag
    end

    if clear_description
      current_description = relation.description.to_s.strip.presence
      if current_description.present?
        changes[:description] = {
          from: current_description,
          to: nil
        }
        relation.description = nil
      end
    elsif !description.nil?
      current_description = relation.description.to_s.strip.presence
      if current_description != description
        changes[:description] = {
          from: current_description,
          to: description
        }
        relation.description = description
      end
    end

    relation.save!

    removed_duplicate_relation_ids = relations.map(&:id)
    relations.each(&:destroy!)

    {
      action: action,
      created: created,
      updated: changes.any?,
      removed_duplicate_relation_ids: removed_duplicate_relation_ids,
      changes: changes,
      relation: relation_summary.call(relation)
    }
  when "clear"
    relations = relation_scope.call.to_a
    removed_relation_ids = relations.map(&:id)
    relations.each(&:destroy!)

    {
      action: action,
      removed_count: removed_relation_ids.length,
      removed_relation_ids: removed_relation_ids,
      relation: {
        relation_type: "follows",
        depends_on: {
          id: depends_on.id,
          record_ref: "openproject://work_packages/#{depends_on.id}",
          subject: depends_on.subject,
          status: depends_on.status&.name
        },
        target: {
          id: target.id,
          record_ref: "openproject://work_packages/#{target.id}",
          subject: target.subject,
          status: target.status&.name
        }
      }
    }
  else
    raise "ACTION must be set or clear"
  end

puts JSON.pretty_generate(result)
