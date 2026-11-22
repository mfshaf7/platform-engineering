# frozen_string_literal: true

require_relative "openproject_delivery_catalog_control"

catalog = OpenprojectDeliveryCatalogControl
start_date = Date.iso8601("2027-01-11")
windows = catalog.iteration_windows(start_date, 14, 5)
raise "expected five two-week iterations" unless windows.length == 5
raise "calendar boundaries drifted" unless windows.first == {
  "sequence" => 1, "start_date" => "2027-01-11", "end_date" => "2027-01-24"
} && windows.last == {
  "sequence" => 5, "start_date" => "2027-03-08", "end_date" => "2027-03-21"
}
leap = catalog.iteration_windows(Date.iso8601("2028-02-22"), 14, 2)
raise "leap day cadence invalid" unless leap.last["start_date"] == "2028-03-07" && leap.last["end_date"] == "2028-03-20"
raise "unequal iterations" unless (windows + leap).all? do |window|
  (Date.iso8601(window.fetch("end_date")) - Date.iso8601(window.fetch("start_date"))).to_i + 1 == 14
end

begin
  catalog.calendar_date("2027-02-29")
  raise "invalid date accepted"
rescue catalog::Error
end

backend = catalog::Backend.allocate
state = catalog.default_state
pi = "PI-2027-01"
matching = "#{pi} / Iteration 1"
other = "#{pi} / iteration 1"
historical_usage = { matching => 2, other => 1 }
backend.send(:add_iteration_windows!, state, pi, windows, historical_usage)
registered = state.fetch("registry_values").fetch(catalog::ITERATION_ID)
raise "registry did not retain the date and PI link" unless registered.length == 5 &&
  registered.last["parent_catalog_value_key"] == pi && registered.last["iteration_window"] == windows.last
raise "matching reference changed identity" unless registered.first["catalog_value_id"] ==
  backend.send(:discovered_registry_id, catalog::ITERATION_ID, matching)
raise "ambiguous recorded label gained dates" if registered.any? { |entry| entry["value_key"] == other }
backend.send(:add_iteration_windows!, state, pi, windows, historical_usage)
raise "duplicate generated iteration" unless registered.length == 5
begin
  backend.send(:add_iteration_windows!, state, pi, catalog.iteration_windows(start_date, 7, 10), historical_usage)
  raise "existing dates silently changed"
rescue catalog::Error => error
  raise unless error.status == 409
end

begin
  backend.mutate!({ "catalog_item_id" => catalog::ITERATION_ID }, {}, state)
  raise "standalone iteration mutation was accepted"
rescue catalog::Error => error
  raise unless error.status == 409
end

version = Struct.new(:name, :start_date, :effective_date, :description).new(
  pi, start_date, Date.iso8601("2027-03-21"), "Original notes"
)
def version.update!(attributes)
  attributes.each { |attribute, value| self[attribute] = value }
end
versions = Object.new
versions.define_singleton_method(:find) do |id|
  raise "wrong PI" unless id == "1"
  version
end
versions.define_singleton_method(:exists?) { |name:| name == version.name }
backend.instance_variable_set(:@project, Struct.new(:versions).new(versions))
backend.define_singleton_method(:locate_value!) { |*, **| { "catalog_value_id" => "openproject-version-1" } }
target_pi_item = { "catalog_item_id" => catalog::TARGET_PI_ID, "source" => { "kind" => "versions" } }
metadata = { "value_key" => pi, "description" => "Updated notes" }
edit = { "mode" => "edit", "draft" => metadata }
backend.mutate!(target_pi_item, edit, state)
raise "PI metadata change cleared the calendar" unless version.start_date == start_date &&
  version.effective_date == Date.iso8601("2027-03-21") && version.description == "Updated notes"
[
  { "mode" => "add", "draft" => metadata.merge("value_key" => "PI-2027-02") },
  edit.merge("draft" => metadata.merge("planning_window_start_date" => "2027-01-12"))
].each do |request|
  begin
    backend.mutate!(target_pi_item, request, state)
    raise "date-only PI mutation was accepted"
  rescue catalog::Error => error
    raise unless error.status == 400
  end
end
puts "PI calendar date generation and registry checks passed"
