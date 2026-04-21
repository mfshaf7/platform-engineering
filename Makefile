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
	@printf "  openproject-sync-delivery-art-views Reconcile delivery boards, PM² initiative register, PI objectives, risk views, and Program Increment views\n"
	@printf "  openproject-update-delivery-initiative Update the top-level delivery Epic governance fields, PI, PM², system demo, and inspect-and-adapt state\n"
	@printf "  openproject-record-system-demo Append one supported system-demo evidence entry to a delivery Epic\n"
	@printf "  openproject-record-inspect-and-adapt Append one supported inspect-and-adapt entry to a delivery Epic\n"
	@printf "  openproject-create-delivery-work-item Create one new child delivery work item under an existing parent with the supported SAFe execution fields\n"
	@printf "  openproject-bulk-update-delivery-work-items Apply one reviewable batch of delivery work-item execution updates\n"
	@printf "  openproject-move-delivery-work-item Reparent one existing delivery work item under a new parent\n"
	@printf "  openproject-update-delivery-work-item Update one delivery work item for day-to-day execution changes and SAFe execution metadata\n"
	@printf "  openproject-complete-delivery-work-item Mark one delivery work item done with explicit completion evidence and optional attached test output\n"
	@printf "  openproject-show-delivery-initiatives Show the portfolio-level delivery initiative summary across Workspace Delivery ART\n"
	@printf "  openproject-check-delivery-art-quality Check whether the current delivery ART records are clean enough to use as primary work-state truth\n"
	@printf "  openproject-show-delivery-execution Show the current execution tree, blockers, assignees, and PI placement for one delivery Epic\n"
	@printf "  openproject-show-delivery-planning Show the current team and iteration planning summary for one delivery Epic\n"
	@printf "  openproject-show-pi-objectives Show the PI objective summary, business value rollup, and objective health for one delivery Epic\n"
	@printf "  openproject-record-pi-review Record PI objective review outcomes and actual business value for one PI\n"
	@printf "  openproject-check-delivery-closeout-readiness Check whether a delivery Epic is truly ready for closeout\n"
	@printf "  openproject-manage-delivery-blocker Record or clear blocker governance on a delivery work package\n"
	@printf "  openproject-manage-delivery-parking Park or resume one delivery work item without deleting it\n"
	@printf "  openproject-manage-delivery-dependency Add or remove one explicit delivery dependency link\n"
	@printf "  openproject-consume-accepted-idea Consume one accepted proposal into the delivery ART through the broker-owned internal route\n"
	@printf "  openproject-apply-delivery-plan Apply a delivery execution plan to an existing delivery Epic\n"
	@printf "  openproject-close-delivery-initiative Close a completed delivery Epic and mark the source proposal implemented\n"
	@printf "  openproject-verify-clean-start Report or enforce the clean-start gate for future production activation\n"
	@printf "  openproject-provision-operator-orchestration-identity Create or converge the OpenProject service identity for operator-orchestration-service\n"
	@printf "  openproject-provision-operator-orchestration-delivery-access Grant the broker service identity access to both proposal and delivery projects\n"
	@printf "  openproject-uninstall Remove the OpenProject Argo apps after GitOps removal\n"
	@printf "  devint-up Launch or converge a local-k3s dev-integration profile\n"
	@printf "  devint-status Show the current local-k3s dev-integration profile state\n"
	@printf "  devint-access Hold open the primary inspection surface for a local-k3s dev-integration profile\n"
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
	OPENPROJECT_DELIVERY_PI_NAMES="$(PI_NAMES)" ./products/openproject/scripts/openproject_configure_delivery_art.sh

.PHONY: openproject-sync-delivery-art-views
openproject-sync-delivery-art-views:
	OPENPROJECT_DELIVERY_PI_NAMES="$(PI_NAMES)" ./products/openproject/scripts/openproject_sync_delivery_art_views.sh

.PHONY: openproject-update-delivery-initiative
openproject-update-delivery-initiative:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-update-delivery-initiative TARGET_EPIC_ID=38 PM2_PHASE=Planning TARGET_PI=PI-2026-02 SPONSOR=mfshaf7 STATUS=in-progress"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" PM2_PHASE="$(PM2_PHASE)" TARGET_PI="$(TARGET_PI)" SPONSOR="$(SPONSOR)" BUSINESS_OBJECTIVE="$(BUSINESS_OBJECTIVE)" SUCCESS_CRITERIA="$(SUCCESS_CRITERIA)" SYSTEM_DEMO_EVIDENCE="$(SYSTEM_DEMO_EVIDENCE)" INSPECT_AND_ADAPT_ACTIONS="$(INSPECT_AND_ADAPT_ACTIONS)" NFR_CATEGORY="$(NFR_CATEGORY)" STATUS="$(STATUS)" DESCRIPTION="$(DESCRIPTION)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_update_delivery_initiative.sh

.PHONY: openproject-record-system-demo
openproject-record-system-demo:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-record-system-demo TARGET_EPIC_ID=38 DEMO_SUMMARY='Iteration 1 demo complete' DEMO_EVIDENCE='Reviewed PI objective progress'"; exit 1; }
	@test -n "$(DEMO_SUMMARY)" || { echo "DEMO_SUMMARY is required, for example: make openproject-record-system-demo TARGET_EPIC_ID=38 DEMO_SUMMARY='Iteration 1 demo complete' DEMO_EVIDENCE='Reviewed PI objective progress'"; exit 1; }
	@test -n "$(DEMO_EVIDENCE)" || { echo "DEMO_EVIDENCE is required, for example: make openproject-record-system-demo TARGET_EPIC_ID=38 DEMO_SUMMARY='Iteration 1 demo complete' DEMO_EVIDENCE='Reviewed PI objective progress'"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" DEMO_DATE="$(DEMO_DATE)" DEMO_OUTCOME="$(DEMO_OUTCOME)" DEMO_SUMMARY="$(DEMO_SUMMARY)" DEMO_EVIDENCE="$(DEMO_EVIDENCE)" DEMO_FOLLOW_UP="$(DEMO_FOLLOW_UP)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_record_system_demo.sh

.PHONY: openproject-record-inspect-and-adapt
openproject-record-inspect-and-adapt:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-record-inspect-and-adapt TARGET_EPIC_ID=38 INSPECT_SUMMARY='PI review complete' ACTION_ITEMS='- Continue broker API migration'"; exit 1; }
	@test -n "$(INSPECT_SUMMARY)" || { echo "INSPECT_SUMMARY is required, for example: make openproject-record-inspect-and-adapt TARGET_EPIC_ID=38 INSPECT_SUMMARY='PI review complete' ACTION_ITEMS='- Continue broker API migration'"; exit 1; }
	@test -n "$(ACTION_ITEMS)" || { echo "ACTION_ITEMS is required, for example: make openproject-record-inspect-and-adapt TARGET_EPIC_ID=38 INSPECT_SUMMARY='PI review complete' ACTION_ITEMS='- Continue broker API migration'"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" INSPECT_DATE="$(INSPECT_DATE)" INSPECT_SUMMARY="$(INSPECT_SUMMARY)" ACTION_ITEMS="$(ACTION_ITEMS)" INSPECT_FOLLOW_UP="$(INSPECT_FOLLOW_UP)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_record_inspect_and_adapt.sh

.PHONY: openproject-create-delivery-work-item
openproject-create-delivery-work-item:
	@test -n "$(PARENT_WORK_PACKAGE_ID)" || { echo "PARENT_WORK_PACKAGE_ID is required, for example: make openproject-create-delivery-work-item PARENT_WORK_PACKAGE_ID=39 TYPE=Task SUBJECT='Inventory repo split'"; exit 1; }
	@test -n "$(TYPE)" || { echo "TYPE is required, for example: make openproject-create-delivery-work-item PARENT_WORK_PACKAGE_ID=39 TYPE=Task SUBJECT='Inventory repo split'"; exit 1; }
	@test -n "$(SUBJECT)" || { echo "SUBJECT is required, for example: make openproject-create-delivery-work-item PARENT_WORK_PACKAGE_ID=39 TYPE=Task SUBJECT='Inventory repo split'"; exit 1; }
	PARENT_WORK_PACKAGE_ID="$(PARENT_WORK_PACKAGE_ID)" TYPE="$(TYPE)" SUBJECT="$(SUBJECT)" STATUS="$(STATUS)" TARGET_PI="$(TARGET_PI)" ASSIGNEE_LOGIN="$(ASSIGNEE_LOGIN)" DESCRIPTION="$(DESCRIPTION)" START_DATE="$(START_DATE)" DUE_DATE="$(DUE_DATE)" ESTIMATED_WORK="$(ESTIMATED_WORK)" REMAINING_WORK="$(REMAINING_WORK)" PERCENT_COMPLETE="$(PERCENT_COMPLETE)" DELIVERY_TEAM="$(DELIVERY_TEAM)" ITERATION="$(ITERATION)" ACCEPTANCE_CRITERIA="$(ACCEPTANCE_CRITERIA)" DEFINITION_OF_READY="$(DEFINITION_OF_READY)" DEFINITION_OF_DONE="$(DEFINITION_OF_DONE)" NFR_CATEGORY="$(NFR_CATEGORY)" PI_OBJECTIVE_TYPE="$(PI_OBJECTIVE_TYPE)" PLANNED_BUSINESS_VALUE="$(PLANNED_BUSINESS_VALUE)" ACTUAL_BUSINESS_VALUE="$(ACTUAL_BUSINESS_VALUE)" ROAM_STATE="$(ROAM_STATE)" RISK_OWNER="$(RISK_OWNER)" RISK_REVIEW_DATE="$(RISK_REVIEW_DATE)" RISK_DISPOSITION="$(RISK_DISPOSITION)" WSJF_USER_BUSINESS_VALUE="$(WSJF_USER_BUSINESS_VALUE)" WSJF_TIME_CRITICALITY="$(WSJF_TIME_CRITICALITY)" WSJF_RR_OE="$(WSJF_RR_OE)" WSJF_JOB_SIZE="$(WSJF_JOB_SIZE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_create_delivery_work_item.sh

.PHONY: openproject-bulk-update-delivery-work-items
openproject-bulk-update-delivery-work-items:
	@test -n "$(DELIVERY_WORK_ITEM_UPDATE_FILE)" || { echo "DELIVERY_WORK_ITEM_UPDATE_FILE is required, for example: make openproject-bulk-update-delivery-work-items DELIVERY_WORK_ITEM_UPDATE_FILE=/abs/path/work-item-updates.json"; exit 1; }
	DELIVERY_WORK_ITEM_UPDATE_FILE="$(DELIVERY_WORK_ITEM_UPDATE_FILE)" OPENPROJECT_DELIVERY_PI_NAMES="$(OPENPROJECT_DELIVERY_PI_NAMES)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_bulk_update_delivery_work_items.sh

.PHONY: openproject-move-delivery-work-item
openproject-move-delivery-work-item:
	@test -n "$(TARGET_WORK_PACKAGE_ID)" || { echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-move-delivery-work-item TARGET_WORK_PACKAGE_ID=40 NEW_PARENT_WORK_PACKAGE_ID=43"; exit 1; }
	@test -n "$(NEW_PARENT_WORK_PACKAGE_ID)" || { echo "NEW_PARENT_WORK_PACKAGE_ID is required, for example: make openproject-move-delivery-work-item TARGET_WORK_PACKAGE_ID=40 NEW_PARENT_WORK_PACKAGE_ID=43"; exit 1; }
	TARGET_WORK_PACKAGE_ID="$(TARGET_WORK_PACKAGE_ID)" NEW_PARENT_WORK_PACKAGE_ID="$(NEW_PARENT_WORK_PACKAGE_ID)" WORK_NOTE="$(WORK_NOTE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_move_delivery_work_item.sh

.PHONY: openproject-update-delivery-work-item
openproject-update-delivery-work-item:
	@test -n "$(TARGET_WORK_PACKAGE_ID)" || { echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-update-delivery-work-item TARGET_WORK_PACKAGE_ID=40 STATUS=in-progress ASSIGNEE_LOGIN=admin"; exit 1; }
	TARGET_WORK_PACKAGE_ID="$(TARGET_WORK_PACKAGE_ID)" STATUS="$(STATUS)" TARGET_PI="$(TARGET_PI)" CLEAR_TARGET_PI="$(CLEAR_TARGET_PI)" ASSIGNEE_LOGIN="$(ASSIGNEE_LOGIN)" CLEAR_ASSIGNEE="$(CLEAR_ASSIGNEE)" DESCRIPTION="$(DESCRIPTION)" CLEAR_DESCRIPTION="$(CLEAR_DESCRIPTION)" WORK_NOTE="$(WORK_NOTE)" START_DATE="$(START_DATE)" CLEAR_START_DATE="$(CLEAR_START_DATE)" DUE_DATE="$(DUE_DATE)" CLEAR_DUE_DATE="$(CLEAR_DUE_DATE)" ESTIMATED_WORK="$(ESTIMATED_WORK)" CLEAR_ESTIMATED_WORK="$(CLEAR_ESTIMATED_WORK)" REMAINING_WORK="$(REMAINING_WORK)" CLEAR_REMAINING_WORK="$(CLEAR_REMAINING_WORK)" PERCENT_COMPLETE="$(PERCENT_COMPLETE)" DELIVERY_TEAM="$(DELIVERY_TEAM)" ITERATION="$(ITERATION)" ACCEPTANCE_CRITERIA="$(ACCEPTANCE_CRITERIA)" DEFINITION_OF_READY="$(DEFINITION_OF_READY)" DEFINITION_OF_DONE="$(DEFINITION_OF_DONE)" NFR_CATEGORY="$(NFR_CATEGORY)" PI_OBJECTIVE_TYPE="$(PI_OBJECTIVE_TYPE)" PLANNED_BUSINESS_VALUE="$(PLANNED_BUSINESS_VALUE)" ACTUAL_BUSINESS_VALUE="$(ACTUAL_BUSINESS_VALUE)" ROAM_STATE="$(ROAM_STATE)" RISK_OWNER="$(RISK_OWNER)" RISK_REVIEW_DATE="$(RISK_REVIEW_DATE)" RISK_DISPOSITION="$(RISK_DISPOSITION)" WSJF_USER_BUSINESS_VALUE="$(WSJF_USER_BUSINESS_VALUE)" WSJF_TIME_CRITICALITY="$(WSJF_TIME_CRITICALITY)" WSJF_RR_OE="$(WSJF_RR_OE)" WSJF_JOB_SIZE="$(WSJF_JOB_SIZE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_update_delivery_work_item.sh

.PHONY: openproject-complete-delivery-work-item
openproject-complete-delivery-work-item:
	@test -n "$(TARGET_WORK_PACKAGE_ID)" || { echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-complete-delivery-work-item TARGET_WORK_PACKAGE_ID=55 COMPLETION_SUMMARY='Implemented broker read surface' CHANGED_SURFACES='- src/app.js' TEST_RESULT_EVIDENCE='- PASS: npm test' VALIDATION_EVIDENCE='- npm test'"; exit 1; }
	TARGET_WORK_PACKAGE_ID="$(TARGET_WORK_PACKAGE_ID)" COMPLETION_SUMMARY="$(COMPLETION_SUMMARY)" COMPLETION_SUMMARY_FILE="$(COMPLETION_SUMMARY_FILE)" CHANGED_SURFACES="$(CHANGED_SURFACES)" CHANGED_SURFACES_FILE="$(CHANGED_SURFACES_FILE)" TEST_RESULT_EVIDENCE="$(TEST_RESULT_EVIDENCE)" TEST_RESULT_EVIDENCE_FILE="$(TEST_RESULT_EVIDENCE_FILE)" TEST_RESULT_ARTIFACT_FILE="$(TEST_RESULT_ARTIFACT_FILE)" TEST_RESULT_ARTIFACT_DESCRIPTION="$(TEST_RESULT_ARTIFACT_DESCRIPTION)" VALIDATION_EVIDENCE="$(VALIDATION_EVIDENCE)" VALIDATION_EVIDENCE_FILE="$(VALIDATION_EVIDENCE_FILE)" COMPLETION_NOTE="$(COMPLETION_NOTE)" COMPLETION_NOTE_FILE="$(COMPLETION_NOTE_FILE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_complete_delivery_work_item.sh

.PHONY: openproject-show-delivery-initiatives
openproject-show-delivery-initiatives:
	INCLUDE_DONE="$(INCLUDE_DONE)" INCLUDE_PARKED="$(INCLUDE_PARKED)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_show_delivery_initiatives.sh

.PHONY: openproject-check-delivery-art-quality
openproject-check-delivery-art-quality:
	INCLUDE_DONE="$(INCLUDE_DONE)" TARGET_EPIC_ID="$(TARGET_EPIC_ID)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_check_delivery_art_quality.sh

.PHONY: openproject-show-delivery-execution
openproject-show-delivery-execution:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-show-delivery-execution TARGET_EPIC_ID=38"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" INCLUDE_DONE="$(INCLUDE_DONE)" INCLUDE_PARKED="$(INCLUDE_PARKED)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_show_delivery_execution.sh

.PHONY: openproject-show-delivery-planning
openproject-show-delivery-planning:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-show-delivery-planning TARGET_EPIC_ID=38"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" INCLUDE_DONE="$(INCLUDE_DONE)" INCLUDE_PARKED="$(INCLUDE_PARKED)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_show_delivery_planning.sh

.PHONY: openproject-show-pi-objectives
openproject-show-pi-objectives:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-show-pi-objectives TARGET_EPIC_ID=38 TARGET_PI=PI-2026-02"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" TARGET_PI="$(TARGET_PI)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_show_pi_objectives.sh

.PHONY: openproject-record-pi-review
openproject-record-pi-review:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-record-pi-review TARGET_EPIC_ID=38 TARGET_PI=PI-2026-02 PI_REVIEW_FILE=/abs/path/pi-review.json"; exit 1; }
	@test -n "$(PI_REVIEW_FILE)" || { echo "PI_REVIEW_FILE is required, for example: make openproject-record-pi-review TARGET_EPIC_ID=38 TARGET_PI=PI-2026-02 PI_REVIEW_FILE=/abs/path/pi-review.json"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" TARGET_PI="$(TARGET_PI)" PI_REVIEW_DATE="$(PI_REVIEW_DATE)" PI_REVIEW_FILE="$(PI_REVIEW_FILE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_record_pi_review.sh

.PHONY: openproject-check-delivery-closeout-readiness
openproject-check-delivery-closeout-readiness:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-check-delivery-closeout-readiness TARGET_EPIC_ID=38"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_check_delivery_closeout_readiness.sh

.PHONY: openproject-manage-delivery-blocker
openproject-manage-delivery-blocker:
	@test -n "$(ACTION)" || { echo "ACTION is required, for example: make openproject-manage-delivery-blocker ACTION=set TARGET_WORK_PACKAGE_ID=40 ..."; exit 1; }
	@test -n "$(TARGET_WORK_PACKAGE_ID)" || { echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-blocker ACTION=set TARGET_WORK_PACKAGE_ID=40 ..."; exit 1; }
	ACTION="$(ACTION)" TARGET_WORK_PACKAGE_ID="$(TARGET_WORK_PACKAGE_ID)" RESUME_STATUS="$(RESUME_STATUS)" BLOCKER_STATEMENT="$(BLOCKER_STATEMENT)" BLOCKER_IMPACT="$(BLOCKER_IMPACT)" BLOCKER_OWNER="$(BLOCKER_OWNER)" BLOCKER_DISCOVERED_ON="$(BLOCKER_DISCOVERED_ON)" BLOCKER_DECISION_PATH="$(BLOCKER_DECISION_PATH)" BLOCKER_JUSTIFICATION="$(BLOCKER_JUSTIFICATION)" BLOCKER_FOLLOW_UP_OWNER="$(BLOCKER_FOLLOW_UP_OWNER)" BLOCKER_REVIEW_DATE="$(BLOCKER_REVIEW_DATE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_manage_delivery_blocker.sh

.PHONY: openproject-manage-delivery-parking
openproject-manage-delivery-parking:
	@test -n "$(ACTION)" || { echo "ACTION is required, for example: make openproject-manage-delivery-parking ACTION=park TARGET_WORK_PACKAGE_ID=43 ..."; exit 1; }
	@test -n "$(TARGET_WORK_PACKAGE_ID)" || { echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-parking ACTION=park TARGET_WORK_PACKAGE_ID=43 ..."; exit 1; }
	ACTION="$(ACTION)" TARGET_WORK_PACKAGE_ID="$(TARGET_WORK_PACKAGE_ID)" RESUME_STATUS="$(RESUME_STATUS)" PARK_DECISION="$(PARK_DECISION)" PARK_REASON="$(PARK_REASON)" PARK_REVIEW_DATE="$(PARK_REVIEW_DATE)" WORK_NOTE="$(WORK_NOTE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_manage_delivery_parking.sh

.PHONY: openproject-manage-delivery-dependency
openproject-manage-delivery-dependency:
	@test -n "$(ACTION)" || { echo "ACTION is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40"; exit 1; }
	@test -n "$(TARGET_WORK_PACKAGE_ID)" || { echo "TARGET_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40"; exit 1; }
	@test -n "$(DEPENDS_ON_WORK_PACKAGE_ID)" || { echo "DEPENDS_ON_WORK_PACKAGE_ID is required, for example: make openproject-manage-delivery-dependency ACTION=set TARGET_WORK_PACKAGE_ID=41 DEPENDS_ON_WORK_PACKAGE_ID=40"; exit 1; }
	ACTION="$(ACTION)" TARGET_WORK_PACKAGE_ID="$(TARGET_WORK_PACKAGE_ID)" DEPENDS_ON_WORK_PACKAGE_ID="$(DEPENDS_ON_WORK_PACKAGE_ID)" LAG="$(LAG)" DESCRIPTION="$(DESCRIPTION)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_manage_delivery_dependency.sh

.PHONY: openproject-consume-accepted-idea
openproject-consume-accepted-idea:
	@test -n "$(IDEA_ID)" || { echo "IDEA_ID is required, for example: make openproject-consume-accepted-idea IDEA_ID=idea-64 TARGET_PI=PI-2026-02 OPERATOR_ID=mfshaf7 OPERATOR_HANDLE=mfshaf7"; exit 1; }
	IDEA_ID="$(IDEA_ID)" TARGET_PI="$(TARGET_PI)" OPERATOR_ID="$(OPERATOR_ID)" OPERATOR_HANDLE="$(OPERATOR_HANDLE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DEPLOYMENT="$(OPENPROJECT_DEPLOYMENT)" \
	./products/openproject/scripts/openproject_consume_accepted_idea.sh

.PHONY: openproject-apply-delivery-plan
openproject-apply-delivery-plan:
	@test -n "$(TARGET_EPIC_ID)" || { echo "TARGET_EPIC_ID is required, for example: make openproject-apply-delivery-plan TARGET_EPIC_ID=38 DELIVERY_PLAN_FILE=/abs/path/delivery-plan.json"; exit 1; }
	@test -n "$(DELIVERY_PLAN_FILE)" || { echo "DELIVERY_PLAN_FILE is required, for example: make openproject-apply-delivery-plan TARGET_EPIC_ID=38 DELIVERY_PLAN_FILE=/abs/path/delivery-plan.json"; exit 1; }
	TARGET_EPIC_ID="$(TARGET_EPIC_ID)" DELIVERY_PLAN_FILE="$(DELIVERY_PLAN_FILE)" RECONCILE_MISSING="$(RECONCILE_MISSING)" RECONCILE_DECISION="$(RECONCILE_DECISION)" RECONCILE_REASON="$(RECONCILE_REASON)" RECONCILE_REVIEW_DATE="$(RECONCILE_REVIEW_DATE)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_apply_delivery_plan.sh

.PHONY: openproject-close-delivery-initiative
openproject-close-delivery-initiative:
	@test -n "$(IDEA_ID)" || { echo "IDEA_ID is required, for example: make openproject-close-delivery-initiative IDEA_ID=idea-37 CLOSEOUT_NOTES='Delivered through PI-2026-02' OPERATOR_ID=mfshaf7 OPERATOR_HANDLE=mfshaf7"; exit 1; }
	@test -n "$(CLOSEOUT_NOTES)" || { echo "CLOSEOUT_NOTES is required, for example: make openproject-close-delivery-initiative IDEA_ID=idea-37 CLOSEOUT_NOTES='Delivered through PI-2026-02' OPERATOR_ID=mfshaf7 OPERATOR_HANDLE=mfshaf7"; exit 1; }
	IDEA_ID="$(IDEA_ID)" CLOSEOUT_NOTES="$(CLOSEOUT_NOTES)" OPERATOR_ID="$(OPERATOR_ID)" OPERATOR_HANDLE="$(OPERATOR_HANDLE)" BROKER_NAMESPACE="$(BROKER_NAMESPACE)" BROKER_DEPLOYMENT="$(BROKER_DEPLOYMENT)" BROKER_PORT="$(BROKER_PORT)" OPENPROJECT_NAMESPACE="$(OPENPROJECT_NAMESPACE)" OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER="$(OPENPROJECT_DELIVERY_PROJECT_IDENTIFIER)" \
	./products/openproject/scripts/openproject_close_delivery_initiative.sh

.PHONY: openproject-verify-clean-start
openproject-verify-clean-start:
	REQUIRE_EMPTY="$(REQUIRE_EMPTY)" ./products/openproject/scripts/openproject_verify_clean_start.sh

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

.PHONY: devint-access
devint-access:
	@test -n "$(PROFILE)" || { echo "PROFILE is required, for example: make devint-access PROFILE=accepted-idea-delivery"; exit 1; }
	python3 scripts/dev_integration.py access --profile $(PROFILE) $(if $(OPERATOR),--operator $(OPERATOR),) $(if $(EXTRA_ARGS),$(EXTRA_ARGS),)

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
