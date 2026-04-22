# frozen_string_literal: true

require "date"
require "json"
require_relative "openproject_delivery_art_custom_field_support"

action = ENV.fetch("ACTION").strip
target_work_package_id = Integer(ENV.fetch("TARGET_WORK_PACKAGE_ID"))
delivery_project_identifier = ENV.fetch(
  "OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER",
  "workspace-delivery-art",
)
resume_status_name = ENV["RESUME_STATUS"]&.strip

project = Project.find_by!(identifier: delivery_project_identifier)
work_package = WorkPackage.find(target_work_package_id)

unless work_package.project_id == project.id
  raise "Work package #{target_work_package_id} is not in project #{delivery_project_identifier}"
end

field_names = [
  "Blocker Statement",
  "Blocker Impact",
  "Blocker Owner",
  "Blocker Discovered On",
  "Blocker Decision Path",
  "Blocker Justification",
  "Blocker Follow-Up Owner",
  "Blocker Review Date"
]

custom_fields = project.work_package_custom_fields.where(name: field_names).index_by(&:name)
missing_fields = field_names.reject { |name| custom_fields.key?(name) }
raise "Missing delivery blocker custom fields: #{missing_fields.join(', ')}" if missing_fields.any?

decision_field = custom_fields.fetch("Blocker Decision Path")
decision_values = OpenprojectDeliveryArtCustomFieldSupport.list_allowed_values(decision_field)

def parse_iso_date!(value, field_name)
  Date.iso8601(value)
  value
rescue ArgumentError
  raise "#{field_name} must be an ISO date (YYYY-MM-DD)"
end

case action
when "set"
  statement = ENV["BLOCKER_STATEMENT"]&.strip
  impact = ENV["BLOCKER_IMPACT"]&.strip
  owner = ENV["BLOCKER_OWNER"]&.strip
  discovered_on = ENV["BLOCKER_DISCOVERED_ON"]&.strip
  decision_path = ENV["BLOCKER_DECISION_PATH"]&.strip
  justification = ENV["BLOCKER_JUSTIFICATION"]&.strip
  follow_up_owner = ENV["BLOCKER_FOLLOW_UP_OWNER"]&.strip
  review_date = ENV["BLOCKER_REVIEW_DATE"]&.strip

  required_fields = {
    "BLOCKER_STATEMENT" => statement,
    "BLOCKER_IMPACT" => impact,
    "BLOCKER_OWNER" => owner,
    "BLOCKER_DISCOVERED_ON" => discovered_on,
    "BLOCKER_DECISION_PATH" => decision_path,
    "BLOCKER_JUSTIFICATION" => justification
  }
  missing = required_fields.filter_map { |key, value| key if value.nil? || value.empty? }
  raise "Missing blocker fields for ACTION=set: #{missing.join(', ')}" if missing.any?

  parse_iso_date!(discovered_on, "BLOCKER_DISCOVERED_ON")

  if decision_values.any? && !decision_values.include?(decision_path)
    raise "Unknown BLOCKER_DECISION_PATH #{decision_path.inspect}"
  end

  if decision_path != "remove"
    missing_follow_up = []
    missing_follow_up << "BLOCKER_FOLLOW_UP_OWNER" if follow_up_owner.nil? || follow_up_owner.empty?
    missing_follow_up << "BLOCKER_REVIEW_DATE" if review_date.nil? || review_date.empty?
    raise "Missing blocker follow-up fields: #{missing_follow_up.join(', ')}" if missing_follow_up.any?
    parse_iso_date!(review_date, "BLOCKER_REVIEW_DATE")
  elsif review_date && !review_date.empty?
    parse_iso_date!(review_date, "BLOCKER_REVIEW_DATE")
  end

  blocked_status = Status.find_by!(name: "blocked")
  work_package.status = blocked_status

  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Blocker Statement"), value: statement, kind: :string)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Blocker Impact"), value: impact, kind: :string)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Blocker Owner"), value: owner, kind: :string)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Blocker Discovered On"), value: discovered_on, kind: :date)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Blocker Decision Path"), value: decision_path, kind: :list)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Blocker Justification"), value: justification, kind: :string)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Blocker Follow-Up Owner"), value: follow_up_owner.presence, kind: :string)
  OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field: custom_fields.fetch("Blocker Review Date"), value: review_date.presence, kind: :date)
when "clear"
  if resume_status_name.nil? || resume_status_name.empty?
    raise "RESUME_STATUS is required for ACTION=clear"
  end

  resume_status = Status.find_by(name: resume_status_name)
  raise "Unknown RESUME_STATUS #{resume_status_name.inspect}" unless resume_status
  raise "RESUME_STATUS must not be blocked for ACTION=clear" if resume_status.name == "blocked"

  work_package.status = resume_status
  custom_fields.each_value do |field|
    OpenprojectDeliveryArtCustomFieldSupport.assign_custom_value!(entry: work_package, field:, value: nil)
  end
else
  raise "ACTION must be set or clear"
end

work_package.save!
work_package.reload

result = {
  action: action,
  work_package: {
    id: work_package.id,
    record_ref: "openproject://work_packages/#{work_package.id}",
    subject: work_package.subject,
    type: work_package.type&.name,
    status: work_package.status&.name
  },
  blocker_fields: field_names.to_h do |field_name|
    field = custom_fields.fetch(field_name)
    [field_name, OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(entry: work_package, field: field)]
  end
}

puts JSON.pretty_generate(result)
