# warm_tdm_jupyter refactor — Progress

Plan: [PLAN.md](PLAN.md) · Spec: [SPEC.md](SPEC.md)

## Status: planning — awaiting approval to execute

See also: [MERGE-cleanup.md](MERGE-cleanup.md) — analysis + plan for adopting the
`cleanup` branch's software refactor (do NOT straight-merge; cherry-pick the
software side, gated on hardware validation).

Review of PR #61 complete. Branch `wtj-refactor` created off `wtj`. Plan set
scaffolded. No source code changed yet.

| Task | Description | Status | Commit |
|---|---|---|---|
| 0 | Review PR #61 + scaffold plan/branch | ✅ | — |
| 1 | Correctness fixes (README, scipy, take_raw timeout, dead import, num_generators) | ⬜ | — |
| 2 | Adopt `cleanup` software refactor (Group split, launcher, maxRows) — [MERGE-cleanup.md](MERGE-cleanup.md), HW-gated | ⬜ | — |
| 3 | Rename/rehome → `warm_tdm_api.operations` | ⬜ | — |
| 4 | Analysis + `operations` structural cleanup | ⬜ | — |
| 5 | Group graduations (G-items, as they mature — deprioritized) | ⬜ | — |
| 6 | Verification | ⬜ | — |

**Blocked on user decisions:** constants home (PLAN open decision 3) and the
bench board for the Task 2 HW gate. Package name resolved (`operations`); cadence
resolved (rehome-first, graduate-later).

## Log

- 2026-07-21: Reviewed PR #61 (branch `wtj`). Findings: the package is
  mislabeled "jupyter" (only one incidental, unused-downstream Jupyter call);
  the central smell is the global-singleton `Client`; reusable hardware
  capabilities are trapped in the convenience layer instead of living on the
  rogue tree like `TesBiasWaveformProcess` does. User confirmed the
  single-system/global-`Client` limits are acceptable and asked to start a
  running list of capabilities that should move to `Group` methods (see PLAN.md
  "Capabilities to move to Group": G1–G8).
- 2026-07-21: Created `wtj-refactor` branch off `wtj` and scaffolded SPEC/PLAN/
  PROGRESS under `docs/plans/wtj-refactor/`. Awaiting decisions before executing.
- 2026-07-21: Scoped the cleanup software adoption. Resolved: `maxRows` pinned
  to 256 (derived from RTL — `2**ROW_ADDR_BITS_G`, default 8; `160Coord`
  overrides to 32). Deferred (not part of the software merge): the v1/retired
  register-driver deletions (firmware track). Adoption is by content (path-scoped
  diff), not commit cherry-pick, because the software refactor spans partial
  commits (e.g. f917982 mixes GroupConfig software changes with firmware-python
  deletions).
- 2026-07-21: Placed the cleanup adoption as **Task 2** (was unplaced — it lived
  only in MERGE-cleanup.md while the task list jumped to a Group-migration PoC).
  It's the structural foundation: it creates `_GroupVariables`/`_GroupConfig`,
  which the rename (Task 3) rehomes and the Group graduations (Task 5) target, so
  it must precede both. Dropped the old "PoC Group migration" task — the
  graduation reframing made it obsolete (nothing meets the move-now gate, and
  adopting cleanup's `_GroupVariables` split is what validates the architecture
  the PoC was meant to prove). Resequenced: 1 fixes → 2 cleanup (HW-gated) →
  3 rename → 4 analysis cleanup → 5 graduations → 6 verify.
- 2026-07-21: Resolved package name → **`warm_tdm_api.operations`** (subpackage,
  not sibling). It's the client-side operational layer, production-bound, not
  throwaway. Also captured the original author's key rationale: these functions
  were kept client-side deliberately for **runtime editability** (a `Group`
  method needs a server restart → drops tuning state → slow re-tune). Reframed
  the G-list as a **maturity-gated graduation list** with a client/server
  criterion: move now only if it needs server-side execution (loops/GUI/state,
  like the already-migrated `TesBiasWaveformProcess`); otherwise keep in
  `operations` and graduate as it stabilizes. Near-term: rehome everything into
  `operations`, graduate later. Noted the "make retuning MCE-fast" alternative as
  the deeper (out-of-scope) unblock.
- 2026-07-21: Reversed the launch-script deferral — the unified `warmTdmServer.py`
  consolidation (89c194f: GUI folded behind `--gui`, `gui.py`/`warmTdmGui.py`
  deleted, new `WarmTdmArgparse`/`arg_dict` surface) is now IN SCOPE. Corrected
  an earlier wrong note: that commit does NOT delete `testGroup.py`. Flagged that
  its `--floatPid`/`--maxRows` flags come in but must default to current
  (pre-FP) firmware values, and added a `--gui` GUI-launch check to the
  validation gate.
- 2026-07-21: Analyzed the `cleanup` branch for merge. Straight `git merge`
  rejected: 52 commits, merge-base predates `pre-release`, all conflicts are
  firmware/target-reorg (old target names vs our renames, submodule + AdcDsp +
  releases.yaml), and it would drag in untested firmware (AdcDspFp FP rewrite,
  accumulator split). The `software/` refactor itself auto-merges clean, but
  `GroupConfig.maxRows` couples to firmware `ROW_ADDR_BITS_G`, so it still needs
  hardware validation. Recommendation written to MERGE-cleanup.md: cherry-pick
  the software refactor (Group split → `_GroupVariables`/`_GroupConfig`, logging,
  ArgParser) on a gated branch, hold back firmware-python deletions and row-size
  reductions. This should precede the G1/G3 Group migrations since it changes
  where `GroupLinkVariable` lives.
- 2026-07-21: Merged `origin/pre-release` into `wtj-refactor` (merge `d9baabb`,
  no conflicts). Brought in the target-cleanup firmware reorg, root `AGENTS.md`,
  `firmware/FIRMWARE_GUIDE.md`, `software/SOFTWARE_GUIDE.md`, `docs/RELEASE.md`,
  and release automation. Reconciled the plan against these guides: added a
  Conventions & references section, adopted the documented `GroupLinkVariable`
  pattern for G1/G3, added doc-update steps to the rename task (both guides omit
  the new package), and pinned the PR target to `pre-release`.
