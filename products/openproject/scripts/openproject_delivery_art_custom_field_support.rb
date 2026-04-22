# frozen_string_literal: true

require "date"
require "set"

module OpenprojectDeliveryArtCustomFieldSupport
  module_function

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
