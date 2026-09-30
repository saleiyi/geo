"""Local operator workflow. Run with ``python -m mandapi_geo.growth_cli``.

The CLI keeps repository write access and deployment attestations off the
anonymous public API. Scans still use the existing guarded public transport.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .growth import GrowthStore
from .scanner import scan


def main() -> None:
    parser = argparse.ArgumentParser(description="Local evidence-to-result workflow")
    parser.add_argument("--db", default="reports/growth.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    project = commands.add_parser("project")
    project.add_argument("name")
    project.add_argument("site_url")
    ingest = commands.add_parser("scan")
    ingest.add_argument("project_id")
    ingest.add_argument("url")
    evidence = commands.add_parser("evidence")
    evidence.add_argument("project_id")
    opportunities = commands.add_parser("opportunities")
    opportunities.add_argument("project_id")
    experiment = commands.add_parser("experiment")
    experiment.add_argument("opportunity_id")
    change = commands.add_parser("changeset")
    change.add_argument("experiment_id")
    change.add_argument("repo")
    change.add_argument("relative_file")
    change.add_argument("new_content_file", help="UTF-8 file containing the full proposed content")
    change.add_argument("instructions")
    review = commands.add_parser("review")
    review.add_argument("changeset_id")
    review.add_argument("decision", choices=("approve", "reject"))
    apply = commands.add_parser("apply")
    apply.add_argument("changeset_id")
    deploy = commands.add_parser("deploy")
    deploy.add_argument("changeset_id")
    deploy.add_argument("commit_sha")
    deploy.add_argument("deployed_at", help="ISO 8601 timestamp with timezone")
    deploy.add_argument("urls", nargs="+")
    commands.add_parser("due")
    retest = commands.add_parser("retest")
    retest.add_argument("experiment_id")
    retest.add_argument("window_days", type=int, choices=(3, 7, 14, 30))
    retest.add_argument("url")
    args = parser.parse_args()
    store = GrowthStore(args.db)

    if args.command == "project":
        result = store.create_project(args.name, args.site_url)
    elif args.command == "scan":
        report = scan(args.url, ai_summary=False)
        result = store.ingest_scan(args.project_id, report)
    elif args.command == "evidence":
        result = store.list_evidence(args.project_id)
    elif args.command == "opportunities":
        result = store.list_opportunities(args.project_id)
    elif args.command == "experiment":
        result = store.create_experiment(args.opportunity_id)
    elif args.command == "changeset":
        content = Path(args.new_content_file).read_text(encoding="utf-8")
        result = store.prepare_changeset(args.experiment_id, args.repo,
                                         args.relative_file, content, args.instructions)
    elif args.command == "review":
        result = store.review_changeset(args.changeset_id, args.decision == "approve")
    elif args.command == "apply":
        result = store.apply_changeset(args.changeset_id)
    elif args.command == "deploy":
        result = store.record_deployment(args.changeset_id, args.commit_sha,
                                         datetime.fromisoformat(args.deployed_at), args.urls)
    elif args.command == "due":
        result = store.due_retests()
    else:
        report = scan(args.url, ai_summary=False)
        result = store.record_retest(args.experiment_id, args.window_days, report)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
