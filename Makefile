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
	@printf "  verify-platform-host Verify fresh WSL host and k3s bootstrap health\n"
	@printf "  verify-restart-survival Verify full restart survival across host, Vault, and core Argo apps\n"
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

.PHONY: verify-platform-host
verify-platform-host:
	$(ANSIBLE_ENV) ansible-playbook -i ansible/inventory/hosts.ini ansible/playbooks/verify-platform-host.yml $(ANSIBLE_EXTRA_VARS_ARG)

.PHONY: verify-restart-survival
verify-restart-survival: verify-platform-host

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
