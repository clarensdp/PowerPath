# Push PowerPath to a **private** GitHub repository

1. Unzip the handoff archive. This archive intentionally contains no `.git` directory or developer credentials.
2. Open the extracted folder in a terminal, then run:

   ```bash
   git init -b main
   git add .
   git status --short
   git commit -m "Initial PowerPath engineering-alpha handoff"
   git remote add origin git@github.com:YOUR-ORG/YOUR-PRIVATE-REPO.git
   git push -u origin main
   ```

3. Grant your cofounder GitHub access to the **private** repository (do not share a personal access token).
4. Enable branch protection/rulesets, PR reviews and mandatory CI checks. Review CI output before merging production-related changes.
5. Read `README.md`, `docs/COFOUNDER_HANDOFF.md` and `VERIFICATION_2026-11-07.md`. Run local checks on a fresh checkout.

## What is *not* in the repository

No live Supabase credentials, database dumps, migration-source snapshots, local SQLite workspace, private uploaded evidence or production approval. The PostgreSQL runtime adapter is experimental and disabled for the local demo. Obtain future credentials through an approved secret manager and use a disposable test database for database acceptance.

## Pre-push review

- Confirm private visibility and ownership of source/data rights.
- Inspect `git diff --cached --name-only`, preferably with a second engineer, before the first commit.
- Run a dedicated scanner such as `gitleaks` or GitHub secret scanning; offline regex scanning is not comprehensive.
- Do not enable real agent actions, PG cutover, public API hosting or financial certification as part of initial push.
