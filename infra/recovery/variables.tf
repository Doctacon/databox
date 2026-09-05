variable "aws_account_id" {
  description = "Existing AWS account that owns the primary and recovery buckets."
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

variable "primary_iceberg_bucket" {
  description = "Existing authoritative Iceberg warehouse bucket."
  type        = string
}

variable "warehouse_prefix" {
  description = "Existing authoritative Iceberg warehouse prefix."
  type        = string
  default     = "warehouse"
  validation {
    condition     = length(trim(var.warehouse_prefix, "/")) > 0
    error_message = "warehouse_prefix must not be empty."
  }
}

variable "catalog_backup_bucket" {
  description = "Globally unique bucket name for encrypted pgBackRest backups and WAL."
  type        = string
}

variable "iceberg_recovery_bucket" {
  description = "Globally unique bucket name for retained Iceberg object versions."
  type        = string
}

variable "operator_principal_arn" {
  description = "Principal allowed to assume backup and recovery operator roles."
  type        = string
}

variable "routine_writer_principal_arn" {
  description = "Normal Iceberg writer explicitly denied destructive recovery-bucket access."
  type        = string
}
