output "catalog_backup_bucket" {
  value = aws_s3_bucket.catalog_backup.bucket
}

output "catalog_backup_role_arn" {
  value = aws_iam_role.catalog_backup.arn
}

output "iceberg_recovery_bucket" {
  value = aws_s3_bucket.iceberg_recovery.bucket
}

output "iceberg_recovery_reader_role_arn" {
  value = aws_iam_role.iceberg_recovery_reader.arn
}

output "aws_profile" {
  value = var.aws_profile
}
