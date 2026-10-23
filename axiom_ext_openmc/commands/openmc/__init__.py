# Copyright (c) 2026 The University of Texas at Austin and B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""``axiom-openmc`` verbs. Each verb calls ``axiom_ext_openmc.library``.

The verb names are the imperative set AEOS §4.3 checks. ``show`` summarizes
a model, ``stat`` reads a statepoint, ``diff`` compares two, ``check`` looks
at cross-section data, ``review`` is the dry run, and ``validate`` checks
the XML. None of them starts OpenMC.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from axiom_ext_openmc import library

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """Parser ``axi ext lint`` walks. Subcommand names are the verbs."""
    parser = argparse.ArgumentParser(
        prog="axiom-openmc",
        description="Inspect an OpenMC model and its statepoints without starting a solve.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Check materials, geometry, settings, and tallies.")
    validate.add_argument("input_dir")
    validate.add_argument(
        "--use-openmc",
        action="store_true",
        help="Also ask the optional openmc package to parse the directory.",
    )

    show = sub.add_parser("show", help="Summarize cells, materials, tallies, and batch settings.")
    show.add_argument("input_dir")

    stat = sub.add_parser("stat", help="Read k-eff and tally tables from a statepoint.")
    stat.add_argument("path", help="A statepoint file or a directory that contains one.")

    diff = sub.add_parser("diff", help="Compare two statepoints.")
    diff.add_argument("left")
    diff.add_argument("right")

    check = sub.add_parser("check", help="Check OPENMC_CROSS_SECTIONS and, optionally, a model.")
    check.add_argument("--path", help="Cross-section index. Defaults to the environment, then materials.xml.")
    check.add_argument("--model", help="Model directory whose nuclide names are matched against the index.")

    review = sub.add_parser("review", help="Dry-run plan. Does not start OpenMC.")
    review.add_argument("input_dir")
    review.add_argument("--runner", help="subprocess, docker, or ssh:<peer>. Omit to use adapter auto-detect.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one verb. Prints one JSON document. Returns 0 when the report's ok/ready is true."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        payload, succeeded = _dispatch(args)
    except (FileNotFoundError, ValueError, ImportError, OSError) as exc:
        payload = {"ok": False, "errors": [str(exc)]}
        succeeded = False
    json.dump(payload, sys.stdout, indent=2, allow_nan=False)
    sys.stdout.write("\n")
    return 0 if succeeded else 1


def _dispatch(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    if args.command == "validate":
        report = library.validate_model(args.input_dir, use_openmc=args.use_openmc)
        return report, bool(report["ok"])
    if args.command == "show":
        report = library.summarize_model(args.input_dir)
        return report, not report["errors"]
    if args.command == "stat":
        return library.read_statepoint(args.path), True
    if args.command == "diff":
        report = library.compare_statepoints(args.left, args.right)
        return report, True
    if args.command == "check":
        report = library.check_cross_sections(args.path, args.model)
        return report, bool(report["ok"])
    if args.command == "review":
        options = {"runner": args.runner} if args.runner else None
        report = library.plan_run(args.input_dir, kernel_options=options)
        return report, bool(report["ready"])
    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
