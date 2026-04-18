# frozen_string_literal: true

require "json"
require "securerandom"

RESULT_BEGIN = "__OPENPROJECT_OPERATOR_ORCHESTRATION_IDENTITY_BEGIN__"
RESULT_END = "__OPENPROJECT_OPERATOR_ORCHESTRATION_IDENTITY_END__"

TARGET_LOGIN = ENV.fetch("TARGET_LOGIN", "operator-orchestration-service")
TARGET_FIRSTNAME = ENV.fetch("TARGET_FIRSTNAME", "Operator")
TARGET_LASTNAME = ENV.fetch("TARGET_LASTNAME", "Orchestration Service")
TARGET_MAIL = ENV.fetch("TARGET_MAIL", "operator-orchestration-service@local.invalid")
TARGET_PROJECT_IDENTIFIER = ENV.fetch("TARGET_PROJECT_IDENTIFIER", "workspace-proposals")
TARGET_TOKEN_NAME = ENV.fetch("TARGET_TOKEN_NAME", "openproject-workspace-proposals-v1")
TARGET_LANGUAGE = ENV.fetch("TARGET_LANGUAGE", Setting.default_language.presence || "en")
ROTATE_API_TOKEN = ENV.fetch("ROTATE_API_TOKEN", "false") == "true"

ROLE_NAMES = JSON.parse(ENV.fetch("TARGET_ROLE_NAMES_JSON", '["Reader","Work package editor"]'))

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

def ensure_api_token!(user:)
  existing_tokens = user.api_tokens.where("data ->> 'token_name' = ?", TARGET_TOKEN_NAME).order(:id).to_a
  repaired_duplicates = existing_tokens.length > 1

  if repaired_duplicates || ROTATE_API_TOKEN
    existing_tokens.each(&:destroy!)
    existing_tokens = []
  end

  if existing_tokens.one?
    token = existing_tokens.first
    return {
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
    token_id: token.id,
    token_name: token.token_name,
    created: !ROTATE_API_TOKEN && !repaired_duplicates,
    rotated: ROTATE_API_TOKEN || repaired_duplicates,
    repaired_duplicates: repaired_duplicates,
    plaintext_value: token.plain_value
  }
end

project = Project.find_by!(identifier: TARGET_PROJECT_IDENTIFIER)
roles = ROLE_NAMES.map { |name| Role.distinct.find_by!(name:) }

user_result = ensure_user!
member = ensure_membership!(project:, user: user_result[:user], roles:)
token_result = ensure_api_token!(user: user_result[:user])

result = {
  login: user_result[:user].login,
  mail: user_result[:user].mail,
  user_created: user_result[:created],
  project_identifier: project.identifier,
  project_name: project.name,
  role_names: member.roles.order(:name).pluck(:name),
  api_token: {
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
