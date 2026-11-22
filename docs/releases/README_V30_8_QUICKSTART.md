# PowerPath v30.8.0 Architecture Foundation

This is the full local application and a first **controlled SQLite migration baseline**. No production PostgreSQL or autonomous cloud deployment has been enabled.

## Start and inspect

```bash
python3 -m pip install -r requirements.txt
python3 -m scripts.db_manage inspect
./run_local.sh
```

Access `http://127.0.0.1:8768`. For migration, first stop any running processes and follow [the v30.8 release guide](RELEASE_V30_8_0_ARCHITECTURE_FOUNDATION.md). The guide includes consistent backup, verification, Alembic commands and recovery steps.

## Additional development controls

```bash
python3 -m pytest -q tests/test_v308_database_foundation.py
python3 -m scripts.run_v308_gate
```

See `architecture/TECHNICAL_DEBT_REGISTER_V30_8.md` for what remains before PostgreSQL staging and production readiness.
