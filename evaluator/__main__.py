"""CLI entry point: `python -m evaluator experiment` or legacy `python -m evaluator cases`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .evaluator import main as cases_main
from .experiment import run_experiment


def _experiment(argv: list[str]) -> dict[str, Any]:
    parser = argparse.ArgumentParser(prog="evaluator experiment", description="Run the H1/H2/H3 experiment from a manifest.")
    parser.add_argument("--manifest", type=Path, required=True, help="Experiment manifest JSON.")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/evaluation_experiment"), help="Directory for report.json, cases.csv, h1_paired.csv, h2_ocr.csv, h3_routing.csv and report.md.")
    args = parser.parse_args(argv)
    payload = run_experiment(args.manifest.resolve(), args.output_dir.resolve())
    for key, pair in payload["h1"]["pairs"].items():
        paired = pair["paired"]
        print(f"h1[{key}] accuracy e2e={pair['e2e']['accuracy_all']:.2%} cas={pair['cas']['accuracy_all']:.2%} "
              f"mcnemar_p={paired['mcnemar_exact_p']:.4f}")
    if payload["h2"]["overall"]:
        h2 = payload["h2"]["overall"]
        suffix = (f" cas_accuracy_drop={h2['verdict_accuracy_drop']:+.3f}"
                  if h2.get("verdict_accuracy_drop") is not None else " cas_on_gt=not_used")
        print(f"h2 exact_match={h2['exact_match_rate']:.2%}{suffix}")
    for key, pair in payload["h3"]["pairs"].items():
        for name, stats in pair["policies"].items():
            print(f"h3[{key}:{name}] accuracy={stats['accuracy_all']:.2%} automation={stats['automation_rate']:.2%}")
    print(f"wrote {args.output_dir.resolve()}")
    return payload


def main(argv: list[str] | None = None) -> Any:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "experiment":
        return _experiment(argv[1:])
    if argv and argv[0] == "cases":
        return cases_main(argv[1:])
    if argv and argv[0] in ("-h", "--help"):
        print("usage: python -m evaluator {experiment,cases} [options]")
        return {}
    print("usage: python -m evaluator {experiment,cases} [options]", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
