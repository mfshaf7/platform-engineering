variable "vm_name" {
  type = string
}

variable "vm_cpu" {
  type = number
}

variable "vm_memory_mb" {
  type = number
}

resource "local_file" "isolated_vm_plan" {
  filename = "${path.module}/generated-${var.vm_name}.txt"
  content  = <<-EOT
  vm_name=${var.vm_name}
  vm_cpu=${var.vm_cpu}
  vm_memory_mb=${var.vm_memory_mb}
  EOT
}

output "vm_name" {
  value = var.vm_name
}
