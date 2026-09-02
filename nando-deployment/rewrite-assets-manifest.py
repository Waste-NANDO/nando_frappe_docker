#!/usr/bin/env python3
"""Point sites/assets/assets*.json at the hashed bundles that exist on disk."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

BENCH = Path("/home/frappe/frappe-bench")
ASSETS = BENCH / "sites" / "assets"
BAKED = BENCH / ".baked-assets"
BUNDLE = re.compile(r"^(.+\.bundle)\.[A-Za-z0-9_-]+(\.(?:css|js))$")


def restore_baked() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if not BAKED.is_dir():
        return
    for src in BAKED.glob("*.json"):
        dest = ASSETS / src.name
        if not dest.is_file():
            shutil.copy2(src, dest)
            print(f"restored {dest.name} from baked")


def index_files() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in ASSETS.rglob("*"):
        if not path.is_file():
            continue
        match = BUNDLE.match(path.name)
        if not match:
            continue
        logical = match.group(1) + match.group(2)
        url = "/assets/" + str(path.relative_to(ASSETS))
        found.setdefault(logical, []).append(url)
    return found


def pick(candidates: list[str], old: str) -> str:
    old_rtl = "/css-rtl/" in old
    old_js = "/dist/js/" in old or old.endswith(".js")
    for url in candidates:
        if old_rtl and "/css-rtl/" in url:
            return url
        if (not old_rtl) and "/css-rtl/" not in url and old_js == ("/dist/js/" in url):
            if ".bundle." in url:
                return url
    return candidates[0]


def rewrite_value(value: object, found: dict[str, list[str]]) -> object:
    if isinstance(value, dict):
        return {key: rewrite_value(item, found) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_value(item, found) for item in value]
    if not isinstance(value, str) or ".bundle." not in value:
        return value
    name = value.rsplit("/", 1)[-1]
    match = BUNDLE.match(name)
    if not match:
        return value
    logical = match.group(1) + match.group(2)
    candidates = found.get(logical, [])
    if not candidates:
        return value
    return pick(candidates, value)


def rewrite_manifest(path: Path, found: dict[str, list[str]]) -> None:
    data = json.loads(path.read_text())
    path.write_text(json.dumps(rewrite_value(data, found), indent=1) + "\n")
    print(f"rewrote {path.name}")


def main() -> None:
    restore_baked()
    found = index_files()
    if not found:
        raise SystemExit("no hashed bundles under sites/assets")
    for name in ("assets.json", "assets-rtl.json"):
        path = ASSETS / name
        if path.is_file():
            rewrite_manifest(path, found)
    desk = sorted({u.rsplit("/", 1)[-1] for u in found.get("desk.bundle.css", [])})
    print("desk.bundle.css files:", " ".join(desk) or "(none)")
    if (ASSETS / "assets.json").is_file():
        hashes = sorted(set(re.findall(r"desk.bundle.[A-Za-z0-9]+", (ASSETS / "assets.json").read_text())))
        print("assets.json desk refs:", " ".join(hashes))


if __name__ == "__main__":
    main()
