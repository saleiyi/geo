"""Durable, evidence-first local growth workflow.

This is deliberately independent of the public anonymous scan API. A ScanReport
enters here only through an explicit operator action; imported browser baselines
are not authenticated evidence.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sqlite3
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .models import ScanReport
from .network import normalize_public_url

WINDOW_DAYS = (3, 7, 14, 30)
STATUSES = {"DRAFT", "READY", "IMPLEMENTING", "REVIEW", "DEPLOYED",
            "OBSERVING", "COMPLETED", "FAILED", "ABORTED"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def _git(root: Path, *args: str, input_text: str | None = None) -> str:
    command = subprocess.run(["git", *args], cwd=root, input=input_text,
                             text=True, capture_output=True, check=False)
    if command.returncode:
        raise ValueError(f"Git {args[0]} failed: {command.stderr.strip()[:300]}")
    return command.stdout.strip()


class GrowthStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    def _migrate(self) -> None:
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError(f"Unsupported growth database version: {version}")
            if version == 1:
                return
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, site_url TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    type TEXT NOT NULL, source TEXT NOT NULL, source_key TEXT NOT NULL,
                    title TEXT NOT NULL, summary TEXT NOT NULL,
                    target_url TEXT, final_url TEXT, value TEXT, unit TEXT,
                    payload_json TEXT NOT NULL, confidence TEXT NOT NULL,
                    sample_size INTEGER NOT NULL, engine TEXT,
                    schema_version TEXT, scoring_version TEXT,
                    observed_at TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS evidence_project_time ON evidence(project_id, observed_at DESC);
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    source_key TEXT NOT NULL, type TEXT NOT NULL,
                    title TEXT NOT NULL, problem TEXT NOT NULL, target_url TEXT,
                    recommended_action TEXT NOT NULL, impact TEXT NOT NULL,
                    confidence TEXT NOT NULL, effort TEXT NOT NULL,
                    commercial_intent REAL NOT NULL, evidence_strength REAL NOT NULL,
                    priority_score REAL NOT NULL, executable INTEGER NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(project_id, source_key)
                );
                CREATE TABLE IF NOT EXISTS opportunity_evidence (
                    opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
                    evidence_id TEXT NOT NULL REFERENCES evidence(id),
                    PRIMARY KEY(opportunity_id, evidence_id)
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
                    hypothesis TEXT NOT NULL, target_metric TEXT NOT NULL,
                    baseline TEXT NOT NULL, baseline_evidence_id TEXT NOT NULL REFERENCES evidence(id),
                    expected_outcome TEXT NOT NULL,
                    status TEXT NOT NULL, started_at TEXT, deployed_at TEXT,
                    ended_at TEXT, observation_windows TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS changesets (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    experiment_id TEXT NOT NULL REFERENCES experiments(id),
                    title TEXT NOT NULL, summary TEXT NOT NULL,
                    target_type TEXT NOT NULL, repository TEXT,
                    branch TEXT, base_commit TEXT, affected_files TEXT NOT NULL,
                    patch TEXT NOT NULL, instructions TEXT NOT NULL,
                    generated_by TEXT NOT NULL, model TEXT,
                    status TEXT NOT NULL, review_status TEXT NOT NULL,
                    created_at TEXT NOT NULL, applied_at TEXT
                );
                CREATE TABLE IF NOT EXISTS deployments (
                    id TEXT PRIMARY KEY, changeset_id TEXT NOT NULL REFERENCES changesets(id),
                    source TEXT NOT NULL, commit_sha TEXT, pr_number INTEGER,
                    environment TEXT NOT NULL, deployed_at TEXT NOT NULL,
                    urls TEXT NOT NULL, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL REFERENCES experiments(id),
                    metric TEXT NOT NULL, value TEXT, source TEXT NOT NULL,
                    window_days INTEGER NOT NULL, measured_at TEXT NOT NULL,
                    sample_size INTEGER NOT NULL, metadata_json TEXT NOT NULL,
                    UNIQUE(experiment_id, metric, window_days, source)
                );
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL UNIQUE REFERENCES experiments(id),
                    metric TEXT NOT NULL, baseline TEXT, after TEXT,
                    absolute_change REAL, relative_change REAL,
                    confidence TEXT NOT NULL, attribution TEXT NOT NULL,
                    summary TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS learned_rules (
                    id TEXT PRIMARY KEY, pattern TEXT NOT NULL, action_type TEXT NOT NULL,
                    sample_count INTEGER NOT NULL, positive_count INTEGER NOT NULL,
                    negative_count INTEGER NOT NULL, avg_effect REAL,
                    confidence TEXT NOT NULL, segment TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                PRAGMA user_version=1;
            """)

    def create_project(self, name: str, site_url: str) -> dict:
        name = name.strip()
        if not 1 <= len(name) <= 120:
            raise ValueError("Project name must contain 1–120 characters.")
        target = normalize_public_url(site_url)
        parsed = urlsplit(target)
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Project site_url must be a public origin.")
        origin = f"{parsed.scheme}://{parsed.netloc}"
        project = {"id": _id(), "name": name, "site_url": origin, "created_at": _now()}
        with self._connect() as db:
            db.execute("INSERT INTO projects VALUES (:id,:name,:site_url,:created_at)", project)
        return project

    def get_project(self, project_id: str) -> dict:
        with self._connect() as db:
            project = _row(db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
        if not project:
            raise ValueError("Project not found.")
        return project

    def ingest_scan(self, project_id: str, report: ScanReport) -> dict:
        project = self.get_project(project_id)
        if urlsplit(project["site_url"]).hostname != urlsplit(report.target_url).hostname:
            raise ValueError("Scan target does not belong to this project origin.")
        if report.scope != "single_page" or not report.facts:
            raise ValueError("Only an actual single-page report with fetched facts can be ingested.")
        observed_at = report.scanned_at.astimezone(timezone.utc).isoformat()
        final_url = report.facts.final_url
        issues = {(issue.area, issue.id): issue for issue in report.issues}
        created_evidence = 0
        linked_opportunities = set()
        with self._connect() as db:
            for area in report.areas:
                for check in area.checks:
                    source_key = f"{check.area}:{check.id}:{report.scoring_version}"
                    evidence_id = _fingerprint(project_id, source_key, report.target_url,
                                               final_url, observed_at, report.engine)
                    issue = issues.get((check.area, check.id))
                    payload = {
                        "check_id": check.id, "area": check.area, "status": check.status,
                        "weight": check.weight,
                        "hint": check.hint, "issue_id": issue.id if issue else None,
                        "issue_detail": issue.detail if issue else None,
                    }
                    evidence = {
                        "id": evidence_id, "project_id": project_id,
                        "type": "TECHNICAL_FINDING", "source": "crawl",
                        "source_key": source_key, "title": check.label,
                        "summary": issue.detail if issue else (check.hint or check.label),
                        "target_url": report.target_url, "final_url": final_url,
                        "value": check.value, "unit": None,
                        "payload_json": json.dumps(payload, ensure_ascii=False),
                        "confidence": "LOW" if check.status == "info" else "MEDIUM",
                        "sample_size": 1, "engine": report.engine,
                        "schema_version": str(report.schema_version),
                        "scoring_version": report.scoring_version,
                        "observed_at": observed_at, "created_at": _now(),
                    }
                    cursor = db.execute("""
                        INSERT OR IGNORE INTO evidence
                        (id,project_id,type,source,source_key,title,summary,target_url,final_url,
                         value,unit,payload_json,confidence,sample_size,engine,schema_version,
                         scoring_version,observed_at,created_at)
                        VALUES
                        (:id,:project_id,:type,:source,:source_key,:title,:summary,:target_url,:final_url,
                         :value,:unit,:payload_json,:confidence,:sample_size,:engine,:schema_version,
                         :scoring_version,:observed_at,:created_at)
                    """, evidence)
                    created_evidence += cursor.rowcount
                    if not issue or check.status not in {"warn", "fail"}:
                        continue
                    opportunity_key = f"{report.target_url}:{check.area}:{check.id}"
                    existing = db.execute(
                        "SELECT id,status FROM opportunities WHERE project_id=? AND source_key=?",
                        (project_id, opportunity_key),
                    ).fetchone()
                    impact = max(1, min(5, round(issue.impact / 20) or 1))
                    confidence = 0.7 if check.status == "fail" else 0.5
                    evidence_strength = 0.7 if check.value else 0.5
                    effort = 2 if check.area == "seo" else 3
                    # Commercial intent is neutral until actual query data exists.
                    priority = round(impact * confidence * evidence_strength / effort, 4)
                    opportunity_id = existing["id"] if existing else _id()
                    if not existing:
                        db.execute("""
                            INSERT INTO opportunities
                            (id,project_id,source_key,type,title,problem,target_url,recommended_action,
                             impact,confidence,effort,commercial_intent,evidence_strength,priority_score,
                             executable,status,created_at,updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            opportunity_id, project_id, opportunity_key,
                            "TECHNICAL_FIX" if check.area == "seo" else "AI_READABILITY",
                            issue.title, issue.detail, report.target_url, issue.fix,
                            "HIGH" if impact >= 4 else "MEDIUM" if impact >= 2 else "LOW",
                            "MEDIUM" if confidence >= 0.7 else "LOW",
                            "LOW" if effort == 2 else "MEDIUM", 1.0, evidence_strength,
                            priority, 0, "OPEN", _now(), _now(),
                        ))
                    if existing and existing["status"] == "OPEN":
                        db.execute("""
                            UPDATE opportunities SET problem=?,recommended_action=?,
                                priority_score=?,updated_at=? WHERE id=?
                        """, (issue.detail, issue.fix, priority, _now(), opportunity_id))
                    db.execute(
                        "INSERT OR IGNORE INTO opportunity_evidence VALUES (?,?)",
                        (opportunity_id, evidence_id),
                    )
                    linked_opportunities.add(opportunity_id)
        return {"evidence_created": created_evidence,
                "opportunities_linked": len(linked_opportunities)}

    def list_evidence(self, project_id: str) -> list[dict]:
        self.get_project(project_id)
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM evidence WHERE project_id=? ORDER BY observed_at DESC,id",
                (project_id,),
            )]

    def list_opportunities(self, project_id: str) -> list[dict]:
        self.get_project(project_id)
        with self._connect() as db:
            rows = [dict(row) for row in db.execute(
                "SELECT * FROM opportunities WHERE project_id=? ORDER BY priority_score DESC,id",
                (project_id,),
            )]
            for row in rows:
                row["evidence_ids"] = [item[0] for item in db.execute(
                    "SELECT evidence_id FROM opportunity_evidence WHERE opportunity_id=? ORDER BY evidence_id",
                    (row["id"],),
                )]
        return rows

    def create_experiment(self, opportunity_id: str) -> dict:
        with self._connect() as db:
            opportunity = _row(db.execute(
                "SELECT * FROM opportunities WHERE id=?", (opportunity_id,)
            ).fetchone())
            if not opportunity:
                raise ValueError("Opportunity not found.")
            if opportunity["status"] != "OPEN":
                raise ValueError("Opportunity is not open.")
            baseline_row = db.execute("""
                SELECT e.id,e.payload_json FROM evidence e
                JOIN opportunity_evidence oe ON oe.evidence_id=e.id
                WHERE oe.opportunity_id=? ORDER BY e.observed_at DESC LIMIT 1
            """, (opportunity_id,)).fetchone()
            if not baseline_row:
                raise ValueError("Opportunity has no baseline evidence.")
            baseline = json.loads(baseline_row["payload_json"])["status"]
            experiment = {
                "id": _id(), "project_id": opportunity["project_id"],
                "opportunity_id": opportunity_id,
                "hypothesis": f"If we apply this change, the same check may improve: {opportunity['recommended_action']}",
                "target_metric": "CHECK_STATUS", "baseline": baseline,
                "baseline_evidence_id": baseline_row["id"],
                "expected_outcome": "A later scan of the same final URL passes the same check.",
                "status": "DRAFT", "started_at": None, "deployed_at": None,
                "ended_at": None, "observation_windows": json.dumps(WINDOW_DAYS),
                "created_at": _now(),
            }
            db.execute("""
                INSERT INTO experiments VALUES
                (:id,:project_id,:opportunity_id,:hypothesis,:target_metric,:baseline,:baseline_evidence_id,
                 :expected_outcome,:status,:started_at,:deployed_at,:ended_at,
                 :observation_windows,:created_at)
            """, experiment)
            db.execute("UPDATE opportunities SET status='IN_EXPERIMENT',updated_at=? WHERE id=?",
                       (_now(), opportunity_id))
        return experiment

    def prepare_changeset(self, experiment_id: str, repo_path: str | Path,
                          relative_file: str, new_content: str, instructions: str,
                          generated_by: str = "human", model: str | None = None) -> dict:
        """Store a real diff for review; never modify the repository."""
        with self._connect() as db:
            experiment = _row(db.execute(
                "SELECT * FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone())
            if not experiment or experiment["status"] not in {"DRAFT", "READY"}:
                raise ValueError("Experiment is missing or cannot accept a new ChangeSet.")
        root = Path(repo_path).resolve(strict=True)
        if not (root / ".git").exists():
            raise ValueError("Repository is missing.")
        relative = Path(relative_file)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("File path must stay inside the repository.")
        target = (root / relative).resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError("File is missing or outside the repository.")
        if target.stat().st_size > 256_000 or len(new_content.encode("utf-8")) > 256_000:
            raise ValueError("ChangeSet exceeds the local file size limit.")
        original = target.read_text(encoding="utf-8")
        if _git(root, "ls-files", "--error-unmatch", "--", relative.as_posix()) == "":
            raise ValueError("File must be tracked by Git.")
        if _git(root, "status", "--porcelain", "--", relative.as_posix()):
            raise ValueError("Target file has uncommitted changes.")
        base_commit = _git(root, "rev-parse", "HEAD")
        patch = "".join(difflib.unified_diff(
            original.splitlines(keepends=True), new_content.splitlines(keepends=True),
            fromfile=f"a/{relative.as_posix()}", tofile=f"b/{relative.as_posix()}",
        ))
        if not patch or not patch.startswith("--- a/") or "\n+++ b/" not in patch:
            raise ValueError("Proposed content does not produce a valid non-empty diff.")
        changeset = {
            "id": _id(), "project_id": experiment["project_id"],
            "experiment_id": experiment_id, "title": f"Review {relative.as_posix()}",
            "summary": instructions[:500], "target_type": "LOCAL_REPO",
            "repository": str(root), "branch": None, "base_commit": base_commit,
            "affected_files": json.dumps([relative.as_posix()]),
            "patch": patch, "instructions": instructions[:2000],
            "generated_by": generated_by, "model": model,
            "status": "READY", "review_status": "PENDING",
            "created_at": _now(), "applied_at": None,
        }
        with self._connect() as db:
            db.execute("""
                INSERT INTO changesets VALUES
                (:id,:project_id,:experiment_id,:title,:summary,:target_type,
                 :repository,:branch,:base_commit,:affected_files,:patch,:instructions,
                 :generated_by,:model,:status,:review_status,:created_at,:applied_at)
            """, changeset)
            db.execute("UPDATE experiments SET status='REVIEW' WHERE id=?", (experiment_id,))
        return changeset

    def apply_changeset(self, changeset_id: str) -> dict:
        """Apply an approved patch on a new local branch and commit it."""
        with self._connect() as db:
            changeset = _row(db.execute(
                "SELECT * FROM changesets WHERE id=?", (changeset_id,)
            ).fetchone())
        if not changeset or changeset["review_status"] != "APPROVED" or changeset["status"] != "REVIEWED":
            raise ValueError("Only an approved, unapplied ChangeSet can be committed.")
        root = Path(changeset["repository"]).resolve(strict=True)
        if not (root / ".git").exists() or _git(root, "rev-parse", "HEAD") != changeset["base_commit"]:
            raise ValueError("Repository HEAD changed after ChangeSet creation.")
        if _git(root, "status", "--porcelain"):
            raise ValueError("Repository must be clean before applying a ChangeSet.")
        branch = f"codex/geo-{changeset_id[:12]}"
        _git(root, "apply", "--check", "-", input_text=changeset["patch"])
        _git(root, "switch", "-c", branch)
        try:
            _git(root, "apply", "-", input_text=changeset["patch"])
            files = json.loads(changeset["affected_files"])
            _git(root, "add", "--", *files)
            _git(root, "-c", "user.name=GEO Local Operator",
                 "-c", "user.email=geo-local@example.invalid",
                 "commit", "-m", changeset["title"])
            commit_sha = _git(root, "rev-parse", "HEAD")
        except Exception:
            _git(root, "reset", "--hard", changeset["base_commit"])
            _git(root, "switch", "-")
            _git(root, "branch", "-D", branch)
            raise
        with self._connect() as db:
            db.execute("UPDATE changesets SET status='COMMITTED',branch=?,applied_at=? WHERE id=?",
                       (branch, _now(), changeset_id))
            db.execute("UPDATE experiments SET status='IMPLEMENTING' WHERE id=?",
                       (changeset["experiment_id"],))
        return {"changeset_id": changeset_id, "branch": branch,
                "commit_sha": commit_sha, "repository": str(root)}

    def review_changeset(self, changeset_id: str, approved: bool) -> dict:
        with self._connect() as db:
            changeset = _row(db.execute(
                "SELECT * FROM changesets WHERE id=?", (changeset_id,)
            ).fetchone())
            if not changeset or changeset["review_status"] != "PENDING":
                raise ValueError("ChangeSet is missing or already reviewed.")
            review_status = "APPROVED" if approved else "REJECTED"
            status = "REVIEWED" if approved else "REJECTED"
            db.execute("UPDATE changesets SET review_status=?,status=? WHERE id=?",
                       (review_status, status, changeset_id))
            if not approved:
                db.execute("UPDATE experiments SET status='DRAFT' WHERE id=?",
                           (changeset["experiment_id"],))
            changeset.update(review_status=review_status, status=status)
        return changeset

    def record_deployment(self, changeset_id: str, commit_sha: str,
                          deployed_at: datetime, urls: list[str]) -> dict:
        if deployed_at.tzinfo is None or not commit_sha or not urls:
            raise ValueError("Deployment needs a commit, timezone-aware date and affected URLs.")
        with self._connect() as db:
            changeset = _row(db.execute(
                "SELECT * FROM changesets WHERE id=?", (changeset_id,)
            ).fetchone())
            if not changeset or changeset["review_status"] != "APPROVED" or changeset["status"] != "COMMITTED":
                raise ValueError("Only an approved and committed ChangeSet can be deployed.")
            if deployed_at.astimezone(timezone.utc) < datetime.fromisoformat(changeset["applied_at"]):
                raise ValueError("Deployment cannot precede the local commit.")
            if not re.fullmatch(r"[0-9a-f]{40,64}", commit_sha):
                raise ValueError("Deployment commit must be a full Git SHA.")
            root = Path(changeset["repository"]).resolve(strict=True)
            branch_commit = _git(root, "rev-parse", changeset["branch"])
            if _git(root, "cat-file", "-t", commit_sha) != "commit":
                raise ValueError("Deployment SHA is not a commit in the local repository.")
            _git(root, "merge-base", "--is-ancestor", branch_commit, commit_sha)
            if db.execute("SELECT 1 FROM deployments WHERE changeset_id=?",
                          (changeset_id,)).fetchone():
                raise ValueError("Deployment already recorded.")
            project = self.get_project(changeset["project_id"])
            host = urlsplit(project["site_url"]).hostname
            normalized = [normalize_public_url(url) for url in urls]
            if any(urlsplit(url).hostname != host for url in normalized):
                raise ValueError("Affected URLs must belong to the project origin.")
            target_url = db.execute("""
                SELECT o.target_url FROM opportunities o
                JOIN experiments e ON e.opportunity_id=o.id
                WHERE e.id=?
            """, (changeset["experiment_id"],)).fetchone()[0]
            if target_url not in normalized:
                raise ValueError("Affected URLs must include the experiment target URL.")
            deployment = {
                "id": _id(), "changeset_id": changeset_id, "source": "manual",
                "commit_sha": commit_sha, "pr_number": None,
                "environment": "production", "deployed_at": deployed_at.isoformat(),
                "urls": json.dumps(normalized), "status": "RECORDED",
            }
            db.execute("""
                INSERT INTO deployments VALUES
                (:id,:changeset_id,:source,:commit_sha,:pr_number,:environment,
                 :deployed_at,:urls,:status)
            """, deployment)
            db.execute("UPDATE changesets SET status='DEPLOYED',applied_at=? WHERE id=?",
                       (deployment["deployed_at"], changeset_id))
            db.execute("""
                UPDATE experiments SET status='OBSERVING',deployed_at=?,started_at=COALESCE(started_at,?)
                WHERE id=?
            """, (deployment["deployed_at"], deployment["deployed_at"], changeset["experiment_id"]))
        return deployment

    def due_retests(self, now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        due = []
        with self._connect() as db:
            for experiment in db.execute(
                "SELECT * FROM experiments WHERE status='OBSERVING' AND deployed_at IS NOT NULL"
            ):
                deployed = datetime.fromisoformat(experiment["deployed_at"])
                for days in json.loads(experiment["observation_windows"]):
                    if deployed + timedelta(days=days) > now:
                        continue
                    if db.execute("""
                        SELECT 1 FROM observations WHERE experiment_id=? AND metric='CHECK_STATUS'
                        AND window_days=? AND source='crawl'
                    """, (experiment["id"], days)).fetchone():
                        continue
                    due.append({"experiment_id": experiment["id"], "window_days": days,
                                "target_url": db.execute("""
                                    SELECT target_url FROM opportunities WHERE id=?
                                """, (experiment["opportunity_id"],)).fetchone()[0]})
        return due

    def record_retest(self, experiment_id: str, window_days: int,
                      report: ScanReport) -> dict:
        if window_days not in WINDOW_DAYS or not report.facts:
            raise ValueError("Invalid re-test window or missing page facts.")
        with self._connect() as db:
            experiment = _row(db.execute(
                "SELECT * FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone())
            if not experiment or experiment["status"] != "OBSERVING":
                raise ValueError("A recorded deployment is required before observing.")
            if report.scanned_at.tzinfo is None or report.scanned_at.astimezone(timezone.utc) < (
                datetime.fromisoformat(experiment["deployed_at"]) + timedelta(days=window_days)
            ):
                raise ValueError("Re-test was scanned before its observation window.")
            opportunity = _row(db.execute(
                "SELECT * FROM opportunities WHERE id=?", (experiment["opportunity_id"],)
            ).fetchone())
            if report.target_url != opportunity["target_url"]:
                raise ValueError("Re-test must use the same requested URL.")
            original_evidence = db.execute(
                "SELECT * FROM evidence WHERE id=?", (experiment["baseline_evidence_id"],)
            ).fetchone()
            if not original_evidence or report.facts.final_url != original_evidence["final_url"]:
                raise ValueError("Re-test final URL differs from baseline.")
            key = json.loads(original_evidence["payload_json"])
            check = next((check for area in report.areas for check in area.checks
                          if check.area == key["area"] and check.id == key["check_id"]), None)
            comparable = (report.engine == original_evidence["engine"]
                          and str(report.schema_version) == original_evidence["schema_version"]
                          and report.scoring_version == original_evidence["scoring_version"]
                          and check is not None and check.weight == key["weight"])
            status = check.status if comparable else None
            observation = {
                "id": _id(), "experiment_id": experiment_id, "metric": "CHECK_STATUS",
                "value": status, "source": "crawl", "window_days": window_days,
                "measured_at": report.scanned_at.isoformat(), "sample_size": 1,
                "metadata_json": json.dumps({
                    "comparable": comparable, "reason": None if comparable else "version_or_check_mismatch",
                    "engine": report.engine, "scoring_version": report.scoring_version,
                    "check_id": key["check_id"], "target_url": report.target_url,
                    "final_url": report.facts.final_url,
                }),
            }
            db.execute("""
                INSERT INTO observations VALUES
                (:id,:experiment_id,:metric,:value,:source,:window_days,
                 :measured_at,:sample_size,:metadata_json)
                ON CONFLICT(experiment_id,metric,window_days,source)
                DO UPDATE SET value=excluded.value,measured_at=excluded.measured_at,
                    metadata_json=excluded.metadata_json
            """, observation)
            baseline = experiment["baseline"]
            improved = baseline in {"warn", "fail"} and status == "pass"
            summary = ("The same check passed after deployment; causality is not established."
                       if improved else "No comparable confirmed fix was observed.")
            result = {
                "id": _id(), "experiment_id": experiment_id, "metric": "CHECK_STATUS",
                "baseline": baseline, "after": status, "absolute_change": None,
                "relative_change": None,
                "confidence": "MEDIUM" if comparable else "LOW",
                "attribution": "OBSERVED" if comparable else "INCONCLUSIVE",
                "summary": summary, "created_at": _now(),
            }
            db.execute("""
                INSERT INTO results VALUES
                (:id,:experiment_id,:metric,:baseline,:after,:absolute_change,
                 :relative_change,:confidence,:attribution,:summary,:created_at)
                ON CONFLICT(experiment_id)
                DO UPDATE SET after=excluded.after,confidence=excluded.confidence,
                    attribution=excluded.attribution,summary=excluded.summary,
                    created_at=excluded.created_at
            """, result)
        return result
