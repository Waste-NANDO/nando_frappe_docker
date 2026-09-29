"""Unit tests for fixture merge/diff and lint (no docker required)."""
from __future__ import annotations

import json
from pathlib import Path

from nando_erp_ops.fixtures import comparable, diff_dirs, merge_file, write_docs
from nando_erp_ops.fixtures.lint import lint_app_fixtures
from nando_erp_ops.structure import StructureConfig, AppSpec


def test_comparable_ignores_modified():
    a = {"name": "x", "doctype": "DocType", "modified": "1", "foo": 1}
    b = {"name": "x", "doctype": "DocType", "modified": "2", "foo": 1}
    assert comparable(a) == comparable(b)


def test_merge_adds_missing(tmp_path: Path):
    src = [{"name": "A", "doctype": "X", "v": 1}, {"name": "B", "doctype": "X", "v": 2}]
    dst = [{"name": "A", "doctype": "X", "v": 1}]
    merged, missing, changed, report = merge_file(src, dst, force_update=False)
    assert {d["name"] for d in missing} == {"B"}
    assert report["added"] == ["B"]
    assert len(merged) == 2


def test_diff_dirs(tmp_path: Path):
    s = tmp_path / "src"
    d = tmp_path / "dst"
    s.mkdir()
    d.mkdir()
    write_docs(s / "doctype.json", [{"name": "T1", "module": "NANDO_CRM", "doctype": "DocType"}])
    write_docs(d / "doctype.json", [{"name": "T1", "module": "NANDO_CRM", "doctype": "DocType", "modified": "x"}])
    report = diff_dirs(s, d)
    assert report["identical"] == 1
    assert not report["has_drift"]

    write_docs(s / "doctype.json", [
        {"name": "T1", "module": "NANDO_CRM", "doctype": "DocType", "label": "new"},
        {"name": "T2", "module": "NANDO_CRM", "doctype": "DocType"},
    ])
    report = diff_dirs(s, d)
    assert report["has_drift"]
    assert len(report["missing"]) == 1
    assert len(report["changed"]) == 1


def test_lint_requires_module(tmp_path: Path):
    fx = tmp_path / "fixtures"
    fx.mkdir()
    (fx / "custom_field.json").write_text(
        json.dumps([{"name": "cf1", "doctype": "Custom Field", "dt": "Customer", "fieldname": "x"}])
    )
    structure = StructureConfig(
        apps={
            "nando_crm": AppSpec("nando_crm", "NANDO_CRM", "", ""),
            "nando_fulfillment": AppSpec("nando_fulfillment", "NANDO_Operations", "", ""),
        },
        structure_doctypes=["Custom Field"],
        per_environment=["Email Account"],
        data_doctypes=[],
    )
    errors = lint_app_fixtures("nando_crm", fx, structure)
    assert any("missing module" in e for e in errors)

    (fx / "custom_field.json").write_text(
        json.dumps([{
            "name": "cf1",
            "doctype": "Custom Field",
            "module": "NANDO_CRM",
            "dt": "Customer",
            "fieldname": "x",
        }])
    )
    errors = lint_app_fixtures("nando_crm", fx, structure)
    assert errors == []


def test_lint_rejects_per_env(tmp_path: Path):
    fx = tmp_path / "fixtures"
    fx.mkdir()
    (fx / "email_account.json").write_text(
        json.dumps([{"name": "e", "doctype": "Email Account"}])
    )
    structure = StructureConfig(
        apps={"nando_crm": AppSpec("nando_crm", "NANDO_CRM", "", "")},
        structure_doctypes=[],
        per_environment=["Email Account"],
        data_doctypes=[],
    )
    errors = lint_app_fixtures("nando_crm", fx, structure)
    assert errors
