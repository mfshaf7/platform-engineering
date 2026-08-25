# frozen_string_literal: true

require ENV.fetch("OPENPROJECT_CATALOG_CONTROL_EXTENSION_PATH")

config.middleware.use OpenprojectDeliveryCatalogControl::Middleware
config.after_initialize do
  OpenprojectDeliveryCatalogControl.register_setting!
end
