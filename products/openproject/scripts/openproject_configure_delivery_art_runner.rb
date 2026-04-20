# frozen_string_literal: true

require "json"

RESULT_BEGIN = "__OPENPROJECT_DELIVERY_ART_BEGIN__"
RESULT_END = "__OPENPROJECT_DELIVERY_ART_END__"

PROJECT_IDENTIFIER = "workspace-delivery-art"
PROJECT_NAME = "Workspace Delivery ART"
PROJECT_DESCRIPTION = <<~TEXT.strip
  Canonical delivery plane for accepted ideas that have moved out of Workspace Proposals.
TEXT
PROJECT_MODULES = %w[work_package_tracking].freeze

TYPE_SPECS = [
  {
    name: "Epic",
    description: "Top-level delivery initiative for one consumed accepted idea.",
    is_milestone: false
  },
  {
    name: "Feature",
    description: "Delivery feature inside the single-ART execution model.",
    is_milestone: false
  },
  {
    name: "Enabler",
    description: "Delivery enabler needed for the single-ART execution model.",
    is_milestone: false
  },
  {
    name: "User story",
    description: "User-facing or operator-facing delivery slice under a feature or enabler.",
    is_milestone: false
  },
  {
    name: "Task",
    description: "Execution task inside the delivery ART project.",
    is_milestone: false
  },
  {
    name: "Milestone",
    description: "Milestone marker inside the delivery ART project.",
    is_milestone: true
  }
].freeze

STATUS_SPECS = [
  { name: "new", is_closed: false, default_done_ratio: 0 },
  { name: "ready", is_closed: false, default_done_ratio: 20 },
  { name: "in-progress", is_closed: false, default_done_ratio: 50 },
  { name: "blocked", is_closed: false, default_done_ratio: 50 },
  { name: "done", is_closed: true, default_done_ratio: 100 }
].freeze

CUSTOM_FIELD_SPECS = [
  {
    name: "PM² Phase",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["Initiating", "Planning", "Executing", "Closing"]
  },
  {
    name: "Origin Idea Ref",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 512
  },
  {
    name: "Sponsor",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255
  },
  {
    name: "Business Objective",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024
  },
  {
    name: "Success Criteria",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024
  },
  {
    name: "Target PI",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255
  },
  {
    name: "Blocker Statement",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024
  },
  {
    name: "Blocker Impact",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024
  },
  {
    name: "Blocker Owner",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255
  },
  {
    name: "Blocker Discovered On",
    field_format: "date",
    searchable: false,
    is_filter: true,
    multi_value: false
  },
  {
    name: "Blocker Decision Path",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["remove", "workaround", "accept-risk", "defer"]
  },
  {
    name: "Blocker Justification",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024
  },
  {
    name: "Blocker Follow-Up Owner",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255
  },
  {
    name: "Blocker Review Date",
    field_format: "date",
    searchable: false,
    is_filter: true,
    multi_value: false
  }
].freeze

def find_by_name_ci(model_class, name)
  model_class.where("LOWER(name) = ?", name.downcase).first
end

def ensure_statuses!
  max_position = Status.maximum(:position) || 0

  STATUS_SPECS.map do |spec|
    status = find_by_name_ci(Status, spec[:name]) || Status.new
    if status.new_record?
      max_position += 1
      status.position = max_position
    end
    status.name = spec[:name]
    status.is_closed = spec[:is_closed]
    status.default_done_ratio = spec[:default_done_ratio]
    status.save!
    status
  end
end

def ensure_types!
  max_position = Type.maximum(:position) || 0

  TYPE_SPECS.map do |spec|
    type = find_by_name_ci(Type, spec[:name]) || Type.new
    if type.new_record?
      max_position += 1
      type.position = max_position
    end
    type.name = spec[:name]
    type.description = spec[:description]
    type.is_default = false
    type.is_standard = false
    type.is_milestone = spec[:is_milestone]
    type.is_in_roadmap = false
    type.save!
    type
  end
end

def ensure_custom_field!(project:, types:, spec:, position:)
  field = WorkPackageCustomField.find_or_initialize_by(name: spec[:name])
  if field.new_record?
    field.field_format = spec[:field_format]
  elsif field.field_format != spec[:field_format]
    raise "Custom field #{spec[:name].inspect} has format #{field.field_format.inspect}, expected #{spec[:field_format].inspect}"
  end
  field.searchable = spec.fetch(:searchable, false)
  field.is_filter = spec.fetch(:is_filter, false)
  field.multi_value = spec.fetch(:multi_value, false)
  field.is_for_all = false
  field.is_required = false
  field.editable = true
  field.admin_only = false
  field.position = position if field.new_record?
  field.max_length = spec[:max_length] if spec.key?(:max_length)
  field.possible_values = spec[:possible_values] if spec.key?(:possible_values)
  field.save!

  field.projects = [project]
  field.types = types
  field.save!
  field
end

def ensure_project!(types:)
  project = Project.find_or_initialize_by(identifier: PROJECT_IDENTIFIER)
  project.name = PROJECT_NAME
  project.description = PROJECT_DESCRIPTION
  project.public = false
  project.active = true
  project.workspace_type = :project
  project.enabled_module_names = PROJECT_MODULES
  project.save!
  project.types = types
  project.save!
  project
end

def rebuild_workflows!(types:, statuses:)
  role_ids = Role.distinct.pluck(:id)
  status_ids = statuses.map(&:id)
  type_ids = types.map(&:id)
  quoted_status_ids = status_ids.join(",")
  statuses_table = Status.table_name

  Workflow.transaction do
    Workflow.where(type_id: type_ids).delete_all

    types.each do |type|
      role_ids.each do |role_id|
        Workflow.connection.insert(<<~SQL)
          INSERT INTO #{Workflow.table_name} (type_id, role_id, old_status_id, new_status_id, author, assignee)
          SELECT #{type.id}, #{role_id}, old_statuses.id, new_statuses.id, FALSE, FALSE
          FROM #{statuses_table} old_statuses
          CROSS JOIN #{statuses_table} new_statuses
          WHERE old_statuses.id IN (#{quoted_status_ids})
            AND new_statuses.id IN (#{quoted_status_ids})
        SQL
      end
    end
  end
end

statuses = ensure_statuses!
types = ensure_types!
project = ensure_project!(types: types)

CUSTOM_FIELD_SPECS.each_with_index do |spec, index|
  ensure_custom_field!(project: project, types: types, spec: spec, position: index + 1)
end

rebuild_workflows!(types: types, statuses: statuses)

project.reload

result = {
  project: {
    id: project.id,
    identifier: project.identifier,
    name: project.name,
    enabled_modules: project.enabled_module_names,
    types: project.types.pluck(:name),
    work_package_custom_fields: project.work_package_custom_fields.order(:position).map do |field|
      {
        id: field.id,
        name: field.name,
        field_format: field.field_format
      }
    end
  },
  statuses: statuses.map do |status|
    {
      id: status.id,
      name: status.name,
      is_closed: status.is_closed
    }
  end,
  types: types.map do |type|
    {
      id: type.id,
      is_milestone: type.is_milestone,
      name: type.name
    }
  end
}

puts RESULT_BEGIN
puts JSON.pretty_generate(result)
puts RESULT_END
