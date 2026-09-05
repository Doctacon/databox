FROM postgres:17.6-bookworm

ARG PGBACKREST_VERSION=2.55.1
RUN apt-get update \
    && apt-get install --yes --no-install-recommends pgbackrest python3 \
    && test "$(pgbackrest version | awk '{print $2}')" = "${PGBACKREST_VERSION}" \
    && rm -rf /var/lib/apt/lists/*
COPY infra/recovery/pgbackrest.conf.example /etc/pgbackrest/pgbackrest.conf
COPY scripts/platform/catalog-backup-readiness.py /opt/databox/catalog-backup-readiness.py
COPY scripts/platform/run-pgbackrest.sh /usr/local/bin/run-pgbackrest
RUN chmod 0755 \
    /usr/local/bin/run-pgbackrest \
    /opt/databox/catalog-backup-readiness.py
