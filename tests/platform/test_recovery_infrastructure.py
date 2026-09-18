"""Static contracts for catalog recovery and bounded writer IAM inspection."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
INFRA = ROOT / "infra" / "recovery"


def _text(name: str) -> str:
    return (INFRA / name).read_text()


def _block(text: str, declaration: str) -> str:
    start = text.find(declaration)
    assert start >= 0, f"missing block: {declaration}"
    opening_brace = text.find("{", start + len(declaration))
    assert opening_brace >= 0
    depth = 0
    for index in range(opening_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unterminated block: {declaration}")


def _tokens(text: str) -> list[str]:
    """Ignore HCL formatting while preserving quoted strings and structure."""
    return re.findall(r'"(?:\\.|[^"\\])*"|[^\s"]', text)


def _assert_block_tokens(text: str, declaration: str, expected: str) -> None:
    assert _tokens(_block(text, declaration)) == _tokens(expected)


def test_opentofu_is_bounded_and_same_region() -> None:
    versions = _text("versions.tf")
    variables = _text("variables.tf")
    assert 'required_version = ">= 1.8.0, < 2.0.0"' in versions
    assert 'version = ">= 5.80.0, < 7.0.0"' in versions
    assert 'default     = "us-west-1"' in variables
    assert 'var.aws_region == "us-west-1"' in variables
    assert "credential_process_command" not in variables
    assert "aws_account_id" in variables


def test_catalog_backup_bucket_is_protected_for_thirty_days() -> None:
    main = _text("main.tf")
    versioning = _block(main, 'resource "aws_s3_bucket_versioning" "catalog_backup"')
    lifecycle = _block(
        main,
        'resource "aws_s3_bucket_lifecycle_configuration" "catalog_backup"',
    )
    public_access = _block(main, 'resource "aws_s3_bucket_public_access_block" "catalog_backup"')
    encryption = _block(
        main,
        'resource "aws_s3_bucket_server_side_encryption_configuration" "catalog_backup"',
    )
    assert 'status = "Enabled"' in versioning
    assert "noncurrent_days = 30" in lifecycle
    assert "block_public_acls       = true" in public_access
    assert 'sse_algorithm = "AES256"' in encryption


def test_catalog_backup_bucket_denies_insecure_transport() -> None:
    main = _text("main.tf")
    assert 'data "aws_iam_policy_document" "catalog_backup"' in main
    assert 'resource "aws_s3_bucket_policy" "catalog_backup"' in main
    assert 'sid       = "DenyInsecureTransport"' in main
    assert 'effect    = "Deny"' in main
    assert 'actions   = ["s3:*"]' in main
    resources = (
        'resources = [aws_s3_bucket.catalog_backup.arn, "${aws_s3_bucket.catalog_backup.arn}/*"]'
    )
    assert resources in main
    assert 'variable = "aws:SecureTransport"' in main
    assert 'values   = ["false"]' in main


def test_catalog_backup_bucket_grants_runtime_and_protects_versions() -> None:
    main = _text("main.tf")
    variables = _text("variables.tf")
    assert 'variable "warehouse_runtime_role_arn"' in variables
    assert 'sid    = "AllowRuntimeBackupBucketAccess"' in main
    assert 'sid    = "AllowRuntimeBackupObjectAccess"' in main
    assert '"arn:aws:iam::${var.aws_account_id}:user/databox-lake-user"' in main
    assert "var.warehouse_runtime_role_arn" in main
    assert 'sid       = "DenyNonRootVersionDeletion"' in main
    assert 'actions   = ["s3:DeleteObjectVersion"]' in main
    assert 'sid    = "DenyNonRootProtectionChanges"' in main


def test_only_catalog_backup_permissions_remain() -> None:
    main = _text("main.tf")
    outputs = _text("outputs.tf")
    assert 'resource "aws_iam_role" "catalog_backup"' in main
    catalog_role_policy = _block(main, 'resource "aws_iam_role_policy" "catalog_backup"')
    assert "s3:GetBucketLocation" in catalog_role_policy
    assert "s3:ListBucket" in catalog_role_policy
    assert "s3:GetObject" in catalog_role_policy
    assert "s3:PutObject" in catalog_role_policy
    assert "s3:DeleteObject" in catalog_role_policy
    assert "s3:AbortMultipartUpload" in catalog_role_policy
    assert "s3:GetObjectVersion" not in catalog_role_policy
    assert "s3:DeleteObjectVersion" not in catalog_role_policy
    assert "iceberg" not in main.lower()
    assert "replication" not in main.lower()
    assert "primary" not in main.lower()
    assert "iceberg_recovery" not in outputs.lower()


def test_recovery_operator_preserves_remote_login_and_backup_role_access() -> None:
    main = _text("main.tf")
    outputs = _text("outputs.tf")
    assert 'resource "aws_iam_user" "recovery_operator"' in main
    assert 'name          = "databox-recovery-operator"' in main
    assert "force_destroy = false" in main
    assert 'resource "aws_iam_user_policy" "recovery_operator"' in main
    assert 'Action   = ["sts:AssumeRole"]' in main
    assert "Resource = aws_iam_role.catalog_backup.arn" in main
    assert '"signin:AuthorizeOAuth2Access"' in main
    assert '"signin:CreateOAuth2Token"' in main
    signin_resource = (
        'Resource = "arn:aws:signin:us-west-1:${var.aws_account_id}:oauth2/public-client/remote"'
    )
    assert signin_resource in main
    assert "oauth2/public-client/*" not in main
    assert "oauth2/public-client/localhost" not in main
    assert "identifiers = [aws_iam_user.recovery_operator.arn]" in main
    assert 'variable = "aws:MultiFactorAuthPresent"' in main
    assert 'values   = ["true"]' in main
    assert 'output "recovery_operator_user_arn"' in outputs
    assert "aws_iam_access_key" not in main
    assert "aws_iam_user_login_profile" not in main
    assert "operator_principal_arn" not in main


def test_recovery_operator_has_exact_stage1_warehouse_permissions() -> None:
    main = _text("main.tf")
    expected = """resource "aws_iam_user_policy" "warehouse_recovery_drill" {
      name = "databox-warehouse-recovery-drill"
      user = aws_iam_user.recovery_operator.name
      policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
          {
            Sid = "InspectWarehouseProtection"
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
            Sid = "ListStage1ObjectVersions"
            Effect = "Allow"
            Action = ["s3:ListBucketVersions"]
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
            Sid = "OperateStage1FixtureOnly"
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
    }"""
    policy = _block(main, 'resource "aws_iam_user_policy" "warehouse_recovery_drill"')
    assert _tokens(policy) == _tokens(expected)
    assert 's3:GetObject"' not in policy
    assert "s3:DeleteObjectVersion" not in policy
    assert "s3:PutBucket" not in policy
    assert "s3:DeleteBucket" not in policy
    assert "s3:*" not in policy
    assert 'Resource = "${data.aws_s3_bucket.warehouse.arn}/warehouse/*"' not in policy
    assert 'Resource = "${data.aws_s3_bucket.warehouse.arn}/integration/*"' not in policy
    assert 'Resource = "${data.aws_s3_bucket.warehouse.arn}/*"' not in policy


def test_dedicated_stage1_storage_role_is_exactly_scoped() -> None:
    main = _text("main.tf")
    outputs = _text("outputs.tf")
    role = """resource "aws_iam_role" "warehouse_recovery_storage" {
      name = "databox-warehouse-recovery-storage"
      assume_role_policy = data.aws_iam_policy_document.operator_assume.json
      max_session_duration = 3600
    }"""
    assume = """resource "aws_iam_user_policy" "warehouse_recovery_storage_assume" {
      name = "databox-warehouse-recovery-storage-assume"
      user = aws_iam_user.recovery_operator.name
      policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
          {
            Sid = "AssumeDedicatedStage1StorageRole"
            Effect = "Allow"
            Action = ["sts:AssumeRole"]
            Resource = "arn:aws:iam::${var.aws_account_id}:role/databox-warehouse-recovery-storage"
          },
        ]
      })
      depends_on = [aws_iam_role.warehouse_recovery_storage]
    }"""
    policy = """resource "aws_iam_role_policy" "warehouse_recovery_storage" {
      name = "databox-warehouse-recovery-storage-stage1"
      role = aws_iam_role.warehouse_recovery_storage.id
      policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
          {
            Sid = "ReadStage1WarehouseLocation"
            Effect = "Allow"
            Action = ["s3:GetBucketLocation"]
            Resource = data.aws_s3_bucket.warehouse.arn
          },
          {
            Sid = "ListStage1WarehousePrefix"
            Effect = "Allow"
            Action = ["s3:ListBucket"]
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
            Sid = "OperateStage1WarehouseObjects"
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
    }"""
    _assert_block_tokens(main, 'resource "aws_iam_role" "warehouse_recovery_storage"', role)
    _assert_block_tokens(
        main,
        'resource "aws_iam_user_policy" "warehouse_recovery_storage_assume"',
        assume,
    )
    _assert_block_tokens(
        main,
        'resource "aws_iam_role_policy" "warehouse_recovery_storage"',
        policy,
    )
    exact_policy = _block(main, 'resource "aws_iam_role_policy" "warehouse_recovery_storage"')
    for rejected in (
        "s3:GetObjectVersion",
        "s3:ListBucketVersions",
        "s3:DeleteObjectVersion",
        "s3:PutBucket",
        "s3:DeleteBucket",
        "s3:*",
        "catalog_backup",
    ):
        assert rejected not in exact_policy
    assert 'Resource = "*"' not in exact_policy
    assert main.count('resource "aws_iam_role"') == 2
    expected_output = """output "recovery_storage_role_arn" {
      value = aws_iam_role.warehouse_recovery_storage.arn
      sensitive = true
    }"""
    _assert_block_tokens(outputs, 'output "recovery_storage_role_arn"', expected_output)


def test_writer_inspection_is_exact_user_discovery_only_access() -> None:
    main = _text("main.tf")
    match = re.search(
        r'^resource "aws_iam_user_policy" "warehouse_writer_inspection" \{.*?^\}',
        main,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None
    expected = """resource "aws_iam_user_policy" "warehouse_writer_inspection" {
      name = "databox-warehouse-writer-inspection"
      user = aws_iam_user.recovery_operator.name
      policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
          {
            Sid = "InspectOnlyWarehouseWriter"
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
    }"""

    assert _tokens(match.group()) == _tokens(expected)
    assert main.count('"warehouse_writer_inspection"') == 1
    assert "DATABOX_AWS_ACCOUNT_ID" not in main
    assert "allowed_account_ids = [var.aws_account_id]" in _text("versions.tf")
    runbook = (ROOT / "docs" / "runbook.md").read_text()
    assert "tofu plan -refresh=false" not in runbook
    assert "saved live-refresh plan" in runbook


def test_existing_warehouse_is_root_checked_settings_only_data_source() -> None:
    main = _text("main.tf")
    _assert_block_tokens(
        main,
        'data "aws_caller_identity" "current"',
        'data "aws_caller_identity" "current" {}',
    )
    root_condition = (
        "          condition = data.aws_caller_identity.current.arn == "
        '"arn:aws:iam::${var.aws_account_id}:root"'
    )
    root_error = (
        '          error_message = "Warehouse protection planning and apply require '
        'the exact account-root principal."'
    )
    expected = f"""data "aws_s3_bucket" "warehouse" {{
      bucket = var.warehouse_bucket
      lifecycle {{
        precondition {{
{root_condition}
{root_error}
        }}
        precondition {{
          condition = var.warehouse_bucket != var.catalog_backup_bucket
          error_message = "warehouse_bucket must differ from catalog_backup_bucket."
        }}
        precondition {{
          condition = startswith(
            var.warehouse_runtime_role_arn,
            "arn:aws:iam::${{var.aws_account_id}}:role/",
          )
          error_message = "warehouse_runtime_role_arn must belong to aws_account_id."
        }}
      }}
    }}"""
    _assert_block_tokens(main, 'data "aws_s3_bucket" "warehouse"', expected)
    assert 'resource "aws_s3_bucket" "warehouse"' not in main
    assert "force_destroy" not in _block(main, 'data "aws_s3_bucket" "warehouse"')


def test_warehouse_policy_is_exactly_two_root_only_denies() -> None:
    main = _text("main.tf")
    expected = """data "aws_iam_policy_document" "warehouse" {
      statement {
        sid = "DenyNonRootVersionDeletion"
        effect = "Deny"
        actions = ["s3:DeleteObjectVersion"]
        resources = ["${data.aws_s3_bucket.warehouse.arn}/*"]
        principals {
          type = "*"
          identifiers = ["*"]
        }
        condition {
          test = "ArnNotEquals"
          variable = "aws:PrincipalArn"
          values = ["arn:aws:iam::${var.aws_account_id}:root"]
        }
      }
      statement {
        sid = "DenyNonRootProtectionChanges"
        effect = "Deny"
        actions = [
          "s3:PutBucketVersioning",
          "s3:PutLifecycleConfiguration",
          "s3:PutBucketPolicy",
          "s3:DeleteBucketPolicy",
        ]
        resources = [data.aws_s3_bucket.warehouse.arn]
        principals {
          type = "*"
          identifiers = ["*"]
        }
        condition {
          test = "ArnNotEquals"
          variable = "aws:PrincipalArn"
          values = ["arn:aws:iam::${var.aws_account_id}:root"]
        }
      }
    }"""
    _assert_block_tokens(main, 'data "aws_iam_policy_document" "warehouse"', expected)


def test_warehouse_retention_resources_have_exact_ordered_configuration() -> None:
    main = _text("main.tf")
    policy = """resource "aws_s3_bucket_policy" "warehouse" {
      bucket = data.aws_s3_bucket.warehouse.id
      policy = data.aws_iam_policy_document.warehouse.json
    }"""
    versioning = """resource "aws_s3_bucket_versioning" "warehouse" {
      bucket = data.aws_s3_bucket.warehouse.id
      versioning_configuration {
        status = "Enabled"
      }
      depends_on = [aws_s3_bucket_policy.warehouse]
    }"""
    lifecycle = """resource "aws_s3_bucket_lifecycle_configuration" "warehouse" {
      bucket = data.aws_s3_bucket.warehouse.id
      rule {
        id = "expire-noncurrent-object-versions-after-30-days"
        status = "Enabled"
        filter {}
        noncurrent_version_expiration {
          noncurrent_days = 30
        }
      }
      depends_on = [aws_s3_bucket_versioning.warehouse]
    }"""
    _assert_block_tokens(main, 'resource "aws_s3_bucket_policy" "warehouse"', policy)
    _assert_block_tokens(main, 'resource "aws_s3_bucket_versioning" "warehouse"', versioning)
    _assert_block_tokens(
        main,
        'resource "aws_s3_bucket_lifecycle_configuration" "warehouse"',
        lifecycle,
    )


def test_warehouse_has_no_unrelated_settings_or_bucket_output() -> None:
    main = _text("main.tf")
    outputs = _text("outputs.tf")
    declarations = re.findall(r'^(data|resource) "([^"]+)" "warehouse"', main, re.MULTILINE)
    assert declarations == [
        ("data", "aws_s3_bucket"),
        ("data", "aws_iam_policy_document"),
        ("resource", "aws_s3_bucket_policy"),
        ("resource", "aws_s3_bucket_versioning"),
        ("resource", "aws_s3_bucket_lifecycle_configuration"),
    ]
    assert "aws_s3_bucket.warehouse" not in outputs
    assert "data.aws_s3_bucket.warehouse" not in outputs
    assert 'output "warehouse' not in outputs


def test_warehouse_bucket_is_required_nonempty_input_with_safe_example() -> None:
    variables = _text("variables.tf")
    example = _text("terraform.tfvars.example")
    expected = """variable "warehouse_bucket" {
      description = "Existing warehouse bucket protected by root-only retention controls."
      type = string
      validation {
        condition = length(trimspace(var.warehouse_bucket)) > 0
        error_message = "warehouse_bucket must not be empty."
      }
    }"""
    _assert_block_tokens(variables, 'variable "warehouse_bucket"', expected)
    assert 'warehouse_bucket           = "replace-existing-warehouse-bucket"' in example
    assert 'aws_profile           = "replace-root-backed-profile"' in example


def test_rejected_warehouse_inputs_and_outputs_are_absent() -> None:
    variables = _text("variables.tf")
    outputs = _text("outputs.tf")
    example = _text("terraform.tfvars.example")
    rejected = (
        "primary_iceberg_bucket",
        "warehouse_prefix",
        "iceberg_recovery_bucket",
        "routine_writer_principal_arn",
        "iceberg_recovery_reader_role_arn",
    )
    for name in rejected:
        assert name not in variables
        assert name not in outputs
        assert name not in example


def test_example_contains_no_real_account_or_bucket_identity() -> None:
    example = _text("terraform.tfvars.example")
    assert "123456789012" in example
    assert "replace-catalog-backup-bucket" in example
    assert "replace-existing-warehouse-bucket" in example
    assert "AKIA" not in example
    assert "secret" not in example.lower()


def test_local_state_ownership_is_documented_and_ignored() -> None:
    runbook = (ROOT / "docs" / "runbook.md").read_text()
    gitignore = (ROOT / ".gitignore").read_text()
    assert "infra/recovery/terraform.tfstate" in runbook
    assert "FileVault" in runbook
    assert "tofu import" in runbook
    assert "*.tfstate" in gitignore


def test_raw_recovery_evidence_remains_private() -> None:
    gitignore = (ROOT / ".gitignore").read_text()
    runbook = (ROOT / "docs" / "runbook.md").read_text()
    assert "/.recovery/" in gitignore
    assert "*.tfplan" in gitignore
    assert "Never force-add" in runbook
    assert "raw recovery evidence" in runbook
    assert "ignored `/.recovery/` custody root" in runbook
