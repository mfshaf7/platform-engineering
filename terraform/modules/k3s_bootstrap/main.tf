variable "cluster_name" {
  type = string
}

variable "argocd_namespace" {
  type = string
}

variable "github_repo_url" {
  type = string
}

variable "github_repo_ref" {
  type = string
}

resource "local_file" "bootstrap_plan" {
  filename = "${path.module}/generated-${var.cluster_name}.txt"
  content  = <<-EOT
  cluster_name=${var.cluster_name}
  argocd_namespace=${var.argocd_namespace}
  github_repo_url=${var.github_repo_url}
  github_repo_ref=${var.github_repo_ref}
  EOT
}

output "github_repo_url" {
  value = var.github_repo_url
}
