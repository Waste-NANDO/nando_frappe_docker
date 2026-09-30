"""CLI command implementations."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from nando_erp_ops.config import (
    STACKS,
    apps_monorepo_root,
    get_paths,
    local_bench_root,
    normalize_stack,
)
from nando_erp_ops.executor import get_executor
from nando_erp_ops.fixtures import diff_dirs, write_docs, load_docs
from nando_erp_ops.fixtures.lint import lint_all, lint_app_fixtures, lint_hooks_coverage
from nando_erp_ops.stack import Stack
from nando_erp_ops.structure import load_structure
from nando_erp_ops.versions import REQUIRED_PINS, load_stack_env, load_versions, parse_env_file


def cmd_doctor(stack: str | None = None, local: bool = True) -> int:
    versions = load_versions()
    print("=== versions.env ===")
    for key in REQUIRED_PINS:
        print(f"  {key}={versions.get(key, '(missing)')}")
    rc = 0
    names = list(STACKS) if not stack else [normalize_stack(stack)]
    for name in names:
        env = load_stack_env(name)
        print(f"\n=== stack {name} ===")
        for key in REQUIRED_PINS:
            want = versions.get(key)
            got = env.get(key)
            mark = "OK" if want == got else "DRIFT"
            if mark != "OK":
                rc = 1
            print(f"  [{mark}] {key}: stack={got} manifest={want}")
        print(f"  CUSTOM_IMAGE={env.get('CUSTOM_IMAGE')}:{env.get('CUSTOM_TAG')}")
        print(f"  BACKUP_INTERVAL_SECONDS={env.get('BACKUP_INTERVAL_SECONDS')}")
    if local:
        bench = local_bench_root()
        print(f"\n=== local bench ({bench}) ===")
        if not bench:
            print("  [WARN] NANDO_LOCAL_BENCH not set / not found")
            return rc
        for app, key in (("frappe", "FRAPPE_VERSION"), ("erpnext", "ERPNEXT_VERSION"), ("hrms", "HRMS_BRANCH")):
            app_dir = bench / "apps" / app
            if not app_dir.is_dir():
                print(f"  [MISS] {app} not installed (want {versions.get(key)})")
                if app != "hrms":
                    rc = 1
                continue
            ex = get_executor()
            r = ex.run(["git", "describe", "--tags", "--exact-match"], cwd=str(app_dir))
            tag = (r.stdout or r.stderr).strip() or "(detached/unknown)"
            want = versions.get(key)
            mark = "OK" if tag == want else "DRIFT"
            if mark != "OK" and app != "hrms":
                rc = 1
            print(f"  [{mark}] {app}: {tag} (want {want})")
        for app in load_structure().apps:
            app_dir = bench / "apps" / app
            if app_dir.is_dir():
                r = get_executor().run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(app_dir))
                print(f"  [info] {app} branch={r.stdout.strip()}")
            else:
                print(f"  [MISS] {app}")
                rc = 1
    return rc


def cmd_local_bootstrap(*, skip_hrms: bool = False, dry_run: bool = False) -> int:
    versions = load_versions()
    bench = local_bench_root()
    if not bench:
        print("Set NANDO_LOCAL_BENCH to your nando-bench path", flush=True)
        return 1
    ex = get_executor()
    steps = [
        ("frappe", versions["FRAPPE_VERSION"]),
        ("erpnext", versions["ERPNEXT_VERSION"]),
    ]
    if not skip_hrms and versions.get("INCLUDE_HRMS", "yes").lower() in {"yes", "true", "1"}:
        steps.append(("hrms", versions["HRMS_BRANCH"]))
    for app, tag in steps:
        app_dir = bench / "apps" / app
        print(f"→ {app} @ {tag}")
        if dry_run:
            continue
        if not app_dir.is_dir():
            if app == "hrms":
                url = versions.get("HRMS_REPO", "https://github.com/frappe/hrms.git")
                r = ex.run(["bench", "get-app", url, "--branch", tag], cwd=str(bench), timeout=600)
                if not r.ok:
                    print(r.stderr)
                    return r.returncode
                continue
            print(f"  missing {app_dir}")
            return 1
        for argv in (
            ["git", "fetch", "--tags", "--force"],
            ["git", "checkout", "--force", tag],
            ["git", "clean", "-fd"],
        ):
            r = ex.run(argv, cwd=str(app_dir), timeout=300)
            if not r.ok:
                print(r.stderr or r.stdout)
                return r.returncode
    # Ensure custom apps exist as editable checkouts (prefer monorepo symlinks)
    structure = load_structure()
    stack = load_stack_env("dev")
    mono = apps_monorepo_root()
    for app, spec in structure.apps.items():
        app_dir = bench / "apps" / app
        if app_dir.is_dir() or app_dir.is_symlink():
            print(f"→ {app} present (leave branch as-is for feature work)")
            continue
        if mono:
            src = mono / structure.path_for(app)
            print(f"→ symlink {app_dir} → {src}")
            if dry_run:
                continue
            if not src.is_dir():
                print(f"  missing monorepo path {src}")
                return 1
            app_dir.symlink_to(src)
            continue
        repo = stack.get(spec.repo_env) or versions.get(spec.repo_env)
        branch = stack.get(spec.branch_env, "dev")
        print(f"→ get-app {app} from {repo}@{branch}")
        if dry_run:
            continue
        r = ex.run(["bench", "get-app", repo, "--branch", branch], cwd=str(bench), timeout=600)
        if not r.ok:
            print(r.stderr)
            return r.returncode
    print("Run: bench --site <site> migrate && bench build")
    return 0


def cmd_lint(app_dirs: dict[str, Path] | None = None) -> int:
    structure = load_structure()
    paths = get_paths()
    mono = apps_monorepo_root()
    if app_dirs is None:
        app_dirs = {}
        bench = local_bench_root()
        for app in structure.apps:
            candidates = []
            if bench:
                candidates.append(bench / "apps" / app / app / "fixtures")
            if mono:
                candidates.append(mono / structure.path_for(app) / app / "fixtures")
            candidates.append(paths.custom_apps / app / app / "fixtures")
            for c in candidates:
                if c.is_dir():
                    app_dirs[app] = c
                    break
    errors = lint_all(app_dirs, structure)
    # hooks.py must cover structure_doctypes
    for app in structure.apps:
        hooks_candidates = []
        if mono:
            hooks_candidates.append(mono / structure.path_for(app) / app / "hooks.py")
        bench = local_bench_root()
        if bench:
            hooks_candidates.append(bench / "apps" / app / app / "hooks.py")
        hooks_candidates.append(paths.custom_apps / app / app / "hooks.py")
        for hp in hooks_candidates:
            if hp.is_file():
                errors.extend(lint_hooks_coverage(app, hp, structure))
                break
    if not errors:
        print("lint OK")
        return 0
    for e in errors:
        print(f"ERROR: {e}")
    return 1


def _fixture_dir_for(app: str, root: Path) -> Path:
    a = root / app / "fixtures"
    b = root / app / app / "fixtures"
    return b if b.parent.is_dir() or not a.parent.is_dir() else a


def cmd_export(*, target: str = "local", apps: list[str] | None = None) -> int:
    """Export fixtures from local site or a cloud stack into app fixture dirs."""
    structure = load_structure()
    apps = apps or list(structure.apps)
    if target == "local":
        bench = local_bench_root()
        if not bench:
            print("NANDO_LOCAL_BENCH required for local export")
            return 1
        site = os.environ.get("NANDO_LOCAL_SITE", "nando.local")
        ex = get_executor()
        for app in apps:
            print(f"export-fixtures --app {app}")
            r = ex.run(
                ["bench", "--site", site, "export-fixtures", "--app", app],
                cwd=str(bench),
                timeout=600,
            )
            print(r.stdout)
            if not r.ok:
                print(r.stderr)
                return r.returncode
        return cmd_lint({a: bench / "apps" / a / a / "fixtures" for a in apps})

    stack = Stack(target)
    with tempfile.TemporaryDirectory(prefix="nando-export-") as tmp:
        tmp_path = Path(tmp)
        for app in apps:
            print(f"[{stack.name}] export-fixtures --app {app}")
            r = stack.bench("export-fixtures", "--app", app, timeout=600)
            print(r.stdout)
            if not r.ok:
                print(r.stderr)
                return r.returncode
            dest = tmp_path / app
            dest.mkdir()
            container_fx = f"/home/frappe/frappe-bench/apps/{app}/{app}/fixtures"
            # docker compose cp
            r = stack.run_compose("cp", f"backend:{container_fx}", str(dest / "fixtures"))
            if not r.ok:
                print(r.stderr or r.stdout)
                # empty ok
            out = get_paths().custom_apps / app / app / "fixtures"
            out.mkdir(parents=True, exist_ok=True)
            src = dest / "fixtures"
            if src.is_dir():
                for f in src.glob("*.json"):
                    shutil.copy2(f, out / f.name)
                    print(f"  wrote {out / f.name}")
    return 0


def cmd_drift(*, stack: str = "dev", apps: list[str] | None = None) -> int:
    """Compare live stack fixtures to git fixtures in custom-apps (or local apps)."""
    structure = load_structure()
    apps = apps or list(structure.apps)
    st = Stack(stack)
    paths = get_paths()
    with tempfile.TemporaryDirectory(prefix="nando-drift-") as tmp:
        tmp_path = Path(tmp)
        any_drift = False
        for app in apps:
            live = tmp_path / app / "live"
            live.mkdir(parents=True)
            r = st.bench("export-fixtures", "--app", app, timeout=600)
            if not r.ok:
                print(r.stderr or r.stdout)
                return r.returncode
            container_fx = f"/home/frappe/frappe-bench/apps/{app}/{app}/fixtures"
            st.run_compose("cp", f"backend:{container_fx}", str(live / "fixtures"))
            live_fx = live / "fixtures"
            git_fx = paths.custom_apps / app / app / "fixtures"
            bench = local_bench_root()
            if not git_fx.is_dir() and bench:
                git_fx = bench / "apps" / app / app / "fixtures"
            if not git_fx.is_dir():
                print(f"[{app}] no git fixtures at {git_fx} — treating all live docs as drift")
                any_drift = True
                continue
            report = diff_dirs(live_fx if live_fx.is_dir() else live, git_fx)
            print(f"=== {app} ===")
            print(f"  identical={report['identical']} missing_in_git={len(report['missing'])} "
                  f"changed={len(report['changed'])} git_only={len(report['dest_only'])}")
            for item in report["missing"][:20]:
                print(f"  + live-only: {item['file']} {item['name']}")
            for item in report["changed"][:20]:
                print(f"  ~ changed:   {item['file']} {item['name']}")
            if report["has_drift"]:
                any_drift = True
        if any_drift:
            print("\nDRIFT DETECTED — run `nando-erp capture` before deploy")
            return 2
        print("\nNo drift")
        return 0


def _monorepo_worktree() -> Path | None:
    """Prefer local nando-erp-modules checkout; else host fetch cache."""
    mono = apps_monorepo_root()
    if mono and (mono / ".git").exists():
        return mono
    paths = get_paths()
    if (paths.monorepo_cache / ".git").exists():
        return paths.monorepo_cache
    return None


def cmd_capture(*, stack: str = "dev", push: bool = False, base: str | None = None) -> int:
    """Export live stack fixtures into the monorepo and optionally open one PR."""
    structure = load_structure()
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    branch = f"capture/{stack}-{date}"
    base = base or ("quality" if stack == "quality" else "dev")
    rc = cmd_export(target=stack)
    if rc != 0:
        return rc
    paths = get_paths()
    mono = _monorepo_worktree()
    if not mono:
        print("No monorepo checkout (.apps-monorepo or NANDO_APPS_CHECKOUT). Run fetch-custom-app first.")
        return 1
    ex = get_executor()
    # Copy exported fixtures from custom-apps into monorepo app folders
    for app in structure.apps:
        src = paths.custom_apps / app / app / "fixtures"
        if not src.is_dir():
            print(f"[{app}] no exported fixtures at {src}")
            continue
        dest = mono / structure.path_for(app) / app / "fixtures"
        dest.mkdir(parents=True, exist_ok=True)
        for f in src.glob("*.json"):
            shutil.copy2(f, dest / f.name)
            print(f"  wrote {dest / f.name}")
    r = ex.run(["git", "checkout", "-B", branch], cwd=str(mono))
    if not r.ok:
        print(r.stderr)
        return r.returncode
    ex.run(["git", "add", "-A"], cwd=str(mono))
    r = ex.run(
        ["git", "commit", "-m", f"capture: {stack} fixtures {date}"],
        cwd=str(mono),
    )
    if r.ok:
        print(f"committed on {branch} in {mono}")
    else:
        print(f"nothing to commit or commit failed: {r.stderr or r.stdout}")
    if push:
        ex.run(["git", "push", "-u", "origin", branch], cwd=str(mono))
        pr = ex.run(
            [
                "gh", "pr", "create",
                "--base", base,
                "--head", branch,
                "--title", f"capture: {stack} fixtures {date}",
                "--body", f"Auto-captured Desk edits from {stack}. Review before merge.",
            ],
            cwd=str(mono),
        )
        print(pr.stdout or pr.stderr)
    return 0


def _monorepo_sha(paths) -> str:
    sha_file = paths.custom_apps / ".nando_monorepo_sha"
    if sha_file.is_file():
        return sha_file.read_text().strip()[:7]
    mono = _monorepo_worktree()
    if mono:
        r = get_executor().run(["git", "rev-parse", "--short=7", "HEAD"], cwd=str(mono))
        if r.ok and r.stdout.strip():
            return r.stdout.strip()
    return "unknown"


def cmd_build(*, stack: str = "dev") -> int:
    stack = normalize_stack(stack)
    paths = get_paths()
    env_file = paths.env_file(stack)
    ex = get_executor()
    fetch = paths.deployment / "fetch-custom-app.sh"
    r = ex.run(["bash", str(fetch), str(env_file)], cwd=str(paths.repo_root), timeout=600)
    print(r.stdout)
    if not r.ok:
        print(r.stderr)
        return r.returncode
    env = load_stack_env(stack)
    short = _monorepo_sha(paths)
    print(f"  apps@{short}")
    versions = load_versions()
    tag = f"{versions['ERPNEXT_VERSION']}-frappe-{versions['FRAPPE_VERSION'].lstrip('v')}-apps.{short}"
    tag = tag.replace("/", "-")
    print(f"Building image tag: {tag}")
    build = paths.deployment / "build-custom-image.sh"
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as tf:
        text = env_file.read_text()
        lines = []
        replaced = False
        for line in text.splitlines():
            if line.startswith("CUSTOM_TAG="):
                lines.append(f"CUSTOM_TAG={tag}")
                replaced = True
            else:
                lines.append(line)
        if not replaced:
            lines.append(f"CUSTOM_TAG={tag}")
        tf.write("\n".join(lines) + "\n")
        tmp_env = tf.name
    try:
        r = ex.run(["bash", str(build), tmp_env], cwd=str(paths.repo_root), timeout=7200)
        print(r.stdout)
        if not r.ok:
            print(r.stderr)
            return r.returncode
    finally:
        Path(tmp_env).unlink(missing_ok=True)
    print(f"IMAGE_TAG={env.get('CUSTOM_IMAGE')}:{tag}")
    return 0


def cmd_deploy(*, stack: str = "dev", skip_drift: bool = False, with_build: bool = False) -> int:
    """Deploy to dev or quality (drift-gated). Use promote for prod."""
    stack = normalize_stack(stack)
    if stack == "main":
        print("Use `nando-erp promote` for prod")
        return 1
    if not skip_drift:
        rc = cmd_drift(stack=stack)
        if rc != 0:
            return rc
    paths = get_paths()
    env_file = paths.env_file(stack)
    argv = ["bash", str(paths.deployment / "deploy-stack.sh"), str(env_file)]
    if with_build:
        argv.append("--with-build")
    r = get_executor().run(argv, cwd=str(paths.repo_root), timeout=7200)
    print(r.stdout)
    if not r.ok:
        print(r.stderr)
    return r.returncode


def cmd_deploy_dev(*, skip_drift: bool = False, with_build: bool = False) -> int:
    """Back-compat wrapper."""
    return cmd_deploy(stack="dev", skip_drift=skip_drift, with_build=with_build)


def cmd_backup(
    *,
    stack: str = "main",
    with_files: bool = True,
    prefix: str | None = None,
    upload: bool = True,
) -> int:
    """Run bench backup and optionally upload to GCS under a custom prefix."""
    st = Stack(stack)
    args = ["backup"]
    if with_files:
        args.append("--with-files")
    print(f"[{st.name}] bench {' '.join(args)}")
    r = st.bench(*args, timeout=7200)
    print(r.stdout)
    if not r.ok:
        print(r.stderr)
        return r.returncode
    if not upload:
        return 0
    gcs_bucket = st.env.get("GCS_BUCKET", "nando-it-backups")
    app_name = st.env.get("APP_NAME", "nando-erp-main")
    erp_ver = st.env.get("ERPNEXT_VERSION", "latest")
    gcs_prefix = prefix or f"{app_name}/{erp_ver}"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # Use existing upload-to-gcs.py inside the backup service / backend
    site = st.site
    backup_dir = f"/home/frappe/frappe-bench/sites/{site}/private/backups"
    script = (
        f"cd /home/frappe/frappe-bench && "
        f"python3 /home/frappe/upload-to-gcs.py "
        f"--prefix {gcs_prefix} --bucket {gcs_bucket} "
        f"--key-file /home/frappe/gcs-key.json "
        f"--timestamp {timestamp} --keep {st.env.get('BACKUP_KEEP', '14')} "
        f"--backup-dir {backup_dir} --since 0"
    )
    # Prefer backup container if present, else backend (may lack upload script + key)
    r = st.run_compose("exec", "-T", "backup", "bash", "-lc", script, timeout=3600)
    if not r.ok:
        # fallback: copy scripts into backend — may fail if key not mounted
        print("backup service upload failed, trying backend:", r.stderr or r.stdout)
        r2 = st.run_compose(
            "exec", "-T", "backend", "bash", "-lc",
            f"test -f /home/frappe/upload-to-gcs.py && {script} || "
            f"echo 'Upload skipped: mount upload-to-gcs.py + gcs key (backup service). "
            f"Local backup is in {backup_dir}'",
            timeout=600,
        )
        print(r2.stdout or r2.stderr)
        # Local backup succeeded even if upload skipped
        return 0
    print(r.stdout)
    print(f"Uploaded to gs://{gcs_bucket}/{gcs_prefix}/{timestamp}/")
    return 0


def _image_apps_sha(image_ref: str) -> str | None:
    """Extract apps.<sha7> from an image tag like …-apps.abc1234."""
    tag = image_ref.split(":", 1)[-1]
    for part in tag.split("-"):
        if part.startswith("apps.") and len(part) >= 12:
            return part.split(".", 1)[1]
    # also handle apps.SHA glued: look for apps.
    if "apps." in tag:
        return tag.rsplit("apps.", 1)[-1][:7]
    return None


def _trees_match(expect_sha: str, image_sha: str, mono: Path) -> bool:
    """True if expect_sha and image_sha point at the same git tree in the monorepo."""
    ex = get_executor()
    for label, sha in (("expect", expect_sha), ("image", image_sha)):
        r = ex.run(["git", "rev-parse", "--verify", f"{sha}^{{tree}}"], cwd=str(mono))
        if not r.ok:
            # try short SHA resolve
            r = ex.run(["git", "rev-parse", "--verify", f"{sha}^{{tree}}"], cwd=str(mono))
        if not r.ok:
            print(f"Could not resolve tree for {label} sha {sha}: {r.stderr or r.stdout}")
            return False
    r1 = ex.run(["git", "rev-parse", f"{expect_sha}^{{tree}}"], cwd=str(mono))
    r2 = ex.run(["git", "rev-parse", f"{image_sha}^{{tree}}"], cwd=str(mono))
    return r1.ok and r2.ok and r1.stdout.strip() == r2.stdout.strip()


def cmd_promote(
    *,
    image_tag: str | None = None,
    yes: bool = False,
    actor: str | None = None,
    source: str = "quality",
    target: str = "main",
    expect_sha: str | None = None,
) -> int:
    """Promote the image running on source (default Quality) to target (prod)."""
    if not yes:
        print("Refusing: pass --yes to confirm promotion (logged).")
        return 1
    source = normalize_stack(source)
    target = normalize_stack(target)
    if target != "main":
        print("Promote target must be main/prod")
        return 1
    actor = actor or os.environ.get("USER") or os.environ.get("NANDO_ACTOR") or "unknown"
    drift_rc = cmd_drift(stack=source)
    if drift_rc != 0:
        print(f"Promote blocked: {source} has fixture drift")
        return drift_rc

    src_stack = Stack(source)
    main = Stack("main")
    running = src_stack.running_backend_image()
    if not running:
        print(f"Could not resolve running {source} backend image")
        return 1
    print(f"{source} running image: {running}")
    if image_tag and running != image_tag and not running.endswith(":" + image_tag.split(":")[-1]):
        print(f"Requested {image_tag} but {source} runs {running}")
        return 1

    if expect_sha:
        image_sha = _image_apps_sha(running)
        mono = _monorepo_worktree()
        if not image_sha or not mono:
            print("Promote blocked: could not verify expect_sha against image tag / monorepo")
            return 1
        if not _trees_match(expect_sha, image_sha, mono):
            print(
                f"Promote blocked: expect_sha tree ({expect_sha}) != image apps sha tree ({image_sha})"
            )
            return 1
        print(f"Tree match OK: expect_sha={expect_sha} image_apps={image_sha}")

    src_image = running
    if image_tag and ":" in image_tag:
        dest_image = image_tag
    else:
        tag = src_image.split(":", 1)[-1]
        dest_image = f"{main.custom_image}:{tag}"

    print(f"Pre-deploy backup → GCS pre-deploy/{dest_image.replace(':', '_')}")
    brc = cmd_backup(
        stack="main",
        with_files=False,
        prefix=f"{main.env.get('APP_NAME', 'nando-erp-main')}/pre-deploy/{dest_image.replace(':', '_').replace('/', '_')}",
        upload=True,
    )
    if brc != 0:
        print("Pre-deploy backup failed — aborting promote")
        return brc

    print(f"docker tag {src_image} {dest_image}")
    ex = get_executor()
    r = ex.run(["docker", "tag", src_image, dest_image])
    if not r.ok:
        print(r.stderr)
        return r.returncode

    paths = get_paths()
    env_file = paths.env_file("main")
    tag_only = dest_image.split(":", 1)[-1]
    text = env_file.read_text().splitlines()
    out_lines = []
    for line in text:
        if line.startswith("CUSTOM_TAG="):
            out_lines.append(f"CUSTOM_TAG={tag_only}")
        elif line.startswith("CUSTOM_IMAGE="):
            out_lines.append(f"CUSTOM_IMAGE={dest_image.split(':', 1)[0]}")
        else:
            out_lines.append(line)
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as tf:
        tf.write("\n".join(out_lines) + "\n")
        tmp_env = tf.name
    try:
        r = ex.run(
            ["bash", str(paths.deployment / "deploy-stack.sh"), tmp_env],
            cwd=str(paths.repo_root),
            timeout=7200,
        )
        print(r.stdout)
        if not r.ok:
            print(r.stderr)
            return r.returncode
    finally:
        Path(tmp_env).unlink(missing_ok=True)

    audit = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": "promote",
        "source": source,
        "source_image": src_image,
        "dest_image": dest_image,
        "expect_sha": expect_sha,
    }
    audit_path = paths.deployment / "logs" / "promote-audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a") as f:
        f.write(json.dumps(audit) + "\n")
    print(f"Promote complete. Audit: {audit_path}")
    print(json.dumps(audit))
    return 0


def cmd_refresh(
    *,
    target: str = "dev",
    skip_drift: bool = False,
    skip_if_drift: bool = False,
    with_files: bool = False,
) -> int:
    """Restore latest prod GCS backup into target, sanitize, migrate."""
    if target == "local":
        return _refresh_local(with_files=with_files)
    target = normalize_stack(target) if target != "local" else target
    if not skip_drift:
        rc = cmd_drift(stack=target)
        if target != "main" and rc != 0:
            if skip_if_drift:
                print(f"Refresh skipped: uncaptured drift on {target}")
                return 0
            print("Refresh blocked: uncaptured drift on target")
            return rc

    # Pre-refresh backup of target
    print("Pre-refresh backup of target...")
    cmd_backup(stack=target, with_files=False, upload=True)

    main = Stack("main")
    dest = Stack(target)
    bucket = main.env.get("GCS_BUCKET", "nando-it-backups")
    prefix = f"{main.env.get('APP_NAME', 'nando-erp-main')}/{main.env.get('ERPNEXT_VERSION', 'latest')}"
    # List latest via backup container / gsutil if available
    list_cmd = (
        f"python3 - <<'PY'\n"
        f"from google.cloud import storage\n"
        f"client = storage.Client.from_service_account_json('/home/frappe/gcs-key.json')\n"
        f"bucket = client.bucket('{bucket}')\n"
        f"blobs = sorted([b.name for b in bucket.list_blobs(prefix='{prefix}/') if b.name.endswith('.sql.gz') or b.name.endswith('-database.sql.gz')])\n"
        f"print(blobs[-1] if blobs else '')\n"
        f"PY"
    )
    r = main.run_compose("exec", "-T", "backup", "bash", "-lc", list_cmd, timeout=300)
    latest = (r.stdout or "").strip().splitlines()[-1] if r.ok else ""
    if not latest:
        print("Could not find latest prod SQL backup in GCS. Download manually and use bench restore.")
        print(f"Expected prefix gs://{bucket}/{prefix}/")
        return 1
    print(f"Latest backup object: {latest}")
    # Download + restore is environment-specific; shell out to a helper script
    helper = get_paths().deployment / "refresh-from-gcs.sh"
    if helper.is_file():
        r = get_executor().run(
            ["bash", str(helper), "--target", target, "--object", latest],
            cwd=str(get_paths().repo_root),
            timeout=14400,
        )
        print(r.stdout)
        if not r.ok:
            print(r.stderr)
            return r.returncode
    else:
        print(f"Helper {helper} missing — restore manually then run sanitize + migrate")
        return 1
    return _sanitize_and_migrate(dest)


def _sanitize_and_migrate(st: Stack) -> int:
    sanitize = r'''
import frappe
frappe.connect()
# Disable email + scheduler side effects
frappe.db.set_single_value("System Settings", "enable_scheduler", 0)
try:
    frappe.db.set_single_value("Email Account", "default_outgoing", 0)
except Exception:
    pass
for name in frappe.get_all("Email Account", pluck="name"):
    try:
        doc = frappe.get_doc("Email Account", name)
        doc.password = ""
        doc.enable_outgoing = 0
        doc.enable_incoming = 0
        doc.save(ignore_permissions=True)
    except Exception as e:
        print("email skip", name, e)
# Clear Google Settings secrets
if frappe.db.exists("DocType", "Google Settings"):
    try:
        gs = frappe.get_single("Google Settings")
        for field in ("api_key", "api_secret", "client_secret"):
            if hasattr(gs, field):
                setattr(gs, field, None)
        gs.save(ignore_permissions=True)
    except Exception as e:
        print("google settings", e)
frappe.db.commit()
print("sanitize ok")
'''
    r = st.run_compose(
        "exec", "-T", "backend", "bench", "--site", st.site, "console",
        timeout=300,
    )
    # console is interactive — use execute instead
    r = st.run_compose(
        "exec", "-T", "backend", "bash", "-lc",
        f"cd /home/frappe/frappe-bench && ./env/bin/python - <<'PY'\n"
        f"import frappe\n"
        f"frappe.init(site='{st.site}')\n"
        f"frappe.connect()\n"
        + sanitize.replace("frappe.connect()\n", "")
        + "\nfrappe.destroy()\nPY",
        timeout=300,
    )
    print(r.stdout or r.stderr)
    r = st.bench("migrate", timeout=3600)
    print(r.stdout)
    if not r.ok:
        print(r.stderr)
        return r.returncode
    st.bench("clear-cache")
    return 0


def _refresh_local(*, with_files: bool = False) -> int:
    bench = local_bench_root()
    if not bench:
        print("NANDO_LOCAL_BENCH required")
        return 1
    site = os.environ.get("NANDO_LOCAL_SITE", "nando.local")
    print(
        f"Local refresh: download latest prod DB from GCS into {bench}/sites/{site}, "
        f"then: bench --site {site} restore <sql> && sanitize && migrate"
    )
    print("Use NANDO_EXECUTOR=ssm nando-erp refresh --target dev for cloud; for local, prefer:")
    print("  gsutil cp gs://nando-it-backups/nando-erp-main/.../xxx-database.sql.gz /tmp/")
    print(f"  bench --site {site} restore /tmp/xxx-database.sql.gz")
    print("  nando-erp refresh --target local --sanitize-only   # after restore")
    return 0


def cmd_baseline(*, stack: str = "main", commit: bool = False) -> int:
    """Export prod fixtures as the git baseline (run once)."""
    print("Baseline export from", stack)
    print("Prerequisite: run `nando-erp assign-modules --stack main --apply` on prod first.")
    rc = cmd_export(target=stack)
    if rc != 0:
        return rc
    # Also copy into local app checkouts if present
    paths = get_paths()
    bench = local_bench_root()
    structure = load_structure()
    for app in structure.apps:
        src = paths.custom_apps / app / app / "fixtures"
        if bench and src.is_dir():
            dest = bench / "apps" / app / app / "fixtures"
            dest.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.json"):
                shutil.copy2(f, dest / f.name)
            print(f"synced fixtures → {dest}")
    if commit:
        ex = get_executor()
        for app in structure.apps:
            for repo in (paths.custom_apps / app, (bench / "apps" / app) if bench else None):
                if not repo or not (repo / ".git").exists():
                    continue
                ex.run(["git", "add", "-A"], cwd=str(repo))
                r = ex.run(
                    ["git", "commit", "-m", "fixtures: baseline export from prod"],
                    cwd=str(repo),
                )
                print(app, r.stdout or r.stderr)
    print(
        "Next: push to main/master and merge into dev. "
        "Then deploy-stack on main and confirm migrate is a no-op."
    )
    return 0


def cmd_assign_modules(*, stack: str = "main", apply: bool = False) -> int:
    """Assign module on Custom Field / Property Setter rows that lack one."""
    structure = load_structure()
    # Heuristic: fields/scripts referencing NANDO Operations DocTypes → NANDO_Operations,
    # else NANDO_CRM. Operators should review the report before --apply.
    st = Stack(stack)
    py = '''
import frappe, json
from collections import defaultdict

FULFILLMENT_HINTS = ("service_order", "service_configuration", "configuration_template",
                     "customer_site", "business_unit", "nando_operations", "fulfillment")
CRM_HINTS = ("quotation", "lead", "opportunity", "nando_crm", "crm")

def guess(doc):
    blob = json.dumps(doc, default=str).lower()
    if any(h in blob for h in FULFILLMENT_HINTS):
        return "NANDO_Operations"
    if any(h in blob for h in CRM_HINTS):
        return "NANDO_CRM"
    # Custom fields on fulfillment-touched ERPNext doctypes
    dt = (doc.get("dt") or doc.get("doc_type") or "").lower()
    if dt in {"delivery note", "work order", "pick list", "material request",
              "stock entry", "installation note", "sales order", "item"}:
        return "NANDO_Operations"
    return "NANDO_CRM"

report = []
for dt in ("Custom Field", "Property Setter"):
    for name in frappe.get_all(dt, pluck="name"):
        doc = frappe.get_doc(dt, name)
        if doc.get("module"):
            continue
        module = guess(doc.as_dict())
        report.append({"doctype": dt, "name": name, "module": module})
print(json.dumps(report, indent=2))
'''
    apply_py = py + '''
APPLY = True
if APPLY:
    for row in report:
        doc = frappe.get_doc(row["doctype"], row["name"])
        doc.module = row["module"]
        doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("applied", len(report))
'''
    code = apply_py if apply else py + "\nprint('dry-run', len(report))\n"
    r = st.run_compose(
        "exec", "-T", "backend", "bash", "-lc",
        f"cd /home/frappe/frappe-bench && ./env/bin/python - <<'PY'\n"
        f"import frappe, json\n"
        f"frappe.init(site='{st.site}')\n"
        f"frappe.connect()\n"
        + code
        + "\nfrappe.destroy()\nPY",
        timeout=600,
    )
    print(r.stdout)
    if not r.ok:
        print(r.stderr)
        return r.returncode
    if not apply:
        print("Re-run with --apply after reviewing the assignment list.")
    return 0


def cmd_release(*, yes: bool = False, actor: str | None = None) -> int:
    """Hotfix release from Quality: capture → push quality → open PRs to master and dev.

    Does not promote to prod by itself — merging the quality→master PR (or the
    push-to-master CI job) runs promote. Rebuild of Quality is triggered by the
    push to the quality branch.
    """
    if not yes:
        print("Refusing: pass --yes to confirm release from Quality.")
        return 1
    actor = actor or os.environ.get("USER") or os.environ.get("NANDO_ACTOR") or "unknown"
    mono = _monorepo_worktree()
    if not mono:
        print("No monorepo checkout for release")
        return 1

    # Capture Quality Desk into monorepo working tree
    rc = cmd_export(target="quality")
    if rc != 0:
        return rc
    paths = get_paths()
    structure = load_structure()
    ex = get_executor()
    for app in structure.apps:
        src = paths.custom_apps / app / app / "fixtures"
        if not src.is_dir():
            continue
        dest = mono / structure.path_for(app) / app / "fixtures"
        dest.mkdir(parents=True, exist_ok=True)
        for f in src.glob("*.json"):
            shutil.copy2(f, dest / f.name)

    # Commit directly on quality (bot identity expected in git config / GH App)
    r = ex.run(["git", "fetch", "origin", "quality"], cwd=str(mono))
    r = ex.run(["git", "checkout", "-B", "quality", "origin/quality"], cwd=str(mono))
    if not r.ok:
        # quality may only exist locally
        r = ex.run(["git", "checkout", "-B", "quality"], cwd=str(mono))
    if not r.ok:
        print(r.stderr)
        return r.returncode
    ex.run(["git", "add", "-A"], cwd=str(mono))
    date = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    r = ex.run(
        ["git", "commit", "-m", f"release: Quality capture {date} ({actor})"],
        cwd=str(mono),
    )
    if r.ok:
        print(f"committed release capture on quality ({date})")
    else:
        print(f"nothing new to commit: {r.stderr or r.stdout}")

    r = ex.run(["git", "push", "origin", "quality"], cwd=str(mono))
    print(r.stdout or r.stderr)
    if not r.ok:
        return r.returncode

    for base in ("master", "dev"):
        # Open PR if none open already
        check = ex.run(
            ["gh", "pr", "list", "--base", base, "--head", "quality", "--json", "number", "-q", "length"],
            cwd=str(mono),
        )
        if check.ok and (check.stdout or "").strip() not in {"", "0"}:
            print(f"PR quality → {base} already open")
            continue
        pr = ex.run(
            [
                "gh", "pr", "create",
                "--base", base,
                "--head", "quality",
                "--title", f"release: Quality → {base} ({date})",
                "--body", (
                    f"Hotfix release captured from Quality by {actor}.\n\n"
                    f"- Merging into **master** triggers promote of the Quality image to prod.\n"
                    f"- Merging into **dev** back-merges the hotfix lane."
                ),
            ],
            cwd=str(mono),
        )
        print(pr.stdout or pr.stderr)
    print("Release capture pushed. Approve/merge PRs to complete.")
    return 0
