# frozen_string_literal: true

require "date"
require "digest"
require "json"
require "set"

module OpenprojectDeliveryCatalogControl
  SETTING_NAME = "delivery_catalog_control_v1"
  MAX_REQUEST_BYTES = 1_048_576
  MUTATION_PATH = %r{\A/v1/delivery-catalog/([^/]+)/mutations\z}

  class Error < StandardError
    attr_reader :code, :retryable, :status

    def initialize(status, code, message, retryable: false)
      super(message)
      @status = status
      @code = code
      @retryable = retryable
    end
  end

  module_function

  def register_setting!
    definitions = Settings::Definition.all
    return if definitions.key?(SETTING_NAME) || definitions.key?(SETTING_NAME.to_sym)

    Settings::Definition.add(
      SETTING_NAME,
      default: default_state,
      format: :hash,
      writable: true
    )
  end

  def default_state
    {
      "schema_version" => 1,
      "registry_values" => {},
      "retired_values" => {},
      "receipts" => {},
      "membership_receipts" => {}
    }
  end

  def canonical(value)
    case value
    when Hash
      value.keys.map(&:to_s).sort.to_h do |key|
        source_key = value.key?(key) ? key : key.to_sym
        [key, canonical(value[source_key])]
      end
    when Array
      value.map { |entry| canonical(entry) }
    else
      value
    end
  end

  def canonical_json(value)
    JSON.generate(canonical(value))
  end

  def digest(value)
    "sha256:#{Digest::SHA256.hexdigest(canonical_json(value))}"
  end

  def detached(value)
    JSON.parse(JSON.generate(value))
  end

  class Store
    def with_locked_state
      Setting.transaction do
        record = Setting.lock.find_or_initialize_by(name: SETTING_NAME)
        record.set_value!(OpenprojectDeliveryCatalogControl.default_state, force: true) if record.new_record?
        record.save! if record.new_record?
        record.lock!
        state = OpenprojectDeliveryCatalogControl.detached(
          OpenprojectDeliveryCatalogControl.default_state.merge(record.value || {})
        )
        result = yield(state)
        record.set_value!(OpenprojectDeliveryCatalogControl.detached(state), force: true)
        record.save!
        Setting.clear_cache
        result
      end
    end

    def read
      record = Setting.find_by(name: SETTING_NAME)
      OpenprojectDeliveryCatalogControl.detached(
        OpenprojectDeliveryCatalogControl.default_state.merge(record&.value || {})
      )
    end
  end

  class Backend
    def initialize(contract:, clock: -> { Time.now.utc })
      @contract = contract
      @clock = clock
      @project = Project.find_by!(identifier: contract.fetch("project_identifier"))
    end

    def projection(state)
      projected_at = @clock.call.iso8601
      values = @contract.fetch("items").flat_map do |item|
        project_item_values(item, state, projected_at)
      end
      items = @contract.fetch("items").map do |item|
        projected = values.select { |value| value.fetch("catalog_item_id") == item.fetch("catalog_item_id") }
        item.except("source").merge(
          "usage_count" => projected.sum { |value| value.fetch("usage_count") },
          "usage_summary" => usage_summary(projected),
          "last_projected_at" => projected_at
        )
      end
      groups = @contract.fetch("groups").map do |group|
        group.merge(
          "item_ids" => items.filter_map do |item|
            item.fetch("catalog_item_id") if item.fetch("group_id") == group.fetch("group_id")
          end
        )
      end
      source_revision = OpenprojectDeliveryCatalogControl.digest(
        "contract_id" => @contract.fetch("contract_id"),
        "groups" => groups,
        "items" => items.map { |item| item.except("last_projected_at", "usage_summary") },
        "values" => values.map { |value| value.except("last_projected_at", "usage_summary") }
      )
      {
        "schema_version" => 1,
        "source_revision" => source_revision,
        "projection_status" => "ready",
        "summary" => {
          "total_items" => items.length,
          "requestable_count" => items.count { |item| item.fetch("console_capability") == "request" },
          "owner_routed_count" => items.count { |item| item.fetch("console_capability") == "owner_routed" },
          "missing_route_count" => items.count { |item| item.fetch("gap_status") == "missing_backend_route" },
          "drift_count" => items.count { |item| %w[projection_drift stale_projection].include?(item.fetch("gap_status")) }
        },
        "groups" => groups,
        "items" => items,
        "values" => values.sort_by { |value| [value.fetch("catalog_item_id"), value.fetch("label")] },
        "projected_at" => projected_at
      }
    end

    def mutate!(item, request, state)
      source = item.fetch("source")
      case source.fetch("kind")
      when "versions"
        mutate_version!(item, request)
      when "custom-options"
        mutate_custom_option!(item, request, state)
      when "registry"
        mutate_registry!(item, request, state)
      else
        raise Error.new(409, "catalog_read_only", "This Catalog item is read-only.")
      end
    end

    private

    def project_item_values(item, state, projected_at)
      source = item.fetch("source")
      values = case source.fetch("kind")
               when "versions" then version_values(item, projected_at)
               when "version-dates" then version_date_values(item, projected_at)
               when "custom-options" then custom_option_values(item, projected_at)
               when "registry" then registry_values(item, state, projected_at)
               when "principals" then principal_values(item, projected_at)
               when "static" then static_values(item, projected_at)
               else []
               end
      values + Array(state.dig("retired_values", item.fetch("catalog_item_id"))).map do |value|
        value.merge("last_projected_at" => projected_at)
      end
    end

    def catalog_value(item, id:, key:, label:, description:, lifecycle:, usage_count:, projected_at:, parent_key: nil, repository_binding: nil, evidence_refs: nil)
      {
        "catalog_item_id" => item.fetch("catalog_item_id"),
        "catalog_value_id" => id,
        "value_key" => key,
        "label" => label,
        "description" => description.to_s,
        "lifecycle_state" => lifecycle,
        "usage_count" => usage_count,
        "usage_summary" => usage_count.zero? ? "No Delivery records use this value." : "#{usage_count} Delivery record#{usage_count == 1 ? '' : 's'} use this value.",
        "evidence_refs" => evidence_refs || item.fetch("evidence_refs"),
        "last_projected_at" => projected_at,
        "parent_catalog_item_id" => parent_key ? item.dig("source", "parent_item_id") : nil,
        "parent_catalog_value_key" => parent_key,
        "repository_binding" => repository_binding
      }
    end

    def field(name)
      @project.work_package_custom_fields.find_by!(name: name)
    end

    def raw_usage(field_name)
      custom_field = field(field_name)
      WorkPackage
        .joins(:custom_values)
        .where(project_id: @project.id)
        .where(custom_values: { custom_field_id: custom_field.id })
        .group("custom_values.value")
        .count
    end

    def usage_for(field_name, value, option_id: nil)
      usage = raw_usage(field_name)
      usage.fetch((option_id || value).to_s, 0)
    end

    def version_values(item, projected_at)
      usage = raw_usage(item.dig("source", "usage_field"))
      @project.versions.order(:name).map do |version|
        catalog_value(
          item,
          id: "openproject-version-#{version.id}",
          key: version.name,
          label: version.name,
          description: version.description.to_s,
          lifecycle: version.status == "closed" ? "retired" : "active",
          usage_count: usage.fetch(version.name, 0),
          projected_at: projected_at,
          evidence_refs: ["openproject://versions/#{version.id}"]
        )
      end
    end

    def version_date_values(item, projected_at)
      parent_item = @contract.fetch("items").find do |entry|
        entry.fetch("catalog_item_id") == item.dig("source", "parent_item_id")
      end
      @project.versions.order(:name).filter_map do |version|
        next if version.start_date.nil? && version.effective_date.nil?

        key = "#{version.start_date || 'unscheduled'}/#{version.effective_date || 'unscheduled'}"
        catalog_value(
          item,
          id: "openproject-version-dates-#{version.id}",
          key: key,
          label: "#{version.name} Planning Window",
          description: "#{version.start_date || 'Unscheduled'} to #{version.effective_date || 'Unscheduled'}.",
          lifecycle: version.status == "closed" ? "retired" : "read_only",
          usage_count: usage_for(parent_item.dig("source", "usage_field"), version.name),
          projected_at: projected_at,
          parent_key: version.name,
          evidence_refs: ["openproject://versions/#{version.id}"]
        )
      end
    end

    def custom_option_values(item, projected_at)
      custom_field = field(item.dig("source", "field"))
      custom_field.custom_options.order(:position).map do |option|
        catalog_value(
          item,
          id: "openproject-custom-option-#{option.id}",
          key: option.value,
          label: option.value,
          description: "OpenProject #{item.fetch('label')} value.",
          lifecycle: item.fetch("lifecycle_state") == "read_only" ? "read_only" : "active",
          usage_count: usage_for(custom_field.name, option.value, option_id: option.id),
          projected_at: projected_at,
          evidence_refs: ["openproject://custom_options/#{option.id}"]
        )
      end
    end

    def registry_values(item, state, projected_at)
      registered = Array(state.dig("registry_values", item.fetch("catalog_item_id")))
      known_keys = registered.map { |entry| entry.fetch("value_key") }.to_set
      discovered = raw_usage(item.dig("source", "usage_field")).filter_map do |key, count|
        next if key.to_s.empty? || known_keys.include?(key)

        {
          "catalog_value_id" => "openproject-discovered-#{Digest::SHA256.hexdigest("#{item.fetch('catalog_item_id')}:#{key}")[0, 20]}",
          "value_key" => key,
          "label" => key,
          "description" => "Value discovered from canonical Delivery records.",
          "lifecycle_state" => "active",
          "repository_binding" => nil,
          "parent_catalog_value_key" => nil
        }.tap { |entry| entry["_usage_count"] = count }
      end
      (registered + discovered).map do |entry|
        usage_count = entry.fetch(
          "_usage_count",
          usage_for(item.dig("source", "usage_field"), entry.fetch("value_key"))
        )
        catalog_value(
          item,
          id: entry.fetch("catalog_value_id"),
          key: entry.fetch("value_key"),
          label: entry.fetch("label"),
          description: entry.fetch("description", ""),
          lifecycle: entry.fetch("lifecycle_state", "active"),
          usage_count: usage_count,
          projected_at: projected_at,
          parent_key: entry["parent_catalog_value_key"],
          repository_binding: entry["repository_binding"]
        )
      end
    end

    def principal_values(item, projected_at)
      assignment_columns = %w[assigned_to_id responsible_id] & WorkPackage.column_names
      Principal.possible_assignee(@project).order(:id).map do |user|
        usage_scope = WorkPackage.where(project_id: @project.id)
        usage_count = if assignment_columns.empty?
                        0
                      else
                        predicate = assignment_columns.map { |column| "#{column} = :id" }.join(" OR ")
                        usage_scope.where(predicate, id: user.id).count
                      end
        catalog_value(
          item,
          id: "openproject-principal-#{user.id}",
          key: user.login.presence || "principal:#{user.id}",
          label: user.name,
          description: "Assignable Workspace Delivery ART principal.",
          lifecycle: "read_only",
          usage_count: usage_count,
          projected_at: projected_at,
          evidence_refs: ["openproject://#{user.is_a?(Group) ? 'groups' : user.is_a?(PlaceholderUser) ? 'placeholder_users' : 'users'}/#{user.id}"]
        )
      end
    end

    def static_values(item, projected_at)
      item.dig("source", "values").map do |key|
        catalog_value(
          item,
          id: "contract-value-#{Digest::SHA256.hexdigest("#{item.fetch('catalog_item_id')}:#{key}")[0, 20]}",
          key: key,
          label: key.split("-").map(&:capitalize).join(" "),
          description: "Governed read-only contract value.",
          lifecycle: "read_only",
          usage_count: 0,
          projected_at: projected_at
        )
      end
    end

    def usage_summary(values)
      count = values.sum { |value| value.fetch("usage_count") }
      count.zero? ? "No Delivery records currently use these values." : "#{count} Delivery value references are currently projected."
    end

    def locate_value!(item, request, state)
      target_id = request["target_value_id"]
      value = project_item_values(item, state, @clock.call.iso8601).find do |entry|
        entry.fetch("catalog_value_id") == target_id
      end
      raise Error.new(409, "catalog_conflict", "The selected Catalog value no longer exists.") unless value
      value
    end

    def assert_unused!(value)
      return if value.fetch("usage_count").zero?

      raise Error.new(409, "catalog_value_in_use", "Catalog values in use cannot be changed or retired.")
    end

    def mutate_version!(item, request)
      draft = request.fetch("draft")
      if request.fetch("mode") == "add"
        raise Error.new(409, "catalog_conflict", "Target PI already exists.") if @project.versions.exists?(name: draft.fetch("value_key"))

        @project.versions.create!(
          name: draft.fetch("value_key"),
          description: draft.fetch("description"),
          start_date: draft["planning_window_start_date"],
          effective_date: draft["planning_window_end_date"],
          status: "open"
        )
        return
      end
      value = locate_value!(item, request, OpenprojectDeliveryCatalogControl.default_state)
      version = @project.versions.find(value.fetch("catalog_value_id").delete_prefix("openproject-version-"))
      assert_unused!(value) if request.fetch("mode") == "retire"
      if request.fetch("mode") == "retire"
        version.update!(status: "closed")
      else
        version.update!(
          name: draft.fetch("value_key"),
          description: draft.fetch("description"),
          start_date: draft["planning_window_start_date"],
          effective_date: draft["planning_window_end_date"]
        )
      end
    end

    def mutate_custom_option!(item, request, state)
      custom_field = field(item.dig("source", "field"))
      draft = request.fetch("draft")
      if request.fetch("mode") == "add"
        raise Error.new(409, "catalog_conflict", "Catalog value already exists.") if custom_field.custom_options.exists?(value: draft.fetch("value_key"))

        custom_field.custom_options.create!(value: draft.fetch("value_key"), position: custom_field.custom_options.maximum(:position).to_i + 1)
        return
      end
      value = locate_value!(item, request, state)
      option = custom_field.custom_options.find(value.fetch("catalog_value_id").delete_prefix("openproject-custom-option-"))
      if request.fetch("mode") == "retire"
        assert_unused!(value)
        state["retired_values"][item.fetch("catalog_item_id")] ||= []
        state["retired_values"][item.fetch("catalog_item_id")] << value.merge("lifecycle_state" => "retired")
        option.destroy!
      else
        assert_unused!(value)
        option.update!(value: draft.fetch("value_key"))
      end
    end

    def mutate_registry!(item, request, state)
      item_id = item.fetch("catalog_item_id")
      state["registry_values"][item_id] ||= []
      values = state["registry_values"][item_id]
      draft = request.fetch("draft")
      if request.fetch("mode") == "add"
        raise Error.new(409, "catalog_conflict", "Catalog value already exists.") if values.any? { |entry| entry.fetch("value_key") == draft.fetch("value_key") }

        values << {
          "catalog_value_id" => "openproject-catalog-#{Digest::SHA256.hexdigest("#{item_id}:#{draft.fetch('value_key')}")[0, 20]}",
          "value_key" => draft.fetch("value_key"),
          "label" => draft.fetch("label"),
          "description" => draft.fetch("description"),
          "lifecycle_state" => "active",
          "parent_catalog_value_key" => draft["parent_catalog_value_key"],
          "repository_binding" => draft["repository_binding"]
        }
        return
      end
      projected = locate_value!(item, request, state)
      assert_unused!(projected)
      entry = values.find { |candidate| candidate.fetch("catalog_value_id") == request.fetch("target_value_id") }
      raise Error.new(409, "catalog_read_only", "Discovered values must be adopted with an add request before mutation.") unless entry

      if request.fetch("mode") == "retire"
        entry["lifecycle_state"] = "retired"
        entry["repository_binding"] = nil
      else
        entry.merge!(
          "value_key" => draft.fetch("value_key"),
          "label" => draft.fetch("label"),
          "description" => draft.fetch("description"),
          "parent_catalog_value_key" => draft["parent_catalog_value_key"],
          "repository_binding" => draft["repository_binding"]
        )
      end
    end
  end

  class Service
    def initialize(contract:, store: Store.new, clock: -> { Time.now.utc })
      @contract = contract
      @store = store
      @clock = clock
    end

    def projection
      Backend.new(contract: @contract, clock: @clock).projection(@store.read)
    end

    def mutate(catalog_item_id, request)
      @store.with_locked_state do |state|
        backend = Backend.new(contract: @contract, clock: @clock)
        request_digest = OpenprojectDeliveryCatalogControl.digest(request)
        replay = state.fetch("receipts")[request.fetch("idempotency_key")]
        if replay
          raise Error.new(409, "catalog_conflict", "The idempotency key belongs to another request.") unless replay.fetch("request_digest") == request_digest
          next replay.fetch("result").merge("replayed" => true)
        end

        before = backend.projection(state)
        raise Error.new(409, "source_revision_stale", "Catalog source changed after this request was prepared.") unless request["source_revision"] == before.fetch("source_revision")
        raise Error.new(400, "request_invalid", "Catalog route and request item do not match.") unless request["catalog_item_id"] == catalog_item_id
        item = @contract.fetch("items").find { |entry| entry.fetch("catalog_item_id") == catalog_item_id }
        raise Error.new(404, "request_invalid", "Unknown Catalog item.") unless item
        raise Error.new(409, "catalog_read_only", "This Catalog item is read-only.") unless item.fetch("console_capability") == "request"

        backend.mutate!(item, request, state)
        after = backend.projection(state)
        value = after.fetch("values").find do |entry|
          entry.fetch("catalog_item_id") == catalog_item_id &&
            entry.fetch("value_key") == request.dig("draft", "value_key")
        end
        if request.fetch("mode") == "retire"
          value = after.fetch("values").find { |entry| entry.fetch("catalog_value_id") == request.fetch("target_value_id") }
        end
        raise Error.new(502, "backend_readback_incomplete", "Canonical Catalog readback is incomplete.") unless value

        related = after.fetch("values").select do |entry|
          entry["parent_catalog_value_key"] == value.fetch("value_key")
        end
        mutation_id = "catalog-mutation-#{Digest::SHA256.hexdigest(request.fetch('idempotency_key'))[0, 24]}"
        applied_at = @clock.call.iso8601
        receipt_payload = {
          "mutation_id" => mutation_id,
          "request_digest" => request_digest,
          "source_revision" => after.fetch("source_revision"),
          "value" => value
        }
        result = {
          "schema_version" => 1,
          "request_id" => request.fetch("request_id"),
          "correlation_id" => request.fetch("correlation_id"),
          "mutation_id" => mutation_id,
          "status" => "applied",
          "replayed" => false,
          "applied_at" => applied_at,
          "applied_by" => request.dig("operator", "id"),
          "value" => value,
          "related_values" => related,
          "source_revision" => after.fetch("source_revision"),
          "readback_complete" => true,
          "receipt" => {
            "ref" => "openproject://delivery-catalog/receipts/#{mutation_id}",
            "digest" => OpenprojectDeliveryCatalogControl.digest(receipt_payload)
          }
        }
        state.fetch("receipts")[request.fetch("idempotency_key")] = {
          "request_digest" => request_digest,
          "result" => result
        }
        result
      end
    rescue KeyError, JSON::ParserError => error
      raise Error.new(400, "request_invalid", "Catalog request is incomplete: #{error.message}")
    end
  end

  # Reuse the Catalog transaction/receipt store so a committed membership and
  # its outcome cannot separate on process interruption. Native services still
  # enforce OpenProject's project-role and inherited-membership contracts.
  class MembershipService
    LIMIT = 100
    REQUEST_KEYS = %w[request_id caller_id operator_id operation principal_id membership_id role_ids expected_version].sort.freeze
    PROTECTED_LOGINS = %w[operator-orchestration-service platform-engineering workspace-governance workspace-governance-control-fabric security-architecture openclaw-runtime-distribution openclaw-telegram-enhanced openclaw-host-bridge].freeze

    def initialize(contract:, store: Store.new, clock: -> { Time.now.utc })
      @contract, @store, @clock = contract, store, clock
    end

    def authority!
      @project = Project.find_by!(identifier: @contract.fetch("project_identifier"))
      @user = User.find_by!(login: "operator-orchestration-service")
      unless !@user.admin? && @user.active? && @user.allowed_in_project?(:manage_members, @project)
        raise Error.new(403, "membership_permission_required", "Project membership management is not enabled for this connection.")
      end
    end

    def protected?(principal)
      return true unless principal.is_a?(User) || principal.is_a?(Group)
      return true if principal.is_a?(User) && (principal.admin? || PROTECTED_LOGINS.include?(principal.login))
      principal.is_a?(Group) && principal.users.any? { |user| protected?(user) }
    end

    def roles
      ProjectRole.where(builtin: 0).where.not(name: "Project membership manager").order(:name).map do |role|
        { "id" => role.id, "name" => role.name,
          "can_assign_work" => role.permissions.include?(:work_package_assigned),
          "manages_members" => role.permissions.include?(:manage_members) }
      end
    end

    def principal_value(principal)
      { "id" => principal.id, "name" => principal.name, "kind" => principal.is_a?(Group) ? "group" : principal.is_a?(User) ? "user" : "placeholder" }
    end

    def member_value(member)
      inherited = member.member_roles.where.not(inherited_from: nil).exists?
      role_ids = member.roles.order(:id).pluck(:id)
      version = OpenprojectDeliveryCatalogControl.digest([member.id, member.updated_at.iso8601(6), role_ids,
        member.member_roles.order(:id).pluck(:id, :role_id, :inherited_from)])
      principal_value(member.principal).merge("membership_id" => member.id, "role_ids" => role_ids,
        "role_names" => member.roles.order(:name).pluck(:name), "version" => version,
        "protected" => protected?(member.principal) || inherited,
        "restriction" => !(member.principal.is_a?(User) || member.principal.is_a?(Group)) ? "Placeholder accounts are managed in OpenProject." : inherited ? "Roles inherited from a group are managed through that group." :
          protected?(member.principal) ? "Installation operator and service access is protected." : nil)
    end

    def scope
      Member.where(project: @project, entity_id: nil).includes(:principal, :roles, :member_roles)
    end

    def visible_principals
      Principal.visible(@user).where(type: %w[User Group], status: 1)
    end

    def projection(context, query = {})
      authority!
      page = [Integer(query.fetch("page", "1"), exception: false).to_i, 1].max
      size = Integer(query.fetch("page_size", "25"), exception: false)
      size = 25 unless [25, 50, 100].include?(size)
      text = query.fetch("search", "").to_s[0, 200].downcase
      candidate_text = query.fetch("candidate_search", "").to_s[0, 200].downcase
      # Native visibility is retained; the Console cannot enumerate hidden users.
      matching = scope.joins(:principal)
      unless text.empty?
        matching = matching.where("LOWER(CONCAT(users.firstname, ' ', users.lastname)) LIKE ?", "%#{ActiveRecord::Base.sanitize_sql_like(text)}%")
      end
      protected_ids = User.where(admin: true).or(User.where(login: PROTECTED_LOGINS)).select(:id)
      candidates = visible_principals.where.not(id: scope.select(:user_id)).where.not(id: protected_ids)
        .where.not(id: GroupUser.where(user_id: protected_ids).select(:group_id))
      unless candidate_text.empty?
        candidates = candidates.where("LOWER(CONCAT(users.firstname, ' ', users.lastname)) LIKE ?", "%#{ActiveRecord::Base.sanitize_sql_like(candidate_text)}%")
      end
      candidate_total = candidates.count
      candidates = candidates.order(:id).limit(LIMIT).to_a
      recent = @store.read.fetch("membership_receipts").values.map { |entry| entry.fetch("result") }
        .select { |entry| entry["caller_id"] == context.fetch("caller_id") && entry["operator_id"] == context.fetch("operator_id") }
        .sort_by { |entry| entry.fetch("applied_at") }.last(10).reverse
      { "schema_version" => 1, "project_id" => @project.id, "project_identifier" => @project.identifier, "project_name" => @project.name,
        "members" => matching.order(:id).offset((page - 1) * size).limit(size).map { |member| member_value(member) },
        "total" => matching.count, "page" => page, "page_size" => size,
        "candidates" => candidates.first(LIMIT).map { |principal| principal_value(principal) },
        "candidate_total" => candidate_total, "roles" => roles, "recent_outcomes" => recent }
    end

    def mutate(request)
      authority!
      unless request.is_a?(Hash) && request.keys.sort == REQUEST_KEYS &&
          %w[add change remove].include?(request["operation"]) &&
          %w[request_id caller_id operator_id].all? { |key| request[key].is_a?(String) && request[key].match?(/\A[A-Za-z0-9_.:@-]{1,160}\z/) } &&
          request["principal_id"].is_a?(Integer) && request["principal_id"].positive? &&
          request["role_ids"].is_a?(Array) && request["role_ids"].size <= 20 &&
          request["role_ids"].all? { |id| id.is_a?(Integer) && id.positive? } &&
          request["role_ids"].uniq == request["role_ids"] &&
          (request["operation"] == "add" ? request["membership_id"].nil? && request["expected_version"].nil? :
            request["membership_id"].is_a?(Integer) && request["expected_version"].to_s.match?(/\Asha256:[a-f0-9]{64}\z/))
        raise Error.new(400, "membership_request_invalid", "Use the exact reviewed membership request.")
      end
      request_digest = OpenprojectDeliveryCatalogControl.digest(request)
      key = OpenprojectDeliveryCatalogControl.digest(request.values_at("caller_id", "operator_id", "request_id"))
      @store.with_locked_state do |state|
        replay = state.fetch("membership_receipts")[key]
        if replay
          raise Error.new(409, "membership_request_conflict", "This request already belongs to a different decision.") unless replay.fetch("request_digest") == request_digest
          next replay.fetch("result").merge("replayed" => true)
        end
        principal = visible_principals.find_by(id: request.fetch("principal_id"))
        raise Error.new(409, "membership_principal_unavailable", "This user or group is no longer available to this connection.") unless principal
        raise Error.new(403, "membership_protected", "Installation operator and service access is protected.") if protected?(principal)
        # Serialize against native updates to the target, including group-role changes.
        member = scope.lock.find_by(principal: principal)
        before = member && member_value(member)
        if request["operation"] == "add"
          raise Error.new(409, "membership_source_changed", "This user or group is already a project member. Reload members before deciding again.") if member
        elsif !member || member.id != request["membership_id"] || before["version"] != request["expected_version"]
          raise Error.new(409, "membership_source_changed", "Membership changed after review. Reload members before deciding again.")
        end
        raise Error.new(409, "membership_inherited", before["restriction"]) if before && before["protected"]
        selected_ids = request.fetch("role_ids")
        available_ids = roles.map { |role| role.fetch("id") }
        if request["operation"] == "remove" ? selected_ids.any? : selected_ids.empty? || (selected_ids - available_ids).any?
          raise Error.new(400, "membership_role_invalid", "Choose current project roles. Global and internal service roles are unavailable.")
        end
        operation = case request.fetch("operation")
                    when "add"
                      Members::CreateService.new(user: @user).call(project_id: @project.id, user_id: principal.id, role_ids: selected_ids, send_notifications: false)
                    when "change"
                      Members::UpdateService.new(user: @user, model: member).call(role_ids: selected_ids, send_notifications: false)
                    when "remove"
                      Members::DeleteService.new(user: @user, model: member).call
                    end
        unless operation.success?
          raise Error.new(409, "membership_native_rejected", "OpenProject rejected this membership change. Reload members and review the current roles.")
        end
        after_member = scope.find_by(principal: principal)
        after = after_member && member_value(after_member)
        verified = request["operation"] == "remove" ? after.nil? : after && after["role_ids"].sort == selected_ids.sort
        raise Error.new(502, "membership_readback_incomplete", "The membership readback does not match this decision.") unless verified
        result = request.slice("request_id", "caller_id", "operator_id", "operation").merge(
          "schema_version" => 1, "status" => "applied", "project_id" => @project.id, "project_identifier" => @project.identifier,
          "principal" => principal_value(principal), "before" => before, "after" => after,
          "applied_at" => @clock.call.iso8601, "replayed" => false, "request_digest" => request_digest)
        result["receipt"] = { "ref" => "openproject://delivery-memberships/receipts/#{key.delete_prefix('sha256:')}",
          "digest" => OpenprojectDeliveryCatalogControl.digest(result) }
        state.fetch("membership_receipts")[key] = { "request_digest" => request_digest, "result" => result }
        result
      end
    end
  end

  class Middleware
    def initialize(app)
      @app = app
      contract_path = ENV.fetch("OPENPROJECT_CATALOG_CONTROL_CONTRACT_PATH")
      @service = Service.new(contract: JSON.parse(File.read(contract_path)))
      @memberships = MembershipService.new(contract: JSON.parse(File.read(contract_path)))
    end

    def call(environment)
      path = environment.fetch("PATH_INFO", "")
      method = environment.fetch("REQUEST_METHOD", "GET")
      return @app.call(environment) unless path == "/v1/delivery-catalog/projection" || path.match?(MUTATION_PATH) ||
        %w[/v1/delivery-memberships/projection /v1/delivery-memberships/mutations].include?(path)

      authenticate!(environment)
      if method == "GET" && path == "/v1/delivery-memberships/projection"
        query = Rack::Utils.parse_query(environment.fetch("QUERY_STRING", ""))
        context = query.slice("caller_id", "operator_id")
        raise Error.new(400, "membership_request_invalid", "Accountable caller and operator are required.") unless context.size == 2 && context.values.all? { |v| v.match?(/\A[A-Za-z0-9_.:@-]{1,160}\z/) }
        return json(200, @memberships.projection(context, query))
      end
      if method == "POST" && path == "/v1/delivery-memberships/mutations"
        return json(200, @memberships.mutate(read_json(environment)))
      end
      if method == "GET" && path == "/v1/delivery-catalog/projection"
        return json(200, @service.projection)
      end
      match = path.match(MUTATION_PATH)
      if method == "POST" && match
        return json(200, @service.mutate(match[1], read_json(environment)))
      end
      json(405, error_payload("request_invalid", "Method is not allowed."))
    rescue Error => error
      json(error.status, error_payload(error.code, error.message, retryable: error.retryable))
    rescue StandardError => error
      Rails.logger.error("delivery catalog control failed: #{error.class}")
      json(500, error_payload("backend_mutation_failed", "Catalog backend failed safely.", retryable: true))
    end

    private

    def authenticate!(environment)
      expected = ENV.fetch("OPENPROJECT_CATALOG_CONTROL_SHARED_SECRET", "")
      supplied = environment.fetch("HTTP_AUTHORIZATION", "").delete_prefix("Bearer ")
      valid = expected.bytesize >= 32 && supplied.bytesize == expected.bytesize &&
        ActiveSupport::SecurityUtils.secure_compare(supplied, expected)
      raise Error.new(401, "request_invalid", "Catalog caller authentication failed.") unless valid
    end

    def read_json(environment)
      length = Integer(environment.fetch("CONTENT_LENGTH", "0"), exception: false) || 0
      raise Error.new(413, "request_invalid", "Catalog request is too large.") if length > MAX_REQUEST_BYTES

      input = environment.fetch("rack.input")
      body = input.read(MAX_REQUEST_BYTES + 1)
      raise Error.new(413, "request_invalid", "Catalog request is too large.") if body.bytesize > MAX_REQUEST_BYTES

      JSON.parse(body)
    rescue JSON::ParserError
      raise Error.new(400, "request_invalid", "Catalog request must contain valid JSON.")
    end

    def error_payload(code, message, retryable: false)
      { "schema_version" => 1, "code" => code, "message" => message, "retryable" => retryable }
    end

    def json(status, payload)
      body = JSON.generate(payload)
      [status, { "content-type" => "application/json", "content-length" => body.bytesize.to_s }, [body]]
    end
  end
end
