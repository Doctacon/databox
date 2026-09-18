variable "aws_account_id" {
  description = "AWS account that owns the catalog backup and warehouse recovery resources."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit AWS account ID."
  }
}

variable "aws_region" {
  description = "Ratified same-region deployment location."
  type        = string
  default     = "us-west-1"
  validation {
    condition     = var.aws_region == "us-west-1"
    error_message = "Recovery infrastructure is approved only for us-west-1."
  }
}

variable "aws_profile" {
  description = "AWS shared-config profile backed by renewable credentials."
  type        = string
}

variable "aws_shared_config_files" {
  description = "Shared AWS config files used by OpenTofu on the host."
  type        = list(string)
  default     = ["~/.aws/config"]
}

variable "catalog_backup_bucket" {
  description = "Globally unique bucket name for encrypted pgBackRest backups and WAL."
  type        = string
}

variable "warehouse_runtime_role_arn" {
  description = "Existing warehouse runtime role that also needs pgBackRest repository access in CI."
  type        = string

  validation {
    condition = can(regex(
      "^arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+$",
      var.warehouse_runtime_role_arn,
    ))
    error_message = "warehouse_runtime_role_arn must be an IAM role ARN."
  }
}

variable "warehouse_bucket" {
  description = "Existing warehouse bucket protected by root-only retention controls."
  type        = string

  validation {
    condition     = length(trimspace(var.warehouse_bucket)) > 0
    error_message = "warehouse_bucket must not be empty."
  }
}
