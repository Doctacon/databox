"""Arizona boundary semantics for manual trip coordinates."""

import pytest
from databox.agent_tools.arizona_boundary import (
    ARIZONA_BOUNDARY_LON_LAT,
    is_in_arizona,
)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (34.5400, -112.4685),  # Prescott
        (33.4484, -112.0740),  # Phoenix
        (32.6920, -114.6270),  # Yuma near the western river boundary
    ],
)
def test_known_arizona_points_are_inside(latitude: float, longitude: float) -> None:
    assert is_in_arizona(latitude, longitude)


def test_census_boundary_vertex_is_inclusive() -> None:
    longitude, latitude = ARIZONA_BOUNDARY_LON_LAT[0]

    assert is_in_arizona(latitude, longitude)


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (36.9000, -114.8000),  # Nevada: inside old rectangle, outside Arizona
        (31.3000, -114.8000),  # Mexico/California: inside old rectangle
        (36.1699, -115.1398),  # Las Vegas
        (34.0522, -118.2437),  # Los Angeles
    ],
)
def test_outside_points_are_rejected(latitude: float, longitude: float) -> None:
    assert not is_in_arizona(latitude, longitude)
