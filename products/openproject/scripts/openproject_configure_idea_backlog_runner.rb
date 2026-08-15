# frozen_string_literal: true

require "json"

RESULT_BEGIN = "__OPENPROJECT_IDEA_BACKLOG_BEGIN__"
RESULT_END = "__OPENPROJECT_IDEA_BACKLOG_END__"

DEMO_PROJECT_IDENTIFIERS = %w[demo-project your-scrum-project].freeze
PROJECT_IDENTIFIER = "workspace-proposals"
PROJECT_NAME = "Workspace Proposals"
PROJECT_DESCRIPTION = <<~TEXT.strip
  Canonical backlog for captured ideas and proposals that originate from operator workflows.
TEXT
PROJECT_MODULES = %w[work_package_tracking].freeze
PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH = File.join(__dir__, "proposal-workflow-state.schema.json")
PROPOSAL_WORKFLOW_STATE_SCHEMA = JSON.parse(File.read(PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH)).freeze

unless PROPOSAL_WORKFLOW_STATE_SCHEMA.dig("properties", "schema_version", "const") == 1
  raise "Proposal workflow-state schema must declare schema_version 1"
end

TYPE_SPECS = [
  { name: "Idea", description: "Default type for newly captured items." },
  { name: "Governance Proposal", description: "Proposal targeting workspace or platform governance." },
  { name: "Security Proposal", description: "Proposal targeting security posture or trust boundaries." },
  { name: "Product Proposal", description: "Proposal targeting a product-level workflow or operating model." },
  { name: "Component Proposal", description: "Proposal targeting a shared or product component." }
].freeze

STATUS_SPECS = [
  { name: "captured", is_closed: false, default_done_ratio: 0 },
  { name: "triaged", is_closed: false, default_done_ratio: 10 },
  { name: "parked", is_closed: false, default_done_ratio: 25 },
  { name: "owner-assigned", is_closed: false, default_done_ratio: 40 },
  { name: "accepted", is_closed: false, default_done_ratio: 60 },
  { name: "rejected", is_closed: true, default_done_ratio: 100 },
  { name: "implemented", is_closed: true, default_done_ratio: 100 },
  { name: "superseded", is_closed: true, default_done_ratio: 100 }
].freeze

CUSTOM_FIELD_SPECS = [
  {
    name: "Source Surface",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false
  },
  {
    name: "Source Reference",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 512
  },
  {
    name: "Delivery Ref",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 512
  },
  {
    name: "Suspected Owner",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false
  },
  {
    name: "Affected Scope",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 512
  },
  {
    name: "Trust Boundary Areas",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: true,
    possible_values: %w[identity secrets delivery runtime ai]
  },
  {
    name: "Promotion Target",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: [
      "workspace-governance",
      "platform-engineering",
      "security-architecture",
      "product-repo"
    ]
  },
  {
    name: "Triage Decision ID",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false
  },
  {
    name: "Triage Confidence",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: %w[low medium high]
  },
  {
    name: "AI Assist Lane",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: %w[none local governed exception]
  },
  {
    name: "Revisit On",
    field_format: "date",
    searchable: false,
    is_filter: true,
    multi_value: false
  },
  {
    name: "Proposal Workflow State",
    field_format: "text",
    searchable: false,
    is_filter: false,
    multi_value: false,
    max_length: 32_768
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
    type.is_milestone = false
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

deleted_projects = []
DEMO_PROJECT_IDENTIFIERS.each do |identifier|
  project = Project.find_by(identifier: identifier)
  next unless project

  deleted_projects << { id: project.id, identifier: project.identifier, name: project.name }
  project.destroy!
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
  deleted_projects: deleted_projects,
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
  proposal_workflow_state: {
    field_name: "Proposal Workflow State",
    schema_id: PROPOSAL_WORKFLOW_STATE_SCHEMA.fetch("$id"),
    schema_version: PROPOSAL_WORKFLOW_STATE_SCHEMA.dig("properties", "schema_version", "const")
  },
  statuses: statuses.map { |status| { id: status.id, name: status.name, is_closed: status.is_closed } },
  types: types.map { |type| { id: type.id, name: type.name, workflow_count: Workflow.where(type_id: type.id).count } }
}

puts RESULT_BEGIN
puts JSON.pretty_generate(result)
puts RESULT_END
