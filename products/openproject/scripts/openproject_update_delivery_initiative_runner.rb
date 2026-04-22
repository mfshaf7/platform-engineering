# frozen_string_literal: true

require "json"
require "date"
require_relative "openproject_delivery_art_custom_field_support"

target_epic_id = Integer(ENV.fetch("TARGET_EPIC_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)

pm2_phase = ENV["PM2_PHASE"]&.strip
target_pi = ENV["TARGET_PI"]&.strip
sponsor = ENV["SPONSOR"]&.strip
business_objective = ENV["BUSINESS_OBJECTIVE"]&.strip
success_criteria = ENV["SUCCESS_CRITERIA"]&.strip
system_demo_evidence = ENV["SYSTEM_DEMO_EVIDENCE"]&.strip
inspect_and_adapt_actions = ENV["INSPECT_AND_ADAPT_ACTIONS"]&.strip
nfr_category = ENV["NFR_CATEGORY"]&.strip
status_name = ENV["STATUS"]&.strip
description = ENV["DESCRIPTION"]&.strip

project = Project.find_by!(identifier: delivery_project_identifier)
epic = WorkPackage.find(target_epic_id)

unless epic.project_id == project.id
  raise "Epic #{target_epic_id} is not in project #{delivery_project_identifier}"
end

field_names = [
  "PM² Phase",
  "Target PI",
  "Sponsor",
  "Business Objective",
  "Success Criteria",
  "System Demo Evidence",
  "Inspect & Adapt Actions",
  "NFR Category"
]

custom_fields = project.work_package_custom_fields.where(name: field_names).index_by(&:name)
missing_fields = field_names.reject { |name| custom_fields.key?(name) }
raise "Missing delivery-art custom fields: #{missing_fields.join(', ')}" if missing_fields.any?

pm2_field = custom_fields.fetch("PM² Phase")
pm2_values = OpenprojectDeliveryArtCustomFieldSupport.list_allowed_values(pm2_field)

if pm2_phase && pm2_values.any? && !pm2_values.include?(pm2_phase)
  raise "Unknown PM² phase #{pm2_phase.inspect}"
end

if status_name
  status = Status.find_by(name: status_name)
  raise "Unknown status #{status_name.inspect}" unless status
  epic.status = status
end

if description
  epic.description = description
end

version = nil
if target_pi && !target_pi.empty?
  version = project.versions.find_or_initialize_by(name: target_pi)
  version.status = "open" if version.respond_to?(:status=)
  version.sharing = "none" if version.respond_to?(:sharing=) && version.sharing.blank?
  version.save!
  if epic.respond_to?(:version=)
    epic.version = version
  elsif epic.respond_to?(:fixed_version=)
    epic.fixed_version = version
  end
end

updates = {
  "PM² Phase" => OpenprojectDeliveryArtCustomFieldSupport.normalize_input_value!(
    field: custom_fields.fetch("PM² Phase"),
    value: pm2_phase,
    kind: :list
  ),
  "Target PI" => target_pi,
  "Sponsor" => sponsor,
  "Business Objective" => business_objective,
  "Success Criteria" => success_criteria,
  "System Demo Evidence" => system_demo_evidence,
  "Inspect & Adapt Actions" => inspect_and_adapt_actions,
  "NFR Category" => OpenprojectDeliveryArtCustomFieldSupport.normalize_input_value!(
    field: custom_fields.fetch("NFR Category"),
    value: nfr_category,
    kind: :list
  )
}.compact

updates.each do |field_name, value|
  field = custom_fields.fetch(field_name)
  unless field.types.include?(epic.type)
    raise "Custom field #{field_name.inspect} is not available for work package type #{epic.type&.name.inspect}"
  end
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: epic, field:, value:)
end

epic.save!
epic.reload

result = {
  epic: {
    id: epic.id,
    record_ref: "openproject://work_packages/#{epic.id}",
    subject: epic.subject,
    status: epic.status&.name,
    version: if epic.respond_to?(:version)
               epic.version&.name
             elsif epic.respond_to?(:fixed_version)
               epic.fixed_version&.name
             end,
    description_present: epic.description.to_s.strip.length.positive?
  },
  governance_fields: updates.keys.sort.to_h do |field_name|
    field = custom_fields.fetch(field_name)
    [field_name, OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: epic, field: field)]
  end
}

puts JSON.pretty_generate(result)
