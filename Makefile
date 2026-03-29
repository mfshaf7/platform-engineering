SHELL := /bin/bash

.PHONY: help
help:
	@printf "Available targets:\n"
	@printf "  validate           Run repo validation checks\n"
	@printf "  show-prod-versions Show current prod version pins\n"
	@printf "  show-stage-versions Show current stage version pins\n"

.PHONY: validate
validate:
	helm lint charts/openclaw-gateway
	helm lint charts/openclaw-platform-version
	terraform -chdir=terraform/environments/prod fmt -check
	terraform -chdir=terraform/environments/prod init -backend=false
	terraform -chdir=terraform/environments/prod validate

.PHONY: show-prod-versions
show-prod-versions:
	cat environments/prod/versions.yaml

.PHONY: show-stage-versions
show-stage-versions:
	cat environments/stage/versions.yaml
