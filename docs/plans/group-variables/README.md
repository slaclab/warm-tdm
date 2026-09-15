# Group variable refactoring plan

Design notes from the September 10, 2026 review. This records the proposed
refactor so it can be resumed later; it does not implement the changes.
Implementation progress and candidate-specific acceptance results belong on
the owning issue under [the development workflow](../../WORKFLOW.md). Link
that issue here when the work is taken up.

The objective is to make grouped variable access easier to understand and
safer to call while preserving the public Group tree, physical units, column
ordering, and useful batching inside variable implementations. Start with
input validation and clear contracts. Structural changes should earn their
place by removing meaningful duplication.

The two source files have different scopes:

- [firmware `_GroupLinkVariable.py`](../../../firmware/python/warm_tdm/_GroupLinkVariable.py)
  combines scalar channels within one board.
- [API `_GroupVariables.py`](../../../software/python/warm_tdm_api/_GroupVariables.py)
  provides five views across a Group's boards.

The two classes named `GroupLinkVariable` are independent implementations.
The API `GroupArrayLinkVariable` and `FastDacVariable` inherit from the API
`GroupLinkVariable`, overriding both access methods and largely reusing its
constructor setup. The actual Group wiring is in
[`_Group.py`](../../../software/python/warm_tdm_api/_Group.py).

| Class | Representation | Current uses |
|---|---|---|
| Firmware `GroupLinkVariable` | Scalar channels to one board array | Board `SaFbForceCurrent`, `Sq1BiasForceCurrent`, `Sq1FbForceCurrent` |
| API `GroupLinkVariable` | Scalar dependencies to one Group column array | `SaBiasVoltage`, `SaBiasCurrent`, `SaOffset`, `TesBias` |
| `GroupArrayLinkVariable` | Eight-channel board arrays to one flat Group array | `SaOutAdc`, `SaOut`, `SaOutNorm`, and the three force-current arrays |
| `FastDacVariable` | Per-column row arrays to a `(columns, rows)` table | Current and voltage tables for `SaFb`, `Sq1Bias`, `Sq1Fb` |
| `GroupBroadcastVariable` | One scalar written to every dependency | `CableResistance`, `LedEnable` |
| `PidGainVariable` | Per-column coefficients converted using sample count | `PidP_Gain`, `PidI_Gain`, `PidD_Gain` |

**Constraints carried forward from the review**

Keep normal `get()` and `set()` calls in tuning algorithms. Encapsulate useful
read issue/wait and staged-write behavior inside grouped variables. Do not
restore `_variableBlocks`, `_uniqueBlocks`, `readAndCheck`, or `stageAndCommit`,
or inline equivalent sequences across unrelated tuning variables. Do not add
small `updateGroup()` wrappers inside tuning functions whose Process already
supplies that context.

The outer API getters wait before returning. Only `SaOutAdc`, `SaOut`, and
`SaOutNorm` opt into backing-block reads (`readBlocks=True` on the API array
variable). Scalar and default board-array getters retain the pre-release
issue/wait/evaluate sequence, preserving cached override/TES behavior and
runtime source selection. Fast-DAC tables and
PID getters also use ordinary reads. Keep the `SampleCount` fix that forwards
`read` to both sample-window registers. Conversion callbacks do not need `wait`
forwarding. Preserve these boundaries during the broader refactor.

`root.updateGroup()` batches client notifications. `writeAndVerifyBlocks()`
coordinates writes and verification across backing blocks. Neither promises
one hardware transaction, simultaneous sampling, or atomic multi-register
writes. A per-board array may span several blocks.

**Proposed implementation sequence**

1. **Document the current contracts and identify compatibility dependencies.**

   Audit repository callers, Python exports, GUI bindings, and configuration
   usage before renaming classes or tightening accepted inputs. Preserve
   public Group variable names and tree paths. Record dtype, shape, units,
   default metadata, cache-only behavior, and empty-dependency behavior.
   Correct documentation that describes grouped operations as one transaction
   or assumes every board array occupies one block.

   Make the existing mask behavior explicit:

   | Operation | Current behavior to preserve initially |
   |---|---|
   | Column/table writes, including indexed writes | Stage only enabled columns |
   | Whole scalar-column or fast-DAC-table reads | Refresh enabled columns; return every column |
   | Whole board-array reads | Refresh boards with any enabled column; return every column |
   | Explicit indexed reads | Read the requested element regardless of its mask |
   | Broadcast and PID gain operations | No `ColTuneEnable` gating |

   Disabled entries can contain cached values. Reading an enabled board can
   also refresh its disabled channels. The mask is a selection policy, not an
   access restriction. Changing this policy would be a separate behavior change.

2. **Validate array shape and indices before changing dependency values.**

   Both `GroupLinkVariable` setters currently use `zip()`, which silently
   accepts short inputs and ignores excess elements. Other setters can stage
   values before discovering a malformed input. Reject invalid structure
   before invoking any dependency setter, including with `write=False`.

   Require the expected one-dimensional length for column/board arrays and
   the expected two-dimensional shape for fast-DAC tables. Validate the whole
   input even when some columns are disabled. Preserve `index=-1` as the
   whole-value sentinel; validate scalar column indices and `(column, row)`
   pairs explicitly. Account for NumPy integer indices used by existing callers.
   Reject other negative or out-of-range indices with clear errors.

   Derive table dimensions from the configured dependencies or existing
   configuration rather than introducing another independently maintained
   size. Confirm whether differing per-column row counts are supported before
   imposing a rectangular-table assumption.

   Define consistent results for empty collections after checking callers.
   Recommend correctly shaped empty arrays for array views; preserve the
   broadcaster's explicit `empty_value` option. Input validation does not
   promise rollback if a valid request later encounters a hardware error.

3. **Clarify class names without changing Group variable names.**

   Consider `ChannelArrayVariable` for the firmware class and
   `GroupColumnVariable` for the API scalar-column class. These names are
   proposals, not settled API changes. Check whether clearer module-qualified
   documentation is sufficient before renaming.

   If renaming improves the code, update internal imports and documentation
   together. Retain compatibility aliases for externally imported class names
   where needed. Do not rename `Group.SaBiasCurrent` or other tree nodes as
   part of this cleanup.

4. **Evaluate a small shared base after the contracts are clear.**

   Keep board/channel mapping, table indexing, and access behavior explicit in
   their respective classes. Consider an API base for genuinely shared setup
   such as metadata, dependency units, and the tune-enable reference. Adopt it
   only if the resulting classes are easier to read and duplication decreases.
   Keeping the current hierarchy with better documentation is acceptable.

   Preserve the package dependency direction: firmware drivers must not gain
   a dependency on `warm_tdm_api`. Avoid a generic transaction framework,
   callback dispatch machinery, or a helper hierarchy merely to remove a few
   repeated loops. Remove unused local assignments during this pass.

5. **Keep broadcast and PID behavior specialized.**

   For `GroupBroadcastVariable`, document that `get()` reports the first
   dependency and does not verify agreement. Preserve `value_map`,
   `empty_value`, and `NoConfig`. State that dependencies must support staging
   correctly; a generic LinkVariable setter can have behavior beyond changing
   a register shadow. No agreement-checking mechanism is proposed here.

   For `PidGainVariable`, preserve:

   - `group_gain = coefficient * sample_count`, with the inverse on writes.
   - The cached sample-count assumption on writes and the need to reapply
     gains after changing the sampling window.
   - Zero-valued reads during unconfigured initialization and errors for
     writes with an invalid sample count.
   - Public coefficient setters, including `I_Coef` PID-state clearing.
   - Reads of both `SampleStartTime` and `SampleEndTime` through `SampleCount`.

   Do not fold PID setters into generic staged block writes or add mask
   behavior as an incidental consequence of new inheritance.

**Read/conversion design selected after the review**

AD5679R deferred-write repair is tracked separately in
[issue #103](https://github.com/slaclab/warm-tdm/issues/103). The read refactor
preserves the original `setVoltages()` sequence; legacy `TesBias` still writes
immediately when called with `write=False`. A generic flush of DAC output
blocks does not preserve the chip's simultaneous paired-channel update.

The deferred question was revisited on September 10. Propagating `wait=False`
through conversion getters produced provisional values that callers had to
discard and recalculate after waiting. The selected design separates the
hardware refresh from value calculation inside the grouped getter.

For whole ADC/SA-output arrays only, collect blocks from enabled boards,
deduplicate them in first-seen order, and call PyRogue's `readAndWaitBlocks()`.
Then evaluate the existing conversion chain with `read=False`. This preserves
the intermediate `ColumnBoard.SaOut` abstraction and refreshes both ADC and
offset DAC inputs without duplicating its math. Indexed reads continue to use
the ordinary dependency getter. The required PyRogue version must expose
`readAndWaitBlocks`; older installations with only `readAndCheckBlocks` do not.

Declared dependencies can include inactive hardware sources, and getters can
deliberately ignore `read`. The default API array path retains the pre-release
issue/wait/evaluate sequence, with the existing board read mask. The scalar API
getter also retains its pre-release sequence, with support for an omitted tune
mask. The firmware GroupLinkVariable
retains its pre-release issue/wait/evaluate getter pending the upstream API and
a later path audit; only its missing `if write:` guard is fixed. Both indexed and whole-array override reads
retain their cached behavior. The TES drivers retain their prior getters,
setters, and dependency declarations, including known staging limitations;
this refactor does not normalize those contracts. Scalar SA/TES links preserve
FEB/AwaXe selection. No new asynchronous conversion API or standalone block
helpers are required. Class naming, validation, and inheritance remain separate.

An additive upstream API exploration is in
[Rogue issue #1290](https://github.com/slaclab/rogue/issues/1290). Those APIs are proposals,
not dependencies or implementations introduced by this WarmTDM change.

Block completion does not guarantee simultaneous sampling. Root listeners
can independently evaluate cached derived values; the grouped getter's
returned result is evaluated after its selected hardware reads complete.

**Validation approach**

Use behavior-focused tests for the changes rather than tests that assert
particular class names or inheritance choices. Extend the existing
[`rogue_link_variable_wait_smoke.py`](../../../software/tests/rogue_link_variable_wait_smoke.py)
where real block completion matters.

| Area | Evidence to obtain |
|---|---|
| Input validation | Short/long arrays, wrong table shape, and invalid indices fail before any dependency value is staged or written |
| Mapping | Multiple boards and rows map to the correct dependencies, including board boundaries |
| Masking | Enabled, disabled, and mixed-board cases retain the documented read/write behavior |
| Reads | ADC/SA reads finish before conversion; ordinary paths preserve getter policies, including cached overrides/TES; read errors propagate |
| Writes | Group staging guards and indexed writes retain their behavior; legacy TES staging limitations remain separate work |
| Broadcasts | Local and remote dependencies, value mapping, representative reads, and empty sets behave as documented |
| PID gains | Scaling, cached sample-count writes, initialization, invalid counts, and coefficient setter side effects remain correct |
| Compatibility | Public tree paths, units, array ordering, config exclusions, and any retained import aliases remain usable |

Run the software unittest suite, the focused Rogue smoke checks with a
compatible runtime, and syntax/whitespace checks. Use emulation for affected
tree construction and integration paths. Hardware timing benefits remain
unmeasured; software checks do not establish a speedup. If implementation
changes hardware transaction behavior, record the applicable bench acceptance
on the owning issue before integration rather than maintaining results here.

On resuming, inspect the current files and git state first: these notes describe
the review baseline, and subsequent edits may have already addressed individual
points. Start with validation and contracts; reconsider naming and inheritance
only after those changes are concrete.
