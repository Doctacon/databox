"""Static contract for automation-first catalog recovery infrastructure."""

from pathlib import Path

ROOT = Path(__file__).parents[2]
INFRA = ROOT / "infra" / "recovery"


def _text(name: str) -> str:
    return (INFRA / name).read_text()


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
    assert 'resource "aws_s3_bucket" "catalog_backup"' in main
    assert 'resource "aws_s3_bucket_versioning" "catalog_backup"' in main
    assert 'status = "Enabled"' in main
    assert "noncurrent_days = 30" in main
    assert "block_public_acls       = true" in main
    assert 'sse_algorithm = "AES256"' in main


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


def test_only_catalog_backup_permissions_remain() -> None:
    main = _text("main.tf")
    outputs = _text("outputs.tf")
    assert 'resource "aws_iam_role" "catalog_backup"' in main
    assert 'resource "aws_iam_role_policy" "catalog_backup"' in main
    assert "s3:GetBucketLocation" in main
    assert "s3:ListBucket" in main
    assert "s3:GetObject" in main
    assert "s3:PutObject" in main
    assert "s3:DeleteObject" in main
    assert "s3:AbortMultipartUpload" in main
    assert "s3:GetObjectVersion" not in main
    assert "s3:DeleteObjectVersion" not in main
    assert "iceberg" not in main.lower()
    assert "replication" not in main.lower()
    assert "primary" not in main.lower()
    assert "recovery" not in outputs.lower()


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
    assert "AKIA" not in example
    assert "secret" not in example.lower()


def test_local_state_ownership_is_documented_and_ignored() -> None:
    runbook = (ROOT / "docs" / "runbook.md").read_text()
    gitignore = (ROOT / ".gitignore").read_text()
    assert "infra/recovery/terraform.tfstate" in runbook
    assert "FileVault" in runbook
    assert "tofu import" in runbook
    assert "*.tfstate" in gitignore
