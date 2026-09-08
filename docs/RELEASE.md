# Making a WarmTDM Release

This document describes the branch and release mechanics for WarmTDM. For
integration criteria, issue completion and the hardware verification queue,
see [Development and work tracking](WORKFLOW.md).

## Branch model

WarmTDM uses two long-lived branches:

- **`main`** — the stable, released branch. Tags are cut from here.
- **`pre-release`** — the shared development and integration branch. Reviewed
  work can merge after appropriate checks while hardware acceptance remains
  tracked on open issues. Its tip is not necessarily a verified release.

Feature and bugfix branches follow this flow:

```
feature-branch ──PR──▶ pre-release ──PR──▶ main ──tag vX.Y.Z──▶ release
```

1. Branch from `pre-release` and open a PR targeting it explicitly:
   `gh pr create --base pre-release`. The repository default is `main`, so do
   not let tooling guess the PR base.
2. Meet the [integration criteria](WORKFLOW.md#integrating-a-pr), then merge.
   Keep acceptance issues open for any remaining hardware checks. A merged
   feature becomes a foundation for subsequent short-lived branches.
3. Select and verify a fixed release candidate. Promote the tested content to
   `main` using one of the routes below.
4. Tag `main` and publish the verified artifacts.

**Merge, do not rebase.** Bring upstream changes into feature branches with
`git merge`, resolve conflicts, and check the combined result. Use merge
commits when landing stacked branches so their common ancestry is preserved.
Retarget dependent PRs to `pre-release` after their prerequisites land and
inspect the remaining diff before merging.

Feature and ordinary fix PRs target `pre-release`. Only release promotion PRs
target `main`. Temporary release branches accept stabilization fixes through
the explicit exception described below.

## Selecting and testing a candidate

Choose a specific `pre-release` commit for a bench session. Record its exact
software/firmware and submodule revisions, built images and checksums, Vivado
2024.1 build settings, relevant generics/configuration and required board/target
coverage. Preserve the images so the tested firmware remains identifiable.
Record pass/fail evidence on the owning issues; later commits do not inherit
hardware verification automatically.

For a short session, pin the commit in a separate checkout or worktree. Direct
`pre-release` → `main` promotion is appropriate only while the source tip still
matches the verified candidate. If development advances, preserve the selected
commit on a release branch instead of promoting untested additions.

When testing spans days or needs fixes, create one temporary
`release/<version>` branch from the selected commit:

```text
pre-release ── candidate S ───────── new feature work continues
                    \
                     release/<version> ── fixes/tests ──PR──▶ main
```

Accept only candidate stabilization fixes on this branch. Start a fix branch
from the release branch and merge it through PRs into both `release/<version>`
and `pre-release`. This is the release-fix exception to the usual PR base.
Reconcile any conflicts for each destination and verify that the fix reaches
both. Resolve conflicts that require newer `pre-release` work on a separate
integration-side branch; keep that work out of the release fix branch. Do not
merge newer feature work into the candidate to obtain a fix. Repeat affected
checks on the corrected candidate.

A hotfix to an existing release follows the same pattern: create a temporary
release branch from the released tag on `main`, apply and verify the fix, and
ensure it also reaches `pre-release` before completing the release.

## Promotion gate

The promotion PR names the candidate revision and artifacts, the supported
board/target configurations and the issue evidence establishing acceptance.
Link to the evidence rather than maintaining another per-feature status table.
Include system regression checks appropriate to the combined candidate.

All required checks for the included functionality and supported configurations
must pass. Open verification issues for changes outside this candidate do not
block it. For an included failure, fix it, revert it with dependencies
considered, or explicitly exclude the functionality/configuration from the
release and verify the resulting candidate. A label or an open issue alone
does not exclude code from an image. Record any reduced release scope and
retain tracking for the deferred work; do not count deferral as a pass.

Promote either the verified `pre-release` tip or `release/<version>` into
`main`. Confirm that the resulting source tree and submodule revisions match
the verified candidate. Conflict resolutions or other content changes require
validation before tagging. If images are rebuilt or version metadata changes,
record their relationship to the tested artifacts and validate the changes;
do not silently substitute untested images.

After promotion, verify that release fixes are present on `pre-release` and
remove the temporary release branch when no maintenance work depends on it.
Release tags and preserved artifacts retain the verified baseline.

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

Complete the promotion gate above first. The version below is an example;
choose the next version appropriate to the release.

```bash
git checkout main
git pull --ff-only
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
