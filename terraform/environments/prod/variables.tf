variable "vm_name" {
  type    = string
  default = "openclaw-prod"
}

variable "vm_provider" {
  type    = string
  default = "manual"
}

variable "vm_os_image" {
  type    = string
  default = "ubuntu-24.04"
}

variable "vm_cpu" {
  type    = number
  default = 8
}

variable "vm_memory_mb" {
  type    = number
  default = 16384
}

variable "vm_disk_gb" {
  type    = number
  default = 160
}

variable "cluster_name" {
  type    = string
  default = "openclaw-prod"
}

variable "argocd_namespace" {
  type    = string
  default = "argocd"
}

variable "openclaw_namespace" {
  type    = string
  default = "openclaw"
}

variable "observability_namespace" {
  type    = string
  default = "observability"
}

variable "github_repo_url" {
  type    = string
  default = "https://github.com/mfshaf7/platform-engineering.git"
}

variable "github_repo_ref" {
  type    = string
  default = "main"
}

variable "gateway_image_repository" {
  type    = string
  default = "ghcr.io/mfshaf7/openclaw-gateway"
}

variable "gateway_image_tag" {
  type    = string
  default = "replace-me"
}

variable "host_bridge_wsl_distro" {
  type    = string
  default = "Ubuntu"
}

variable "host_bridge_root" {
  type    = string
  default = "/opt/openclaw-host-bridge"
}

variable "host_bridge_policy_path" {
  type    = string
  default = "/opt/openclaw-host-bridge/config/policy.local.json"
}

variable "openclaw_config_path" {
  type    = string
  default = "/root/.openclaw/openclaw.json"
}
