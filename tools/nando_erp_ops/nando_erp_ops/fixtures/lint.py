"""Lint fixture JSON against structure.yaml ownership rules."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nando_erp_ops.structure import StructureConfig, load_structure


def _iter_docs(fixtures_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    out: list[tuple[Path, dict[str, Any]]] = []
    if not fixtures_dir.is_dir():
        return out
    for path in sorted(fixtures_dir.glob("*.json")):
        data = json.loads(path.read_text() or "[]")
        docs = data if isinstance(data, list) else [data]
        for doc in docs:
            if isinstance(doc, dict):
                out.append((path, doc))
    return out


# DocTypes that have no `module` field in Frappe — owned by name prefix instead.
NO_MODULE_STEMS = {"desktop_icon", "role"}
NAME_PREFIXES = ("NANDO", "Nando")


def _name_owned(name: str) -> bool:
    return any(str(name).startswith(p) for p in NAME_PREFIXES)


def lint_app_fixtures(
    app: str,
    fixtures_dir: Path,
    structure: StructureConfig | None = None,
) -> list[str]:
    structure = structure or load_structure()
    if app not in structure.apps:
        return [f"Unknown app '{app}' (not in structure.yaml)"]
    expected_module = structure.apps[app].module
    other_modules = {s.module for k, s in structure.apps.items() if k != app}
    errors: list[str] = []

    module_stems = {
        "custom_field",
        "property_setter",
        "client_script",
        "server_script",
        "doctype",
        "workspace",
        "workspace_sidebar",
        "report",
        "print_format",
        "notification",
        "dashboard_chart",
        "number_card",
        "custom_docperm",
        "workflow",
    }

    for path, doc in _iter_docs(fixtures_dir):
        doctype = doc.get("doctype") or ""
        name = doc.get("name") or "?"
        module = doc.get("module")

        if doctype in structure.per_environment:
            errors.append(
                f"{path.name}:{name}: per-environment DocType '{doctype}' must not be in fixtures"
            )
            continue

        if path.stem in {"email_account", "google_settings", "system_settings"}:
            errors.append(f"{path.name}: per-environment fixture file must be removed")
            continue

        if path.stem in NO_MODULE_STEMS:
            if not _name_owned(name) and not _name_owned(doc.get("label") or ""):
                # CRM allows explicit Role names from hooks; still require NANDO/Nando prefix
                # or known CRM roles.
                if path.stem == "role" and name in {"Nando sales", "NANDO Import user"}:
                    continue
                errors.append(
                    f"{path.name}:{name}: DocType has no module field; name/label must start with NANDO"
                )
            continue

        if doctype in structure.structure_doctypes or path.stem in module_stems:
            if not module:
                errors.append(
                    f"{path.name}:{name}: missing module (expected {expected_module})"
                )
            elif module != expected_module:
                if module in other_modules:
                    errors.append(
                        f"{path.name}:{name}: module={module} belongs to another app "
                        f"(this app owns {expected_module})"
                    )
                else:
                    errors.append(
                        f"{path.name}:{name}: module={module} != {expected_module}"
                    )

    return errors


def lint_all(app_fixture_dirs: dict[str, Path], structure: StructureConfig | None = None) -> list[str]:
    structure = structure or load_structure()
    errors: list[str] = []
    # Cross-app name collisions for same DocType file
    by_key: dict[tuple[str, str], list[str]] = {}
    for app, fixtures_dir in app_fixture_dirs.items():
        errors.extend(lint_app_fixtures(app, fixtures_dir, structure))
        for path, doc in _iter_docs(fixtures_dir):
            name = doc.get("name") or ""
            if not name:
                continue
            by_key.setdefault((path.name, name), []).append(app)
    for (fname, name), apps in by_key.items():
        if len(set(apps)) > 1:
            errors.append(f"{fname}:{name}: exported by multiple apps {sorted(set(apps))}")
    return errors
