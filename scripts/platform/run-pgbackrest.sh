#!/usr/bin/env bash
set -euo pipefail
: "${PGBACKREST_REPO1_CIPHER_PASS:?set pgBackRest repository cipher passphrase}"
: "${PGBACKREST_REPO1_S3_KEY:?set temporary backup access key}"
: "${PGBACKREST_REPO1_S3_KEY_SECRET:?set temporary backup secret key}"
: "${PGBACKREST_REPO1_S3_TOKEN:?set temporary backup session token}"
exec pgbackrest --config=/etc/pgbackrest/pgbackrest.conf "$@"
