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
    args = parser.parse_args()
    try:
        if args.command == "parse":
            result = parse_latex(args.latex).to_dict()
        elif args.command == "verify":
            result = run_isolated([args.step_i, args.step_next], args.timeout)
        elif args.command == "oracle":
            from .oracle import run_oracle
            result = run_oracle(args.inputs, args.output, timeout=args.timeout, workers=args.workers, split_name=args.split_name)["summary"]
        else:
            result = run_benchmark(args.dataset, args.output, args.timeout)["summary"]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
