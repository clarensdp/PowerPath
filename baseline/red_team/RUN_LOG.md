# Run Log — PowerPath v25.8 independent review

**Date:** Mon 26 Oct 2026 (America/New_York). **Environment:** Linux 6.18 container, Node.js v22.23.4, Python 3.13.17, Playwright 1.63.0 / Chromium (preinstalled). No credentials or private data were used.

## Provenance
- Package: `PowerPath_v25_8_Claude_Independent_Audit_Package.zip`, SHA-256 `9f99f6ab…5b041381`. `sha256sum -c MANIFEST_SHA256.txt` → **0 mismatches**.
- The attached `PowerPath_v25_8.html` (`fd0562ce…3e1059eb`) is **byte-identical** to `python3 workspace/build_page.py` output from the package, so the build is deterministic.
- The two attached prompt copies are identical (`74043f3a…`), and so are the two run-log copies (`c075ec77…`).
- The blind code notes (`evidence/BLIND_NOTES.md`) were written before `V25_8_FINANCIAL_AUDIT.md` or any test file was opened.
- Public sources were re-opened on 26 Oct 2026 (see `VERIFIED_FACTS.csv`). SEC EDGAR pages were reached through search-result URLs. Two primary pages were not reachable: the Galaxy Q2 release and the Helios II notes PDF.

## File hashes (SHA-256)
```
2e01c4d70b63c399a93fd01f0e205aeb0a8c68b511fb3a6cbec8224e03464ace  PowerPath_v25_8/workspace/underwrite25.js
633dd5472ea3e67ee6ca95ce09f4688c9fdae0501b4188bbbe56921d99224ef3  PowerPath_v25_8/workspace/contract_notes258.js
70c62d299383418b0816d287c003600398f11444bc2b0b2849d60c1dd9aa80c9  PowerPath_v25_7/workspace/underwrite25.js
fd0562ce6031d29424ad9b8fc181942bbbd87a6466bbd310c8ea2d8c3e1059eb  PowerPath_v25_8/PowerPath.html
6fc9afcbbf60bd5a8e595c1aca2b380d5298928b2fb6aee6f0a78e06b0a42156  PowerPath_v25_8/benchmarks/case_catalog_v258.json
60d0ce62d939c344af45617229a8f42e4350346ce3493fbce084e7af6cec2887  PowerPath_v25_8/benchmarks/note_terms_v258.json
05bd893161e2b24e93ab63855287dab45f36845705c2d026d5986529a7626d7a  PowerPath_v25_8/audit/reference257.py
f7d9b9a6bc2cb9b09c257af102c2e3eeed5451df9e60637c7b93469b1af4dfa6  PowerPath_v25_8/audit/verify_v258_cases.py
bea94912e4527aa188d3102f6dac89adf7bf0d00eae0eff02ba5a64996bdbadc  RUN_AUDIT.sh
33cd80a3711a4a46a9cd9d249db8eca0b47e2f6ab14abf3d76f76381bacdfce3  MANIFEST_SHA256.txt

9e87cd92bc5b36c8d311a8037c05c5863b5338fc77263af79f6a555d7ea86b5a  PowerPath_v25_8_CA/workspace/underwrite25.js
41e2eaa9812c0cad3cfc4ce7ddd906bb7ba7e98c89f477185735bd53b3dab3f3  PowerPath_v25_8_CA/workspace/contract_notes258.js
b6ed8aa6fa57b5ae234999a9a823444ab3477d5a412f0cb5909966ca27cecb7c  PowerPath_v25_8_CA/workspace/test_contract_notes258.cjs
46a62ffee846804f52a86666c8701c6cd57da4fecc6eb94642dd4a2386c727e1  PowerPath_v25_8_CA/workspace/test_claude_audit.cjs
03b7ab378624938bdb38826dc407707298983df20d0c0adffb4c92298aeb20ad  PowerPath_v25_8_CA/benchmarks/run_benchmarks_v258.cjs
22f92d9cb3bd71fc743db4ddc38c5e3ff24db9068098ab64267de02d0ff50732  PowerPath_v25_8_CA/audit/reference257.py
ba864cacb9aa85d202b88c9659d01684f660121af590c8735833b6e9b16fb634  PowerPath_v25_8_CA/audit/verify_v258_cases.py
7368bd57967882967b81e8d9b780039087409b032f2f170d0aef4da0a026b1d6  PowerPath_v25_8_CA/PowerPath.html
59c7a02943475f5eba1e46f03b699cc99d616db5795f7d010193581b425ff34e  evidence/ca_reference.py
```

## Commands and results
| # | Command | Result |
|---|---|---|
| 1 | `bash RUN_AUDIT.sh` (original v25.8) | EXIT 0 in 13.3 s: 21/21 JS suites; Python reference 8 cases / 24,024 checks; v25.8 edge cases 7 / 13,971 checks (max gap 1.36e-12); 16 projects, 720 stresses, 0 errors; 5 APLD totals normalized; 0 contract-verified. Reproduces the bundled log (`evidence/run_audit_original.txt`) |
| 2 | `node evidence/probe*.cjs` (hypothesis probes on v25.8) | H1, H2, H3, H4, H5 confirmed; H6 led to CA-04 (phantom financing, min cash −$861.0M) |
| 3 | `node CODE_PATCHES/test_claude_audit.cjs <v25.8 engine> <v25.8 notes>` | **1/9 pass — 8 FAIL as designed** (`evidence/test_claude_audit_BEFORE.txt`) |
| 4 | `node CODE_PATCHES/test_claude_audit.cjs` (patched) | **9/9 pass** (`evidence/test_claude_audit_AFTER.txt`) |
| 5 | `python3 -I evidence/ca_reference.py cases.json ref.json` + `dump_js.cjs` + `compare.py` | Patched vs independent reference: 10 cases, 24,320 monthly field checks, **max gap 1.42e-12 $M**, NPVs equal to 1e-9. v25.8 vs reference: variances in 8 of 10 cases (max $93.9M, plus 2 exceptions), all explained in `MONTHLY_RECONCILIATION.csv` |
| 6 | `node evidence/impact720.cjs` | 720 stresses with identical inputs: engine-patch max \|ΔNPV\| **$50.74M** (Abilene, +12 m delay); harness-calendar max \|ΔNPV\| $5.53M; max identity residual 1.8e-12; breach scenarios 720 → 720; defaults 0 → 0 |
| 7 | `bash CODE_PATCHES/RUN_AUDIT_CLAUDE.sh` (patched copy, `set -euo pipefail`) | EXIT 0: **22/22 JS suites**; bundled reference 24,024 checks (max gap 5.7e-13) after the P1 alignment and legacy-policy pinning of 3 default cases; v25.8 edge cases 13,971 checks (max 1.8e-12); 16 / 720 / 0 errors; maxVersionDelta vs v25.7 $57.53M; HTML rebuilt (`7368bd57…`) |
| 8 | `node smoke.cjs PowerPath.html` (patched build, Chromium) | 1440 px and 390 px: 0 page errors, no horizontal overflow, patched engine present in page |

## Notes on the bundled scripts
- `RUN_AUDIT.sh` rebuilds `PowerPath.html` **inside** the frozen v25.8 folder (CA-22). The rebuild was byte-identical here, so no content changed.
- The bundled Python reference needed two edits to agree with the patched engine: annuity amortization (P1), and `fundingDefaultPolicy='continue'` on its "capped sponsor", "zero borrowing" and "tenant funding collection delay" cases, which exercise the legacy post-default spending path. The halt policy is verified by the separate from-scratch reference.
