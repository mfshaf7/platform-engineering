# frozen_string_literal: true

require "json"
require "securerandom"

RESULT_BEGIN = "__OPENPROJECT_IDENTITY_PROVISION_BEGIN__"
RESULT_END = "__OPENPROJECT_IDENTITY_PROVISION_END__"

TARGET_LOGIN = ENV.fetch("TARGET_LOGIN")
TARGET_FIRSTNAME = ENV.fetch("TARGET_FIRSTNAME")
TARGET_LASTNAME = ENV.fetch("TARGET_LASTNAME")
TARGET_MAIL = ENV.fetch("TARGET_MAIL")
TARGET_PROJECT_IDENTIFIER = ENV.fetch("TARGET_PROJECT_IDENTIFIER", "workspace-delivery-art")
TARGET_PROJECT_IDENTIFIERS = begin
  raw = ENV["TARGET_PROJECT_IDENTIFIERS_JSON"]
  parsed = raw ? JSON.parse(raw) : nil
  values = Array(parsed).filter_map do |entry|
    value = entry.to_s.strip
    value.empty? ? nil : value
  end
  values.empty? ? [TARGET_PROJECT_IDENTIFIER] : values.uniq
rescue JSON::ParserError
  [TARGET_PROJECT_IDENTIFIER]
end
TARGET_TOKEN_NAME = ENV.fetch("TARGET_TOKEN_NAME", "openproject-#{TARGET_LOGIN}-v1")
TARGET_LANGUAGE = ENV.fetch("TARGET_LANGUAGE", Setting.default_language.presence || "en")
ROTATE_API_TOKEN = ENV.fetch("ROTATE_API_TOKEN", "false") == "true"
ISSUE_API_TOKEN = ENV.fetch("ISSUE_API_TOKEN", "false") == "true"

ROLE_NAMES = JSON.parse(
  ENV.fetch(
    "TARGET_ROLE_NAMES_JSON",
    '["Reader"]'
  )
)
CUSTOM_ROLE_PERMISSIONS = {
  "Work package creator" => ["add_work_packages"],
  "Work package structure editor" => [
    "manage_subtasks",
    "manage_work_package_relations",
    "move_work_packages"
  ]
}.freeze
CUSTOM_ROLE_CLASSES = {
  "Work package creator" => ProjectRole,
  "Work package structure editor" => ProjectRole
}.freeze

def ensure_user!
  user = User.find_or_initialize_by(login: TARGET_LOGIN)
  created = user.new_record?

  user.firstname = TARGET_FIRSTNAME
  user.lastname = TARGET_LASTNAME
  user.mail = TARGET_MAIL
  user.language = TARGET_LANGUAGE
  user.first_login = false
  user.force_password_change = false
  user.admin = false if user.respond_to?(:admin=)
  user.status = :active if user.respond_to?(:status=)

  if created || user.passwords.empty?
    password = SecureRandom.base58(48)
    user.password = password
    user.password_confirmation = password
  end

  user.save!

  { user:, created: }
end

def ensure_membership!(project:, user:, roles:)
  member = Member.find_or_initialize_by(project:, principal: user)
  member.role_ids = roles.map(&:id)
  member.save!
  member
end

def ensure_role!(name)
  permissions = CUSTOM_ROLE_PERMISSIONS[name]
  return Role.distinct.find_by!(name:) unless permissions

  role_class = CUSTOM_ROLE_CLASSES.fetch(name)
  role = role_class.find_or_initialize_by(name:)
  role.builtin = 0 if role.respond_to?(:builtin=) && role.new_record?
  role.position ||= Role.maximum(:position).to_i + 1 if role.respond_to?(:position=)
  role.permissions = permissions.map(&:to_sym)
  role.save!
  role
end

def ensure_api_token!(user:)
  return {
    enabled: false,
    token_id: nil,
    token_name: nil,
    created: false,
    rotated: false,
    repaired_duplicates: false,
    plaintext_value: nil
  } unless ISSUE_API_TOKEN

  existing_tokens = user.api_tokens.where("data ->> 'token_name' = ?", TARGET_TOKEN_NAME).order(:id).to_a
  repaired_duplicates = existing_tokens.length > 1

  if repaired_duplicates || ROTATE_API_TOKEN
    existing_tokens.each(&:destroy!)
    existing_tokens = []
  end

  if existing_tokens.one?
    token = existing_tokens.first
    return {
      enabled: true,
      token_id: token.id,
      token_name: token.token_name,
      created: false,
      rotated: false,
      repaired_duplicates: false,
      plaintext_value: nil
    }
  end

  token = user.api_tokens.create!(token_name: TARGET_TOKEN_NAME)

  {
    enabled: true,
    token_id: token.id,
    token_name: token.token_name,
    created: !ROTATE_API_TOKEN && !repaired_duplicates,
    rotated: ROTATE_API_TOKEN || repaired_duplicates,
    repaired_duplicates: repaired_duplicates,
    plaintext_value: token.plain_value
  }
end

projects = TARGET_PROJECT_IDENTIFIERS.map do |identifier|
  Project.find_by!(identifier: identifier)
end
roles = ROLE_NAMES.map { |name| ensure_role!(name) }

user_result = ensure_user!
memberships = projects.map do |project|
  member = ensure_membership!(project:, user: user_result[:user], roles:)
  {
    project_identifier: project.identifier,
    project_name: project.name,
    role_names: member.roles.order(:name).pluck(:name)
  }
end
token_result = ensure_api_token!(user: user_result[:user])
primary_membership = memberships.first

result = {
  login: user_result[:user].login,
  mail: user_result[:user].mail,
  user_created: user_result[:created],
  project_identifier: primary_membership[:project_identifier],
  project_name: primary_membership[:project_name],
  project_identifiers: memberships.map { |membership| membership[:project_identifier] },
  role_names: primary_membership[:role_names],
  memberships: memberships,
  api_token: {
    enabled: token_result[:enabled],
    token_name: token_result[:token_name],
    token_id: token_result[:token_id],
    created: token_result[:created],
    rotated: token_result[:rotated],
    repaired_duplicates: token_result[:repaired_duplicates],
    plaintext_value: token_result[:plaintext_value]
  }
}

puts RESULT_BEGIN
puts JSON.pretty_generate(result)
puts RESULT_END
