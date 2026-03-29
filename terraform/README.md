# Terraform

Terraform in this repo owns platform bootstrap inputs and environment metadata.

It does not replace host configuration management. Host configuration stays in
Ansible.

Current module boundaries:

- `modules/isolated_vm`
- `modules/k3s_bootstrap`

Current environment:

- `environments/prod`

The modules are deliberately conservative scaffolding for now. Replace the
placeholder `local_file` resources with the actual virtualization or cloud
provider resources when the environment contract is finalized.
