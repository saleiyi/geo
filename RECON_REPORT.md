# SEO/GEO execution loop — PASS 0 recon

Date: 2026-09-30. This report describes the repository as found before domain-model work.

## Current architecture and routes

| Area | Existing implementation | Reuse for execution loop |
| --- | --- | --- |
| Stack | Python 3.10+, FastAPI, Pydantic v2, static HTML/CSS/JS; no frontend build step | Keep all of it. Add narrow project APIs and pages. |
| Pages | PT at `/`, EN at `/en`, ZH at `/zh`; methodology, privacy and guide in all three locales | Preserve routes and reciprocal hreflang. New project UI should not replace the free audit. |
| API | `GET /health`, `GET /api/capabilities`, `POST /api/scan`; static assets, robots and sitemap | `/api/scan` remains the free single-page evidence source. |
| Scan | `scanner.py` orchestrates guarded fetch, parser, SEO/GEO analyzers, scoring, optional LLM summary | Convert actual checks and issues through an adapter. Preserve their source report and versions. |
| Transport | `network.py` and `fetcher.py` enforce public-address DNS/IP, redirect, timeout, type and size checks | Any future crawl or re-test must use this transport. |
| Report | `ScanReport` with raw observed facts, checks, issues, rule versions and limitations | Existing checks and facts supply traceable technical Evidence. No visibility measurements exist. |
| Comparison | Browser-local, explicit single baseline in `comparison.js`; version, URL, coverage and time guards | Preserve as free-audit flow; project outcomes need separately stored observations. |
| AI | OpenAI-compatible chat-completions URL and operator key; optional summary only, no structured patch agent | May generate reviewed proposals later. Keep key server-side, cost bounds and fail-soft. |
| Limits | Single-process in-memory IP-based daily quota and concurrency guard | Cannot serve as project authentication, durable jobs or paid-provider quota isolation. |

## Data, authentication and integrations

- **Database / ORM / migrations:** none. No production tables exist. A new SQLite-backed project store can be additive, but multi-worker hosting will need a shared database before scale.
- **Auth / projects / sites:** none. The app accepts an arbitrary public URL but does not establish ownership of a site or repository. Project mutation routes must remain disabled for public anonymous users until an operator/auth boundary exists.
- **GitHub:** this development checkout has a remote, but the product has no user-level GitHub integration, OAuth/App installation, repository permissions or PR service. The operator's CLI login is not customer authorization.
- **GSC, SERP, AI visibility, competitor data, bot logs:** no connectors, credentials, measurements, sampling records or claims of coverage. A Search Console verification meta tag is only publication configuration, not GSC API access.
- **Content writer / CMS:** no content-writing workflow or WordPress/CMS connector in this repository. Optional LLM text is a report summary.
- **Background jobs / queues / scheduler:** none. Uvicorn serves requests directly. In-process timers would not be durable across restarts or replicas.

## Existing tests and deploy shape

- Python tests cover parser, analyzers, API, public-network safety, publication and report behavior. JS tests cover baseline comparison. Optional Playwright smoke checks the three locales and free-audit flow.
- Docker, Compose and Render templates exist, but no real HTTPS domain, operator contact, GSC connection or deployed product is configured. Preview is noindex by default.
- `requirements.lock` is universal and hash-locked. Additive standard-library SQLite is the least disruptive persistence starting point.

## Gaps and migration risks

1. The requested Evidence → Opportunity → Experiment → ChangeSet → Deployment → Observation → Result chain is absent. Existing `Issue` is a scan finding, not an Opportunity.
2. The proposed full-site, rendered DOM, GSC, SERP, AI-visibility and competitor examples cannot be presented as facts. Only single-page HTML observations can be ingested now.
3. No identity or authorization protects project/repository mutations. Public PR creation or CMS editing would be unsafe; an explicit operator-only boundary is required before these routes can be exposed.
4. No owned site, GSC property, production deployment or customer repository has been supplied. Real dogfood can prove only the stages backed by actual available evidence until those connections exist.
5. Browser-local baseline imports are unauthenticated. They must never establish deployments or measured outcomes in the durable project store.
6. Any re-test must preserve final URL, engine, schema/scoring version, coverage and weights before claiming a score change. A deployment timestamp alone does not prove causality.

## Narrow implementation path

1. Add durable, normalized domain tables and an adapter from actual `ScanReport` checks/issues. Preserve the current free audit.
2. Produce bounded, evidence-linked technical Opportunities. Label unavailable data sources instead of filling them with examples.
3. Build reviewable minimal ChangeSets and a human-gated branch/PR path. Do not merge or publish automatically.
4. Bind deployment evidence, schedule targeted re-tests and show before/after observations with `OBSERVED` or `INCONCLUSIVE` attribution.
5. Add GSC and measured AI-visibility adapters only when credentials, ownership and sampling contract are available.

PASS 0 acceptance: completed read-only assessment. No product code was changed during this pass.
