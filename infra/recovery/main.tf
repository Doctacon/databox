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

  statement {
    sid    = "AllowRuntimeBackupBucketAccess"
    effect = "Allow"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.catalog_backup.arn]
    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::${var.aws_account_id}:user/databox-lake-user",
        var.warehouse_runtime_role_arn,
      ]
    }
  }

  statement {
    sid    = "AllowRuntimeBackupObjectAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${aws_s3_bucket.catalog_backup.arn}/*"]
    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::${var.aws_account_id}:user/databox-lake-user",
        var.warehouse_runtime_role_arn,
      ]
    }
  }

  statement {
    sid       = "DenyNonRootVersionDeletion"
    effect    = "Deny"
    actions   = ["s3:DeleteObjectVersion"]
    resources = ["${aws_s3_bucket.catalog_backup.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = ["arn:aws:iam::${var.aws_account_id}:root"]
    }
  }

  statement {
    sid    = "DenyNonRootProtectionChanges"
    effect = "Deny"
    actions = [
      "s3:PutBucketVersioning",
      "s3:PutLifecycleConfiguration",
      "s3:PutBucketPolicy",
      "s3:DeleteBucketPolicy",
    ]
    resources = [aws_s3_bucket.catalog_backup.arn]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = ["arn:aws:iam::${var.aws_account_id}:root"]
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

data "aws_caller_identity" "current" {}

data "aws_s3_bucket" "warehouse" {
  bucket = var.warehouse_bucket

  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.arn == "arn:aws:iam::${var.aws_account_id}:root"
      error_message = "Warehouse protection planning and apply require the exact account-root principal."
    }

    precondition {
      condition     = var.warehouse_bucket != var.catalog_backup_bucket
      error_message = "warehouse_bucket must differ from catalog_backup_bucket."
    }

    precondition {
      condition = startswith(
        var.warehouse_runtime_role_arn,
        "arn:aws:iam::${var.aws_account_id}:role/",
      )
      error_message = "warehouse_runtime_role_arn must belong to aws_account_id."
    }
  }
}

data "aws_iam_policy_document" "warehouse" {
  statement {
    sid       = "DenyNonRootVersionDeletion"
    effect    = "Deny"
    actions   = ["s3:DeleteObjectVersion"]
    resources = ["${data.aws_s3_bucket.warehouse.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = ["arn:aws:iam::${var.aws_account_id}:root"]
    }
  }

  statement {
    sid    = "DenyNonRootProtectionChanges"
    effect = "Deny"
    actions = [
      "s3:PutBucketVersioning",
      "s3:PutLifecycleConfiguration",
      "s3:PutBucketPolicy",
      "s3:DeleteBucketPolicy",
    ]
    resources = [data.aws_s3_bucket.warehouse.arn]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = ["arn:aws:iam::${var.aws_account_id}:root"]
    }
  }
}

resource "aws_s3_bucket_policy" "warehouse" {
  bucket = data.aws_s3_bucket.warehouse.id
  policy = data.aws_iam_policy_document.warehouse.json
}

resource "aws_s3_bucket_versioning" "warehouse" {
  bucket = data.aws_s3_bucket.warehouse.id

  versioning_configuration {
    status = "Enabled"
  }

  depends_on = [aws_s3_bucket_policy.warehouse]
}

resource "aws_s3_bucket_lifecycle_configuration" "warehouse" {
  bucket = data.aws_s3_bucket.warehouse.id

  rule {
    id     = "expire-noncurrent-object-versions-after-30-days"
    status = "Enabled"
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  depends_on = [aws_s3_bucket_versioning.warehouse]
}

resource "aws_iam_user" "recovery_operator" {
  name          = "databox-recovery-operator"
  force_destroy = false
}

data "aws_iam_policy_document" "operator_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_user.recovery_operator.arn]
    }
    condition {
      test     = "Bool"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["true"]
    }
  }
}

resource "aws_iam_role" "catalog_backup" {
  name               = "databox-polaris-catalog-backup"
  assume_role_policy = data.aws_iam_policy_document.operator_assume.json
}

resource "aws_iam_role" "warehouse_recovery_storage" {
  name                 = "databox-warehouse-recovery-storage"
  assume_role_policy   = data.aws_iam_policy_document.operator_assume.json
  max_session_duration = 3600
}

resource "aws_iam_user_policy" "recovery_operator" {
  user = aws_iam_user.recovery_operator.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sts:AssumeRole"]
        Resource = aws_iam_role.catalog_backup.arn
      },
      {
        Effect = "Allow"
        Action = [
          "signin:AuthorizeOAuth2Access",
          "signin:CreateOAuth2Token",
        ]
        Resource = "arn:aws:signin:us-west-1:${var.aws_account_id}:oauth2/public-client/remote"
      },
    ]
  })
}

resource "aws_iam_user_policy" "warehouse_recovery_storage_assume" {
  name = "databox-warehouse-recovery-storage-assume"
  user = aws_iam_user.recovery_operator.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AssumeDedicatedStage1StorageRole"
        Effect   = "Allow"
        Action   = ["sts:AssumeRole"]
        Resource = "arn:aws:iam::${var.aws_account_id}:role/databox-warehouse-recovery-storage"
      },
    ]
  })

  depends_on = [aws_iam_role.warehouse_recovery_storage]
}

resource "aws_iam_user_policy" "warehouse_writer_inspection" {
  name = "databox-warehouse-writer-inspection"
  user = aws_iam_user.recovery_operator.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InspectOnlyWarehouseWriter"
        Effect = "Allow"
        Action = [
          "iam:GetUser",
          "iam:ListUserPolicies",
          "iam:GetUserPolicy",
          "iam:ListAttachedUserPolicies",
          "iam:ListGroupsForUser",
        ]
        Resource = "arn:aws:iam::${var.aws_account_id}:user/databox-lake-user"
      },
    ]
  })
}

resource "aws_iam_user_policy" "warehouse_recovery_drill" {
  name = "databox-warehouse-recovery-drill"
  user = aws_iam_user.recovery_operator.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InspectWarehouseProtection"
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning",
          "s3:GetLifecycleConfiguration",
          "s3:GetBucketPolicy",
        ]
        Resource = data.aws_s3_bucket.warehouse.arn
      },
      {
        Sid      = "ListStage1ObjectVersions"
        Effect   = "Allow"
        Action   = ["s3:ListBucketVersions"]
        Resource = data.aws_s3_bucket.warehouse.arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["integration/recovery/????????????????/stage1/warehouse/*"]
          }
          NumericLessThanEquals = {
            "s3:max-keys" = "1000"
          }
        }
      },
      {
        Sid    = "OperateStage1FixtureOnly"
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersion",
          "s3:PutObject",
          "s3:DeleteObject",
        ]
        Resource = join("", [
          data.aws_s3_bucket.warehouse.arn,
          "/integration/recovery/????????????????/stage1/warehouse/*",
        ])
      },
    ]
  })
}

resource "aws_iam_role_policy" "warehouse_recovery_storage" {
  name = "databox-warehouse-recovery-storage-stage1"
  role = aws_iam_role.warehouse_recovery_storage.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadStage1WarehouseLocation"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = data.aws_s3_bucket.warehouse.arn
      },
      {
        Sid      = "ListStage1WarehousePrefix"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = data.aws_s3_bucket.warehouse.arn
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "integration/recovery/????????????????/stage1/warehouse/*",
            ]
          }
        }
      },
      {
        Sid    = "OperateStage1WarehouseObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
        ]
        Resource = join("", [
          data.aws_s3_bucket.warehouse.arn,
          "/integration/recovery/????????????????/stage1/warehouse/*",
        ])
      },
    ]
  })
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
