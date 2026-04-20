SHELL := /bin/bash
ANSIBLE_CONFIG := $(CURDIR)/ansible/ansible.cfg
ANSIBLE_TMP_DIR := /tmp/.ansible
ANSIBLE_EXTRA_VARS ?=
ANSIBLE_EXTRA_VARS_ARG := $(if $(strip $(ANSIBLE_EXTRA_VARS)),--extra-vars "$(ANSIBLE_EXTRA_VARS)",)
ANSIBLE_ENV := ANSIBLE_CONFIG=$(ANSIBLE_CONFIG) ANSIBLE_LOCAL_TEMP=$(ANSIBLE_TMP_DIR) ANSIBLE_REMOTE_TEMP=$(ANSIBLE_TMP_DIR)

.PHONY: help
help:
	@printf "Available targets:\n"
	@printf "  provision-wsl-host Run the WSL host provisioning playbook\n"
	@printf "  provision-k3s-node Run the k3s node provisioning playbook\n"
	@printf "  provision-transit-vault-host Run the dedicated transit Vault host provisioning playbook\n"
	@printf "  openproject-apply  Register and wait for the OpenProject Argo apps\n"
	@printf "  openproject-status Show current OpenProject Argo and workload status\n"
	@printf "  openproject-access Show the preferred Windows and WSL OpenProject URLs\n"
	@printf "  openproject-sync-admin-password Reconcile the admin password from Vault-backed secret into OpenProject\n"
	@printf "  openproject-configure-idea-backlog Remove demo projects and provision the workspace proposals backlog model\n"
	@printf "  openproject-configure-delivery-art Provision the workspace delivery ART project model\n"
	@printf "  openproject-provision-operator-orchestration-identity Create or converge the OpenProject service identity for operator-orchestration-service\n"
	@printf "  openproject-provision-operator-orchestration-delivery-access Grant the broker service identity access to both proposal and delivery projects\n"
	@printf "  openproject-uninstall Remove the OpenProject Argo apps after GitOps removal\n"
	@printf "  devint-up Launch or converge a local-k3s dev-integration profile\n"
	@printf "  devint-status Show the current local-k3s dev-integration profile state\n"
	@printf "  devint-smoke Run the smoke checks for a local-k3s dev-integration profile\n"
	@printf "  devint-down Stop a local-k3s dev-integration profile while keeping local state\n"
	@printf "  devint-reset Tear down a local-k3s dev-integration profile and remove local state\n"
	@printf "  devint-promote-check Render the local handoff report required before governed stage rehearsal\n"
	@printf "  verify-platform-host Verify fresh WSL host and k3s bootstrap health\n"
	@printf "  verify-restart-survival Verify full restart survival across host, Vault, and core Argo apps\n"
	@printf "  openclaw-gateway-prepull-image Warm the current OpenClaw gateway image digest onto every node before rollout\n"
	@printf "  openclaw-gateway-tag Print the deterministic OpenClaw gateway release tag for an environment\n"
	@printf "  openclaw-gateway-pin Pin OpenClaw source SHAs for an environment from local repo checkouts\n"
	@printf "  openclaw-gateway-validate Validate an OpenClaw environment contract\n"
	@printf "  openclaw-gateway-record Record a built OpenClaw image digest into an environment contract\n"
	@printf "  openclaw-gateway-verification Record or validate OpenClaw stage verification evidence\n"
	@printf "  openclaw-gateway-promote Promote one validated OpenClaw environment candidate into another\n"
	@printf "  openclaw-gateway-prod-verification Record or validate post-promotion OpenClaw prod smoke evidence\n"
	@printf "  openclaw-gateway-readiness Manage OpenClaw stage promotion readiness\n"
	@printf "  openclaw-telegram-overlay-status Show the current Telegram overlay lane state\n"
	@printf "  openclaw-telegram-overlay-pin Pin a stage Telegram overlay source commit from local repos\n"
	@printf "  openclaw-telegram-overlay-validate Validate the Telegram overlay lane contract\n"
	@printf "  openclaw-telegram-overlay-record Record a built stage Telegram overlay image digest\n"
	@printf "  openclaw-telegram-overlay-disable Disable the Telegram overlay lane in stage\n"
	@printf "  openclaw-prod-state Set or inspect the OpenClaw prod lifecycle state\n"
	@printf "  openclaw-stage-state Resume, suspend, or inspect the OpenClaw stage environment\n"
	@printf "  render-windows-bootstrap Render the Windows WSL bootstrap script\n"
	@printf "  validate           Run repo validation checks\n"
	@printf "  show-prod-versions Show current prod version pins\n"
	@printf "  show-stage-versions Show current stage version pins\n"
	@printf "\n"
	@printf "Legacy migration helpers (historical Docker-to-Platform-Core cutover only):\n"
	@printf "  legacy-capture-cutover-evidence Snapshot legacy cutover host and runtime state\n"
	@printf "  legacy-render-cutover-command-inventory Render historical stop/start command inventory\n"
	@printf "  legacy-render-cutover-record Render the historical cutover record template\n"
	@printf "  legacy-render-runtime-container-verification Render historical runtime container verification commands\n"
	@printf "  legacy-render-runtime-reachability Render historical runtime reachability checklist\n"
	@printf "  legacy-render-windows-cutover-inventory Render historical Windows task cutover inventory\n"
	@printf "  legacy-capture-windows-task-evidence Capture historical Windows scheduled-task evidence\n"
	@printf "\n"
	@printf "Override variables with ANSIBLE_EXTRA_VARS, for example:\n"
	@printf "  make render-windows-bootstrap ANSIBLE_EXTRA_VARS=\"platform_windows_wsl_distro=Platform-Core\"\n"

.PHONY: provision-wsl-host
provision-wsl-host:
	$(ANSIBLE_ENV) ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/provision-wsl-host.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: provision-k3s-node
provision-k3s-node:
	$(ANSIBLE_ENV) ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/provision-k3s-node.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: provision-transit-vault-host
provision-transit-vault-host:
	$(ANSIBLE_ENV) ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/provision-transit-vault-host.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: legacy-capture-cutover-evidence
legacy-capture-cutover-evidence:
	$(ANSIBLE_ENV) ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/legacy/capture-cutover-evidence.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: legacy-render-cutover-command-inventory
legacy-render-cutover-command-inventory:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/legacy/render-cutover-command-inventory.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: legacy-render-cutover-record
legacy-render-cutover-record:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/legacy/render-cutover-record.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: legacy-render-runtime-container-verification
legacy-render-runtime-container-verification:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/legacy/render-runtime-container-verification.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: legacy-render-runtime-reachability
legacy-render-runtime-reachability:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/legacy/render-runtime-reachability-checklist.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: legacy-render-windows-cutover-inventory
legacy-render-windows-cutover-inventory:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/legacy/render-windows-cutover-inventory.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: legacy-capture-windows-task-evidence
legacy-capture-windows-task-evidence:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/legacy/capture-windows-task-evidence.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: openproject-apply
openproject-apply:
	./products/openproject/scripts/openproject_apply.sh

.PHONY: openproject-status
openproject-status:
	./products/openproject/scripts/openproject_status.sh

.PHONY: openproject-access
openproject-access:
	./products/openproject/scripts/openproject_access.sh

.PHONY: openproject-sync-admin-password
openproject-sync-admin-password:
	./products/openproject/scripts/openproject_sync_admin_password.sh

.PHONY: openproject-configure-idea-backlog
openproject-configure-idea-backlog:
	./products/openproject/scripts/openproject_configure_idea_backlog.sh

.PHONY: openproject-configure-delivery-art
openproject-configure-delivery-art:
	./products/openproject/scripts/openproject_configure_delivery_art.sh

.PHONY: openproject-provision-operator-orchestration-identity
openproject-provision-operator-orchestration-identity:
	./products/openproject/scripts/openproject_provision_operator_orchestration_identity.sh

.PHONY: openproject-provision-operator-orchestration-delivery-access
openproject-provision-operator-orchestration-delivery-access:
	OPENPROJECT_AUTOMATION_PROJECT_IDENTIFIERS_JSON='["workspace-proposals","workspace-delivery-art"]' \
	./products/openproject/scripts/openproject_provision_operator_orchestration_identity.sh

.PHONY: openproject-uninstall
openproject-uninstall:
	./products/openproject/scripts/openproject_uninstall.sh

.PHONY: devint-up
devint-up:
	@test -n "$(PROFILE)" || { echo "PROFILE is required, for example: make devint-up PROFILE=idea-workflow"; exit 1; }
	python3 scripts/dev_integration.py up --profile $(PROFILE) $(if $(OPERATOR),--operator $(OPERATOR),) $(if $(EXTRA_ARGS),$(EXTRA_ARGS),)

.PHONY: devint-status
devint-status:
	@test -n "$(PROFILE)" || { echo "PROFILE is required, for example: make devint-status PROFILE=idea-workflow"; exit 1; }
	python3 scripts/dev_integration.py status --profile $(PROFILE) $(if $(OPERATOR),--operator $(OPERATOR),) $(if $(EXTRA_ARGS),$(EXTRA_ARGS),)

.PHONY: devint-smoke
devint-smoke:
	@test -n "$(PROFILE)" || { echo "PROFILE is required, for example: make devint-smoke PROFILE=idea-workflow"; exit 1; }
	python3 scripts/dev_integration.py smoke --profile $(PROFILE) $(if $(OPERATOR),--operator $(OPERATOR),) $(if $(EXTRA_ARGS),$(EXTRA_ARGS),)

.PHONY: devint-down
devint-down:
	@test -n "$(PROFILE)" || { echo "PROFILE is required, for example: make devint-down PROFILE=idea-workflow"; exit 1; }
	python3 scripts/dev_integration.py down --profile $(PROFILE) $(if $(OPERATOR),--operator $(OPERATOR),) $(if $(EXTRA_ARGS),$(EXTRA_ARGS),)

.PHONY: devint-reset
devint-reset:
	@test -n "$(PROFILE)" || { echo "PROFILE is required, for example: make devint-reset PROFILE=idea-workflow"; exit 1; }
	python3 scripts/dev_integration.py reset --profile $(PROFILE) $(if $(OPERATOR),--operator $(OPERATOR),) $(if $(EXTRA_ARGS),$(EXTRA_ARGS),)

.PHONY: devint-promote-check
devint-promote-check:
	@test -n "$(PROFILE)" || { echo "PROFILE is required, for example: make devint-promote-check PROFILE=idea-workflow"; exit 1; }
	python3 scripts/dev_integration.py promote-check --profile $(PROFILE) $(if $(OPERATOR),--operator $(OPERATOR),) $(if $(EXTRA_ARGS),$(EXTRA_ARGS),)

.PHONY: verify-platform-host
verify-platform-host:
	$(ANSIBLE_ENV) ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/verify-platform-host.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: verify-restart-survival
verify-restart-survival: verify-platform-host

.PHONY: openclaw-gateway-prepull-image
openclaw-gateway-prepull-image:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make openclaw-gateway-prepull-image ENVIRONMENT=stage"; exit 1; }
	python3 products/openclaw/scripts/prepull_gateway_image.py $(ENVIRONMENT)

.PHONY: openclaw-gateway-tag
openclaw-gateway-tag:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make openclaw-gateway-tag ENVIRONMENT=stage"; exit 1; }
	python3 products/openclaw/scripts/gateway_release.py tag $(ENVIRONMENT)

.PHONY: openclaw-gateway-pin
openclaw-gateway-pin:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make openclaw-gateway-pin ENVIRONMENT=stage"; exit 1; }
	python3 products/openclaw/scripts/gateway_release.py pin $(ENVIRONMENT)

.PHONY: openclaw-gateway-validate
openclaw-gateway-validate:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make openclaw-gateway-validate ENVIRONMENT=stage"; exit 1; }
	python3 products/openclaw/scripts/gateway_release.py validate $(ENVIRONMENT) $(if $(REQUIRE_DETERMINISTIC_TAG),--require-deterministic-tag,)

.PHONY: openclaw-gateway-record
openclaw-gateway-record:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make openclaw-gateway-record ENVIRONMENT=stage DIGEST=sha256:..."; exit 1; }
	@test -n "$(DIGEST)" || { echo "DIGEST is required, for example: make openclaw-gateway-record ENVIRONMENT=stage DIGEST=sha256:..."; exit 1; }
	python3 products/openclaw/scripts/gateway_release.py record $(ENVIRONMENT) --digest $(DIGEST) $(if $(TAG),--tag $(TAG),) $(if $(PLATFORM_SHA),--platform-sha $(PLATFORM_SHA),)

.PHONY: openclaw-gateway-verification
openclaw-gateway-verification:
	@test -n "$(ACTION)" || { echo "ACTION is required, for example: make openclaw-gateway-verification ACTION=validate"; exit 1; }
	python3 products/openclaw/scripts/gateway_release.py verification $(ACTION) $(if $(STATUS),--status $(STATUS),) $(if $(NOTE),--note "$(NOTE)",) $(if $(VERIFIED_BY),--verified-by $(VERIFIED_BY),) $(if $(EVIDENCE_REF),--evidence-ref "$(EVIDENCE_REF)",) $(if $(CHECK_RESULTS),--check-results "$(CHECK_RESULTS)",)

.PHONY: openclaw-gateway-promote
openclaw-gateway-promote:
	@test -n "$(SOURCE_ENVIRONMENT)" || { echo "SOURCE_ENVIRONMENT is required, for example: make openclaw-gateway-promote SOURCE_ENVIRONMENT=stage TARGET_ENVIRONMENT=prod"; exit 1; }
	@test -n "$(TARGET_ENVIRONMENT)" || { echo "TARGET_ENVIRONMENT is required, for example: make openclaw-gateway-promote SOURCE_ENVIRONMENT=stage TARGET_ENVIRONMENT=prod"; exit 1; }
	python3 products/openclaw/scripts/gateway_release.py promote $(SOURCE_ENVIRONMENT) $(TARGET_ENVIRONMENT)

.PHONY: openclaw-gateway-prod-verification
openclaw-gateway-prod-verification:
	@test -n "$(ACTION)" || { echo "ACTION is required, for example: make openclaw-gateway-prod-verification ACTION=validate"; exit 1; }
	python3 products/openclaw/scripts/gateway_release.py prod-verification $(ACTION) $(if $(STATUS),--status $(STATUS),) $(if $(NOTE),--note "$(NOTE)",) $(if $(VERIFIED_BY),--verified-by $(VERIFIED_BY),) $(if $(EVIDENCE_REF),--evidence-ref "$(EVIDENCE_REF)",) $(if $(CHECK_RESULTS),--check-results "$(CHECK_RESULTS)",)

.PHONY: openclaw-gateway-readiness
openclaw-gateway-readiness:
	@test -n "$(ACTION)" || { echo "ACTION is required, for example: make openclaw-gateway-readiness ACTION=validate"; exit 1; }
	python3 products/openclaw/scripts/gateway_release.py readiness $(ACTION) $(if $(STATUS),--status $(STATUS),) $(if $(NOTE),--note "$(NOTE)",) $(if $(APPROVED_BY),--approved-by $(APPROVED_BY),)

.PHONY: openclaw-telegram-overlay-status
openclaw-telegram-overlay-status:
	python3 products/openclaw/scripts/telegram_overlay_experiment.py status stage

.PHONY: openclaw-telegram-overlay-pin
openclaw-telegram-overlay-pin:
	python3 products/openclaw/scripts/telegram_overlay_experiment.py pin stage $(if $(TELEGRAM_REPO),--telegram-repo $(TELEGRAM_REPO),) $(if $(TELEGRAM_REF),--telegram-ref $(TELEGRAM_REF),)

.PHONY: openclaw-telegram-overlay-validate
openclaw-telegram-overlay-validate:
	python3 products/openclaw/scripts/telegram_overlay_experiment.py validate stage

.PHONY: openclaw-telegram-overlay-record
openclaw-telegram-overlay-record:
	@test -n "$(DIGEST)" || { echo "DIGEST is required, for example: make openclaw-telegram-overlay-record DIGEST=sha256:..."; exit 1; }
	python3 products/openclaw/scripts/telegram_overlay_experiment.py record stage --digest $(DIGEST) $(if $(TAG),--tag $(TAG),) $(if $(PLATFORM_SHA),--platform-sha $(PLATFORM_SHA),)

.PHONY: openclaw-telegram-overlay-disable
openclaw-telegram-overlay-disable:
	python3 products/openclaw/scripts/telegram_overlay_experiment.py disable stage $(if $(NOTE),--note "$(NOTE)",)

.PHONY: openclaw-prod-state
openclaw-prod-state:
	@test -n "$(STATE)" || { echo "STATE is required, for example: make openclaw-prod-state STATE=suspended CHANGED_BY=mfshaf7 REASON=incident-containment"; exit 1; }
	python3 products/openclaw/scripts/set_prod_environment_state.py $(STATE) $(if $(CHANGED_BY),--changed-by $(CHANGED_BY),) $(if $(REASON),--reason "$(REASON)",) $(if $(INCIDENT_REF),--incident-ref "$(INCIDENT_REF)",) $(if $(NOTE),--note "$(NOTE)",)

.PHONY: openclaw-stage-state
openclaw-stage-state:
	@test -n "$(STATE)" || { echo "STATE is required, for example: make openclaw-stage-state STATE=resume COMPONENTS=gateway,version"; exit 1; }
	python3 products/openclaw/scripts/set_stage_environment_state.py $(STATE) $(if $(COMPONENTS),--components $(COMPONENTS),)

.PHONY: render-windows-bootstrap
render-windows-bootstrap:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/render-windows-bootstrap.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: validate
validate:
	python3 scripts/validate_repo_structure.py
	python3 scripts/validate_governance_docs.py
	python3 scripts/validate_ai_model_profiles.py
	python3 scripts/validate_operational_docs.py
	helm lint charts/openclaw-gateway
	helm lint charts/platform-version
	terraform -chdir=terraform/environments/prod fmt -check
	terraform -chdir=terraform/environments/prod init -backend=false
	terraform -chdir=terraform/environments/prod validate

.PHONY: show-prod-versions
show-prod-versions:
	cat environments/prod/versions.yaml

.PHONY: show-stage-versions
show-stage-versions:
	cat environments/stage/versions.yaml
