"""Click CLI entrypoint: `nando-erp`."""
from __future__ import annotations

import click

from nando_erp_ops import commands as cmd

STACK_CHOICE = ["dev", "quality", "main", "prod"]
DEPLOY_CHOICE = ["dev", "quality"]


@click.group()
@click.version_option(package_name="nando-erp-ops")
def main() -> None:
    """NANDO ERP ops — structure up, data down."""


@main.command("doctor")
@click.option("--stack", type=click.Choice(STACK_CHOICE), default=None)
@click.option("--no-local", is_flag=True)
def doctor(stack: str | None, no_local: bool) -> None:
    raise SystemExit(cmd.cmd_doctor(stack=stack, local=not no_local))


@main.command("local-bootstrap")
@click.option("--skip-hrms", is_flag=True)
@click.option("--dry-run", is_flag=True)
def local_bootstrap(skip_hrms: bool, dry_run: bool) -> None:
    raise SystemExit(cmd.cmd_local_bootstrap(skip_hrms=skip_hrms, dry_run=dry_run))


@main.command("lint")
def lint() -> None:
    raise SystemExit(cmd.cmd_lint())


@main.command("export")
@click.option("--target", type=click.Choice(["local", *STACK_CHOICE]), default="local")
@click.option("--app", "apps", multiple=True)
def export(target: str, apps: tuple[str, ...]) -> None:
    raise SystemExit(cmd.cmd_export(target=target, apps=list(apps) or None))


@main.command("drift")
@click.option("--stack", type=click.Choice(STACK_CHOICE), default="dev")
@click.option("--app", "apps", multiple=True)
def drift(stack: str, apps: tuple[str, ...]) -> None:
    raise SystemExit(cmd.cmd_drift(stack=stack, apps=list(apps) or None))


@main.command("capture")
@click.option("--stack", type=click.Choice(["dev", "quality"]), default="dev")
@click.option("--push", is_flag=True, help="Push branch and open PR")
@click.option("--base", default=None, help="PR base branch (default: quality for quality stack, else dev)")
def capture(stack: str, push: bool, base: str | None) -> None:
    raise SystemExit(cmd.cmd_capture(stack=stack, push=push, base=base))


@main.command("build")
@click.option("--stack", type=click.Choice(["dev", "quality", "main", "prod"]), default="dev")
def build(stack: str) -> None:
    raise SystemExit(cmd.cmd_build(stack=stack))


@main.command("deploy")
@click.argument("env", type=click.Choice(DEPLOY_CHOICE))
@click.option("--skip-drift", is_flag=True)
@click.option("--with-build", is_flag=True)
def deploy(env: str, skip_drift: bool, with_build: bool) -> None:
    raise SystemExit(cmd.cmd_deploy(stack=env, skip_drift=skip_drift, with_build=with_build))


@main.command("promote")
@click.option("--image-tag", default=None, help="Optional explicit image ref")
@click.option("--yes", is_flag=True, help="Required confirmation")
@click.option("--actor", default=None)
@click.option("--from", "source", default="quality", type=click.Choice(["quality", "dev"]))
@click.option("--to", "target", default="main", type=click.Choice(["main", "prod"]))
@click.option("--expect-sha", default=None, help="Require image apps sha tree == this commit")
def promote(
    image_tag: str | None,
    yes: bool,
    actor: str | None,
    source: str,
    target: str,
    expect_sha: str | None,
) -> None:
    raise SystemExit(
        cmd.cmd_promote(
            image_tag=image_tag,
            yes=yes,
            actor=actor,
            source=source,
            target=target,
            expect_sha=expect_sha,
        )
    )


@main.command("release")
@click.option("--yes", is_flag=True, help="Required confirmation")
@click.option("--actor", default=None)
def release(yes: bool, actor: str | None) -> None:
    """Capture Quality Desk → push quality → open PRs to master and dev."""
    raise SystemExit(cmd.cmd_release(yes=yes, actor=actor))


@main.command("backup")
@click.option("--stack", type=click.Choice(STACK_CHOICE), default="main")
@click.option("--with-files/--no-files", default=True)
@click.option("--prefix", default=None, help="GCS prefix override (e.g. pre-deploy/...)")
@click.option("--no-upload", is_flag=True)
def backup(stack: str, with_files: bool, prefix: str | None, no_upload: bool) -> None:
    raise SystemExit(
        cmd.cmd_backup(stack=stack, with_files=with_files, prefix=prefix, upload=not no_upload)
    )


@main.command("refresh")
@click.option("--target", type=click.Choice(["dev", "quality", "local"]), default="dev")
@click.option("--skip-drift", is_flag=True)
@click.option("--skip-if-drift", is_flag=True, help="Exit 0 if drift (for cron)")
@click.option("--with-files", is_flag=True)
def refresh(target: str, skip_drift: bool, skip_if_drift: bool, with_files: bool) -> None:
    raise SystemExit(
        cmd.cmd_refresh(
            target=target,
            skip_drift=skip_drift,
            skip_if_drift=skip_if_drift,
            with_files=with_files,
        )
    )


@main.command("baseline")
@click.option("--stack", type=click.Choice(STACK_CHOICE), default="main")
@click.option("--commit", is_flag=True)
def baseline(stack: str, commit: bool) -> None:
    raise SystemExit(cmd.cmd_baseline(stack=stack, commit=commit))


@main.command("assign-modules")
@click.option("--stack", type=click.Choice(STACK_CHOICE), default="main")
@click.option("--apply", is_flag=True)
def assign_modules(stack: str, apply: bool) -> None:
    raise SystemExit(cmd.cmd_assign_modules(stack=stack, apply=apply))


if __name__ == "__main__":
    main()
