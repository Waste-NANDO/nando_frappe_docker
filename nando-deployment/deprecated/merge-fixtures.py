#!/usr/bin/env python3
"""Merge Frappe fixture JSON: add missing docs, keep dest on conflicts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

IGNORE_KEYS = {"modified", "modified_by", "creation", "owner", "migration_hash"}


def load_docs(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


def doc_name(doc: dict[str, Any]) -> str:
    return str(doc.get("name") or "")


def comparable(doc: dict[str, Any]) -> Any:
    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: strip(v)
                for k, v in sorted(value.items())
                if k not in IGNORE_KEYS
            }
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    return strip(doc)


def write_docs(path: Path, docs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    docs = sorted(docs, key=lambda d: (doc_name(d), json.dumps(d, sort_keys=True)))
    path.write_text(json.dumps(docs, indent=1, ensure_ascii=False) + "\n")


def merge_file(
    source_docs: list[dict[str, Any]],
    dest_docs: list[dict[str, Any]],
    force_update: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[str]]]:
    dest_by_name = {doc_name(d): d for d in dest_docs if doc_name(d)}
    source_by_name = {doc_name(d): d for d in source_docs if doc_name(d)}

    added: list[str] = []
    changed: list[str] = []
    unchanged: list[str] = []
    merged: list[dict[str, Any]] = []
    missing_only: list[dict[str, Any]] = []
    changed_only: list[dict[str, Any]] = []

    for name, dest_doc in dest_by_name.items():
        src = source_by_name.get(name)
        if src is None:
            merged.append(dest_doc)
            continue
        if comparable(src) == comparable(dest_doc):
            unchanged.append(name)
            merged.append(dest_doc)
            continue
        changed.append(name)
        changed_only.append(src)
        merged.append(src if force_update else dest_doc)

    for name, src in source_by_name.items():
        if name in dest_by_name:
            continue
        added.append(name)
        merged.append(src)
        missing_only.append(src)

    report = {"added": added, "changed": changed, "unchanged": unchanged}
    return merged, missing_only, changed_only, report


def iter_json_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.json") if p.is_file())


def rel(path: Path, root: Path) -> Path:
    return path.relative_to(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument("--merged-out", required=True, type=Path)
    parser.add_argument("--missing-out", required=True, type=Path)
    parser.add_argument("--changed-out", type=Path, default=None)
    parser.add_argument("--force-update", action="store_true")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help="Limit to these document names (repeatable)",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        dest="file_names",
        metavar="JSON",
        help="Limit to these fixture filenames, e.g. doctype.json (repeatable)",
    )
    args = parser.parse_args()

    source_root = args.source.resolve()
    dest_root = args.dest.resolve()
    merged_root = args.merged_out.resolve()
    missing_root = args.missing_out.resolve()
    changed_root = args.changed_out.resolve() if args.changed_out else None

    files = {rel(p, source_root) for p in iter_json_files(source_root)}
    files |= {rel(p, dest_root) for p in iter_json_files(dest_root)}
    if args.file_names:
        want = set(args.file_names)
        files = {p for p in files if p.name in want}

    only = set(args.only)

    grand: dict[str, list[str]] = {"added": [], "changed": [], "unchanged": []}
    any_work = False

    for rel_path in sorted(files, key=str):
        source_docs = load_docs(source_root / rel_path)
        dest_docs = load_docs(dest_root / rel_path)
        if only:
            source_docs = [d for d in source_docs if doc_name(d) in only]
            dest_docs = [d for d in dest_docs if doc_name(d) in only]
        merged, missing, changed_docs, report = merge_file(
            source_docs,
            dest_docs,
            args.force_update,
        )
        write_docs(merged_root / rel_path, merged)
        if missing:
            write_docs(missing_root / rel_path, missing)
        if changed_root is not None and changed_docs:
            write_docs(changed_root / rel_path, changed_docs)
        for key in grand:
            for name in report[key]:
                grand[key].append(f"{rel_path}::{name}")
                any_work = True

        if report["added"] or report["changed"]:
            print(f"[{rel_path}]")
            if report["added"]:
                print("  missing on dest (will add):")
                for name in report["added"]:
                    print(f"    + {name}")
            if report["changed"]:
                verb = "overwritten from source" if args.force_update else "kept dest (skip)"
                print(f"  same name, different content ({verb}):")
                for name in report["changed"]:
                    print(f"    ~ {name}")

    print("")
    print(
        f"Summary: {len(grand['added'])} missing, "
        f"{len(grand['changed'])} conflicting, "
        f"{len(grand['unchanged'])} identical"
    )
    if not any_work and not files:
        print("No fixture JSON found on either side.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
