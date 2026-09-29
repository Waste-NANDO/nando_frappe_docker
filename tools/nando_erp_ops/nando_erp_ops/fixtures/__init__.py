"""Fixture JSON helpers (merge + compare). Absorbs former nando-deployment/merge-fixtures.py."""
from __future__ import annotations

import json
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, list[str]]]:
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
        missing_only.append(src)
        merged.append(src)

    report = {"added": added, "changed": changed, "unchanged": unchanged}
    return merged, missing_only, changed_only, report


def diff_dirs(source_dir: Path, dest_dir: Path) -> dict[str, Any]:
    """Compare two fixture directories by document name. Returns missing/changed/identical counts."""
    source_files = {p.name: p for p in source_dir.glob("*.json")}
    dest_files = {p.name: p for p in dest_dir.glob("*.json")}
    all_names = sorted(set(source_files) | set(dest_files))

    missing: list[dict[str, str]] = []
    changed: list[dict[str, str]] = []
    identical = 0
    dest_only: list[dict[str, str]] = []

    for fname in all_names:
        src_docs = {doc_name(d): d for d in load_docs(source_files[fname])} if fname in source_files else {}
        dst_docs = {doc_name(d): d for d in load_docs(dest_files[fname])} if fname in dest_files else {}
        for name, src in src_docs.items():
            if name not in dst_docs:
                missing.append({"file": fname, "name": name})
            elif comparable(src) != comparable(dst_docs[name]):
                changed.append({"file": fname, "name": name})
            else:
                identical += 1
        for name in dst_docs:
            if name not in src_docs:
                dest_only.append({"file": fname, "name": name})

    return {
        "missing": missing,
        "changed": changed,
        "identical": identical,
        "dest_only": dest_only,
        "has_drift": bool(missing or changed),
    }
