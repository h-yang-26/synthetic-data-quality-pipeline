"""Command line. Exit codes: 0 = processing completed (row exceptions are reviewable
output, not failure); 2 = fatal file/configuration error. Input validation precedes
output writes; an output I/O failure can leave partial files."""
import argparse
import sys

from dq_pipeline.errors import FatalError
from dq_pipeline.generate import write_sample
from dq_pipeline.pipeline import run

DEFAULT_INPUT, DEFAULT_MAPPING, DEFAULT_OUT = "data/sample_input.csv", "data/reference_mapping.csv", "outputs"


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m dq_pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write the fictional sample input and mapping")
    g.add_argument("--input", default=DEFAULT_INPUT)
    g.add_argument("--mapping", default=DEFAULT_MAPPING)
    g.add_argument("--seed", type=int, default=42)
    for name, helptext in (("run", "process an existing input"), ("demo", "generate sample data, then process it")):
        r = sub.add_parser(name, help=helptext)
        r.add_argument("--input", default=DEFAULT_INPUT)
        r.add_argument("--mapping", default=DEFAULT_MAPPING)
        r.add_argument("--output-dir", default=DEFAULT_OUT)
        if name == "demo":
            r.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)
    try:
        if args.cmd in ("generate", "demo"):
            write_sample(args.input, args.mapping, args.seed)
            print(f"wrote {args.input} and {args.mapping}")
        if args.cmd in ("run", "demo"):
            s = run(args.input, args.mapping, args.output_dir)
            print(f"input={s['input_rows']} accepted={s['accepted_rows']} rejected={s['rejected_rows']} "
                  f"issues={s['issue_count']} -> {args.output_dir}")
    except FatalError as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 2
    return 0
