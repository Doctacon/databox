"""SQLMesh project config — delegates to databox.config.settings.

SQLMesh picks this file up when no config.yaml is present. Keeping the
config in Python means the SQLMesh project, Dagster resources, Soda
datasource, and dlt destinations all read from the same
`DataboxSettings` object.
"""

from databox.config.settings import settings

config = settings.sqlmesh_config()
