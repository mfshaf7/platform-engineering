# frozen_string_literal: true

require "json"

require_relative "openproject_delivery_art_custom_field_support"

PROJECT_IDENTIFIER = ENV.fetch("OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER", "workspace-delivery-art")

project = Project.find_by!(identifier: PROJECT_IDENTIFIER)
custom_fields = project.work_package_custom_fields.index_by(&:name)

work_packages = WorkPackage.where(project_id: project.id)
                           .includes(:type, :status, :parent, :version, :assigned_to, :responsible)
                           .order(:id)
                           .to_a

payload = {
  project: {
    id: project.id,
    identifier: project.identifier,
    name: project.name
  },
  work_packages: work_packages.map do |entry|
    {
      id: entry.id,
      record_ref: "openproject://work_packages/#{entry.id}",
      subject: entry.subject.to_s,
      type: entry.type&.name,
      status: entry.status&.name,
      parent_id: entry.parent_id,
      target_pi: OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(
        entry: entry,
        field: custom_fields["Target PI"]
      ),
      owner_repo: OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(
        entry: entry,
        field: custom_fields["Owner Repo"]
      ),
      delivery_team: OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(
        entry: entry,
        field: custom_fields["Delivery Team"]
      ),
      iteration: OpenprojectDeliveryArtCustomFieldSupport.rendered_custom_value(
        entry: entry,
        field: custom_fields["Iteration"]
      ),
      execution_classification: OpenprojectDeliveryArtCustomFieldSupport.execution_classification(
        entry: entry,
        custom_fields: custom_fields
      ),
      assignee_login: entry.respond_to?(:assigned_to) ? entry.assigned_to&.login : nil,
      responsible_login: entry.respond_to?(:responsible) ? entry.responsible&.login : nil,
      description_headings: OpenprojectDeliveryArtCustomFieldSupport.description_headings(entry: entry),
      description_present: entry.description.to_s.strip.present?
    }
  end
}

puts JSON.pretty_generate(payload)
