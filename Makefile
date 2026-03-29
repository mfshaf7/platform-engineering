SHELL := /bin/bash

.PHONY: validate
validate:
	helm lint charts/openclaw-gateway
	helm lint charts/openclaw-platform-version
	terraform -chdir=terraform/environments/prod fmt -check
	terraform -chdir=terraform/environments/prod init -backend=false
	terraform -chdir=terraform/environments/prod validate
