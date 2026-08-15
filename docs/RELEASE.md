# Making a WarmTDM Release

This document describes the git workflow and release process for WarmTDM,
following the same conventions used by [surf](https://github.com/slaclab/surf)
and other SLAC firmware repositories.

## Branch model

WarmTDM uses two long-lived branches:

- **`main`** — the stable, released branch. Tags are cut from here.
- **`pre-release`** — the integration branch. Feature work is merged here first
  and allowed to stabilize before promotion to `main`.

Feature and bugfix branches follow this flow:

```
feature-branch ──PR──▶ pre-release ──PR──▶ main ──tag vX.Y.Z──▶ release
```

1. Branch off `pre-release` (or `main` for hotfixes) for your work.
2. Open a PR into `pre-release`. CI runs the syntax/lint checks.
3. Once `pre-release` is stable, open a PR merging `pre-release` into `main`.
4. Tag `main` with a version (see below) to trigger the release.

**Merge, do not rebase.** WarmTDM's workflow is merge-based throughout. When a
feature branch has fallen behind, bring the upstream branch in with `git merge`
(e.g. `git merge origin/pre-release`) and resolve any conflicts in the resulting
merge commit — do **not** `git rebase`. This holds even for a local-only branch
that has never been pushed: rebase is simply not the workflow we use.

## Versioning

Releases are tagged `vX.Y.Z` (semantic versioning):

- **Major** (`v1.0.0`) — breaking changes.
- **Minor** (`v1.1.0`) — new features, backward compatible.
- **Patch** (`v1.0.1`) — bug fixes only.

The first release is **`v1.0.0`**.

## Cutting a release

### 1. Tag `main`

```bash
git checkout main
git pull
git tag v1.0.0
git push origin v1.0.0
```

Pushing a `vX.Y.Z` tag triggers the `gen_release` job in
`.github/workflows/warm_tdm_ci.yml`, which calls the reusable ruckus workflow
`slaclab/ruckus/.github/workflows/gen_release.yml`. This creates the GitHub
Release with auto-generated release notes (commit log since the previous tag).

### 2. Attach firmware images

CI cannot build FPGA `.mcs` images, so a maintainer attaches them from a
machine that has the built images. The targets and their image directories are
defined in [`firmware/releases.yaml`](../firmware/releases.yaml).

Run the ruckus release script locally:

```bash
python firmware/submodules/ruckus/scripts/firmwareRelease.py \
    --project firmware \
    --release warmTdm \
    --version v1.0.0 \
    --token <github_token> \
    --push
```

This packages the Rogue software and each target's `.mcs` image and uploads
them as assets to the `v1.0.0` GitHub Release. Omit `--push` for a dry run.

## Prerequisites

- The `GH_TOKEN` repository secret must be set (used by the CI `gen_release`
  job). Already configured for this repo.
- For the local `firmwareRelease.py` step, a GitHub token with `repo` scope and
  the built `.mcs` images present under each target's `ImageDir`.
