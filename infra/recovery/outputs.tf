output "catalog_backup_bucket" {
  value = aws_s3_bucket.catalog_backup.bucket
}

output "catalog_backup_role_arn" {
  value = aws_iam_role.catalog_backup.arn
}

output "recovery_operator_user_arn" {
  value = aws_iam_user.recovery_operator.arn
}

output "aws_profile" {
  value = var.aws_profile
}
