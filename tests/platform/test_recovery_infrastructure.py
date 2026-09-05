"""Static contract for automation-first recovery infrastructure."""

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


def test_three_buckets_are_distinct_and_recovery_is_versioned() -> None:
    main = _text("main.tf")
    assert 'check "distinct_bucket_names"' in main
    assert 'resource "aws_s3_bucket" "catalog_backup"' in main
    assert 'resource "aws_s3_bucket" "iceberg_recovery"' in main
    assert main.count('status = "Enabled"') >= 4
    assert "noncurrent_days = 45" in main
    assert "noncurrent_days = 30" in main
    assert main.count("block_public_acls       = true") == 2
    assert main.count('sse_algorithm = "AES256"') == 2


def test_replication_preserves_deleted_primary_versions() -> None:
    main = _text("main.tf")
    assert 'prefix = "${local.warehouse_prefix}/"' in main
    assert "delete_marker_replication {" in main
    assert 'status = "Disabled"' in main
    assert '"s3:ReplicateObject", "s3:ReplicateTags"' in main
    assert "s3:ReplicateDelete" not in main
    assert '"DenyRoutineWriterDeletes"' in main
    assert '"s3:DeleteObject", "s3:DeleteObjectVersion"' in main


def test_backup_and_recovery_permissions_are_separate() -> None:
    main = _text("main.tf")
    assert 'resource "aws_iam_role" "catalog_backup"' in main
    assert 'resource "aws_iam_role" "iceberg_recovery_reader"' in main
    reader_policy = main.split(
        'resource "aws_iam_role_policy" "iceberg_recovery_reader"', maxsplit=1
    )[1].split('resource "aws_iam_role" "iceberg_replication"', maxsplit=1)[0]
    assert "s3:GetObjectVersion" in reader_policy
    assert "s3:PutObject" not in reader_policy
    assert "s3:DeleteObject" not in reader_policy


def test_example_contains_no_real_account_or_bucket_identity() -> None:
    example = _text("terraform.tfvars.example")
    assert "123456789012" in example
    assert "replace-primary-bucket" in example
    assert "AKIA" not in example
    assert "secret" not in example.lower()
