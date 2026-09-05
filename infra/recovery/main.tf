resource "aws_s3_bucket" "catalog_backup" {
  bucket = var.catalog_backup_bucket
}

resource "aws_s3_bucket_versioning" "catalog_backup" {
  bucket = aws_s3_bucket.catalog_backup.id
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

resource "aws_s3_bucket_public_access_block" "catalog_backup" {
  bucket                  = aws_s3_bucket.catalog_backup.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "catalog_backup" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.catalog_backup.arn, "${aws_s3_bucket.catalog_backup.arn}/*"]
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

resource "aws_s3_bucket_policy" "catalog_backup" {
  bucket = aws_s3_bucket.catalog_backup.id
  policy = data.aws_iam_policy_document.catalog_backup.json
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
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"], Resource = "${aws_s3_bucket.catalog_backup.arn}/*" },
    ]
  })
}
