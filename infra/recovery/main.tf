locals {
  warehouse_prefix = trim(var.warehouse_prefix, "/")
  warehouse_arn    = "arn:aws:s3:::${var.primary_iceberg_bucket}/${local.warehouse_prefix}/*"
}

check "distinct_bucket_names" {
  assert {
    condition = length(distinct([
      var.primary_iceberg_bucket,
      var.catalog_backup_bucket,
      var.iceberg_recovery_bucket,
    ])) == 3
    error_message = "Primary, catalog-backup, and Iceberg-recovery buckets must be distinct."
  }
}

resource "aws_s3_bucket" "catalog_backup" {
  bucket = var.catalog_backup_bucket
}

resource "aws_s3_bucket" "iceberg_recovery" {
  bucket = var.iceberg_recovery_bucket
}

resource "aws_s3_bucket_versioning" "catalog_backup" {
  bucket = aws_s3_bucket.catalog_backup.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "iceberg_recovery" {
  bucket = aws_s3_bucket.iceberg_recovery.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "catalog_backup" {
  bucket = aws_s3_bucket.catalog_backup.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "iceberg_recovery" {
  bucket = aws_s3_bucket.iceberg_recovery.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "catalog_backup" {
  bucket                  = aws_s3_bucket.catalog_backup.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "iceberg_recovery" {
  bucket                  = aws_s3_bucket.iceberg_recovery.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "catalog_backup" {
  bucket = aws_s3_bucket.catalog_backup.id
  rule {
    id     = "retain-deleted-backup-versions-30-days"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  depends_on = [aws_s3_bucket_versioning.catalog_backup]
}

resource "aws_s3_bucket_lifecycle_configuration" "iceberg_recovery" {
  bucket = aws_s3_bucket.iceberg_recovery.id
  rule {
    id     = "retain-noncurrent-iceberg-versions-45-days"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 45
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  depends_on = [aws_s3_bucket_versioning.iceberg_recovery]
}

data "aws_iam_policy_document" "operator_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.operator_principal_arn]
    }
  }
}

resource "aws_iam_role" "catalog_backup" {
  name               = "databox-polaris-catalog-backup"
  assume_role_policy = data.aws_iam_policy_document.operator_assume.json
}

resource "aws_iam_role_policy" "catalog_backup" {
  role = aws_iam_role.catalog_backup.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetBucketLocation", "s3:ListBucket"], Resource = aws_s3_bucket.catalog_backup.arn },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${aws_s3_bucket.catalog_backup.arn}/*" },
    ]
  })
}

resource "aws_iam_role" "iceberg_recovery_reader" {
  name               = "databox-iceberg-recovery-reader"
  assume_role_policy = data.aws_iam_policy_document.operator_assume.json
}

resource "aws_iam_role_policy" "iceberg_recovery_reader" {
  role = aws_iam_role.iceberg_recovery_reader.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketVersions"], Resource = aws_s3_bucket.iceberg_recovery.arn },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = "${aws_s3_bucket.iceberg_recovery.arn}/*" },
    ]
  })
}

resource "aws_iam_role" "iceberg_replication" {
  name = "databox-iceberg-replication"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "s3.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "iceberg_replication" {
  role = aws_iam_role.iceberg_replication.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetReplicationConfiguration", "s3:ListBucket"], Resource = "arn:aws:s3:::${var.primary_iceberg_bucket}" },
      { Effect = "Allow", Action = ["s3:GetObjectVersionForReplication", "s3:GetObjectVersionAcl", "s3:GetObjectVersionTagging"], Resource = local.warehouse_arn },
      { Effect = "Allow", Action = ["s3:ReplicateObject", "s3:ReplicateTags"], Resource = "${aws_s3_bucket.iceberg_recovery.arn}/*" },
    ]
  })
}

resource "aws_s3_bucket_replication_configuration" "iceberg" {
  bucket = var.primary_iceberg_bucket
  role   = aws_iam_role.iceberg_replication.arn

  rule {
    id       = "databox-warehouse-recovery"
    priority = 1
    status   = "Enabled"
    filter {
      prefix = "${local.warehouse_prefix}/"
    }
    delete_marker_replication {
      status = "Disabled"
    }
    destination {
      bucket        = aws_s3_bucket.iceberg_recovery.arn
      storage_class = "STANDARD_IA"
    }
  }
  depends_on = [aws_s3_bucket_versioning.iceberg_recovery]
}

data "aws_iam_policy_document" "iceberg_recovery_bucket" {
  statement {
    sid       = "DenyRoutineWriterDeletes"
    effect    = "Deny"
    actions   = ["s3:DeleteObject", "s3:DeleteObjectVersion"]
    resources = ["${aws_s3_bucket.iceberg_recovery.arn}/*"]
    principals {
      type        = "AWS"
      identifiers = [var.routine_writer_principal_arn]
    }
  }
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.iceberg_recovery.arn, "${aws_s3_bucket.iceberg_recovery.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "iceberg_recovery" {
  bucket = aws_s3_bucket.iceberg_recovery.id
  policy = data.aws_iam_policy_document.iceberg_recovery_bucket.json
}
