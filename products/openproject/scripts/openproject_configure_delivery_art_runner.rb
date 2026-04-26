# frozen_string_literal: true

require "json"
require_relative "openproject_delivery_art_home_support"
require_relative "openproject_delivery_art_taxonomy_support"

RESULT_BEGIN = "__OPENPROJECT_DELIVERY_ART_BEGIN__"
RESULT_END = "__OPENPROJECT_DELIVERY_ART_END__"
INITIATIVE_LINEAGE_CONTRACT_PATH = [
  File.expand_path("delivery-art-initiative-lineage.json", __dir__),
  File.expand_path("../delivery-art-initiative-lineage.json", __dir__)
].find { |path| File.exist?(path) }
raise "Missing delivery-art-initiative-lineage.json support file" if INITIATIVE_LINEAGE_CONTRACT_PATH.nil?
INITIATIVE_LINEAGE_CONTRACT = JSON.parse(
  File.read(INITIATIVE_LINEAGE_CONTRACT_PATH)
)

PROJECT_IDENTIFIER = "workspace-delivery-art"
PROJECT_NAME = "Workspace Delivery ART"
PROJECT_DESCRIPTION = OpenprojectDeliveryArtHomeSupport.render_description
PROJECT_MODULES = %w[work_package_tracking board_view].freeze

EXECUTION_CLASSIFICATION_FIELD_NAME = OpenprojectDeliveryArtTaxonomySupport.classification_field_name
EXECUTION_CLASSIFICATION_VALUES = OpenprojectDeliveryArtTaxonomySupport.classification_values.freeze
STRUCTURAL_TYPE_NAMES = OpenprojectDeliveryArtTaxonomySupport.structural_type_names.freeze
EXECUTION_CLASSIFICATION_TYPE_NAMES = OpenprojectDeliveryArtTaxonomySupport.classification_required_types.freeze
EXECUTION_FIELD_TYPE_NAMES = (STRUCTURAL_TYPE_NAMES - ["Epic"]).freeze
WORKFLOW_FIELD_TYPE_NAMES = STRUCTURAL_TYPE_NAMES.freeze
WSJF_TYPE_NAMES = ["Feature"].freeze
INITIATIVE_LINEAGE_CUSTOM_FIELDS = INITIATIVE_LINEAGE_CONTRACT.fetch("custom_fields")

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
    name: "PI Objective",
    description: "SAFe Program Increment objective tracked under the delivery initiative.",
    is_milestone: false
  },
  {
    name: "User story",
    description: "Operator-facing or implementation-facing delivery story under a feature.",
    is_milestone: false
  },
  {
    name: "Defect",
    description: "Concrete defect correction tracked as a first-class delivery work item.",
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
  },
  {
    name: "Risk",
    description: "SAFe program risk tracked with ROAM state inside the delivery ART.",
    is_milestone: false
  }
].freeze

STATUS_SPECS = [
  { name: "new", is_closed: false, default_done_ratio: 0 },
  { name: "ready", is_closed: false, default_done_ratio: 20 },
  { name: "in-progress", is_closed: false, default_done_ratio: 50 },
  { name: "blocked", is_closed: false, default_done_ratio: 50 },
  { name: "parked", is_closed: false, default_done_ratio: 0 },
  { name: "retired", is_closed: true, default_done_ratio: 100 },
  { name: "done", is_closed: true, default_done_ratio: 100 }
].freeze

CUSTOM_FIELD_SPECS = [
  {
    name: "PM² Phase",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["Initiating", "Planning", "Executing", "Closing"],
    type_names: ["Epic"]
  },
  {
    name: "Origin Idea Ref",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 512,
    type_names: ["Epic"]
  },
  {
    name: "Sponsor",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255,
    type_names: ["Epic"]
  },
  {
    name: "Business Objective",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024,
    type_names: ["Epic"]
  },
  {
    name: "Success Criteria",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024,
    type_names: ["Epic"]
  },
  {
    name: "System Demo Evidence",
    field_format: "text",
    searchable: true,
    is_filter: false,
    multi_value: false,
    type_names: ["Epic"]
  },
  {
    name: "Inspect & Adapt Actions",
    field_format: "text",
    searchable: true,
    is_filter: false,
    multi_value: false,
    type_names: ["Epic"]
  },
  {
    name: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("initiative_family").fetch("name"),
    field_format: "list",
    searchable: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("initiative_family").fetch("searchable"),
    is_filter: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("initiative_family").fetch("filter"),
    multi_value: false,
    possible_values: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("initiative_family").fetch("possible_values"),
    type_names: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("initiative_family").fetch("type_names")
  },
  {
    name: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("lineage_role").fetch("name"),
    field_format: "list",
    searchable: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("lineage_role").fetch("searchable"),
    is_filter: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("lineage_role").fetch("filter"),
    multi_value: false,
    possible_values: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("lineage_role").fetch("possible_values"),
    type_names: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("lineage_role").fetch("type_names")
  },
  {
    name: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("architecture_anchor_ref").fetch("name"),
    field_format: "string",
    searchable: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("architecture_anchor_ref").fetch("searchable"),
    is_filter: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("architecture_anchor_ref").fetch("filter"),
    multi_value: false,
    max_length: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("architecture_anchor_ref").fetch("max_length"),
    type_names: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("architecture_anchor_ref").fetch("type_names")
  },
  {
    name: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("required_upstream_ref").fetch("name"),
    field_format: "string",
    searchable: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("required_upstream_ref").fetch("searchable"),
    is_filter: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("required_upstream_ref").fetch("filter"),
    multi_value: false,
    max_length: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("required_upstream_ref").fetch("max_length"),
    type_names: INITIATIVE_LINEAGE_CUSTOM_FIELDS.fetch("required_upstream_ref").fetch("type_names")
  },
  {
    name: "Target PI",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255,
    type_names: STRUCTURAL_TYPE_NAMES
  },
  {
    name: "Owner Repo",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255,
    type_names: STRUCTURAL_TYPE_NAMES
  },
  {
    name: "Delivery Team",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255,
    type_names: EXECUTION_FIELD_TYPE_NAMES
  },
  {
    name: "Iteration",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255,
    type_names: EXECUTION_FIELD_TYPE_NAMES
  },
  {
    name: EXECUTION_CLASSIFICATION_FIELD_NAME,
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: EXECUTION_CLASSIFICATION_VALUES,
    type_names: EXECUTION_CLASSIFICATION_TYPE_NAMES
  },
  {
    name: "Acceptance Criteria",
    field_format: "text",
    searchable: true,
    is_filter: false,
    multi_value: false,
    type_names: ["Feature", "PI Objective", "User story", "Defect", "Task"]
  },
  {
    name: "Definition of Ready",
    field_format: "text",
    searchable: true,
    is_filter: false,
    multi_value: false,
    type_names: ["Feature", "PI Objective", "User story", "Defect", "Task"]
  },
  {
    name: "Definition of Done",
    field_format: "text",
    searchable: true,
    is_filter: false,
    multi_value: false,
    type_names: ["Feature", "PI Objective", "User story", "Defect", "Task"]
  },
  {
    name: "NFR Category",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["Security", "Reliability", "Performance", "Scalability", "Operability", "Compliance", "Usability", "Maintainability"],
    type_names: ["Feature"]
  },
  {
    name: "WSJF User-Business Value",
    field_format: "int",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: WSJF_TYPE_NAMES
  },
  {
    name: "WSJF Time Criticality",
    field_format: "int",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: WSJF_TYPE_NAMES
  },
  {
    name: "WSJF Risk Reduction / Opportunity Enablement",
    field_format: "int",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: WSJF_TYPE_NAMES
  },
  {
    name: "WSJF Job Size",
    field_format: "int",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: WSJF_TYPE_NAMES
  },
  {
    name: "WSJF Score",
    field_format: "float",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: WSJF_TYPE_NAMES
  },
  {
    name: "PI Objective Type",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["Committed", "Stretch"],
    type_names: ["PI Objective"]
  },
  {
    name: "PI Objective Review Outcome",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["Met", "Partially met", "Not met"],
    type_names: ["PI Objective"]
  },
  {
    name: "Planned Business Value",
    field_format: "int",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: ["PI Objective"]
  },
  {
    name: "Actual Business Value",
    field_format: "int",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: ["PI Objective"]
  },
  {
    name: "ROAM State",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["Resolved", "Owned", "Accepted", "Mitigated"],
    type_names: ["Risk"]
  },
  {
    name: "Risk Owner",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255,
    type_names: ["Risk"]
  },
  {
    name: "Risk Review Date",
    field_format: "date",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: ["Risk"]
  },
  {
    name: "Risk Disposition",
    field_format: "text",
    searchable: true,
    is_filter: false,
    multi_value: false,
    type_names: ["Risk"]
  },
  {
    name: "Blocker Statement",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Blocker Impact",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Blocker Owner",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Blocker Discovered On",
    field_format: "date",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Blocker Decision Path",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["remove", "workaround", "accept-risk", "defer"],
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Blocker Justification",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Blocker Follow-Up Owner",
    field_format: "string",
    searchable: true,
    is_filter: true,
    multi_value: false,
    max_length: 255,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Blocker Review Date",
    field_format: "date",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Parking Decision",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["defer", "retire"],
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Parking Reason",
    field_format: "string",
    searchable: true,
    is_filter: false,
    multi_value: false,
    max_length: 1024,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Parking Review Date",
    field_format: "date",
    searchable: false,
    is_filter: true,
    multi_value: false,
    type_names: WORKFLOW_FIELD_TYPE_NAMES
  },
  {
    name: "Retirement Reason",
    field_format: "list",
    searchable: false,
    is_filter: true,
    multi_value: false,
    possible_values: ["superseded", "duplicate", "invalid", "absorbed", "cancelled"],
    type_names: WORKFLOW_FIELD_TYPE_NAMES
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

def ensure_custom_field!(project:, types_by_name:, spec:, position:)
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

  type_names = spec.fetch(:type_names)
  field_types = type_names.map do |name|
    type = types_by_name[name]
    raise "Unknown work package type #{name.inspect} for custom field #{spec[:name].inspect}" if type.nil?

    type
  end

  field.projects = [project]
  field.types = field_types
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
types_by_name = types.index_by(&:name)
project = ensure_project!(types: types)

CUSTOM_FIELD_SPECS.each_with_index do |spec, index|
  ensure_custom_field!(project: project, types_by_name: types_by_name, spec: spec, position: index + 1)
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
