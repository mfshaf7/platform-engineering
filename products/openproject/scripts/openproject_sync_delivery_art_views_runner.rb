# frozen_string_literal: true

require "json"
require_relative "openproject_delivery_art_custom_field_support"
require_relative "openproject_delivery_art_home_support"

RESULT_BEGIN = "__OPENPROJECT_DELIVERY_ART_VIEWS_BEGIN__"
RESULT_END = "__OPENPROJECT_DELIVERY_ART_VIEWS_END__"

PROJECT_IDENTIFIER = "workspace-delivery-art"
BOARD_MODULE = "board_view"

PM2_TYPE_NAME = "Epic"
PI_OBJECTIVE_TYPE_NAME = "PI Objective"
RISK_TYPE_NAME = "Risk"
ACTIVE_INITIATIVE_STATUS_NAMES = ["new", "ready", "in-progress", "blocked"].freeze
EXECUTION_TYPE_NAMES = ["Feature", "Enabler", "User story", "Task", "Milestone"].freeze
EXECUTION_STATUS_NAMES = ["new", "ready", "in-progress", "blocked", "parked", "done"].freeze
PM2_PHASES = ["Initiating", "Planning", "Executing", "Closing"].freeze
PI_OBJECTIVE_COMMITMENT_TYPES = ["Committed", "Stretch"].freeze
ROAM_STATES = ["Resolved", "Owned", "Accepted", "Mitigated"].freeze

ART_DASHBOARD_BOARD_NAME = "ART Dashboard"
PM2_BOARD_NAME = "PM² Phase Board"
EXECUTION_BOARD_NAME = "ART Execution Kanban"
PI_OBJECTIVES_BOARD_NAME = "PI Objectives"
RISK_BOARD_NAME = "ART Risk Register"
LEGACY_PM2_BOARD_NAME = "PM² Initiative Register"
LEGACY_PI_BOARD_NAME = "Program Increment Planning"

MANAGED_QUERY_PREFIXES = [
  "PM² Initiatives",
  "ART Dashboard / ",
  "PM² Phase / ",
  "ART Execution / ",
  "PI Planning / ",
  "PI Objectives / ",
  "ART Risks / "
].freeze

def admin_user!
  User.admin.active.first || raise("No active OpenProject admin user is available for delivery-art view sync")
end

def project!
  Project.find_by!(identifier: PROJECT_IDENTIFIER)
end

def enable_board_module!(project)
  enabled_modules = (project.enabled_module_names + [BOARD_MODULE]).uniq
  return if enabled_modules == project.enabled_module_names

  project.enabled_module_names = enabled_modules
  project.save!
end

def refresh_project_home!(project)
  rendered = OpenprojectDeliveryArtHomeSupport.render_description
  return if project.description.to_s.strip == rendered.strip

  project.description = rendered
  project.save!
end

def execution_types!
  types = Type.where(name: EXECUTION_TYPE_NAMES).index_by(&:name)
  missing = EXECUTION_TYPE_NAMES.reject { |name| types.key?(name) }
  raise "Missing execution types for delivery-art views: #{missing.join(', ')}" if missing.any?

  EXECUTION_TYPE_NAMES.map { |name| types.fetch(name) }
end

def execution_statuses!
  statuses = Status.where(name: EXECUTION_STATUS_NAMES).index_by(&:name)
  missing = EXECUTION_STATUS_NAMES.reject { |name| statuses.key?(name) }
  raise "Missing execution statuses for delivery-art views: #{missing.join(', ')}" if missing.any?

  EXECUTION_STATUS_NAMES.map { |name| statuses.fetch(name) }
end

def pm2_type!
  Type.find_by!(name: PM2_TYPE_NAME)
end

def pi_objective_type!
  Type.find_by!(name: PI_OBJECTIVE_TYPE_NAME)
end

def risk_type!
  Type.find_by!(name: RISK_TYPE_NAME)
end

def configured_pi_names
  ENV.fetch("OPENPROJECT_DELIVERY_PI_NAMES", "")
     .split(",")
     .map(&:strip)
     .reject(&:empty?)
end

def existing_target_pi_names(project)
  target_pi_field = project.work_package_custom_fields.find_by(name: "Target PI")
  raise "Missing Target PI custom field for PI planning views" if target_pi_field.nil?

  WorkPackage.where(project: project)
             .filter_map do |work_package|
               work_package.custom_value_for(target_pi_field)&.value.to_s.strip.presence
             end
             .uniq
end

def ensure_versions!(project, names)
  names.uniq.sort.map do |name|
    version = project.versions.find_or_initialize_by(name: name)
    version.status = "open" if version.respond_to?(:status=)
    version.sharing = "none" if version.respond_to?(:sharing=) && version.sharing.blank?
    version.save!
    version
  end
end

def destroy_managed_views!(project)
  Boards::Grid.where(
    project: project,
    name: [
      ART_DASHBOARD_BOARD_NAME,
      PM2_BOARD_NAME,
      LEGACY_PM2_BOARD_NAME,
      EXECUTION_BOARD_NAME,
      LEGACY_PI_BOARD_NAME,
      PI_OBJECTIVES_BOARD_NAME,
      RISK_BOARD_NAME
    ]
  ).find_each(&:destroy!)

  Query.where(project: project)
       .find_each do |query|
         next unless MANAGED_QUERY_PREFIXES.any? { |prefix| query.name.start_with?(prefix) }

         query.destroy!
       end
end

def create_query!(project:, name:, filters:)
  result = Queries::CreateService.new(user: User.current).call(
    project: project,
    name: name,
    public: true,
    sort_criteria: [[:manual_sorting, "asc"], [:id, "asc"]],
    filters: filters
  )

  return result.result if result.success?

  raise "Failed to create query #{name.inspect}: #{result.errors.full_messages.join(', ')}"
end

def create_basic_board!(project:, name:, widgets:)
  result = Boards::BasicBoardCreateService.new(user: User.current).call(
    project: project,
    name: name,
    attribute: "basic"
  )

  raise "Failed to create board #{name.inspect}: #{result.errors.full_messages.join(', ')}" unless result.success?

  board = result.result
  board.options = { type: "free" }
  board.row_count = 1
  board.column_count = [widgets.length, 1].max
  board.widgets.destroy_all

  widgets.each_with_index do |widget, index|
    board.widgets.build(
      start_row: 1,
      end_row: 2,
      start_column: index + 1,
      end_column: index + 2,
      identifier: "work_package_query",
      options: {
        "queryId" => widget.fetch(:query).id,
        "filters" => widget.fetch(:filters)
      }
    )
  end

  board.save!
  board
end

def execution_filters(status:, execution_types:)
  [
    { status_id: { operator: "=", values: [status.id.to_s] } },
    { type_id: { operator: "=", values: execution_types.map { |type| type.id.to_s } } }
  ]
end

def ensure_custom_option_value!(field:, value:)
  option =
    if field.respond_to?(:custom_options)
      field.custom_options.find { |entry| entry.value.to_s == value }
    end
  raise "Missing option #{value.inspect} for custom field #{field.name.inspect}" if option.nil?

  option.id.to_s
end

def pm2_phase_filters(pm2_type:, pm2_phase_field:, phase_name:)
  [
    { type_id: { operator: "=", values: [pm2_type.id.to_s] } },
    {
      "cf_#{pm2_phase_field.id}": {
        operator: "=",
        values: [ensure_custom_option_value!(field: pm2_phase_field, value: phase_name)]
      }
    }
  ]
end

def pi_objective_filters(version:, pi_objective_type:, target_pi_field:, pi_objective_type_field:, commitment_type:)
  [
    { "cf_#{target_pi_field.id}": { operator: "=", values: [version.name] } },
    { type_id: { operator: "=", values: [pi_objective_type.id.to_s] } },
    {
      "cf_#{pi_objective_type_field.id}": {
        operator: "=",
        values: [ensure_custom_option_value!(field: pi_objective_type_field, value: commitment_type)]
      }
    }
  ]
end

def active_initiative_filters(pm2_type:, statuses:)
  [
    { type_id: { operator: "=", values: [pm2_type.id.to_s] } },
    { status_id: { operator: "=", values: statuses.map { |status| status.id.to_s } } }
  ]
end

def committed_objective_filters(pi_objective_type:, pi_objective_type_field:)
  [
    { type_id: { operator: "=", values: [pi_objective_type.id.to_s] } },
    {
      "cf_#{pi_objective_type_field.id}": {
        operator: "=",
        values: [ensure_custom_option_value!(field: pi_objective_type_field, value: "Committed")]
      }
    }
  ]
end

def risk_filters(risk_type:)
  [
    { type_id: { operator: "=", values: [risk_type.id.to_s] } }
  ]
end

def risk_filters_by_roam(risk_type:, roam_field:, roam_state:)
  [
    { type_id: { operator: "=", values: [risk_type.id.to_s] } },
    {
      "cf_#{roam_field.id}": {
        operator: "=",
        values: [ensure_custom_option_value!(field: roam_field, value: roam_state)]
      }
    }
  ]
end

admin_user = admin_user!
User.current = admin_user

project = project!
enable_board_module!(project)
refresh_project_home!(project)

pi_names = (configured_pi_names + existing_target_pi_names(project)).uniq
versions = ensure_versions!(project, pi_names)
roam_field = project.work_package_custom_fields.find_by(name: "ROAM State")
raise "Missing ROAM State custom field for risk views" if roam_field.nil?
target_pi_field = project.work_package_custom_fields.find_by(name: "Target PI")
raise "Missing Target PI custom field for PI planning views" if target_pi_field.nil?
pm2_phase_field = project.work_package_custom_fields.find_by(name: "PM² Phase")
raise "Missing PM² Phase custom field for PM² board views" if pm2_phase_field.nil?
pi_objective_type_field = project.work_package_custom_fields.find_by(name: "PI Objective Type")
raise "Missing PI Objective Type custom field for PI objective views" if pi_objective_type_field.nil?

normalized_list_custom_values = OpenprojectDeliveryArtCustomFieldSupport.normalize_list_storage!(project: project)

destroy_managed_views!(project)

active_initiative_statuses = Status.where(name: ACTIVE_INITIATIVE_STATUS_NAMES).index_by(&:name)
missing_active_initiative_statuses = ACTIVE_INITIATIVE_STATUS_NAMES.reject { |name| active_initiative_statuses.key?(name) }
raise "Missing active initiative statuses for ART dashboard: #{missing_active_initiative_statuses.join(', ')}" if missing_active_initiative_statuses.any?

active_initiatives_filters = active_initiative_filters(
  pm2_type: pm2_type!,
  statuses: ACTIVE_INITIATIVE_STATUS_NAMES.map { |name| active_initiative_statuses.fetch(name) }
)
active_initiatives_query = create_query!(
  project: project,
  name: "ART Dashboard / active initiatives",
  filters: active_initiatives_filters
)

committed_objectives_filters = committed_objective_filters(
  pi_objective_type: pi_objective_type!,
  pi_objective_type_field: pi_objective_type_field
)
committed_objectives_query = create_query!(
  project: project,
  name: "ART Dashboard / committed objectives",
  filters: committed_objectives_filters
)

active_execution_filters = execution_filters(status: Status.find_by!(name: "in-progress"), execution_types: execution_types!)
active_execution_query = create_query!(
  project: project,
  name: "ART Dashboard / active execution",
  filters: active_execution_filters
)

blocked_execution_filters = execution_filters(status: Status.find_by!(name: "blocked"), execution_types: execution_types!)
blocked_execution_query = create_query!(
  project: project,
  name: "ART Dashboard / blocked execution",
  filters: blocked_execution_filters
)

owned_risks_filters = risk_filters_by_roam(risk_type: risk_type!, roam_field: roam_field, roam_state: "Owned")
owned_risks_query = create_query!(
  project: project,
  name: "ART Dashboard / owned risks",
  filters: owned_risks_filters
)

parked_work_filters = execution_filters(status: Status.find_by!(name: "parked"), execution_types: execution_types!)
parked_work_query = create_query!(
  project: project,
  name: "ART Dashboard / parked work",
  filters: parked_work_filters
)

dashboard_board = create_basic_board!(
  project: project,
  name: ART_DASHBOARD_BOARD_NAME,
  widgets: [
    { query: active_initiatives_query, filters: active_initiatives_filters },
    { query: committed_objectives_query, filters: committed_objectives_filters },
    { query: active_execution_query, filters: active_execution_filters },
    { query: blocked_execution_query, filters: blocked_execution_filters },
    { query: owned_risks_query, filters: owned_risks_filters },
    { query: parked_work_query, filters: parked_work_filters }
  ]
)

pm2_queries = []
pm2_board = create_basic_board!(
  project: project,
  name: PM2_BOARD_NAME,
  widgets: PM2_PHASES.map do |phase_name|
    filters = pm2_phase_filters(pm2_type: pm2_type!, pm2_phase_field: pm2_phase_field, phase_name: phase_name)
    query = create_query!(
      project: project,
      name: "PM² Phase / #{phase_name}",
      filters: filters
    )
    pm2_queries << query
    { query: query, filters: filters }
  end
)

execution_types = execution_types!
execution_statuses = execution_statuses!
pi_objective_type = pi_objective_type!
risk_type = risk_type!
execution_widgets = execution_statuses.map do |status|
  filters = execution_filters(status: status, execution_types: execution_types)
  query = create_query!(
    project: project,
    name: "ART Execution / #{status.name}",
    filters: filters
  )

  { query: query, filters: filters }
end

execution_board = create_basic_board!(
  project: project,
  name: EXECUTION_BOARD_NAME,
  widgets: execution_widgets
)

pi_objective_board = nil
pi_objective_queries = []
if versions.any?
  pi_objective_widgets = versions.flat_map do |version|
    PI_OBJECTIVE_COMMITMENT_TYPES.map do |commitment_type|
      filters = pi_objective_filters(
        version: version,
        pi_objective_type: pi_objective_type,
        target_pi_field: target_pi_field,
        pi_objective_type_field: pi_objective_type_field,
        commitment_type: commitment_type
      )
      query = create_query!(
        project: project,
        name: "PI Objectives / #{version.name} / #{commitment_type.downcase}",
        filters: filters
      )
      pi_objective_queries << query
      { query: query, filters: filters }
    end
  end

  pi_objective_board = create_basic_board!(
    project: project,
    name: PI_OBJECTIVES_BOARD_NAME,
    widgets: pi_objective_widgets
  )
end

risk_queries = []
risk_widgets = ROAM_STATES.map do |roam_state|
  filters = risk_filters_by_roam(risk_type: risk_type, roam_field: roam_field, roam_state: roam_state)
  query = create_query!(
    project: project,
    name: "ART Risks / #{roam_state}",
    filters: filters
  )
  risk_queries << query
  { query: query, filters: filters }
end

risk_board = create_basic_board!(
  project: project,
  name: RISK_BOARD_NAME,
  widgets: risk_widgets
)

project.reload

result = {
  project: {
    id: project.id,
    identifier: project.identifier,
    name: project.name,
    enabled_modules: project.enabled_module_names
  },
  versions: versions.map do |version|
    {
      id: version.id,
      name: version.name,
      status: version.respond_to?(:status) ? version.status : nil
    }
  end,
  boards: [
    dashboard_board,
    pm2_board,
    execution_board,
    pi_objective_board,
    risk_board
  ].compact.map do |board|
    {
      id: board.id,
      name: board.name,
      type: board.options.with_indifferent_access[:type],
      widget_count: board.widgets.count
    }
  end,
  queries: [
    active_initiatives_query,
    committed_objectives_query,
    active_execution_query,
    blocked_execution_query,
    owned_risks_query,
    parked_work_query,
    *pm2_queries,
    *execution_widgets.map { |widget| widget[:query] },
    *pi_objective_queries,
    *risk_queries
  ].map do |query|
    {
     id: query.id,
     name: query.name
    }
  end,
  normalized_list_custom_values: {
    count: normalized_list_custom_values.length,
    fields: normalized_list_custom_values.group_by { |entry| entry.fetch(:field_name) }.transform_values(&:length).sort.to_h
  },
  notes: if versions.empty?
           [
             "No PI versions exist yet; PI objective lanes will appear after PI names are supplied or delivery records carry Target PI values. Team-and-iteration planning remains a read-model surface, not a managed board."
           ]
         else
           []
         end
}

puts RESULT_BEGIN
puts JSON.pretty_generate(result)
puts RESULT_END
