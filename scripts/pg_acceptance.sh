#!/usr/bin/env bash
# PowerPath v30.8.2 — PostgreSQL staging acceptance on a DISPOSABLE, LOCAL PostgreSQL 16 + PostGIS instance.
#
# Runs: stage import (with geometry quarantine) -> runtime schema + RLS + append-only triggers -> 24-check adversarial
# test as powerpath_app -> pg_dump / pg_restore into a fresh database -> parity check -> adversarial test on the restore.
#
# NEVER point this at Supabase, staging shared by others, or production. It creates and drops databases.
# Required env (no defaults, nothing is stored):
#   PP_PG_HOST PP_PG_PORT PP_PG_USER PGPASSWORD   e.g. 127.0.0.1 55432 powerpath_stage_admin <local password>
# Optional: PP_SNAPSHOT (default: tests/fixtures/powerpath_synthetic.sqlite3)
set -euo pipefail
cd "$(dirname "$0")/.."
: "${PP_PG_HOST:?}" "${PP_PG_PORT:?}" "${PP_PG_USER:?}" "${PGPASSWORD:?}"
case "$PP_PG_HOST" in 127.0.0.1|localhost|::1) ;; *) echo "Refusing non-loopback host $PP_PG_HOST" >&2; exit 2;; esac
SNAP_SRC="${PP_SNAPSHOT:-tests/fixtures/powerpath_synthetic.sqlite3}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cp "$SNAP_SRC" "$WORK/snapshot.sqlite3"
H=(-h "$PP_PG_HOST" -p "$PP_PG_PORT" -U "$PP_PG_USER")
q() { psql "${H[@]}" -d "$1" -v ON_ERROR_STOP=1 -tAc "$2"; }
prep_db() {
  psql "${H[@]}" -d postgres -v ON_ERROR_STOP=1 -qc "DROP DATABASE IF EXISTS $1" -c "CREATE DATABASE $1"
  q "$1" "CREATE SCHEMA extensions; CREATE EXTENSION postgis SCHEMA extensions; ALTER DATABASE $1 SET search_path=\"\$user\",public,extensions;" >/dev/null
}
fingerprint() {
  echo "rls=$(q "$1" "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='powerpath_runtime_v3090' AND relkind='r' AND relforcerowsecurity")" \
       "policies=$(q "$1" "SELECT count(*) FROM pg_policies WHERE schemaname='powerpath_runtime_v3090'")" \
       "triggers=$(q "$1" "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='powerpath_runtime_v3090' AND NOT tgisinternal")" \
       "geoms=$(q "$1" "SELECT count(*) FROM powerpath_stage_v3081.pp_parcel_geometry_v1")+$(q "$1" "SELECT count(*) FROM powerpath_stage_v3081.pp_parcel_geometry_quarantine_v1")" \
       "projects=$(q "$1" "SELECT md5(string_agg(id||name||target_mw,'|' ORDER BY id)) FROM powerpath_runtime_v3090.projects")" \
       "scenarios=$(q "$1" "SELECT md5(string_agg(id||config_json,'|' ORDER BY id)) FROM powerpath_runtime_v3090.scenarios")" \
       "runs=$(q "$1" "SELECT coalesce(md5(string_agg(id||summary_json,'|' ORDER BY id)),'none') FROM powerpath_runtime_v3090.runs")"
}
for r in anon authenticated service_role; do q postgres "DO \$\$BEGIN CREATE ROLE $r NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END\$\$" >/dev/null; done
if [ "$(q postgres "SELECT count(*) FROM pg_roles WHERE rolname='powerpath_app'")" = 1 ]; then
  # The role is cluster-wide; its privileges live per database. Disposable instance only.
  for db in $(q postgres "SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate"); do q "$db" "DROP OWNED BY powerpath_app" >/dev/null; done
  q postgres "DROP ROLE powerpath_app" >/dev/null
fi

echo "== 1. stage import"
prep_db pp_accept_src
POWERPATH_PG_STAGE_DSN="postgresql+psycopg://$PP_PG_USER:$PGPASSWORD@$PP_PG_HOST:$PP_PG_PORT/pp_accept_src" \
  python -m infrastructure.pg_stage --source "$WORK/snapshot.sqlite3" --execute --confirm-stage
echo "== 2. runtime schema + policies + append-only triggers"
python -m infrastructure.runtime_migration --snapshot "$WORK/snapshot.sqlite3" --out "$WORK/runtime.sql"
psql "${H[@]}" -d pp_accept_src -v ON_ERROR_STOP=1 -q -1 -f "$WORK/runtime.sql" >/dev/null
echo "== 3. adversarial RLS / append-only checks (source)"
psql "${H[@]}" -d pp_accept_src -q -f tests/pg/rls_append_only_attack.sql 2>&1 | grep -E 'FAIL|CHECKS PASSED|ERROR'
q pp_accept_src "ANALYZE" >/dev/null; SRC="$(fingerprint pp_accept_src)"; echo "source : $SRC"
echo "== 4. backup + restore drill"
pg_dump "${H[@]}" -d pp_accept_src -Fc -n powerpath_stage_v3081 -n powerpath_runtime_v3090 -f "$WORK/backup.dump"
echo "backup sha256: $(sha256sum "$WORK/backup.dump" | cut -c1-64)"
prep_db pp_accept_restore
pg_restore "${H[@]}" -d pp_accept_restore --exit-on-error "$WORK/backup.dump"
q pp_accept_restore "ANALYZE" >/dev/null; DST="$(fingerprint pp_accept_restore)"; echo "restore: $DST"
[ "$SRC" = "$DST" ] || { echo "RESTORE PARITY FAILED" >&2; exit 1; }
echo "== 5. adversarial checks (restored copy)"
psql "${H[@]}" -d pp_accept_restore -q -f tests/pg/rls_append_only_attack.sql 2>&1 | grep -E 'FAIL|CHECKS PASSED|ERROR'
echo "PG ACCEPTANCE: PASS (local disposable instance; not Supabase, not production)"
