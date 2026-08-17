# Channelization: self-describing frames + channel-layout cleanup

Development plan for **Issue #82** (Self-describing data frames + channel-layout
cleanup). This is the sequenced work plan; the end-to-end *design spec* it
implements is [`firmware/common/DataChannelization.md`](../../../firmware/common/DataChannelization.md)
(read that first — it is the source of truth for the wire/file layout and the
open design questions). This file captures goal, scope, decisions, the phased
approach, affected files, validation, risks, and next steps so the effort can be
resumed without reconstructing it from chat history.

## Goal

Make every bulk-data frame interpretable from its body alone — independent of the
file channel it arrived on — and clean up the channel layout so it scales to
multiple column boards (and, later, multiple Groups). Concretely:

- A `.dat` file with more than one column board must not collide board data onto
  shared file channels.
- A reprocessed/renumbered `.dat` file must still decode: the body carries board
  identity, (eventually) group identity, a global column index, and a format
  version; the file channel becomes a cross-checkable hint, not a decode
  dependency.
- The channel numbering scheme lives in one place, shared by the write side and
  the read side.

## Branch & worktree

- **Worktree:** `warm-tdm-channelization` (sibling dir), **branch:**
  `channelization`, based off `origin/cleanup`. Upstream unset — push with
  `git push -u origin channelization`; merge-not-rebase.
- **Why `cleanup` is the base (decided 2026-08-17):** the read-side code and the
  design doc exist only on the `wtj-refactor`/`fp-pid`/`cleanup` line (never on
  `pre-release`/`main`), and `cleanup` is the only branch that also carries the
  resource-optimization firmware this work touches — notably `GEN_PID_DEBUG_G`,
  which is coupled to the PID-debug tDest collapse. Basing here means the RTL
  frame-builder changes are designed against the *final* firmware shape and
  co-validate with the rest of the stack in one hardware pass. Cost: this work
  inherits the FP-PID + resource-cleanup hardware-validation gate and cannot reach
  `pre-release` until that stack clears. Tops the PR stack above #88. Recorded on
  the [Branch-Merge-Roadmap wiki](https://github.com/slaclab/warm-tdm/wiki/Branch-Merge-Roadmap).

## Scope — four pieces of work

Named by what they are (not by phase numbers or letters). The phases below
sequence them.

1. **File-channel namespacing fix** *(host-only, no RTL).* Today
   `_HardwareGroup.py` wires every board's streams onto the same DataWriter file
   channels (`getChannel(i)` / `getChannel(9)` with no board index), so two column
   boards collide on channel 9 (readout) and 0–7 (PID-debug). Board identity is
   already carried on the wire (`tDest[6:4]`) and preserved through the per-board
   `application(dest=index)` demux — it is only dropped at file-write time.
   Fix: namespace file channels by board, `getChannel(board*16 + stream)`,
   mirroring the wire TDEST (uint8 channel = 16 boards × 16 streams). Centralize
   the channel encoding so write side and read side share one definition. Also
   fold the waveform stream into the file (route it to a `getChannel(...)` instead
   of the `.npy` side path) so one file holds all streams. No firmware change.

2. **Frame-identity design decision** *(design, blocks the RTL pieces).*
   **RESOLVED 2026-08-17 — see `DataChannelization.md` "DECISION" + "Timebase".**
   Chose **one shared 16-byte frame-identity header** on all frames (rejected
   per-format fields): two 64-bit words — word 0 = `formatType`/`formatVersion`/
   `groupId`/`boardId`/`timeSource` (+reserved), word 1 = a **64-bit absolute-epoch
   `timestamp`**. One `_DataFormats` entry point reads word 0, checks the version,
   cross-checks `boardId` vs `file_channel>>4`, and dispatches by `formatType`;
   this replaces the frame-size PID heuristic. The timestamp is committed to
   absolute epoch, with a `timeSource` enum (`run-relative-ticks` / `group-epoch`
   / `instrument-epoch`) and a **standalone invariant**: a Group's coordinator
   always self-roots a valid monotonic timestamp (the near-term/bench fallback);
   the eventual Path-2 instrument-distributed absolute source (PTP/White-Rabbit,
   hardware years out) supersedes it via `timeSource`/`formatVersion` with no
   re-layout. `groupId` stays reserved/zero until #80.

3. **Self-describing frames** *(coordinated RTL + decoders + readers).* Embed
   identity into the frame bodies of all three formats — Readout (`EventBuilder`),
   PID-debug (`AdcDsp`/`AdcDspFp` debug word packing), Waveform — per the decision
   from piece 2. Readout gains a per-frame identity block in its header
   (`boardId`, `colBase = boardId·8` so the reader computes
   `global_col = colBase + local_col`) plus `formatVersion`. PID-debug can likely
   absorb identity into its existing dummy padding words (no frame-size change).
   The RTL frame builders, the `_DataFormats` decoders, and the host readers land
   together — the byte layout is the contract.

   **Group-id decision for this effort (2026-08-17):** implement board-level
   identity now; include a **reserved `groupId` field + `formatVersion`** in the
   layout, but leave `groupId` semantics unused/zero. The meaning of `groupId`
   (in-band field vs. federated writer-per-Group) is gated on the #80
   federated-vs-not decision and is an explicit dependency, not part of this
   effort. Reserving the field now avoids a second format-version bump later.

   **Replace the PID-format-by-size heuristic (carry-over from Phase 1).** The
   two PID-debug layouts — the 80-byte fixed-point (`PID_DEBUG_TYPE`) and the
   40-byte float (`PID_DEBUG_FP_TYPE`), both added to `warm_tdm._DataFormats` in
   Phase 1 — are currently distinguished in `StreamReader._accept_pid` **by frame
   size alone**. That is safe today (a board runs either fixed or float PID within
   a file, and 40 != 80), but it is a heuristic, not a contract. When
   self-describing frames land, the `formatType`/`formatVersion` byte becomes the
   authoritative discriminator and the size check must be replaced by dispatch on
   the declared type (with size then a cross-check, not the selector). This is a
   concrete motivation for the version/type byte, not a separate task.

4. **PID-debug tDest collapse** *(RTL).* Merge the 8 per-column PID-debug streams
   (currently on `tDest 0–7`, stamped by an INDEXED mux in `DataPath.vhd`) onto a
   single board-local tDest. The frame body already carries `col`, so the
   per-column tDest is redundant. This reclaims stream slots `1–7` — the headroom
   the board/group-namespaced channel scheme needs. Requires a host-side change:
   the live/GUI path currently attaches one `PidDebugger` per column via
   `packetizer.application(i)`; it becomes one receiver that reads `col` from the
   body and dispatches. Land this together with the self-describing-frames work
   (piece 3) since both make the body authoritative. This is coupled to
   `GEN_PID_DEBUG_G` (present on the `cleanup` base).

## Phased approach (sequencing)

**Phase 1 — Host-only channel namespacing + central channel map.** Piece 1.
No firmware; testable in emulate immediately; no hardware gate. Deliverable: a
single channel-encoding definition used by `_HardwareGroup.py` (write) and
`operations/streamreader.py` (read), board-namespaced file channels, waveform
folded into the file, reader-side `boardId`-vs-channel cross-check hook stubbed.
This phase is self-contained and could be cherry-picked onto `wtj-refactor`
earlier if the multi-board file fix is needed before the stack lands.

**Phase 2 — Resolve the frame-identity design question. DONE (2026-08-17).**
Chose the shared 16-byte header and committed the absolute-epoch timestamp +
`timeSource` enum + standalone invariant; frozen byte layout and rationale are in
`DataChannelization.md` ("DECISION", "Timebase"). Gates Phase 3, now unblocked.

**Phase 3 — Self-describing frames + PID-debug tDest collapse (coordinated
RTL + host).** Pieces 3 and 4, landed together. RTL frame builders emit the
identity block and global column; `_DataFormats` decoders and host readers parse
it; the PID-debug streams collapse to one tDest and the host live path dispatches
by body `col`. Needs synthesis (Vivado 2024.1) and bench validation — shares the
FP-PID + resource-cleanup hardware pass.

## Affected files / modules

### Host (Python) — Phases 1 & 3
- `firmware/python/warm_tdm/_HardwareGroup.py` — file-channel wiring
  (`getChannel(...)`), per-board demux, waveform routing, PID-debug live-path
  dispatch (Phase 3).
- `software/python/warm_tdm_api/operations/streamreader.py` — read-side channel
  demux; consume the central channel map; `boardId`-vs-channel cross-check.
- **Central channel-encoding module — must live in the lower-level `warm_tdm`
  package**, not in `warm_tdm_api`. The write side (`_HardwareGroup.py`) is in
  `warm_tdm`, which never imports `warm_tdm_api` (verified); the read side
  (`operations/streamreader.py`) already imports `warm_tdm`, so both sides can
  share one definition only if it lives in `warm_tdm`. (`operations/channels.py`
  holds the pure `col_to_board_chan` helper and can re-export or call into it, but
  cannot be the canonical home.)
- `firmware/python/warm_tdm/_DataFormats.py` — `DataReadout`/`PidDebug` decoders;
  add identity-block parsing + `formatVersion` (Phase 3).
- `software/python/warm_tdm_api/_GroupRoot.py` — `StreamWriter`/config channel
  255 (verify interaction with the new numbering).

### Firmware (RTL) — Phase 3
- `firmware/common/warm_tdm/rtl/EventBuilder.vhd` — readout frame header identity
  block + global column + `formatVersion`.
- `firmware/common/warm_tdm/rtl/DataPath.vhd` — PID-debug mux collapse
  (`U_AxiStreamMux_1` INDEXED → single tDest), stream-type routing
  (`U_AxiStreamMux_2`).
- `firmware/common/warm_tdm/rtl/AdcDsp.vhd`, `AdcDspFp.vhd` — PID-debug word
  identity fields (into dummy padding where possible).

### Docs
- `firmware/common/DataChannelization.md` — record the frame-identity decision;
  update the layout tables and the migration section as pieces land.

## Validation

- **Phase 1:** the primary gate is **unit tests on the pure channel-map module**
  (`file_channel(board, stream)` round-trips with `board_of`/`stream_of`; board 0
  stays byte-identical to today so existing single-board files still decode) plus
  **tree construction** of an emulate `GroupRoot` with `colBoards=2` (imports,
  no exceptions). NOTE: emulate mode skips the file-write wiring entirely
  (`_HardwareGroup.py` gates it behind `if emulate is False:` and feeds a bare
  `Master()`), so **live per-board frame separation in a written `.dat` cannot be
  exercised under emulate** — that verification moves to simulation/bench
  alongside Phase 3. Confirm the config channel (255) is unaffected by the
  renumbering. Conda env `warm-tdm-r615` (see memory).
- **Phase 3 (sim + bench):** GHDL/cocotb bench on the DSP path (see Issue #90 /
  `rtl-cocotb-regression`) for the frame-builder byte layout where feasible;
  synthesis on a Column target (Vivado 2024.1); bench readout of a real 2-board
  file decoding correctly from body alone (renumber a channel and confirm the
  cross-check catches the mismatch). This shares the FP-PID hardware pass.

## Open risks & dependencies

- **Hardware gate.** Phase 3 cannot reach `pre-release` until the FP-PID +
  resource-cleanup stack (#87/#88) clears hardware validation. Only Phase 1 is
  independent.
- **#80 federated-vs-not.** `groupId` semantics are undecided; this effort
  reserves the field but does not define its meaning. If #80 lands "federated"
  (writer-per-Group), the in-band `groupId` may stay permanently unused — the
  reserved field costs one byte and a version note either way.
- **Format-version discipline.** Every frame layout change from here on must bump
  `formatVersion`; reprocessed files outlive the firmware that wrote them.
- **`readout = channel 9` is a fixed wire/format contract** (relic of development
  order). Do not renumber it; the namespacing scheme (`board*16 + stream`) is
  designed around keeping stream-type 9 = readout.
- **Live GUI PID-debug path.** The tDest collapse requires reworking the live
  per-column `PidDebugger` attachment into a single body-`col`-dispatching
  receiver; the file-based parser already dispatches by body `col`, so the file
  path is unaffected.
- **Absolute-epoch timebase.** The header commits to a 64-bit absolute-epoch
  `timestamp`, but the eventual Path-2 instrument-distributed absolute time source
  (PTP/White-Rabbit) is hardware that will not exist for some time. Phase 3
  populates it via the Group-self-rooted fallback (host-seeded epoch); the
  standalone invariant (a Group always self-roots a valid monotonic timestamp)
  must hold on the bench with no upstream. Path 2 lands later as its own timing
  effort into the same slot via `timeSource`/`formatVersion` — no re-layout.
- **Size heuristic is interim.** Until the shared header lands, `StreamReader`
  distinguishes the two PID formats by frame size (80 vs 40); Phase 3 replaces
  that with `formatType`/`formatVersion` dispatch (size demoted to a cross-check).

## Next steps

1. ~~Phase 1: central channel-encoding helper + board-namespaced file channels +
   unified readers.~~ **Done** (committed on `channelization`). Waveform folding
   into the file was deferred (opt-in); not yet done.
2. ~~Phase 2: resolve the frame-identity design and record it in
   `DataChannelization.md`.~~ **Done** — shared 16-byte header, absolute-epoch
   timestamp, standalone invariant.
3. **Phase 3 (next, hardware-gated):** implement the 16-byte shared header across
   the RTL frame builders (`EventBuilder`, `AdcDsp`/`AdcDspFp`) + `_DataFormats`
   decoders + host readers as one coordinated change; collapse the PID-debug
   tDests; populate `timestamp` from the Group-self-rooted epoch. Rides the FP-PID
   + resource-cleanup hardware pass; sim-gate via #90 where feasible.
4. Later / separate effort: Path-2 instrument-distributed absolute time (timing
   subsystem), dropping into the reserved `timestamp` slot via `timeSource`.

## References

- Design spec: [`firmware/common/DataChannelization.md`](../../../firmware/common/DataChannelization.md)
- Timebase future: [`docs/design/timing-distribution.md`](../../design/timing-distribution.md)
  (LCLS-II/LDMX-style timing distribution + standalone-Group invariant; motivates
  the reserved absolute-time slot)
- Issue #82 (this work); related #80 (multi-Group Instrument), #83 (graduate
  operations helpers), #90 (RTL cocotb regression — Phase 3 sim home).
- Roadmap: [Branch-Merge-Roadmap wiki](https://github.com/slaclab/warm-tdm/wiki/Branch-Merge-Roadmap).
