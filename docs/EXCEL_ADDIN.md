# PowerPath for Excel (v31.5 prototype)

The add-in puts PowerPath's approved case, diligence ranking, returns attribution and
deliverability into Excel. It works the same way as the MCP server: it is read-only and
calls the authenticated API, so each user sees only their own tenant's projects with their
own role. Approvals stay in PowerPath.

Files are in `web/excel/` and are served at `/excel/*` from a fixed list. Only that path
gets the relaxed security headers Office needs: Office.js from
`appsforoffice.microsoft.com`, and framing by Office hosts. The app and the API keep
`frame-ancestors 'none'`.

## Formulas (namespace `POWERPATH`)

| Formula | Returns |
|---|---|
| `=POWERPATH.METRIC(project, "npv"\|"irr"\|"dscr"\|"breach_months")` | Approved-case result |
| `=POWERPATH.EXPOSURE(project, key)` | NPV change ($M) at the input's downside |
| `=POWERPATH.SOURCE(project, key)` | Source · date · verification · review state |
| `=POWERPATH.PRIORITIES(project)` | Spilled diligence table ranked by NPV at risk |
| `=POWERPATH.BRIDGE(project, A2:B4)` | What-if; spilled attribution by cause, with a reconciling total row |
| `=POWERPATH.PATHBRIDGE(project, "Grid utility service")` | A power path's change in returns, by cause |
| `=POWERPATH.DELIVERABLE(project, config, "base", "mw"\|"month")` | Firm MW at the target month, or the month the target is reached |

Input keys are the same as the underwriting catalog (`docs/UNDERWRITING_V31_5.md`).
GET results are cached for 60 seconds. **Recalculate** in the task pane clears the cache.

The task pane also inserts three formatted sheets: Diligence, Path bridges and
Deliverability. Each sheet is stamped with the approved case's fingerprint and the time
it was calculated. They are values, not live formulas, so a sheet you send someone
doesn't change after it's sent.

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
- **The sign-in token is kept in the add-in's local storage.** Production should use
  Office single sign-on, or a short-lived token issued for the add-in.
- **No AppSource listing.** That needs a hosted HTTPS deployment, a privacy policy and
  Microsoft review.
- **The Host header allow-list may need your public hostname** before the add-in loads
  from a non-loopback address.
