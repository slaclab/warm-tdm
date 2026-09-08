# Development and work tracking

WarmTDM integrates reviewed changes into `pre-release` before all hardware
acceptance testing is complete. An issue remains open until its acceptance
criteria are satisfied. A merged PR records completed integration; it does not
by itself mean that the feature is verified or released.

For branch mechanics, candidate testing and promotion to `main`, see
[RELEASE.md](RELEASE.md).

## Where information belongs

| Record | Responsibility |
|--------|----------------|
| Issue | Objective, acceptance criteria, outstanding checks, assignee, evidence and completion decision |
| PR | Concrete implementation, review discussion and validation evidence for the proposed revision |
| Project board | Priority, Track and workflow Status on the underlying issues |
| Wiki and repository docs | Reusable procedures, architecture and project policy |

Use the [Warm-TDM Roadmap project](https://github.com/orgs/slaclab/projects/43)
to prioritize issues. Do not add a PR as a second planning card for the same
work. Keep Priority, Track and Status in project fields rather than copying
them into issue or PR bodies. An issue's open/closed state is authoritative
for whether work remains; the board describes its workflow stage.

The [Branch Merge Roadmap wiki](https://github.com/slaclab/warm-tdm/wiki/Branch-Merge-Roadmap)
can explain cross-branch sequencing decisions and link to issues and PRs.
Avoid maintaining copies of their current statuses or completion checklists.
Repository design plans may preserve rationale and implementation guidance;
link ongoing tasks to issues instead of maintaining another progress inventory.

## Issue lifecycle

Use one issue for a coherent feature or fix, through implementation and
acceptance. Several PRs may contribute to it. Keep the objective and remaining
acceptance checklist in the issue body; put dated test results and logs in
comments. Link evidence from completed checklist items where useful.

| Board Status | Meaning |
|--------------|---------|
| Todo | Work has not started |
| In Progress | Implementation, active testing or corrective work is underway |
| Needs HW Test | The implementation and required pre-bench checks are complete; the remaining checks are ready for bench time |
| Blocked | A named dependency prevents progress; explain it in the issue |
| Done | The issue is closed with an explicit completion or cancellation outcome |

Close an issue as completed only after its acceptance criteria pass and the
evidence is recorded. If the work is canceled, superseded or reduced in scope,
record the decision and any replacement issue. A canceled check is not a pass
and must not be presented as release validation. Release publication is a
separate step; an accepted feature need not remain open until it ships.

The `roadmap` label identifies planning/epic issues. They summarize objectives
and relationships; actionable acceptance work belongs to the issues that own
it. Do not maintain duplicate parent and child checklists.

## Integrating a PR

1. Branch from `pre-release` and open a PR targeting `pre-release`. Keep the
   change coherent and identify prerequisite work. If a temporary stack is
   needed for review, identify the parent PR and retarget to `pre-release`
   after the parent lands; do not merge the child PR into the feature branch.
2. Complete review and appropriate checks against the current integration
   baseline. Use software tests, emulation, simulation and affected-target
   builds according to the change. Firmware builds use Vivado 2024.1. The
   current GitHub workflow performs Python syntax checks; a green run alone
   does not establish firmware correctness or timing closure.
3. Record what was tested and what remains unverified. Before merging a
   hardware-affecting change with deferred acceptance, ensure an owning issue
   contains the required checks, pass criteria and the `hw-verification`
   label. Link it from the PR. Do not defer a prerequisite simulation or build
   check merely because the analog bench is unavailable.
4. Merge when the change is ready for other developers to use. Update the
   issue's board stage, leaving the issue open if acceptance remains. Retire
   the feature branch after dependent work is reconciled; follow-up fixes get
   new PRs from `pre-release` linked to the same issue.

Use `Refs #<n>` or an explicit issue link while acceptance remains outstanding.
Do not use closing keywords in PR descriptions or commit messages for work
that is still awaiting verification. With `main` as the default branch,
GitHub does not apply PR-description closing keywords to PRs targeting
`pre-release`; do not rely on an earlier PR's description being processed
later during promotion. Close accepted issues explicitly, or use closing
keywords in a promotion PR only for issues whose acceptance is already complete.
See [GitHub's issue-linking rules](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue).

Treat integration regressions as active work: fix promptly or revert with
dependent changes considered. Integration must remain a useful development
baseline. Hardware acceptance of a particular feature may still be pending.

## Hardware verification queue

Apply **`hw-verification`** to the issue that owns hardware acceptance checks.
Normally this is the original feature issue. Retain the label after closure
so completed verification remains searchable.

The repository-wide backlog is the live issue search:

```text
repo:slaclab/warm-tdm is:issue is:open label:hw-verification
```

[Open hardware verification issues](https://github.com/slaclab/warm-tdm/issues?q=is%3Aissue%20is%3Aopen%20label%3Ahw-verification)
include work under development, ready for testing, blocked or undergoing fixes.
Use a project view with `is:issue is:open label:hw-verification` for this full
backlog, and add `status:"Needs HW Test"` for the ready-to-test view. A failed
test moves the issue back to In Progress or Blocked but leaves it in the full
backlog.

### Acceptance and evidence

In the owning issue, record:

- Required board/target configurations, setup and prerequisites.
- A checklist of remaining checks with observable pass criteria. Put a short
  one-off procedure here; link to a reusable procedure when one exists.
- Implementation PRs and any known compatibility constraints, such as a
  matching firmware/software pair.

For each test session, add a result comment with:

- Date and tester; exact software and firmware commit IDs, submodule revisions,
  image identity or checksum, build tool version and relevant generics/config.
- Board variants and test setup actually exercised.
- Pass/fail for the checks attempted, measurements and links to logs or plots.
- Remaining checks, failures or limitations of that result.

Test a fixed candidate as described in [RELEASE.md](RELEASE.md). A successful
session may satisfy checks on several issues; reference the same evidence
instead of copying the test report. Passing on one setup does not establish
coverage of other targets or later revisions. Changes affecting a previously
tested path require an assessment of which checks must be repeated.

When a test fails, retain the acceptance item and link corrective PRs. Create
a separate bug issue only when the defect needs independent ownership or
scope. Keep required acceptance open until the fix is verified. For a new
regression discovered after closure, open a new issue referencing the earlier
evidence rather than rewriting the historical result.

### When to use a separate verification issue

Use a verification sub-issue only when the checks need independent ownership,
scheduling or completion: for example, separately tested board variants, a
cross-feature system test, or hardware acceptance that can finish while a
larger parent feature remains in development.

The child owns its procedure, evidence and `hw-verification` label. The parent
links to the child and remains open until required children and its own
acceptance are complete. If all hardware checks move to children, remove the
label from the parent so the queue contains each obligation once. A
cross-feature test can have one owning issue with links to all related issues.
Do not create a second verification issue merely because a PR merged.

GitHub [sub-issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues)
and project progress fields can display these relationships without manually
maintained progress summaries.

## Board automation and documentation

Keep `Track` and `Priority` on project items. Use issue labels for categories
such as `roadmap` and `hw-verification`, not a second set of workflow statuses.

Configure automatic addition of repository issues to the project and let
issue closure set project Status to Done. Completion is decided on the issue;
avoid automation that closes unfinished issues on PR merge or simply because
someone moves a board card. Record canceled outcomes explicitly even if the
board also places them in Done.

The [Hardware Verification wiki](https://github.com/slaclab/warm-tdm/wiki/Hardware-Verification)
is an entry point linking to the live backlog, board views and reusable bench
procedures. It does not maintain per-feature status rows. Procedures in the
wiki or repository describe how to test; issue comments record candidate-
specific outcomes. Retain old URLs and historical reports when migrating.

## Adopting this policy

These are one-time migration instructions. Track their execution in a single
migration issue; this document is not a second migration status checklist.

1. Review and merge the policy PR into `pre-release`. Link this policy from
   the migration issue and project description. Bring the updated guidance
   into active branches with merges, resolving older `AGENTS.md` rules in
   favor of this policy while preserving unrelated branch documentation.
2. Create the `hw-verification` label with description "Owns hardware
   acceptance checks; retained after completion". Ensure the board has
   Needs HW Test, and configure the full-backlog and ready-to-test views above.
3. Reconcile existing wiki entries, open PR gates and board items into their
   original owning issues. Preserve completed evidence, move outstanding
   one-off procedures/checklists to the issues, label them and assign the
   correct board stage. Identify an owning issue for branches without PRs.
   Do not mark tests passed merely because implementation is complete.
4. Audit closed issues whose required hardware acceptance is still outstanding.
   Reopen those original issues with an explanation, or link an independently
   scoped verification issue where the exception above applies. Make every
   outstanding obligation appear once in the live backlog.
5. Replace the wiki's manual index with the live links. Leave pointers on old
   per-item pages to the owning issues, preserving historical evidence and
   reusable procedures. Update open PRs to link their owning issues and remove
   obsolete "must bench-test before merge" gates and premature closing keywords.
6. Configure issue auto-add and closure-to-Done automation, then backfill
   existing issues. Enabling auto-add does not immediately import all existing
   matches. Remove duplicate PR planning cards once their issues carry the work.
7. Compare the live backlog with the former wiki/PR lists to confirm nothing
   was lost. Close the migration issue once the GitHub configuration and
   record migration are complete, then use only the new records for updates.

The documentation PR does not itself configure GitHub or migrate existing
issues and wiki pages. See GitHub's [auto-add behavior](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically)
and [built-in workflows](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-built-in-automations).
