# Local growth loop

The public scanner remains a free, anonymous, single-page audit. The local
operator workflow persists its results in SQLite and keeps Git write access
outside the public API. It does not measure rankings, GSC traffic, or AI
citations. A project URL is a grouping key, not proof of ownership.

Use `.venv\Scripts\python.exe -m mandapi_geo.growth_cli --db reports/growth.sqlite3`
followed by one of these commands:

```text
project NAME https://example.com
scan PROJECT_ID https://example.com/page
evidence PROJECT_ID
opportunities PROJECT_ID
experiment OPPORTUNITY_ID
changeset EXPERIMENT_ID REPO_PATH RELATIVE_FILE NEW_CONTENT_FILE "Why this fixes the finding"
review CHANGESET_ID approve|reject
apply CHANGESET_ID
deploy CHANGESET_ID COMMIT_SHA 2026-10-01T12:00:00+00:00 https://example.com/page
due
retest EXPERIMENT_ID 3|7|14|30 https://example.com/page
```

`scan` and `retest` make real requests through the existing guarded public
transport. `changeset` stores a diff for an existing tracked file and does not
alter it. `review approve` is the explicit human gate. `apply` requires a clean
repository at the original commit, checks the patch, creates a local
`codex/geo-*` branch, applies it, and commits it. It does not push or open a PR.
`deploy` is a manual operator attestation, accepted only after a committed
ChangeSet; it is not a deployment detector. `due` lists observation windows
after deployment. A result records the same check's status only when the
requested URL, final URL, engine, schema, scoring version, and check weight
match the frozen baseline. A passing check is an observed technical change,
not proof of search or business impact.

The SQLite file is local and ignored under `reports/`; back it up if used for
real projects. There is no user authentication or tenant isolation, so do not
expose this CLI or database as a hosted multi-tenant service. Existing free
audit routes and trilingual pages remain unchanged.

The current local acceptance test uses synthetic scan reports and a temporary
Git repository. A real dogfood result requires a site the operator controls,
a connected repository, a real deployment, and later live re-tests. GSC and AI
visibility integrations also require real authorized data sources. These
external PASS criteria remain open until those inputs exist.
