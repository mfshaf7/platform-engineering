variable "cluster_name" {
  type = string
}

variable "argocd_namespace" {
  type = string
}

variable "openclaw_namespace" {
  type = string
}

variable "observability_namespace" {
  type = string
}

variable "github_repo_url" {
  type = string
}

variable "github_repo_ref" {
  type = string
}

variable "gateway_image_repository" {
  type = string
}

variable "gateway_image_tag" {
  type = string
}

variable "host_bridge_wsl_distro" {
  type = string
}

variable "host_bridge_root" {
  type = string
}

variable "host_bridge_policy_path" {
  type = string
}

variable "openclaw_config_path" {
  type = string
}

resource "local_file" "bootstrap_plan" {
  filename = "${path.module}/generated-${var.cluster_name}.txt"
  content  = <<-EOT
  cluster_name=${var.cluster_name}
  argocd_namespace=${var.argocd_namespace}
  openclaw_namespace=${var.openclaw_namespace}
  observability_namespace=${var.observability_namespace}
  github_repo_url=${var.github_repo_url}
  github_repo_ref=${var.github_repo_ref}
  gateway_image_repository=${var.gateway_image_repository}
  gateway_image_tag=${var.gateway_image_tag}
  host_bridge_wsl_distro=${var.host_bridge_wsl_distro}
  host_bridge_root=${var.host_bridge_root}
  host_bridge_policy_path=${var.host_bridge_policy_path}
  openclaw_config_path=${var.openclaw_config_path}
  EOT
}

resource "local_file" "bootstrap_contract" {
  filename = "${path.module}/generated-${var.cluster_name}.json"
  content = jsonencode({
    cluster = {
      name                    = var.cluster_name
      argocd_namespace        = var.argocd_namespace
      openclaw_namespace      = var.openclaw_namespace
      observability_namespace = var.observability_namespace
    }
    gitops = {
      repo_url = var.github_repo_url
      repo_ref = var.github_repo_ref
    }
    runtime = {
      gateway_image_repository = var.gateway_image_repository
      gateway_image_tag        = var.gateway_image_tag
    }
    host_integration = {
      wsl_distro         = var.host_bridge_wsl_distro
      host_bridge_root   = var.host_bridge_root
      host_bridge_policy = var.host_bridge_policy_path
      openclaw_config    = var.openclaw_config_path
    }
  })
}

output "github_repo_url" {
  value = var.github_repo_url
}

output "bootstrap_contract_path" {
  value = local_file.bootstrap_contract.filename
}
