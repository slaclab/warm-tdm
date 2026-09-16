# Group variable I/O contracts

Grouped variables hide board/channel traversal and transaction handling from
tuning code. Public names, units, column order, and ordinary `get()`/`set()`
calls remain the interface. The read-path changes integrated through
[PR #104](https://github.com/slaclab/warm-tdm/pull/104) and
[PR #105](https://github.com/slaclab/warm-tdm/pull/105).

Implementations live in
[`_GroupVariables.py`](../../software/python/warm_tdm_api/_GroupVariables.py)
and the firmware package's
[`_GroupLinkVariable.py`](../../firmware/python/warm_tdm/_GroupLinkVariable.py).
The two `GroupLinkVariable` classes serve different layers.

## Shapes and dependency ownership

| Class | Dependency layout | Public view |
|---|---|---|
| Firmware `GroupLinkVariable` | Scalar channels on one board | Channel array |
| API `GroupLinkVariable` | One scalar per global column | Column array |
| `GroupArrayLinkVariable` | One channel array per board | Flat column array, `board = column // 8`, `channel = column % 8` |
| `FastDacVariable` | One row array per column | `(column, row)` table |
| `GroupBroadcastVariable` | Homogeneous scalar dependencies | One representative scalar |
| `PidGainVariable` | Per-column coefficients plus coordinator sample count | Gains normalized to mean window error |

`index=-1` selects the whole array; scalar-column views accept a column index,
and `FastDacVariable` accepts a `(column, row)` pair. Broadcast reads return the
first dependency's value, not an agreement check across boards. Broadcasters
support `value_map` and `empty_value` and default to `NoConfig` because the leaf
variables own configuration serialization.

## Column mask and caching

The API's `tuneEnVar` is the per-column `ColEnableMask`. Its contract is:

| Operation | Mask behavior |
|---|---|
| Whole-array or indexed writes | Stage values only for enabled columns |
| Whole scalar-column/table read | Refresh enabled columns; return all columns |
| Whole board-array read | Refresh a board if any of its columns is enabled; return all columns |
| Explicit indexed read | Read the requested column regardless of mask |
| Broadcast or normalized PID gain access | No column-mask filtering |

Disabled entries in a whole-array result may be cached. Refreshing a board or
shared register block may also refresh its disabled channels. The mask selects
work; it does not isolate hardware access at register-block granularity.

`root.updateGroup()` batches client notifications. It does not make hardware
reads simultaneous or writes atomic. Likewise, `writeAndVerifyBlocks()` flushes
and verifies backing blocks; a logical array may span several blocks.

## Why only ADC/SA arrays read blocks directly

`SaOutAdc`, `SaOut`, and `SaOutNorm` opt into `readBlocks=True`. On a whole-array
hardware read, the group gathers the enabled boards' dependency blocks,
deduplicates them in first-seen order, calls PyRogue `readAndWaitBlocks()`, and
then evaluates the existing conversion getters with `read=False`. Dependencies
must include offsets and intermediate `SaOut` inputs as well as ADC registers.
Indexed reads still use the ordinary dependency getter.

This requires a Rogue version exposing `readAndWaitBlocks()`; the older
`readAndCheckBlocks()` does not provide the same completion guarantee. The
exploratory API in Rogue PR #1290 is not a dependency of this design.

Scalar groups, default board arrays, and the firmware group helper retain their
issue/wait/evaluate paths. Force/override getters can intentionally return cached
values, and FEB/AwaXe selection can choose dependencies at runtime. Replacing
all getters with generic block reads would bypass those semantics. Keep the
conversion in the existing getters and keep transaction logic out of tuning
loops. Do not restore `_variableBlocks`, `_uniqueBlocks`, `readAndCheck`, or
`stageAndCommit` helper layers.

The firmware group helper guards its grouped flush with `if write`.
`TimingTx.SampleCount` forwards `read` to both timing endpoints. Neither change
requires a new application-level transaction API.

## Normalized PID gains

The coefficient interface uses the coordinator's sample count:

```text
N = SampleEndTime - SampleStartTime
normalized_gain = hardware_coefficient * N
hardware_coefficient = normalized_gain / N
```

Normalization belongs at Group scope because other boards' dormant `TimingTx`
registers do not describe the active timing source. Setters use the cached
sample count and delegate to the public coefficient setters, preserving their
implementation-specific state-reset behavior. They must not bypass those
setters by writing raw registers.

Getters report zero during construction when no valid sample window exists;
setters reject nonpositive counts. `Session.setup_mux()` preserves normalized
gains while changing the window. Direct timing-register writes require callers
to reapply the gains. See the
[coefficient analysis](../plans/sensor-wafer-model/PID_COEFFICIENTS.md) for the
control-law derivation and its limits.

## Deliberate limits and maintenance

Legacy TES/AD5679R setters may perform writes even under `write=False`; a group
wrapper cannot promise fully cached staging while that behavior remains.
[#103](https://github.com/slaclab/warm-tdm/issues/103) owns that change, including
the paired-channel simultaneous-update requirement. Preserve it when changing
flush behavior.

The original proposal also discussed strict shape/index validation before any
mutation, clearer class names with compatibility aliases, and an optional shared
base. These were not part of the integrated read fix. In particular, some
whole-array setters still iterate with `zip`; malformed input must not be
documented as transactionally rejected. Any later validation work should cover
Python/NumPy indices, empty dependencies, table shape, and cached writes before
considering renames or a shared base.

The [Rogue smoke check](../../software/tests/rogue_link_variable_wait_smoke.py)
exercises real transaction completion and conversion behavior. Use it alongside
focused group-variable tests when changing these contracts. Tuning graduation
and acceptance remain on [#83](https://github.com/slaclab/warm-tdm/issues/83).
