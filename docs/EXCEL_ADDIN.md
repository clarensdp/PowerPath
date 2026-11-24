# PowerPath for Excel (v31.5 prototype)

The add-in puts PowerPath's approved case, diligence ranking, returns attribution and
deliverability into Excel. It works the same way as the MCP server: it is read-only and
calls the authenticated API, so each user sees only their own tenant's projects with their
own role. Approvals stay in PowerPath.

Files are in `web/excel/` and are served at `/excel/*` from a fixed list. Only that path
gets the relaxed security headers Office needs: Office.js from
`appsforoffice.microsoft.com`, and framing by Office hosts. The app and the API keep
`frame-ancestors 'none'`.

## Formulas (namespace `PP`)

Office web add-ins always name a function `NAMESPACE.FUNCTION`, so a bare `=PP()` isn't
possible. Three formulas cover everything:

| Formula | Returns |
|---|---|
| `=PP.GET(project, field, [arg1], [arg2])` | One value |
| `=PP.TABLE(project, name, [arg])` | A spilled table |
| `=PP.BRIDGE(project, A2:B4)` | What-if: the change in NPV, IRR and DSCR by cause, with a reconciling total row |
| `=PP.MARKET(project, metric, [stat], [window], [location])` | Trailing power-market average (see `docs/MARKET_DATA.md`) |

`PP.GET` fields:

- **Approved-case results:** `npv`, `irr`, `dscr`, `breach_months`.
- **Per input (arg1 = input key):** `exposure`, `source`, `confidence`, `value`, `rank`.
- **Deliverability:** `deliverable_mw` and `time_to_target`. Here arg1 is the case
  (upside, base or downside) and arg2 is the configuration.

`PP.TABLE` names: `priorities`, `pathbridge` (arg = path name), `deliverability`,
`market` (arg = days), `history` (arg = metric), `fields`. `=PP.TABLE(project, "fields")` lists every field and table.

The task pane's **Build a formula** panel fills in the project, field, input, case or path
from dropdowns and inserts the formula into the selected cell, much like FactSet's Insert
Formula. Results are cached for 60 seconds. **Refresh** clears the cache and recalculates.

The pane also inserts three formatted sheets: Diligence, Path bridges and Deliverability.
Each is stamped with the approved case's fingerprint and the time it was calculated. They
are values, not live formulas, so a workbook you send someone doesn't change and doesn't
break for readers without PowerPath access.

## Sign-in

On an installation that requires login, **Sign in to PowerPath** opens a sign-in window
(the Office Dialog API) served by PowerPath itself.

- The window sends the credentials to `/api/v27/auth/login` on the same origin, and
  returns only the session token to the task pane.
- The token is kept in memory and `sessionStorage`, never persistent storage, so it ends
  when Excel closes. It also expires on the server (8 hours for local identity).
- **Sign out** revokes the session on the server.
- In the local workspace, no sign-in is needed.
- Production should add Microsoft 365 single sign-on, so users don't type a separate
  PowerPath password.

## Try it

1. Serve PowerPath over HTTPS, which Office requires. For local work, run it behind
   https://localhost:8768 using a trusted dev certificate (for example, Microsoft's
   `office-addin-dev-certs`).
2. `python -m scripts.excel_manifest --base-url https://your-host` writes a manifest for
   your address. The checked-in `web/excel/manifest.xml` targets https://localhost:8768.
3. Load it. In Excel on the web: **Home → Add-ins → More add-ins → Upload my add-in**.
   In Excel desktop: sideload it through a shared-folder catalog. Organizations can
   deploy it centrally from the Microsoft 365 admin center.

## Status and limits

- **Not yet tested inside Excel.** The tests cover the served files, the security
  headers, that the manifest and function metadata agree, and the formula logic against
  real API responses (run in Node). Microsoft's manifest validator still needs to be
  run.
- **Single sign-on isn't built yet.** Users sign in with a PowerPath password in the
  sign-in window. Microsoft 365 single sign-on is the next step for enterprise use.
- **No AppSource listing.** That needs a hosted HTTPS deployment, a privacy policy and
  Microsoft review.
- **The Host header allow-list may need your public hostname** before the add-in loads
  from a non-loopback address.
