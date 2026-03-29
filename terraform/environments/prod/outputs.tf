output "vm_name" {
  value = module.isolated_vm.vm_name
}

output "argocd_bootstrap_repo" {
  value = module.k3s_bootstrap.github_repo_url
}

output "bootstrap_contract_path" {
  value = module.k3s_bootstrap.bootstrap_contract_path
}
