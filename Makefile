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
	@printf "  capture-cutover-evidence Snapshot pre-cutover host and runtime state\n"
	@printf "  render-cutover-command-inventory Render migration stop/start command inventory\n"
	@printf "  render-cutover-record Render the migration cutover record template\n"
	@printf "  render-runtime-container-verification Render runtime container verification commands\n"
	@printf "  render-runtime-reachability Render post-cutover runtime reachability checklist\n"
	@printf "  render-windows-cutover-inventory Render Windows task cutover inventory\n"
	@printf "  capture-windows-task-evidence Capture current Windows scheduled-task evidence\n"
	@printf "  openproject-apply  Register and wait for the OpenProject Argo apps\n"
	@printf "  openproject-status Show current OpenProject Argo and workload status\n"
	@printf "  openproject-access Show the preferred Windows and WSL OpenProject URLs\n"
	@printf "  openproject-sync-admin-password Reconcile the admin password from Vault-backed secret into OpenProject\n"
	@printf "  openproject-uninstall Remove the OpenProject Argo apps after GitOps removal\n"
	@printf "  verify-platform-host Verify fresh WSL host and k3s bootstrap health\n"
	@printf "  verify-restart-survival Verify full restart survival across host, Vault, and core Argo apps\n"
	@printf "  prepull-gateway-image Warm the current gateway image digest onto every node before rollout\n"
	@printf "  gateway-tag Print the deterministic gateway release tag for an environment\n"
	@printf "  gateway-pin Pin source SHAs for an environment from local repo checkouts\n"
	@printf "  gateway-validate Validate an environment contract\n"
	@printf "  gateway-record Record a built image digest into an environment contract\n"
	@printf "  gateway-promote Promote one validated environment candidate into another\n"
	@printf "  gateway-readiness Manage stage promotion readiness\n"
	@printf "  render-windows-bootstrap Render the Windows WSL bootstrap script\n"
	@printf "  validate           Run repo validation checks\n"
	@printf "  show-prod-versions Show current prod version pins\n"
	@printf "  show-stage-versions Show current stage version pins\n"
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

.PHONY: capture-cutover-evidence
capture-cutover-evidence:
	$(ANSIBLE_ENV) ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/capture-cutover-evidence.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: render-cutover-command-inventory
render-cutover-command-inventory:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/render-cutover-command-inventory.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: render-cutover-record
render-cutover-record:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/render-cutover-record.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: render-runtime-container-verification
render-runtime-container-verification:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/render-runtime-container-verification.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: render-runtime-reachability
render-runtime-reachability:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/render-runtime-reachability-checklist.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: render-windows-cutover-inventory
render-windows-cutover-inventory:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/render-windows-cutover-inventory.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: capture-windows-task-evidence
capture-windows-task-evidence:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/capture-windows-task-evidence.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: openproject-apply
openproject-apply:
	./scripts/openproject_apply.sh

.PHONY: openproject-status
openproject-status:
	./scripts/openproject_status.sh

.PHONY: openproject-access
openproject-access:
	./scripts/openproject_access.sh

.PHONY: openproject-sync-admin-password
openproject-sync-admin-password:
	./scripts/openproject_sync_admin_password.sh

.PHONY: openproject-uninstall
openproject-uninstall:
	./scripts/openproject_uninstall.sh

.PHONY: verify-platform-host
verify-platform-host:
	$(ANSIBLE_ENV) ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/verify-platform-host.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: verify-restart-survival
verify-restart-survival: verify-platform-host

.PHONY: prepull-gateway-image
prepull-gateway-image:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make prepull-gateway-image ENVIRONMENT=stage"; exit 1; }
	python3 scripts/prepull_gateway_image.py $(ENVIRONMENT)

.PHONY: gateway-tag
gateway-tag:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make gateway-tag ENVIRONMENT=stage"; exit 1; }
	python3 scripts/gateway_release.py tag $(ENVIRONMENT)

.PHONY: gateway-pin
gateway-pin:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make gateway-pin ENVIRONMENT=stage"; exit 1; }
	python3 scripts/gateway_release.py pin $(ENVIRONMENT)

.PHONY: gateway-validate
gateway-validate:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make gateway-validate ENVIRONMENT=stage"; exit 1; }
	python3 scripts/gateway_release.py validate $(ENVIRONMENT) $(if $(REQUIRE_DETERMINISTIC_TAG),--require-deterministic-tag,)

.PHONY: gateway-record
gateway-record:
	@test -n "$(ENVIRONMENT)" || { echo "ENVIRONMENT is required, for example: make gateway-record ENVIRONMENT=stage DIGEST=sha256:..."; exit 1; }
	@test -n "$(DIGEST)" || { echo "DIGEST is required, for example: make gateway-record ENVIRONMENT=stage DIGEST=sha256:..."; exit 1; }
	python3 scripts/gateway_release.py record $(ENVIRONMENT) --digest $(DIGEST) $(if $(TAG),--tag $(TAG),) $(if $(PLATFORM_SHA),--platform-sha $(PLATFORM_SHA),)

.PHONY: gateway-promote
gateway-promote:
	@test -n "$(SOURCE_ENVIRONMENT)" || { echo "SOURCE_ENVIRONMENT is required, for example: make gateway-promote SOURCE_ENVIRONMENT=stage TARGET_ENVIRONMENT=prod"; exit 1; }
	@test -n "$(TARGET_ENVIRONMENT)" || { echo "TARGET_ENVIRONMENT is required, for example: make gateway-promote SOURCE_ENVIRONMENT=stage TARGET_ENVIRONMENT=prod"; exit 1; }
	python3 scripts/gateway_release.py promote $(SOURCE_ENVIRONMENT) $(TARGET_ENVIRONMENT)

.PHONY: gateway-readiness
gateway-readiness:
	@test -n "$(ACTION)" || { echo "ACTION is required, for example: make gateway-readiness ACTION=validate"; exit 1; }
	python3 scripts/gateway_release.py readiness $(ACTION) $(if $(STATUS),--status $(STATUS),) $(if $(NOTE),--note "$(NOTE)",) $(if $(APPROVED_BY),--approved-by $(APPROVED_BY),)

.PHONY: pin-gateway-source-repos
pin-gateway-source-repos: gateway-pin

.PHONY: render-windows-bootstrap
render-windows-bootstrap:
	$(ANSIBLE_ENV) ansible-playbook ansible/playbooks/render-windows-bootstrap.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: validate
validate:
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
