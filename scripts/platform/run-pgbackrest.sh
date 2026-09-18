#!/usr/bin/env bash
set -euo pipefail
: "${PGBACKREST_REPO1_CIPHER_PASS:?set pgBackRest repository cipher passphrase}"
: "${PGBACKREST_REPO1_S3_KEY:?set runtime AWS access key}"
: "${PGBACKREST_REPO1_S3_KEY_SECRET:?set runtime AWS secret key}"
if [[ -n "${DATABOX_RUNTIME_AWS_SESSION_TOKEN:-}" ]]; then
  export PGBACKREST_REPO1_S3_TOKEN="$DATABOX_RUNTIME_AWS_SESSION_TOKEN"
else
  unset PGBACKREST_REPO1_S3_TOKEN
fi
exec pgbackrest --config=/etc/pgbackrest/pgbackrest.conf "$@"
