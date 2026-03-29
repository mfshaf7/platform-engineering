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
  platform_name = var.cluster_name
}

module "isolated_vm" {
  source = "../../modules/isolated_vm"

  vm_name      = var.vm_name
  vm_provider  = var.vm_provider
  vm_os_image  = var.vm_os_image
  vm_cpu       = var.vm_cpu
  vm_memory_mb = var.vm_memory_mb
  vm_disk_gb   = var.vm_disk_gb
}

module "k3s_bootstrap" {
  source = "../../modules/k3s_bootstrap"

  cluster_name             = local.platform_name
  argocd_namespace         = var.argocd_namespace
  openclaw_namespace       = var.openclaw_namespace
  observability_namespace  = var.observability_namespace
  github_repo_url          = var.github_repo_url
  github_repo_ref          = var.github_repo_ref
  gateway_image_repository = var.gateway_image_repository
  gateway_image_tag        = var.gateway_image_tag
  host_bridge_wsl_distro   = var.host_bridge_wsl_distro
  host_bridge_root         = var.host_bridge_root
  host_bridge_policy_path  = var.host_bridge_policy_path
  openclaw_config_path     = var.openclaw_config_path
}
