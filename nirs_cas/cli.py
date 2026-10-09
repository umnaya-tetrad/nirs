import argparse
import json
from pathlib import Path

from .parser import parse_latex
from .benchmark import run_benchmark, run_isolated


def main():
    parser = argparse.ArgumentParser(description="Common LaTeX → SymPy parser and CAS feasibility check")
    commands = parser.add_subparsers(dest="command", required=True)
    parse = commands.add_parser("parse")
    parse.add_argument("latex")
    verify = commands.add_parser("verify")
    verify.add_argument("step_i")
    verify.add_argument("step_next")
    verify.add_argument("--timeout", type=float, default=10)
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("dataset", type=Path)
    benchmark.add_argument("--output", type=Path, default=Path("reports/local"))
    benchmark.add_argument("--timeout", type=float, default=10)
    oracle = commands.add_parser("oracle", help="GT/E2E or saved extraction JSON → CAS; only steps[].latex")
    oracle.add_argument("inputs", type=Path, nargs="+")
    oracle.add_argument("--output", type=Path, default=Path("reports/local/gt"))
    oracle.add_argument("--timeout", type=float, default=10)
    oracle.add_argument("--workers", type=int, default=4)
    oracle.add_argument("--split-name", default="exploratory_gt")
    oracle.add_argument("--mode", choices=("ordinary", "exact"), default="ordinary")
    assisted = commands.add_parser("assisted-oracle", help="Saved assisted extraction JSON → task-aware CAS")
    assisted.add_argument("inputs", type=Path, nargs="+")
    assisted.add_argument("--output", type=Path, required=True)
    assisted.add_argument("--timeout", type=float, default=10)
    assisted.add_argument("--split-name", default="assisted_extraction")
    compare = commands.add_parser("assisted-compare", help="Frozen Gemini dev-20: OCR CAS versus assisted TaskSpec CAS")
    compare.add_argument("--ordinary", type=Path, required=True)
    compare.add_argument("--assisted", type=Path, required=True)
    compare.add_argument("--gt", type=Path, required=True)
    compare.add_argument("--output", type=Path, default=Path("reports/local/assisted_comparison"))
    mixed = commands.add_parser("assisted-mixed-coverage", help="Frozen mixed-20 assisted engineering coverage")
    mixed.add_argument("--bundle", type=Path, required=True)
    mixed.add_argument("--output", type=Path, default=Path("reports/local/assisted_mixed"))
    improvement = commands.add_parser("improvement-report", help="Compare completed GT/OCR runs; labels enter reporting only")
    improvement.add_argument("--before", type=Path, required=True)
    improvement.add_argument("--after", type=Path, required=True)
    improvement.add_argument("--ocr", type=Path, required=True)
    improvement.add_argument("--gt", type=Path, nargs="+", required=True)
    improvement.add_argument("--output", type=Path, required=True)
    subset = commands.add_parser("supported-subset", help="Freeze CAS-supported IDs from a completed GT→CAS report")
    subset.add_argument("--oracle-report", type=Path, required=True)
    subset.add_argument("--gt", type=Path, nargs="+", required=True,
                        help="GT file(s) defining the candidate split and its order")
    subset.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "parse":
            result = parse_latex(args.latex).to_dict()
        elif args.command == "verify":
            result = run_isolated([args.step_i, args.step_next], args.timeout)
        elif args.command == "oracle":
            from .oracle import run_oracle
            result = run_oracle(args.inputs, args.output, timeout=args.timeout, workers=args.workers, split_name=args.split_name, mode=args.mode)["summary"]
        elif args.command == "assisted-oracle":
            from .assisted_runner import run_assisted_oracle
            result = run_assisted_oracle(args.inputs, args.output, Path(__file__).resolve().parents[1], timeout=args.timeout, split_name=args.split_name)["summary"]
        elif args.command == "assisted-compare":
            from .assisted_oracle import run_comparison
            result = run_comparison(args.ordinary, args.assisted, args.gt, args.output, Path(__file__).resolve().parents[1])["assisted"]["metrics"]
        elif args.command == "assisted-mixed-coverage":
            from .assisted_oracle import run_mixed_coverage
            result = {"examples": len(run_mixed_coverage(args.bundle, args.output, Path(__file__).resolve().parents[1])["results"])}
        elif args.command == "improvement-report":
            from .improvement_report import write_improvement_report
            result = write_improvement_report(args.before, args.after, args.ocr, args.gt, args.output, Path(__file__).resolve().parents[1])["metrics"]
        elif args.command == "supported-subset":
            from .subset import build_supported_subset
            result = build_supported_subset(args.oracle_report, args.gt, args.output)
        else:
            result = run_benchmark(args.dataset, args.output, args.timeout)["summary"]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    # PowerShell on some Windows machines still exposes a cp1251 stdout.  The
    # CLI result is intended for machine consumption, so ASCII escapes make
    # every subcommand printable without altering the UTF-8 result files.
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
