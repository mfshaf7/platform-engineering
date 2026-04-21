# frozen_string_literal: true

require "json"

RESULT_BEGIN = "__OPENPROJECT_DELIVERY_ART_VIEWS_BEGIN__"
RESULT_END = "__OPENPROJECT_DELIVERY_ART_VIEWS_END__"

PROJECT_IDENTIFIER = "workspace-delivery-art"
BOARD_MODULE = "board_view"

PM2_TYPE_NAME = "Epic"
PI_OBJECTIVE_TYPE_NAME = "PI Objective"
RISK_TYPE_NAME = "Risk"
EXECUTION_TYPE_NAMES = ["Feature", "Enabler", "User story", "Task", "Milestone"].freeze
EXECUTION_STATUS_NAMES = ["new", "ready", "in-progress", "blocked", "done"].freeze
ROAM_STATES = ["Resolved", "Owned", "Accepted", "Mitigated"].freeze

PM2_QUERY_NAME = "PM² Initiatives"
PM2_BOARD_NAME = "PM² Initiative Register"
EXECUTION_BOARD_NAME = "ART Execution Kanban"
PI_BOARD_NAME = "Program Increment Planning"
PI_OBJECTIVES_BOARD_NAME = "PI Objectives"
RISK_BOARD_NAME = "ART Risk Register"

MANAGED_QUERY_PREFIXES = [
  "#{PM2_QUERY_NAME}",
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
  WorkPackage.where(project: project)
             .includes(:version)
             .filter_map do |work_package|
               if work_package.respond_to?(:version)
                 work_package.version&.name
               elsif work_package.respond_to?(:fixed_version)
                 work_package.fixed_version&.name
               end
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
    name: [PM2_BOARD_NAME, EXECUTION_BOARD_NAME, PI_BOARD_NAME, PI_OBJECTIVES_BOARD_NAME, RISK_BOARD_NAME]
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

def pi_filters(version:, execution_types:)
  [
    { version_id: { operator: "=", values: [version.id.to_s] } },
    { type_id: { operator: "=", values: execution_types.map { |type| type.id.to_s } } }
  ]
end

def risk_filters(risk_type:)
  [
    { type_id: { operator: "=", values: [risk_type.id.to_s] } }
  ]
end

def risk_filters_by_roam(risk_type:, roam_field:, roam_state:)
  roam_option =
    if roam_field.respond_to?(:custom_options)
      roam_field.custom_options.find { |entry| entry.value.to_s == roam_state }
    end
  raise "Missing ROAM option #{roam_state.inspect}" if roam_option.nil?

  [
    { type_id: { operator: "=", values: [risk_type.id.to_s] } },
    { "cf_#{roam_field.id}": { operator: "=", values: [roam_option.id.to_s] } }
  ]
end

admin_user = admin_user!
User.current = admin_user

project = project!
enable_board_module!(project)

pi_names = (configured_pi_names + existing_target_pi_names(project)).uniq
versions = ensure_versions!(project, pi_names)
roam_field = project.work_package_custom_fields.find_by(name: "ROAM State")
raise "Missing ROAM State custom field for risk views" if roam_field.nil?

destroy_managed_views!(project)

pm2_query = create_query!(
  project: project,
  name: PM2_QUERY_NAME,
  filters: [
    { type_id: { operator: "=", values: [pm2_type!.id.to_s] } }
  ]
)

pm2_board = create_basic_board!(
  project: project,
  name: PM2_BOARD_NAME,
  widgets: [
    {
      query: pm2_query,
      filters: [{ type_id: { operator: "=", values: [pm2_type!.id.to_s] } }]
    }
  ]
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

pi_board = nil
pi_queries = []
if versions.any?
  pi_planning_types = execution_types + [pi_objective_type]
  pi_widgets = versions.map do |version|
    filters = pi_filters(version: version, execution_types: pi_planning_types)
    query = create_query!(
      project: project,
      name: "PI Planning / #{version.name}",
      filters: filters
    )
    pi_queries << query
    { query: query, filters: filters }
  end

  pi_board = create_basic_board!(
    project: project,
    name: PI_BOARD_NAME,
    widgets: pi_widgets
  )
end

pi_objective_board = nil
pi_objective_queries = []
if versions.any?
  pi_objective_widgets = versions.map do |version|
    filters = pi_filters(version: version, execution_types: [pi_objective_type])
    query = create_query!(
      project: project,
      name: "PI Objectives / #{version.name}",
      filters: filters
    )
    pi_objective_queries << query
    { query: query, filters: filters }
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
    pm2_board,
    execution_board,
    pi_board,
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
    pm2_query,
    *execution_widgets.map { |widget| widget[:query] },
    *pi_queries,
    *pi_objective_queries,
    *risk_queries
  ].map do |query|
    {
      id: query.id,
      name: query.name
    }
  end,
  notes: if versions.empty?
           [
             "No PI versions exist yet; PI planning and PI objective boards will appear after PI names are supplied or delivery records carry Target PI values."
           ]
         else
           []
         end
}

puts RESULT_BEGIN
puts JSON.pretty_generate(result)
puts RESULT_END
