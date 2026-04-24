# frozen_string_literal: true

require "json"

module OpenprojectDeliveryArtTaxonomySupport
  module_function

  TAXONOMY_CANDIDATE_PATHS = [
    ENV["OPENPROJECT_DELIVERY_ART_TAXONOMY_PATH"],
    File.expand_path("../delivery-art-taxonomy.json", __dir__),
    File.expand_path("delivery-art-taxonomy.json", __dir__),
    "/tmp/delivery-art-taxonomy.json"
  ].compact.freeze

  def taxonomy_path
    @taxonomy_path ||= TAXONOMY_CANDIDATE_PATHS.find { |path| File.exist?(path) }
  end

  def taxonomy
    raise Errno::ENOENT, "delivery-art-taxonomy.json not found in any supported location" unless taxonomy_path

    @taxonomy ||= JSON.parse(File.read(taxonomy_path))
  end

  def classification_field_name
    taxonomy.fetch("classification_field").fetch("name")
  end

  def classification_required_types
    taxonomy.fetch("classification_field").fetch("required_for_types")
  end

  def classification_values
    taxonomy.fetch("classification_field").fetch("values")
  end

  def structural_types
    taxonomy.fetch("structural_types")
  end

  def structural_type_names
    structural_types.keys
  end

  def structural_type_spec(type_name)
    structural_types.fetch(type_name)
  end

  def allowed_parent_types(type_name)
    structural_type_spec(type_name).fetch("allowed_parent_types")
  end

  def derived_subject_prefix(type_name:, classification: nil)
    spec = structural_type_spec(type_name)
    classification_prefixes = spec["derived_subject_prefix_by_classification"] || {}
    return classification_prefixes[classification] if classification && classification_prefixes.key?(classification)

    spec["derived_subject_prefix"]
  end

  def required_narrative_headings(type_name:, classification: nil)
    headings = structural_type_spec(type_name).fetch("narrative_headings")
    return headings unless headings.is_a?(Hash)

    headings.fetch(classification.to_s, headings.fetch("default"))
  end

  def legacy_subject_prefixes
    taxonomy.fetch("legacy_subject_prefixes")
  end

  def all_known_subject_prefixes
    derived_prefixes = structural_types.each_with_object([]) do |(_type_name, spec), values|
      values << spec["derived_subject_prefix"] if spec["derived_subject_prefix"]
      values.concat((spec["derived_subject_prefix_by_classification"] || {}).values)
    end

    (legacy_subject_prefixes + derived_prefixes).uniq
  end

  def strip_known_subject_prefix(subject)
    pattern = all_known_subject_prefixes.map { |value| Regexp.escape(value) }.join("|")
    subject.to_s.sub(/\A(?:#{pattern}):\s*/i, "")
  end

  def detected_subject_prefix(subject)
    cleaned = subject.to_s
    all_known_subject_prefixes.find do |value|
      cleaned.match?(/\A#{Regexp.escape(value)}:\s*/i)
    end
  end

  def render_subject(base_subject:, type_name:, classification: nil)
    cleaned = strip_known_subject_prefix(base_subject).strip
    prefix = derived_subject_prefix(type_name:, classification:)
    return cleaned if prefix.nil? || prefix.empty?

    "#{prefix}: #{cleaned}"
  end

  def canonical_business_classification
    "Business"
  end
end
