# Project working agreement

- Keep the existing FastAPI + static HTML/CSS/JS architecture unless a real product need requires a change.
- UI languages: pt-BR at `/`, English at `/en`, Simplified Chinese at `/zh`. Keep corresponding page paths and reciprocal hreflang aligned.
- `web/index.html` and `web/assets/app.js` are the Portuguese bases; `web/build_pages.py` and `web/translations.py` generate translated/static pages. Regenerate and check all languages after editing them.
- Reports describe single-page HTML technical readiness. Never claim actual Google rankings, AI citations, traffic loss, or full-site coverage without measurements.
- Baseline comparisons require the same URL, final URL, engine, schema and scoring versions, and a later scan. Bump `scoring_version` when rules, eligibility or weights change. Unknown evidence never proves a fix or a new regression; score deltas also require matching coverage and weights.
- Baseline storage is explicit, local to the browser and removable. Imported data is not authenticated. Preserve operation ordering so an in-flight import cannot undo a later clear or overwrite a newer baseline.
- Optional schema, FAQ, numbers, lists, training permissions and llms.txt must not become universal requirements or fabricated evidence.
- Every outbound scan, redirect and auxiliary resource uses the public-network transport. Do not bypass DNS/IP, deadline, content-type or size guards.
- Avoid paid or third-party requests during tests. Preserve `PUBLIC_AI_SUMMARY=false` and preview noindex defaults.
- Run `.venv\Scripts\python.exe -m pytest tests -q` and browser smoke checks after changes to the API or user flow. Browser tests are optional dev dependencies, not production dependencies.
- Run `node --test tests/js/comparison.test.cjs` after baseline logic changes. Optional flow acceptance: `.venv\Scripts\python.exe tests/browser/conversion_v2_smoke.py` against a local server on port 8000; it uses explicitly synthetic HTML fixtures and no external scans.
- `requirements.lock` is universal and hash-locked; `httpcore` transport uses private adapter interfaces, so rerun network tests after dependency changes.
- Deployment is not complete until a real host, HTTPS domain and operator contact are configured. Never report a local preview as a public launch.
- Public operator fields and translated logging notices must reflect actual operations. `python -m mandapi_geo.preflight --stage preview|production` checks configuration only; a green result does not verify live deployment, proxy quota isolation, customers or profitability.
- The user's global rule applies: any tool turn containing `view_image` must contain only that single tool call.
