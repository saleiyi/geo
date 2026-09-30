"""Evidence-to-result contract using synthetic reports; no outbound requests."""
from datetime import datetime, timedelta, timezone
import subprocess

import pytest

from mandapi_geo.growth import GrowthStore
from mandapi_geo.models import AreaReport, Check, Issue, PageFacts, ScanReport


def report(status="fail", *, scanned_at=None, final_url="https://example.com/page",
           scoring_version="readiness-2026-09-26", weight=2.0):
    check = Check(id="title", area="seo", label="Title", status=status,
                  weight=weight, value="Missing title" if status == "fail" else "Present")
    issue = Issue(id="title", area="seo", severity="high", title="Missing title",
                  detail="Title is missing", fix="Add an accurate title", impact=80)
    facts = PageFacts(url="https://example.com/page", final_url=final_url,
                      status_code=200, elapsed_ms=30, page_bytes=400, is_https=True)
    return ScanReport(target_url="https://example.com/page", scanned_at=scanned_at or
                      datetime.now(timezone.utc), scoring_version=scoring_version,
                      areas=[AreaReport(area="seo", label="SEO", checks=[check],
                                        issues=[issue] if status == "fail" else [])],
                      issues=[issue] if status == "fail" else [], facts=facts)


def setup(tmp_path):
    store = GrowthStore(tmp_path / "growth.sqlite3")
    project = store.create_project("Example", "https://example.com")
    before = report(scanned_at=datetime.now(timezone.utc) - timedelta(days=10))
    assert store.ingest_scan(project["id"], before) == {
        "evidence_created": 1, "opportunities_linked": 1}
    opportunity = store.list_opportunities(project["id"])[0]
    experiment = store.create_experiment(opportunity["id"])
    return store, project, experiment, before


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "page.html").write_text("<title>Old</title>\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "add", "page.html"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                    "commit", "-qm", "Initial"], cwd=repo, check=True)
    return repo


def test_ingest_is_idempotent_and_opportunity_has_lineage(tmp_path):
    store, project, experiment, before = setup(tmp_path)
    assert store.ingest_scan(project["id"], before)["evidence_created"] == 0
    evidence = store.list_evidence(project["id"])
    opportunity = store.list_opportunities(project["id"])[0]
    assert len(evidence) == 1
    assert opportunity["evidence_ids"] == [evidence[0]["id"]]
    assert opportunity["commercial_intent"] == 1.0
    assert experiment["baseline_evidence_id"] == evidence[0]["id"]
    assert experiment["baseline"] == "fail"
    with pytest.raises(ValueError):
        store.ingest_scan(project["id"],
                          ScanReport(target_url="https://elsewhere.com/", facts=before.facts))


def test_changeset_review_deploy_and_retest(tmp_path):
    store, project, experiment, before = setup(tmp_path)
    repo = make_repo(tmp_path)
    change = store.prepare_changeset(experiment["id"], repo, "page.html",
                                     "<title>Useful title</title>\n", "Clarify title")
    assert "-<title>Old</title>" in change["patch"]
    assert "+<title>Useful title</title>" in change["patch"]
    assert (repo / "page.html").read_text(encoding="utf-8") == "<title>Old</title>\n"
    with pytest.raises(ValueError):
        store.record_deployment(change["id"], "a" * 40, datetime.now(timezone.utc),
                                ["https://example.com/page"])
    store.review_changeset(change["id"], True)
    applied = store.apply_changeset(change["id"])
    assert applied["branch"].startswith("codex/geo-")
    assert (repo / "page.html").read_text(encoding="utf-8") == "<title>Useful title</title>\n"
    assert len(applied["commit_sha"]) == 40
    deployed = datetime.now(timezone.utc) + timedelta(seconds=1)
    with pytest.raises(ValueError, match="cat-file"):
        store.record_deployment(change["id"], "a" * 40, deployed,
                                ["https://example.com/page"])
    with pytest.raises(ValueError, match="target URL"):
        store.record_deployment(change["id"], applied["commit_sha"], deployed,
                                ["https://example.com/other"])
    store.record_deployment(change["id"], applied["commit_sha"], deployed,
                            ["https://example.com/page"])
    assert [item["window_days"] for item in store.due_retests(deployed + timedelta(days=8))] == [3, 7]
    result = store.record_retest(experiment["id"], 3,
                                 report("pass", scanned_at=deployed + timedelta(days=3)))
    assert result["after"] == "pass"
    assert result["attribution"] == "OBSERVED"
    assert "causality is not established" in result["summary"]
    assert [item["window_days"] for item in store.due_retests(deployed + timedelta(days=8))] == [7]


def test_retest_mismatches_are_inconclusive(tmp_path):
    store, project, experiment, before = setup(tmp_path)
    repo = make_repo(tmp_path)
    change = store.prepare_changeset(experiment["id"], repo, "page.html", "new\n", "Fix")
    store.review_changeset(change["id"], True)
    applied = store.apply_changeset(change["id"])
    deployed = datetime.now(timezone.utc) + timedelta(seconds=1)
    store.record_deployment(change["id"], applied["commit_sha"], deployed,
                            ["https://example.com/page"])
    later = deployed + timedelta(days=3)
    result = store.record_retest(experiment["id"], 3,
                                 report("pass", weight=3.0, scanned_at=later))
    assert result["after"] is None
    assert result["attribution"] == "INCONCLUSIVE"
    with pytest.raises(ValueError, match="final URL"):
        store.record_retest(experiment["id"], 7,
                            report("pass", final_url="https://example.com/other",
                                   scanned_at=deployed + timedelta(days=7)))


def test_changeset_rejects_traversal_and_is_reversible(tmp_path):
    store, _, experiment, _ = setup(tmp_path)
    repo = make_repo(tmp_path)
    with pytest.raises(ValueError):
        store.prepare_changeset(experiment["id"], repo, "../outside", "x", "bad")
    change = store.prepare_changeset(experiment["id"], repo, "page.html", "new\n", "Fix")
    store.review_changeset(change["id"], False)
    with pytest.raises(ValueError):
        store.record_deployment(change["id"], "a" * 40, datetime.now(timezone.utc),
                                ["https://example.com/page"])
