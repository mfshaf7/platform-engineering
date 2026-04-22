# frozen_string_literal: true

require "date"
require "set"

module OpenprojectDeliveryArtCustomFieldSupport
  module_function

  ACTIVE_EXECUTION_CONTRACT_STATUSES = %w[ready in-progress blocked].freeze
  NARRATIVE_REQUIREMENTS = {
    "Epic" => [
      "What This Initiative Achieves",
      "Current PI Focus",
      "Scope Boundaries",
      "Execution Context"
    ],
    "PI Objective" => [
      "Outcome",
      "Why This PI",
      "Success Signal",
      "Execution Context"
    ],
    "Risk" => [
      "Risk Event",
      "Impact",
      "Current Handling",
      "Execution Context"
    ],
    "Feature" => [
      "What This Achieves",
      "Benefit Hypothesis",
      "Scope Boundaries",
      "Execution Context"
    ],
    "Enabler" => [
      "What This Enables",
      "Benefit Hypothesis",
      "Scope Boundaries",
      "Execution Context"
    ],
    "User story" => [
      "What This Achieves",
      "Why This Matters Now",
      "Evidence Expectation",
      "Execution Context"
    ],
    "Task" => [
      "What This Achieves",
      "Why This Matters Now",
      "Evidence Expectation",
      "Execution Context"
    ],
    "Milestone" => [
      "Exit Condition",
      "Execution Context"
    ]
  }.freeze
  FORBIDDEN_STRUCTURED_DESCRIPTION_HEADINGS = [
    "Acceptance Criteria",
    "Definition of Ready",
    "Definition of Done"
  ].freeze

  COMPLETION_HEADING_RULES = {
    "Completion Summary" => {
      required: true,
      format: :paragraph,
      disallowed_line_prefixes: ["- ", "* "]
    },
    "Changed Surfaces" => {
      required: true,
      format: :bullets,
      allowed_bullet_prefixes: [""]
    },
    "Test Result Evidence" => {
      required: true,
      format: :bullets,
      allowed_bullet_prefixes: ["PASS:", "FAIL:", "NOT APPLICABLE:", "Attached artifact:"]
    },
    "Validation Evidence" => {
      required: true,
      format: :bullets,
      allowed_bullet_prefixes: ["PASS:", "FAIL:", "CHECK:", "NOT APPLICABLE:", "Attached artifact:"]
    },
    "Residual Follow-Up" => {
      required: false,
      format: :bullets,
      allowed_bullet_prefixes: [""]
    }
  }.freeze

  def list_custom_field?(field:, kind: nil)
    kind == :list || field&.field_format == "list"
  end

  def list_allowed_values(field)
    return [] if field.nil?

    if field.respond_to?(:custom_options)
      field.custom_options.map { |entry| entry.value.to_s.strip }.reject(&:empty?)
    else
      Array(field.possible_values).map { |entry| entry.to_s.strip }.reject(&:empty?)
    end
  end

  def normalize_input_value!(field:, value:, kind:)
    return nil if value.nil?

    case kind
    when :int
      Integer(value).to_s
    when :date
      Date.iso8601(value).iso8601
    when :list
      normalize_list_input_value!(field:, value:)
    else
      value
    end
  rescue ArgumentError
    raise "Invalid #{field.name.inspect} value #{value.inspect}"
  end

  def normalize_list_input_value!(field:, value:)
    normalized = value.to_s.strip
    return nil if normalized.empty?

    option =
      if field.respond_to?(:custom_options)
        field.custom_options.find { |entry| entry.value.to_s.strip == normalized }
      end
    raise "Invalid #{field.name.inspect} value #{value.inspect}" if option.nil?

    option.id.to_s
  end

  def assign_custom_value!(entry:, field:, value:, kind: nil)
    custom_value = entry.custom_value_for(field)
    custom_value = entry.custom_values.build(custom_field: field) if custom_value.nil?
    custom_value.value = normalize_input_value!(field:, value:, kind:)
  end

  def rendered_custom_value(entry:, field:, kind: nil)
    return nil if field.nil?

    custom_value = entry.custom_value_for(field)
    return nil if custom_value.nil?

    raw_value = custom_value.value.to_s.strip
    return nil if raw_value.empty?

    if list_custom_field?(field:, kind:)
      option =
        if field.respond_to?(:custom_options)
          field.custom_options.find { |entry| entry.id.to_s == raw_value }
        end
      return option.value.to_s if option
    end

    raw_value
  end

  def custom_value_present?(entry:, field:, kind: nil)
    rendered_custom_value(entry:, field:, kind:)&.to_s&.strip&.length.to_i.positive?
  end

  def description_headings(entry:)
    entry.description.to_s.scan(/^## ([^\n]+)$/).flatten
  end

  def description_starts_with_heading?(entry:)
    entry.description.to_s.lstrip.start_with?("## ")
  end

  def required_narrative_headings(entry:)
    NARRATIVE_REQUIREMENTS.fetch(entry.type&.name.to_s, [])
  end

  def missing_required_narrative_headings(entry:)
    required_narrative_headings(entry:).reject do |heading|
      description_headings(entry:).include?(heading)
    end
  end

  def forbidden_structured_description_headings(entry:)
    description_headings(entry:) & FORBIDDEN_STRUCTURED_DESCRIPTION_HEADINGS
  end

  def extract_markdown_section(markdown:, heading:)
    rendered = markdown.to_s
    match = rendered.match(/^## #{Regexp.escape(heading)}\n(.*?)(?=^## |\z)/m)
    return nil unless match

    match[1].to_s.strip
  end

  def markdown_bullet_lines(body)
    body.to_s.lines.map(&:rstrip).reject { |line| line.strip.empty? }
  end

  def validate_completion_section(heading:, body:)
    rule = COMPLETION_HEADING_RULES.fetch(heading)
    if body.nil?
      issues = rule[:required] ? ["section body is empty or non-substantive"] : []
      return {
        present: false,
        substantive: false,
        body: body,
        formatting_valid: issues.empty?,
        formatting_issues: issues
      }
    end

    substantive = body.present? && !body.match?(/\ANot yet complete\.?\z/i)
    issues = []
    lines = markdown_bullet_lines(body)

    if rule[:required] && !substantive
      issues << "section body is empty or non-substantive"
    end

    case rule[:format]
    when :paragraph
      if lines.empty?
        issues << "section must contain a short outcome paragraph"
      else
        issues << "section must not use bullet-list formatting" if lines.any? { |line| rule.fetch(:disallowed_line_prefixes).any? { |prefix| line.start_with?(prefix) } }
        issues << "section should be a short paragraph, not a multi-line list" if lines.length > 3
        issues << "section must not contain markdown subheadings" if lines.any? { |line| line.start_with?("## ") }
      end
    when :bullets
      issues << "section must use flat bullet-list formatting" if lines.empty? || lines.any? { |line| !line.start_with?("- ") }

      allowed_bullet_prefixes = Array(rule[:allowed_bullet_prefixes])
      if lines.any? { |line| line.start_with?("- ") } && allowed_bullet_prefixes != [""]
        invalid_lines = lines.reject do |line|
          bullet_body = line.delete_prefix("- ").strip
          allowed_bullet_prefixes.any? { |prefix| bullet_body.start_with?(prefix) }
        end
        if invalid_lines.any?
          issues << "section bullets must start with one of: #{allowed_bullet_prefixes.join(', ')}"
        end
      end

      if heading == "Residual Follow-Up"
        invalid_lines = lines.reject do |line|
          bullet_body = line.delete_prefix("- ").strip
          bullet_body.match?(/#\d+/) || bullet_body.match?(%r{openproject://work_packages/\d+})
        end
        issues << "section bullets must reference an explicit ART item or work package" if invalid_lines.any?
      end
    end

    {
      present: !body.nil?,
      substantive: substantive,
      body: body,
      formatting_valid: issues.empty?,
      formatting_issues: issues
    }
  end

  def completion_evidence_state(entry:)
    rendered = entry.description.to_s
    section_map = COMPLETION_HEADING_RULES.to_h do |heading, _rule|
      body = extract_markdown_section(markdown: rendered, heading:)
      [heading, validate_completion_section(heading:, body:)]
    end

    required_sections = section_map.select { |heading, _state| COMPLETION_HEADING_RULES.fetch(heading)[:required] }
    issues = section_map.flat_map do |heading, state|
      state[:formatting_issues].map { |issue| "#{heading}: #{issue}" }
    end

    {
      present: required_sections.values.all? { |state| state[:substantive] },
      formatting_valid: issues.empty?,
      sections: section_map,
      issues: issues
    }
  end

  def normalize_list_storage!(project:, field_names: nil)
    fields = project.work_package_custom_fields.select { |field| field.field_format == "list" }
    if field_names
      allowed_names = Array(field_names).to_set
      fields = fields.select { |field| allowed_names.include?(field.name) }
    end

    normalized = []
    fields.each do |field|
      options_by_label =
        if field.respond_to?(:custom_options)
          field.custom_options.index_by { |entry| entry.value.to_s.strip }
        else
          {}
        end
      option_ids = options_by_label.values.map { |entry| entry.id.to_s }

      CustomValue.where(customized_type: "WorkPackage", custom_field_id: field.id)
                 .where.not(value: [nil, ""])
                 .find_each do |custom_value|
        raw_value = custom_value.value.to_s.strip
        next if raw_value.empty? || option_ids.include?(raw_value)

        option = options_by_label[raw_value]
        next if option.nil?

        custom_value.update_columns(value: option.id.to_s)
        normalized << {
          custom_value_id: custom_value.id,
          customized_id: custom_value.customized_id,
          field_name: field.name,
          from: raw_value,
          to: option.id.to_s
        }
      end
    end

    normalized
  end
end
