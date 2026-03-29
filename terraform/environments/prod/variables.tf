variable "vm_name" {
  type    = string
  default = "openclaw-prod"
}

variable "vm_cpu" {
  type    = number
  default = 8
}

variable "vm_memory_mb" {
  type    = number
  default = 16384
}

variable "argocd_namespace" {
  type    = string
  default = "argocd"
}

variable "github_repo_url" {
  type    = string
  default = "https://github.com/mfshaf7/platform-engineering.git"
}

variable "github_repo_ref" {
  type    = string
  default = "main"
}
