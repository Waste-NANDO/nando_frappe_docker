"""CLI command implementations."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from nando_erp_ops.config import get_paths, local_bench_root
from nando_erp_ops.executor import get_executor
from nando_erp_ops.fixtures import diff_dirs, write_docs, load_docs
from nando_erp_ops.fixtures.lint import lint_all, lint_app_fixtures
from nando_erp_ops.stack import Stack
from nando_erp_ops.structure import load_structure
from nando_erp_ops.versions import REQUIRED_PINS, load_stack_env, load_versions, parse_env_file


def cmd_doctor(stack: str | None = None, local: bool = True) -> int:
    versions = load_versions()
    print("=== versions.env ===")
    for key in REQUIRED_PINS:
        print(f"  {key}={versions.get(key, '(missing)')}")
    rc = 0
    for name in (["dev", "main"] if not stack else [stack if stack != "prod" else "main"]):
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
    # Ensure custom apps exist as editable checkouts
    structure = load_structure()
    stack = load_stack_env("dev")
    for app, spec in structure.apps.items():
        app_dir = bench / "apps" / app
        if app_dir.is_dir():
            print(f"→ {app} present (leave branch as-is for feature work)")
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
    if app_dirs is None:
        app_dirs = {}
        bench = local_bench_root()
        paths = get_paths()
        for app in structure.apps:
            candidates = []
            if bench:
                candidates.append(bench / "apps" / app / app / "fixtures")
            candidates.append(paths.custom_apps / app / app / "fixtures")
            for c in candidates:
                if c.is_dir():
                    app_dirs[app] = c
                    break
    errors = lint_all(app_dirs, structure)
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


def cmd_capture(*, stack: str = "dev", push: bool = False) -> int:
    """Export live stack fixtures into capture/<date> branches and optionally open PRs."""
    structure = load_structure()
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    branch = f"capture/{date}"
    # First export into custom-apps
    rc = cmd_export(target=stack)
    if rc != 0:
        return rc
    paths = get_paths()
    ex = get_executor()
    for app in structure.apps:
        repo = paths.custom_apps / app
        if not (repo / ".git").exists():
            print(f"[{app}] skip capture commit — {repo} is not a git checkout (fetch-custom-app first)")
            continue
        r = ex.run(["git", "checkout", "-B", branch], cwd=str(repo))
        if not r.ok:
            print(r.stderr)
            return r.returncode
        ex.run(["git", "add", "-A"], cwd=str(repo))
        r = ex.run(
            ["git", "commit", "-m", f"capture: {stack} fixtures {date}"],
            cwd=str(repo),
        )
        if r.ok:
            print(f"[{app}] committed on {branch}")
        else:
            print(f"[{app}] nothing to commit or commit failed: {r.stderr or r.stdout}")
        if push:
            base = "dev"
            ex.run(["git", "push", "-u", "origin", branch], cwd=str(repo))
            # Prefer gh if available
            pr = ex.run(
                ["gh", "pr", "create", "--base", base, "--head", branch,
                 "--title", f"capture: {stack} fixtures {date} ({app})",
                 "--body", "Auto-captured Desk edits from cloud stack. Review before merge."],
                cwd=str(repo),
            )
            print(pr.stdout or pr.stderr)
    return 0


def cmd_build(*, stack: str = "dev") -> int:
    paths = get_paths()
    env_file = paths.env_file(stack if stack != "prod" else "main")
    # Resolve app SHAs after fetch
    ex = get_executor()
    fetch = paths.deployment / "fetch-custom-app.sh"
    r = ex.run(["bash", str(fetch), str(env_file)], cwd=str(paths.repo_root), timeout=600)
    print(r.stdout)
    if not r.ok:
        print(r.stderr)
        return r.returncode
    structure = load_structure()
    env = load_stack_env(stack if stack != "prod" else "main")
    sha_parts = []
    for app in structure.apps:
        repo = paths.custom_apps / app
        r = ex.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=str(repo))
        short = r.stdout.strip() or "unknown"
        sha_parts.append(f"{app.replace('nando_', '')}.{short}")
        print(f"  {app}@{short}")
    versions = load_versions()
    tag = f"{versions['ERPNEXT_VERSION']}-frappe-{versions['FRAPPE_VERSION'].lstrip('v')}-{'-'.join(sha_parts)}"
    tag = tag.replace("/", "-")
    print(f"Building image tag: {tag}")
    # Temporarily set CUSTOM_TAG via env for the build script
    build = paths.deployment / "build-custom-image.sh"
    env_vars = os.environ.copy()
    # Patch CUSTOM_TAG into a temp env file
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


def cmd_deploy_dev(*, skip_drift: bool = False, with_build: bool = False) -> int:
    if not skip_drift:
        rc = cmd_drift(stack="dev")
        if rc != 0:
            return rc
    paths = get_paths()
    env_file = paths.env_file("dev")
    argv = ["bash", str(paths.deployment / "deploy-stack.sh"), str(env_file)]
    if with_build:
        argv.append("--with-build")
    r = get_executor().run(argv, cwd=str(paths.repo_root), timeout=7200)
    print(r.stdout)
    if not r.ok:
        print(r.stderr)
    return r.returncode


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


def cmd_promote(*, image_tag: str | None = None, yes: bool = False, actor: str | None = None) -> int:
    """Promote the image currently running on cloud-dev to prod."""
    if not yes:
        print("Refusing: pass --yes to confirm promotion (logged).")
        return 1
    actor = actor or os.environ.get("USER") or os.environ.get("NANDO_ACTOR") or "unknown"
    drift_rc = cmd_drift(stack="dev")
    if drift_rc != 0:
        print("Promote blocked: cloud-dev has fixture drift")
        return drift_rc

    dev = Stack("dev")
    main = Stack("main")
    # Resolve running image on dev
    r = get_executor().run(
        ["docker", "inspect", "-f", "{{.Config.Image}}", f"{dev.project}-backend-1"],
        cwd=str(get_paths().repo_root),
    )
    running = (r.stdout or "").strip()
    if not running:
        # try compose ps
        r = dev.run_compose("ps", "-q", "backend")
        cid = r.stdout.strip().splitlines()[0] if r.ok and r.stdout.strip() else ""
        if cid:
            r = get_executor().run(["docker", "inspect", "-f", "{{.Config.Image}}", cid])
            running = r.stdout.strip()
    if not running:
        print("Could not resolve running cloud-dev backend image")
        return 1
    print(f"Cloud-dev running image: {running}")
    if image_tag and running != image_tag and not running.endswith(":" + image_tag.split(":")[-1]):
        print(f"Requested {image_tag} but cloud-dev runs {running}")
        return 1

    src_image = running
    dest_image = f"{main.custom_image}:{main.custom_tag}"
    # If CUSTOM_TAG on main is a placeholder, reuse the source tag name
    if image_tag:
        dest_image = image_tag if ":" in image_tag else f"{main.custom_image}:{image_tag}"
    else:
        # retag with same tag component under prod image name
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

    # Update main env CUSTOM_TAG for render/deploy
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
    # Write a temp env for this deploy so we don't require committing secrets/tag churn
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
        "source_image": src_image,
        "dest_image": dest_image,
    }
    audit_path = paths.deployment / "logs" / "promote-audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a") as f:
        f.write(json.dumps(audit) + "\n")
    print(f"Promote complete. Audit: {audit_path}")
    print(json.dumps(audit))
    return 0


def cmd_refresh(*, target: str = "dev", skip_drift: bool = False, with_files: bool = False) -> int:
    """Restore latest prod GCS backup into target, sanitize, migrate."""
    if target == "local":
        return _refresh_local(with_files=with_files)
    if not skip_drift:
        rc = cmd_drift(stack=target if target != "prod" else "dev")
        if target != "main" and rc != 0:
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
