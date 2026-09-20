"""CLI: python -m mandapi_geo.cli https://exemplo.com.br

É assim que geramos o primeiro Demo (Task 2) sem depender de front-end.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .report import to_markdown
from .scanner import ScanError, scan


def _force_utf8() -> None:
    # Console do Windows costuma vir em cp936/cp1252 e quebraria os acentos.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8()

    parser = argparse.ArgumentParser(
        prog="mandapi-geo",
        description="Analisa SEO técnico e visibilidade em IA (GEO) de uma página.",
    )
    parser.add_argument("url", help="URL do site a analisar")
    parser.add_argument("-k", "--keyword", help="Palavra-chave alvo (opcional)")
    parser.add_argument("--json", dest="json_path", help="Salva o relatório completo em JSON")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Adiciona análise em linguagem natural (exige LLM_API_KEY)",
    )
    args = parser.parse_args(argv)

    try:
        report = scan(args.url, keyword=args.keyword, ai_summary=args.llm)
    except ScanError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    print(to_markdown(report))

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(json.loads(report.model_dump_json()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON salvo em: {path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())