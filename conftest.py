"""Repository-wide pytest process isolation."""

from __future__ import annotations

import os

# These collectors are initialized at import time and may flush asynchronously.
# Disable them before test modules import dlt or SQLMesh so network-blocked VCR
# tests cannot inherit or retain telemetry connections bound to a cassette.
os.environ["RUNTIME__DLTHUB_TELEMETRY"] = "false"
os.environ["SQLMESH__DISABLE_ANONYMIZED_ANALYTICS"] = "true"
