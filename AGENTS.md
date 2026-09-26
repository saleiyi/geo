# Project working agreement

- Keep the existing FastAPI + static HTML/CSS/JS architecture unless a real product need requires a change.
- UI languages: pt-BR at `/`, English at `/en`, Simplified Chinese at `/zh`. Keep corresponding page paths and reciprocal hreflang aligned.
- `web/index.html` and `web/assets/app.js` are the Portuguese bases; `web/build_pages.py` and `web/translations.py` generate translated/static pages. Regenerate and check all languages after editing them.
- Reports describe single-page HTML technical readiness. Never claim actual Google rankings, AI citations, traffic loss, or full-site coverage without measurements.
- Optional schema, FAQ, numbers, lists, training permissions and llms.txt must not become universal requirements or fabricated evidence.
- Every outbound scan, redirect and auxiliary resource uses the public-network transport. Do not bypass DNS/IP, deadline, content-type or size guards.
- Avoid paid or third-party requests during tests. Preserve `PUBLIC_AI_SUMMARY=false` and preview noindex defaults.
- Run `.venv\Scripts\python.exe -m pytest tests -q` and browser smoke checks after changes to the API or user flow. Browser tests are optional dev dependencies, not production dependencies.
- `requirements.lock` is universal and hash-locked; `httpcore` transport uses private adapter interfaces, so rerun network tests after dependency changes.
- Deployment is not complete until a real host, HTTPS domain and operator contact are configured. Never report a local preview as a public launch.
- The user's global rule applies: any tool turn containing `view_image` must contain only that single tool call.
