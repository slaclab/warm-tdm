# Work tracking cleanup — 2026-09-16

This is a dated audit/handoff, not another live backlog. Follow linked issues
and [project 43](https://github.com/orgs/slaclab/projects/43) for subsequent work.
The [plans index](../README.md) is the maintained navigation entry point.

## Goal and baseline

Review PR #107 for integration, account for concurrent work on `channelization`,
reconcile issue/PR disposition and project fields, and refresh the wiki.

- `channelization`: `fae715124013d6e36ce4fce5a2dc8f8eecaefa03`; clean at start.
- `pre-release`: `1045236eecac9719092883b78dee6e850c63698b`.
- PR #107 / `ops-fixes`: `5549d4c11ba0691ed206ac5a0a6072d30c110f8d`.
- Wiki before audit: `d1d2e33112c12d671c95d71b6c6aacae3e66de29`.
- Live issues, PRs, branch tips and project fields read on September 16.

## Actions completed

- Closed [#97](https://github.com/slaclab/warm-tdm/issues/97): its final pending
  policy-integration task is complete. `af8d8de` and the current integration
  baseline are ancestors of published `channelization`; workflow guidance is present.
- Closed PRs [#87](https://github.com/slaclab/warm-tdm/pull/87) and
  [#88](https://github.com/slaclab/warm-tdm/pull/88) as superseded by
  [#106](https://github.com/slaclab/warm-tdm/pull/106). Preserved descriptions,
  ancestry exceptions and branch tips; neither PR was merged.
- Refreshed #68/#70/#82/#83/#90/#99/#100 and PR #106/#107 descriptions with
  current ownership, implementation boundaries and known checks. Hardware
  acceptance was not marked passed by this audit.
- Expanded #106's title and description after a follow-up ancestry review:
  separate frame, integer, FP, resource/legacy/target and verification/model
  scopes; target settings and matching-image requirements; concrete validation
  evidence and integration blockers. The PR remains draft at `fae7151`.
- Created [#108](https://github.com/slaclab/warm-tdm/issues/108) for the offline
  PID analyzer and [#109](https://github.com/slaclab/warm-tdm/issues/109) for
  proposed RSSI segment tuning. These were untracked plan proposals, not
  implemented parts of the channelization PR.
- Corrected project stages for #73/#82/#83/#44 to In Progress. Initialized
  #100 as Firmware/P1/Todo, #108 as Software/P2/Todo and #109 as Firmware/P2/Todo.
  Closure put #97 in Done. Existing priorities were preserved. The audit after
  these changes found all 25 open issues on the board, with no unset
  Status/Track/Priority fields and no duplicate PR planning cards.
- Published four wiki pages in commit `cbbdae7` after explicit user approval:
  [roadmap](https://github.com/slaclab/warm-tdm/wiki/Branch-Merge-Roadmap),
  [verification guide](https://github.com/slaclab/warm-tdm/wiki/Hardware-Verification),
  the old #86 pointer and Home. Historical URLs and reference branches remain.
- Prepared unstaged repository documentation cleanup: plan index; separate
  integer/FP/resource/verification entry points; analyzer moved with redirect;
  stale hardware-before-integration gates and old tool claims removed from the
  active plans; historical logs preserved and labeled. AGENTS points to the index.

## PR disposition

| PR | Audit decision | Concrete remaining work |
|---|---|---|
| #107 operations | Hold the reviewed head | Publish the prepared dead-mask/slow-zero fixes, pass CI, then merge into `pre-release`; #68 retains acceptance |
| #106 consolidated firmware | Keep draft | Repair CI/removed-driver test, incorporate #107 fixes, current tree/register checks, generated-IP and system verification, Vivado 2024.1 builds; #70/#82/#90 own checks |
| #87 FP / #88 cleanup | Closed as superseded | Preserve historical reviews; integration now through #106 |
| #74 quick start / Python version | Keep open | Conflicts with current `pre-release`; reconcile docs/environment/CI and validate the updated head |
| #58 Docker | Keep open | `HOST_USER`/`HOST_GROUP` used by `chown` before their ARG declarations and user/group creation; repair build ordering and demonstrate build/runtime against the intended source |

A green old CI run on #58/#74 does not test the current integration or build a
Docker image. No other PR was represented as safe to merge merely to reduce
its count.

## Work carried by channelization

| Effort | What exists at the audit revision | Outstanding owner/boundary |
|---|---|---|
| Frame/channel identity | Tagged header, board-namespaced files, waveform file routing, PID stream collapse, versioned decoders | #82: end-to-end/timestamp/multi-board compatibility; #100 is the separate leading-empty-frame/count defect |
| Accumulator and integer controller | Split front end, state/overflow/feedback repairs, retained fractional feedback, flux/count transport and DAC delivery corrections | #70: generated/system/build/physical validation; #90: maintained tests |
| Floating-point controller | Seed, masked-state, clipping, I-change lifecycle, quantum configuration and diagnostics fixes (`07a87d0`); source cleanup (`fae7151`) | #70: vendor IP, closed-loop comparisons, timing/utilization, hardware |
| Resource/legacy/targets | Debug/memory/FIFO/row-width choices, legacy driver removal, build/power tooling | #70: candidate build/packaging compatibility; #73 runtime capacity discovery is not implemented by this work |
| Regression infrastructure | GHDL integer and modeled FP benches, independent arithmetic oracle, native vendor bench | #90: working CI and generated-IP execution; modeled passes are not vendor/hardware passes |
| Sensor/operations support | Integrated foundations, later wafer shaping and ops-fixes history | #68/#83/#99; #98 closure needs clarification below |
| Offline PID analyzer | Proposal and repaired prerequisite decoders, but no metrics/diagnosis/comparison API | #108: separate future implementation |
| RSSI larger segments | Proposal only; both instances still use 1024-byte segments | #109: independent transport/resource evaluation |

The old plans mixed these scopes and stale next steps. Current design entry
points link existing evidence rather than deleting or duplicating the history.

## Issue closure accounting

Only #97 had a fully evidenced completion suitable for closure in this audit.

- #70/#82/#90 remain open: implementation and local tests exist, but their
  integration/system/build obligations remain.
- #68/#99 retain real hardware/tuning acceptance; #55 retains physical waveform
  and sustainable-rate checks. #24/#36 retain their existing hardware checks.
- #73 still lacks firmware-capacity discovery/clamp/warn; source/tree sizing is
  only part of its scope. #83's mask graduation has the #107 regression.
- #56 explicitly retains bench-notebook curation/output policy, despite the
  operations package and worked notebook being in git.
- #27 still lacks selectable locking slope; current curve selection uses the
  maximum slope. #44 has model-coefficient analysis and sample-normalized gains,
  but that is not a complete supported physical P/I/D-unit contract.
- #31/#39/#42/#52 and #100 retain their distinct fault/acceptance scope; no
  relevant physical pass was inferred from the PID model results.
- #45/#54/#80/#81/#103 remain separate uncompleted features/design decisions.
- #98 was closed by the maintainer on September 11, but its body still has
  unchecked production/startup/hardware items and its only result comment is
  the limited September 8 model regression. Asked whether those checks passed
  or were intentionally removed. Left the issue closed pending that answer;
  did not invent a completion result or silently undo the maintainer's decision.

## Branch accounting

No branches were deleted. Exact containment was tested against the baseline
above using `git merge-base --is-ancestor`; remote refs came from `ls-remote`,
not the stale local tracking-ref list.

`channelization` inherited cleanup directly: its first commit `539b6d0` has
`f0af673` as its parent. That cleanup commit already merged the operations
refactor and FP-PID work. The latest cleanup tip was not subsequently merged
wholesale. Its distinct merge history remains, plus the ADC entity correction
listed below; this distinction is now explicit in PR #106.

**15 remote feature tips fully contained in `pre-release`**, suitable for
retirement after any maintainer-specific retention needs are checked:

`add_data_path_emulator`, `batcher-v2`, `cleanup-sw`,
`docs/integration-verification-policy`, `dup-legends`, `fix-fas-tune`,
`fix-warmtdm-emulate-import`, `fix_release_gh_actions`, `fpga-board-dev`,
`sensor-wafer-sim`, `tes-bias-waveform`, `test-ad9681-ddr`, `tuning-refactor`,
`wtj`, `wtj-refactor`.

| Other remote branch | Disposition |
|---|---|
| `main`, `pre-release` | Long-lived branches; retain |
| `gh-pages` | Documentation deployment; retain |
| `channelization` | Active #106 integration |
| `ops-fixes` | #107; head is in channelization, but not yet pre-release |
| `rtl-cocotb-regression` | Fully contained in channelization; retain until consolidated integration |
| `fp-pid` | Only unique commit `2c65915` updates SURF to `af07029`, an ancestor of channelization's `70191c1`; source consolidated, branch preserved |
| `cleanup` | Unique non-merge commit `fc1d1dd` corrects `surf.Ad9681Readout`, already present; additional unique history consists of merges; preserve until consolidation accepted |
| `basic_instructions`, `docker` | Open #74/#58, with issues above |
| `retire-warmtdm-emulate` | One unique historical cleanup commit; inspect patch equivalence before retirement rather than declaring ancestry |
| `artix-us`, `vesper` | Deliberate reference branches; retain, never merge per existing roadmap |

Local-only/stale-tracking branches also exist. `pydm-widgets` has no unique
commits versus `pre-release`. `pid-fixes` has three old prototype commits whose
harness was salvaged under #90; do not resurrect its older RTL. The local
`sq1-tuning-optimization` experiment needs comparison with current tuning before
any retirement decision. Stale `origin/*` refs are not evidence that those
remote branches still exist.

## PR #107 reproduction, proposed fix and validation

Isolated review worktree: `/private/tmp/warm-tdm-ops107-fix`, detached at
`5549d4c`. Patch: `/private/tmp/warm-tdm-pr107-fixes.patch`.

- `apply_dead_masks({0: 5})` updates the LocalVariable with zero hardware-setter
  calls. The proposed correction writes the board-local register first and
  caches the desired value only after success, including disabled columns.
- With `ColEnableMask=1`, real PyRogue GroupLinkVariable setters leave seven
  slow-output values at 25 while `stop_and_zero` reports True. The reproduction
  uses synthetic leaves and stubs fast-DAC completion; it does not claim a full
  production tree or hardware run. The correction uses the same unmasked
  board-local slow-output leaves and continues after individual failures.
- The two targeted regression cases fail on the original source and pass with
  the patch. Full isolated PR software suite: **74 passed, 42 subtests passed**
  with the patch (original suite: **70 passed, 42 subtests passed**).
- All eight changed production VHDL files in #107 are identical after intended
  identifier substitution, comment removal and whitespace normalization; no
  old timing-record field references remain in those sources. No synthesis or
  new GroupTb result is claimed. SURF's pin update is separate from that check.

The user has been asked to authorize staging/committing/pushing these three
files to `ops-fixes`, followed by a merge after passing CI. No such commit or
merge has occurred at this handoff. The no-commit instruction still applies to
repository plan edits; wiki publication alone was explicitly approved.

## Other validation and next steps

- `channelization` software suite: **127 passed, 54 subtests passed, 1 failed**;
  failure is the removed ColumnModule helper subtest. This confirms the known
  source failure independently of CI's missing-pytest import errors.
- GitHub issue/PR/project mutations were reread; all open issues have board
  cards and complete fields. Wiki push succeeded and the clone is clean.
- Repository and wiki `git diff --check` pass; local Markdown link targets in
  changed/new plan files were checked.
- Await the #107 commit/push exception and #98 scope clarification. If #107 is
  approved, recheck its head, commit only the prepared files, push, wait for CI,
  merge with a merge commit, then ensure the fixes reach channelization through
  the normal merge workflow. Do not claim existing channelization ancestry
  includes those as-yet unpublished corrections.
- Repository plan/navigation changes remain unstaged for the user to review
  and commit. No FPGA build, bench test, branch deletion or release was performed.
