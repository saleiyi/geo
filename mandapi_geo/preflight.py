"""Read-only deployment configuration check. No network or credential output.

python -m mandapi_geo.preflight --stage preview
"""
from __future__ import annotations

import argparse
import json

from .config import Settings, load_settings


def assess(settings: Settings, stage: str) -> dict:
    if stage not in {'local', 'preview', 'production'}:
        raise ValueError('Unknown deployment stage.')
    blocking = [] if stage == 'local' else list(settings.publication_missing)
    if stage == 'preview' and settings.site_indexable:
        blocking.append('PREVIEW_MUST_REMAIN_NOINDEX')
    if stage == 'production' and not settings.site_indexable:
        blocking.append('SITE_INDEXABLE_TRUE')
    warnings = ['Quota is process-local; use one worker and one instance.']
    if settings.public_ai_summary:
        warnings.append('Public LLM summaries are enabled; verify provider costs and disclosure before inviting users.')
    if stage == 'production' and not settings.google_site_verification:
        warnings.append('Search Console verification is not configured; ownership can also be verified using DNS.')
    return {
        'stage': stage,
        'configuration_ready': not blocking,
        'blocking': blocking,
        'warnings': warnings,
        'not_verified': [
            'Accuracy of the supplied operator and logging statements.',
            'Live HTTPS, deployment, container limits and rollback.',
            'Trusted proxy identity and quota isolation between real clients.',
            'Outbound DNS/HTTP(S), scan completion and edge timeouts.',
            'Customer use, willingness to pay and profitability.',
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['local', 'preview', 'production'], default='preview')
    args = parser.parse_args(argv)
    try:
        result = assess(load_settings(), args.stage)
    except ValueError:
        # Do not repeat malformed env values, URLs, tokens or credentials in logs.
        result = {'stage': args.stage, 'configuration_ready': False,
                  'blocking': ['INVALID_CONFIGURATION'],
                  'help': 'Check SITE_URL, operator field lengths, CONTACT_EMAIL and SITE_INDEXABLE prerequisites.'}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['configuration_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
