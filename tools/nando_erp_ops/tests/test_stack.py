"""Unit tests for stack normalization and promote tree matching."""
from __future__ import annotations

from pathlib import Path

import pytest

from nando_erp_ops.config import STACKS, normalize_stack
from nando_erp_ops.commands import _image_apps_sha, _trees_match
from nando_erp_ops.fixtures.lint import lint_hooks_coverage
from nando_erp_ops.structure import AppSpec, StructureConfig


def test_normalize_stack_aliases():
    assert normalize_stack("prod") == "main"
    assert normalize_stack("quality") == "quality"
    assert normalize_stack("dev") == "dev"
    assert set(STACKS) == {"dev", "quality", "main"}
    with pytest.raises(ValueError):
        normalize_stack("staging")


def test_image_apps_sha():
    assert _image_apps_sha("nando-erpnext-quality:v16.5.0-frappe-16.28-apps.abc1234") == "abc1234"
    assert _image_apps_sha("img:nope") is None


def test_trees_match(tmp_path: Path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    (repo / "a.txt").write_text("one")
    subprocess.check_call(["git", "add", "-A"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "one"], cwd=repo)
    sha1 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    (repo / "a.txt").write_text("two")
    subprocess.check_call(["git", "add", "-A"], cwd=repo)
    subprocess.check_call(["git", "commit", "-m", "two"], cwd=repo)
    sha2 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    assert _trees_match(sha1, sha1, repo)
    assert not _trees_match(sha1, sha2, repo)


def test_lint_hooks_coverage(tmp_path: Path):
    hooks = tmp_path / "hooks.py"
    hooks.write_text(
        'fixtures = [\n'
        '  {"dt": "Custom Field", "filters": [["module", "=", "NANDO_CRM"]]},\n'
        '  {"dt": "DocType", "filters": [["module", "=", "NANDO_CRM"]]},\n'
        ']\n'
    )
    structure = StructureConfig(
        apps={"nando_crm": AppSpec("nando_crm", "NANDO_CRM", "", "")},
        structure_doctypes=["Custom Field", "DocType", "Workflow"],
        per_environment=[],
        data_doctypes=[],
    )
    errors = lint_hooks_coverage("nando_crm", hooks, structure)
    assert any("Workflow" in e for e in errors)
    hooks.write_text(
        'fixtures = [\n'
        '  {"dt": "Custom Field"},\n'
        '  {"dt": "DocType"},\n'
        '  {"dt": "Workflow"},\n'
        ']\n'
    )
    assert lint_hooks_coverage("nando_crm", hooks, structure) == []
