terraform {
  required_version = ">= 1.8.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

locals {
  platform_name = "openclaw-prod"
}

module "isolated_vm" {
  source = "../../modules/isolated_vm"

  vm_name      = var.vm_name
  vm_cpu       = var.vm_cpu
  vm_memory_mb = var.vm_memory_mb
}

module "k3s_bootstrap" {
  source = "../../modules/k3s_bootstrap"

  cluster_name      = local.platform_name
  argocd_namespace  = var.argocd_namespace
  github_repo_url   = var.github_repo_url
  github_repo_ref   = var.github_repo_ref
}
