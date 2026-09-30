# 10 — Release a hotfix from Quality

Hotfixes and UAT sign-off happen on **Quality** (`:3001`). Structure edits Desk-side are allowed there; `nando-erp release` captures them into the `quality` branch.

## Prerequisites

- Quality stack is up and running the image you want to ship
- Bot / technical user can push to `quality` on `nando-erp-modules`
- Maintainer approves PRs into `master` (and optionally `dev`)

## Flow

1. Fabri (or you) edits / tests on Quality Desk.
2. On the ERP host (or via SSM):

```bash
nando-erp release --yes
```

This:

1. Exports fixtures from Quality
2. Commits them on the `quality` branch of `nando-erp-modules`
3. Pushes `quality` (CI rebuilds/redeploys Quality)
4. Opens PRs `quality → master` and `quality → dev`

3. Maintainer reviews and merges **`quality → master`**.
4. Push to `master` runs promote: identical Quality image → prod (with pre-deploy backup + tree check).
5. Merge **`quality → dev`** so the hotfix is not lost on the next promotion from cloud-dev.

## Rules

- Never edit structure on prod Desk
- Unfinished work stays on feature branches / local — not on `dev`
- If `release` is blocked by nothing-to-commit, Quality already matches git; open the PRs by hand or re-capture after a real Desk change
- Back-merge conflicts on fixture JSON files are expected when the same doctype was edited on both lanes — resolve in the PR
