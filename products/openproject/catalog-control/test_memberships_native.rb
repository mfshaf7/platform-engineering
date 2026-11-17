# frozen_string_literal: true

# Native integration qualification; all fixtures and changes roll back. Do not
# install this support file as a runtime route or call it from the Console.
require "json"
require "securerandom"
require "stringio"
raise "Use explicit rollback-only qualification" unless ENV["OPENPROJECT_MEMBERSHIP_QUALIFICATION"] == "rollback-only"
load ENV.fetch("OPENPROJECT_MEMBERSHIP_REVIEW_SOURCE")

def check(value, message)
  raise message unless value
end

passed = []
initial_user_count = User.count
initial_member_count = Member.count
initial_group_count = Group.count
initial_group_user_count = GroupUser.count
store = OpenprojectDeliveryCatalogControl::Store.new
original_state = OpenprojectDeliveryCatalogControl.digest(store.read)
ActiveRecord::Base.transaction do
  service = OpenprojectDeliveryCatalogControl::MembershipService.new(contract: { "project_identifier" => "workspace-delivery-art" })
  middleware = OpenprojectDeliveryCatalogControl::Middleware.new(->(_env) { [404, {}, ["not found"]] })
  context = { "caller_id" => "governance-operations-console", "operator_id" => "qualification-operator" }
  broker = User.find_by!(login: "operator-orchestration-service")
  check(!broker.admin? && broker.allowed_in_project?(:manage_members, Project.find_by!(identifier: "workspace-delivery-art")) &&
    !broker.allowed_in_project?(:manage_members, Project.find_by!(identifier: "workspace-proposals")), "Membership permission escaped the Delivery project")
  passed << "non-admin Delivery-only membership permission"
  user = User.new(login: "membership-proof-#{SecureRandom.hex(6)}", firstname: "Membership", lastname: "Qualification",
    mail: "membership-#{SecureRandom.hex(6)}@example.invalid", admin: false, status: :active)
  password = SecureRandom.base58(48)
  user.password = password
  user.password_confirmation = password
  user.save!
  proposal = Project.find_by!(identifier: "workspace-proposals")
  reader = ProjectRole.find_by!(name: "Reader")
  member_role = ProjectRole.find_by!(name: "Member")
  Member.create!(project: proposal, principal: user, roles: [reader])
  initial = service.projection(context)
  check(initial["candidates"].any? { |entry| entry["id"] == user.id }, "Native visible existing principal is absent")
  passed << "native role/principal projection"
  command = context.merge("request_id" => "native-membership-#{SecureRandom.hex(8)}", "operation" => "add",
    "principal_id" => user.id, "membership_id" => nil, "role_ids" => [member_role.id], "expected_version" => nil)
  unauthorized = middleware.call({ "PATH_INFO" => "/v1/delivery-memberships/mutations", "REQUEST_METHOD" => "POST", "HTTP_AUTHORIZATION" => "Bearer denied", "rack.input" => StringIO.new(JSON.generate(command)) })
  check(unauthorized.first == 401, "Native membership HTTP authentication was bypassed")
  status, _headers, response_body = middleware.call({ "PATH_INFO" => "/v1/delivery-memberships/mutations", "REQUEST_METHOD" => "POST",
    "HTTP_AUTHORIZATION" => "Bearer #{ENV.fetch('OPENPROJECT_CATALOG_CONTROL_SHARED_SECRET')}", "rack.input" => StringIO.new(JSON.generate(command)) })
  check(status == 200, "Native membership HTTP add failed: #{response_body.join}")
  added = JSON.parse(response_body.join)
  passed << "native HTTP authentication and dispatch"
  check(added["after"]["role_ids"] == [member_role.id], "Native add readback mismatch")
  passed << "native add"
  catalog = OpenprojectDeliveryCatalogControl::Service.new(contract: JSON.parse(File.read(ENV.fetch("OPENPROJECT_CATALOG_CONTROL_CONTRACT_PATH"))))
  check(Principal.possible_assignee(Project.find(initial["project_id"])).where(id: user.id).exists?, "Assignable member missing from native picker")
  check(catalog.projection["values"].any? { |entry| entry["catalog_item_id"] == "catalog-principal-lookup" && entry["value_key"] == user.login }, "Assignable member missing from Catalog")
  passed << "native assignment and Catalog propagation"
  changed = service.mutate(command.merge("request_id" => "change-#{command['request_id']}", "operation" => "change",
    "membership_id" => added["after"]["membership_id"], "expected_version" => added["after"]["version"], "role_ids" => [reader.id]))
  check(changed["after"]["role_ids"] == [reader.id], "Native change readback mismatch")
  passed << "native role change"
  check(!Principal.possible_assignee(Project.find(initial["project_id"])).where(id: user.id).exists?, "Reader remained assignable")
  check(catalog.projection["values"].none? { |entry| entry["catalog_item_id"] == "catalog-principal-lookup" && entry["value_key"] == user.login }, "Catalog retained nonassignable Reader")
  passed << "Reader removed from assignment and Catalog choices"
  check(service.mutate(command)["replayed"], "Exact retry did not recover the original receipt")
  passed << "replay after later legitimate change"
  begin
    service.mutate(command.merge("role_ids" => [reader.id]))
    raise "Changed accepted request was allowed"
  rescue OpenprojectDeliveryCatalogControl::Error => error
    check(error.code == "membership_request_conflict", "Wrong conflict error")
  end
  passed << "conflicting retry denied"
  begin
    service.mutate(command.merge("request_id" => "stale-#{command['request_id']}", "operation" => "remove",
      "membership_id" => added["after"]["membership_id"], "expected_version" => added["after"]["version"], "role_ids" => []))
    raise "Stale membership decision was allowed"
  rescue OpenprojectDeliveryCatalogControl::Error => error
    check(error.code == "membership_source_changed", "Wrong stale error")
  end
  passed << "stale review denied"
  service_user = User.find_by!(login: "operator-orchestration-service")
  service_member = Member.find_by!(principal: service_user, project_id: initial["project_id"], entity_id: nil)
  begin
    service.mutate(command.merge("request_id" => "protected-#{command['request_id']}", "operation" => "remove",
      "principal_id" => service_user.id, "membership_id" => service_member.id,
      "expected_version" => service.member_value(service_member)["version"], "role_ids" => []))
    raise "Service membership could be removed"
  rescue OpenprojectDeliveryCatalogControl::Error => error
    check(error.code == "membership_protected", "Wrong protection error")
  end
  passed << "service access protected"
  removed = service.mutate(command.merge("request_id" => "remove-#{command['request_id']}", "operation" => "remove",
    "membership_id" => changed["after"]["membership_id"], "expected_version" => changed["after"]["version"], "role_ids" => []))
  check(removed["after"].nil?, "Native removal was not read back")
  passed << "native remove"
  check(service.projection(context)["recent_outcomes"].size == 3, "Durable outcome history incomplete")
  passed << "durable outcome recovery"
  begin
    service.mutate(command.merge("request_id" => "global-#{command['request_id']}", "role_ids" => [GlobalRole.first.id]))
    raise "Global role could be assigned"
  rescue OpenprojectDeliveryCatalogControl::Error => error
    check(error.code == "membership_role_invalid", "Wrong global-role rejection")
  end
  passed << "global roles denied"
  group = Group.create!(lastname: "Membership qualification #{SecureRandom.hex(6)}")
  group.group_users.create!(user: user)
  Member.create!(project: proposal, principal: group, roles: [reader])
  group_command = command.merge("request_id" => "group-#{command['request_id']}", "principal_id" => group.id)
  group_added = service.mutate(group_command)
  inherited_member = Member.find_by!(principal: user, project_id: initial["project_id"], entity_id: nil)
  check(service.member_value(inherited_member)["protected"], "Inherited membership was editable")
  passed << "native group roles propagate and inherited access stays protected"
  group_removed = service.mutate(group_command.merge("request_id" => "remove-group-#{command['request_id']}", "operation" => "remove",
    "membership_id" => group_added["after"]["membership_id"], "expected_version" => group_added["after"]["version"], "role_ids" => []))
  check(group_removed["after"].nil? && !Member.where(principal: user, project_id: initial["project_id"], entity_id: nil).exists?, "Native inherited cleanup failed")
  passed << "native group removal cleans inherited membership"
  check(service.projection(context, { "page" => "2", "page_size" => "25", "search" => "no-match-qualification" })["members"].empty?, "Bounded native search/page is inconsistent")
  passed << "native bounded search and pagination"
  raise ActiveRecord::Rollback
end
check(User.count == initial_user_count && Member.count == initial_member_count && Group.count == initial_group_count && GroupUser.count == initial_group_user_count, "Qualification fixtures leaked")
check(OpenprojectDeliveryCatalogControl.digest(store.read) == original_state, "Qualification receipt state leaked")
passed << "all fixtures and receipt changes rolled back"
puts JSON.generate({ passed: passed, canonical_fixture_changes_retained: 0 })
