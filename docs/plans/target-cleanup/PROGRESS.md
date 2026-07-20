# Target Cleanup — Progress

Plan: [PLAN.md](PLAN.md) · Spec: [../../superpowers/specs/2026-07-20-target-cleanup-design.md](../../superpowers/specs/2026-07-20-target-cleanup-design.md)

## Status: not started

| Task | Description | Status |
|---|---|---|
| 1 | Rename Column targets (part + Coord tokens; repoint canonical paths) | ☐ |
| 2 | Rename Row targets (part + Coord tokens; repoint canonical paths) | ☐ |
| 3 | Archive legacy `*Module*` targets to `targets/legacy/` | ☐ |
| 4 | Update aggregate `firmware/targets/Makefile` | ☐ |
| 5 | Update `firmware/releases.yaml` | ☐ |
| 6 | Full verification (linter, git tree) | ☐ |

## Log

- 2026-07-20: Spec and plan written. Awaiting execution decision.
- 2026-07-20: Revised scope — every active target now carries an explicit
  `160`/`325` part token, and AwaXe gets full `325AwaXeCoord10G` tokens. This
  renames the canonical `*FpgaBoard` RTL dirs, so the plan now includes
  repointing the `../` loadSource paths in the 325/Coord variants.
