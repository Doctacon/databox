"""Atomic Iceberg snapshot-publication contract for AVONET."""

from databox_sources.avonet import source


def test_avonet_snapshot_declares_atomic_replace_publication() -> None:
    """A failed replacement cannot publish a partial AVONET snapshot."""
    avonet_resource = source.avonet_source().resources["species_traits"]
    assert avonet_resource.write_disposition == "replace"
