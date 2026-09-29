#!/usr/bin/env python3
"""Backward-compatible CLI wrapper around nando_erp_ops.fixtures.merge. """
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Prefer installed package; fall back to tools path
try:
    from nando_erp_ops.fixtures import load_docs, merge_file, write_docs
except ImportError:
    # deprecated/ → repo root is parents[2]
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "nando_erp_ops"))
    from nando_erp_ops.fixtures import load_docs, merge_file, write_docs


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--dest", required=True, type=Path)
    p.add_argument("--merged-out", required=True, type=Path)
    p.add_argument("--missing-out", required=True, type=Path)
    p.add_argument("--changed-out", required=True, type=Path)
    p.add_argument("--force-update", action="store_true")
    p.add_argument("--only", action="append", default=[])
    p.add_argument("--file", dest="files", action="append", default=[])
    args = p.parse_args()

    src_files = {f.name: f for f in args.source.glob("*.json")}
    dst_files = {f.name: f for f in args.dest.glob("*.json")}
    names = sorted(set(src_files) | set(dst_files))
    if args.files:
        names = [n for n in names if n in set(args.files)]

    total_missing = total_changed = total_unchanged = 0
    for fname in names:
        src = load_docs(src_files[fname]) if fname in src_files else []
        dst = load_docs(dst_files[fname]) if fname in dst_files else []
        if args.only:
            only = set(args.only)
            src = [d for d in src if d.get("name") in only]
            dst = [d for d in dst if d.get("name") in only]
        merged, missing, changed, report = merge_file(src, dst, args.force_update)
        write_docs(args.merged_out / fname, merged)
        write_docs(args.missing_out / fname, missing)
        write_docs(args.changed_out / fname, changed)
        total_missing += len(report["added"])
        total_changed += len(report["changed"])
        total_unchanged += len(report["unchanged"])
        print(f"{fname}: +{len(report['added'])} ~{len(report['changed'])} ={len(report['unchanged'])}")

    print(f"TOTAL missing={total_missing} changed={total_changed} identical={total_unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
