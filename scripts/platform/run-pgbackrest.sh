#!/usr/bin/env bash
set -euo pipefail
: "${DATABOX_AWS_CREDENTIAL_PROCESS:?set renewable credential process}"
: "${PGBACKREST_REPO1_CIPHER_PASS:?set pgBackRest repository cipher passphrase}"
eval "$(python3 /opt/databox/pgbackrest-credential-process.py --command "$DATABOX_AWS_CREDENTIAL_PROCESS")"
exec pgbackrest --config=/etc/pgbackrest/pgbackrest.conf "$@"
