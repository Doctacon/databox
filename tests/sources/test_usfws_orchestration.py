"""Manual Dagster-owned USFWS media discovery tests."""

from pathlib import Path

from databox.orchestration.domains import usfws
from databox.public_media_ingest import MediaIngestResult


def test_usfws_job_is_manual_unscheduled_and_connected() -> None:
    assert usfws.ingest_job.name == "usfws_ingest"
    assert not hasattr(usfws, "daily_pipeline")
    assert not hasattr(usfws, "schedule")

    specs = {spec.key.to_user_string(): spec for spec in usfws.usfws_dlt_assets.specs}
    target = "sqlmesh/rufous_public/gbif_eod_occurrence"
    assert target in {
        dep.asset_key.to_user_string()
        for name in ("sqlmesh/raw_usfws/image_search_runs", "sqlmesh/raw_usfws/image_records")
        for dep in specs[name].deps
    }
    assert {
        dep.asset_key.to_user_string() for dep in specs["sqlmesh/raw_usfws/_dlt_load_status"].deps
    } == {
        "sqlmesh/raw_usfws/image_search_runs",
        "sqlmesh/raw_usfws/image_records",
    }


def test_usfws_assets_materialize_current_run_metadata(monkeypatch) -> None:
    calls: list[tuple[Path, int]] = []

    def ingest(path: Path, *, max_images_per_target: int) -> MediaIngestResult:
        calls.append((path, max_images_per_target))
        return MediaIngestResult(
            run_id="current-run",
            target_species=2,
            raw_records=7,
            completed_runs=1,
        )

    monkeypatch.setattr(usfws, "ingest_public_usfws_media", ingest)
    config = usfws.UsfwsIngestConfig(database_path="/tmp/modeled.duckdb", max_images_per_target=25)
    events = list(usfws.usfws_dlt_assets.node_def.compute_fn.decorated_fn(config))

    assert calls == [(Path("/tmp/modeled.duckdb"), 25)]
    assert [event.asset_key.to_user_string() for event in events] == [
        "sqlmesh/raw_usfws/image_search_runs",
        "sqlmesh/raw_usfws/image_records",
        "sqlmesh/raw_usfws/_dlt_load_status",
    ]
    assert all(event.metadata["run_id"] == "current-run" for event in events)
    assert events[-1].metadata["rows_loaded"] == 8
