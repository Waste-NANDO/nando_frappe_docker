"""Click CLI entrypoint: `nando-erp`."""
from __future__ import annotations

import click

from nando_erp_ops import commands as cmd


@click.group()
@click.version_option(package_name="nando-erp-ops")
def main() -> None:
    """NANDO ERP ops — structure up, data down."""


@main.command("doctor")
@click.option("--stack", type=click.Choice(["dev", "main", "prod"]), default=None)
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
@click.option("--target", type=click.Choice(["local", "dev", "main", "prod"]), default="local")
@click.option("--app", "apps", multiple=True)
def export(target: str, apps: tuple[str, ...]) -> None:
    raise SystemExit(cmd.cmd_export(target=target, apps=list(apps) or None))


@main.command("drift")
@click.option("--stack", type=click.Choice(["dev", "main", "prod"]), default="dev")
@click.option("--app", "apps", multiple=True)
def drift(stack: str, apps: tuple[str, ...]) -> None:
    raise SystemExit(cmd.cmd_drift(stack=stack, apps=list(apps) or None))


@main.command("capture")
@click.option("--stack", type=click.Choice(["dev", "main"]), default="dev")
@click.option("--push", is_flag=True, help="Push branch and open PR into dev")
def capture(stack: str, push: bool) -> None:
    raise SystemExit(cmd.cmd_capture(stack=stack, push=push))


@main.command("build")
@click.option("--stack", type=click.Choice(["dev", "main"]), default="dev")
def build(stack: str) -> None:
    raise SystemExit(cmd.cmd_build(stack=stack))


@main.command("deploy")
@click.argument("env", type=click.Choice(["dev"]))
@click.option("--skip-drift", is_flag=True)
@click.option("--with-build", is_flag=True)
def deploy(env: str, skip_drift: bool, with_build: bool) -> None:
    if env != "dev":
        raise click.ClickException("Use `nando-erp promote` for prod")
    raise SystemExit(cmd.cmd_deploy_dev(skip_drift=skip_drift, with_build=with_build))


@main.command("promote")
@click.option("--image-tag", default=None, help="Optional explicit image ref")
@click.option("--yes", is_flag=True, help="Required confirmation")
@click.option("--actor", default=None)
def promote(image_tag: str | None, yes: bool, actor: str | None) -> None:
    raise SystemExit(cmd.cmd_promote(image_tag=image_tag, yes=yes, actor=actor))


@main.command("backup")
@click.option("--stack", type=click.Choice(["dev", "main", "prod"]), default="main")
@click.option("--with-files/--no-files", default=True)
@click.option("--prefix", default=None, help="GCS prefix override (e.g. pre-deploy/...)")
@click.option("--no-upload", is_flag=True)
def backup(stack: str, with_files: bool, prefix: str | None, no_upload: bool) -> None:
    raise SystemExit(
        cmd.cmd_backup(stack=stack, with_files=with_files, prefix=prefix, upload=not no_upload)
    )


@main.command("refresh")
@click.option("--target", type=click.Choice(["dev", "local"]), default="dev")
@click.option("--skip-drift", is_flag=True)
@click.option("--with-files", is_flag=True)
def refresh(target: str, skip_drift: bool, with_files: bool) -> None:
    raise SystemExit(cmd.cmd_refresh(target=target, skip_drift=skip_drift, with_files=with_files))


@main.command("baseline")
@click.option("--stack", type=click.Choice(["main", "prod", "dev"]), default="main")
@click.option("--commit", is_flag=True)
def baseline(stack: str, commit: bool) -> None:
    raise SystemExit(cmd.cmd_baseline(stack=stack, commit=commit))


@main.command("assign-modules")
@click.option("--stack", type=click.Choice(["dev", "main", "prod"]), default="main")
@click.option("--apply", is_flag=True)
def assign_modules(stack: str, apply: bool) -> None:
    raise SystemExit(cmd.cmd_assign_modules(stack=stack, apply=apply))


if __name__ == "__main__":
    main()
