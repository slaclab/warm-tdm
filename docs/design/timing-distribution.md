# Timing distribution: global time in, experiment-local fan-out

System-level model for where WarmTDM's timing and absolute time will eventually
come from, and how that shapes decisions we are making now (notably the
self-describing frame timestamp — see
[`firmware/common/DataChannelization.md`](../../firmware/common/DataChannelization.md)
"Timebase"). Written to flesh out the likely path so today's format work
accommodates it, not to specify the timing subsystem itself.

> Status (2026-08-17): **design discussion / forward-looking.** No timing-
> distribution firmware is being built as part of the channelization work. The
> concrete near-term deliverable is only that the frame format reserves a
> 64-bit absolute-time slot + a `timeSource` enum so this can drop in later
> without a re-layout. The timing integration itself is a large, separate future
> effort that will deprecate several current formats — accepted knowingly.

## Two timing regimes (the framing that organizes everything below)

Before comparing distribution technologies, separate the two *regimes* of
"boards agreeing on time," because they have very different tolerances and are
solved by different mechanisms. Conflating them is the main source of confusion.

- **Intra-Group (tight, ~ns / cycle-accurate).** Column and row boards within a
  Group must switch rows and sample together: when the row-select board drives
  row N, every column board must be sampling row N. Skew beyond a small fraction
  of a row means columns sample the wrong row. At a 125 MHz timing clock (8 ns
  tick) and ~2 µs row period, this needs effectively cycle-accurate alignment.
  **This is already solved by the dedicated serial broadcast link** — every board
  acts on the *same fiducial edge* of the *same broadcast frame*, which is
  inherently tighter than any message-exchange protocol (there is no offset to
  estimate; everyone sees one wire event). This regime stays on the serial link
  (or its LCLS-II-style successor) regardless of anything below.
- **Cross-Group (looser, ~µs — probably).** Different Groups read out different
  detector arrays on their own row schedules. What they need from each other is a
  common absolute time axis so data can be correlated after the fact. See the
  physics section below for why this is likely µs-class — with a caveat.

The distribution-technology question is therefore *only* about the **cross-Group
absolute epoch**, plus the option of tightening cross-Group further if desired.

## Candidate directions for the cross-Group epoch (not yet chosen)

Three ways to get an instrument-wide absolute timebase. All are hardware that
will not exist for some time; the frame format must accommodate any of them.

1. **PTP (IEEE 1588) over Ethernet.** Message-based clock discipline over the
   normal Ethernet that already reaches every board — no dedicated timing fiber.
   Hardware-timestamped PTP reaches ~sub-µs to tens of ns. Explored in depth
   below. Likely sufficient for the cross-Group need (see physics).
2. **LCLS-II-style timing link + experiment-local fan-out.** A dedicated serial
   timing protocol (like LCLS-II), received at a root and re-distributed on an
   experiment-local "fast control" link. Most aligned with existing SLAC firmware
   WarmTDM already resembles; strong worked reference in `ldmx-firmware`.
3. **White Rabbit.** PTP *plus* physical-layer syntonization for sub-ns. Only
   needed if cross-Group timing must be ns-class (not motivated by TES physics
   today, but see the physics caveat). Kept *reachable* via the common seam, not
   targeted.

Directions 1 and 3 are the same protocol family (WR is PTP + PHY tricks), so
"PTP now, WR reachable later" is a natural progression. Direction 2 is the
serial-link alternative. The rest of this doc explores direction 2's reference
implementation, then direction 1 (PTP) in implementation detail.

## Reference: LDMX / LCLS-II Fast Control (what direction 2 looks like)

`ldmx-firmware` (`firmware/common/tdaq/`) implements exactly this two-layer
model, and is worth reading before designing WarmTDM's version:

- **Global time in.** An `Lcls2TimingRx` receives the LCLS-II timing link and
  recovers the accelerator-wide absolute time — a **56-bit `pulseId`** (the
  coarse global timestamp) plus bunch structure.
- **Experiment-local fan-out ("Fast Control", the `Fc*` modules).** The global
  time becomes the basis for a local distribution on a PGP-based link. Fixed-size
  timing messages are broadcast to every endpoint; each endpoint's receiver
  regenerates a local timing bus from them.

Two structural ideas from that design are the ones that matter for us:

- **A local free-running timebase that is continuously re-synced to the
  distributed fiducials.** Each receiver counts its own clock (sub-count →
  bunch-count → pulse-id hierarchy, and a 64-bit `runTime` from T0), but every
  arriving timing message corrects those counters to the broadcast values. That
  is what makes a *static-rate* stream safe against drift: the endpoints do not
  depend on catching every strobe, because the periodic message re-aligns them.
- **Run control travels inside the timing stream.** A run-state field (and a
  "state changed" flag) rides in the timing messages, alongside the fiducials, so
  all endpoints change state coherently. Readout requests are a second message
  type on the same link.
- **A local emulator for standalone operation.** A generator block produces the
  same messages locally, with the rates configured by registers, so a system with
  no upstream link still runs. (This is the analog of WarmTDM's bench-standalone
  requirement — see below.)

The DAQ event **frame header** in that system is also a useful data point: it is
a fixed 16-byte prefix carrying a two-level identity (subsystem + contributor)
and a 64-bit timestamp that is itself a *composite fiducial* (the coarse pulse id
in the high bits, the fine bunch count in the low bits) rather than a raw
nanosecond count. This independently matches the 16-byte shared-header decision
in the channelization work, and suggests our absolute-time field will likewise be
a composite fiducial, not a plain tick count.

## Likely WarmTDM path (direction 2)

Mapping the reference onto WarmTDM, and resolving the questions raised while
discussing it:

- **A timing frame/protocol very similar to LCLS-II, on a WarmTDM base clock**
  (probably a 125 MHz word clock), replacing or subsuming today's 259-bit serial
  timing frame. The coordinator board (today `RING_ADDR_0_G`) is the local root;
  boards regenerate their timing bus locally and re-sync on each frame.
- **A static frame rate, not a dynamic one.** Rather than emitting frames only on
  row strobes (a data-dependent rate), emit them at a fixed rate — probably a
  fixed multiple of the maximum row-strobe rate (order ~1 MHz) — and carry
  **row-strobe-enable / readout-enable bits inside the frame word**. Static rate
  is simpler to reason about and to keep aligned.
- **Fiducials + run state in the stream; rates/config in registers.** The open
  question was how much belongs in the timing stream vs. TimingTx registers.
  Likely split: the stream carries **alignment fiducials, run state, and the
  per-frame strobe/readout enable bits**; the *configuration* (periods, row
  order, readout divisors) stays in TimingTx registers as it is today. The risk
  with a fiducial-only stream — that pre-configured TimingTx instances could
  drift out of alignment — is handled the LDMX way: local counters are
  continuously corrected by the periodic frame, so a fixed configuration plus a
  self-correcting stream stays aligned by construction.
- **Absolute time as a composite fiducial**, seeded from the global source when
  present and self-generated on the bench, carried in the 64-bit frame-header
  timestamp slot the channelization work reserves.

## Direction 1 in depth: PTP (IEEE 1588)

PTP synchronizes clocks across boards **over the normal Ethernet** the data
already uses — no dedicated timing fiber. That cabling saving is an argument in
its favor, though not by itself decisive.

### What PTP does and how

Two things must be achieved: **syntonization** (same frequency — clocks tick at
the same rate) and **synchronization** (same offset — clocks read the same value).
One node is the **master** (time reference); others are **slaves** that discipline
their local clock to it, using a four-timestamp handshake:

- master sends a `Sync` at `t1` (its clock); slave receives it at `t2` (its clock).
- slave sends a `Delay_Req` at `t3`; master receives it at `t4` and returns `t4`.

From `t1..t4`: round-trip wire time = `(t4-t1) - (t3-t2)`; **one-way delay** =
half of that (*assuming the path delay is symmetric*); **offset** =
`(t2-t1) - delay`. The slave then steers its clock to null the offset, repeating
continuously.

- **The symmetry assumption is the accuracy limiter.** Any master→slave vs
  slave→master delay asymmetry produces a fixed offset error of half the
  asymmetry. Switches with different queue depths per direction are the usual
  culprit; **transparent clocks** (switches that stamp their own residence time
  into the packet) and **boundary clocks** (switches that re-time each hop)
  mitigate it.
- **Accuracy is a hardware property, not just a protocol.** The timestamps
  `t1..t4` must be latched in hardware at the MAC/PHY the instant the packet
  crosses the wire; software timestamping adds tens of µs of stack jitter.
  Hardware-timestamped PTP over Ethernet reaches roughly **sub-µs to tens of ns**.

### What a PTP implementation looks like in the FPGA (four layers)

| Layer | What it is | Where | In pinned surf today? |
|---|---|---|---|
| Disciplinable clock | a free-running seconds+ns counter whose *rate* is trimmed by a tunable fractional increment (a DDS/phase accumulator) — you steer the clock by speeding/slowing it, not by jumping it | FPGA fabric | counters exist, but no packaged PTP clock |
| Hardware timestamp | latch the clock at packet SOF at the MAC boundary (`t1..t4`) — **the accuracy-critical piece** | FPGA, MAC edge | **no** — `EthMacCore` has no 1588 timestamp hooks |
| Servo | compute offset/delay, run a PI loop driving the rate knob to null offset — a slow (Hz) loop | soft-CPU or host SW | no (LinuxPTP `ptp4l` is the off-the-shelf option) |
| Message gen/parse | Sync / Follow_Up / Delay_Req / Delay_Resp / Announce | SW or light FPGA | no |

**Consequence for effort:** PTP is not a drop-in on the surf version WarmTDM
pins — the hardware-timestamp MAC block (the hard part) is absent and would be a
build or a surf uprev. The disciplined-clock output is exactly the **absolute
epoch** that seeds the coordinator's timebase (see the seam below).

## Physics: how tight does cross-Group actually need to be?

Reasoning from the TES/SQUID-MUX detector, not from a hardware capability:

- A **TES bolometer** is a thermal sensor; its effective time constant (with
  electrothermal feedback) is ~0.1–1 ms, so the science signal is **band-limited
  to ~kHz** (CMB/mm-wave, BICEP3-class, sits at the slow end).
- The **MUX** visits rows at ~500 kHz (2 µs/row) and cycles all rows, sampling
  each detector at frame rate ≈ row_rate / n_rows ≈ 1–15 kHz — oversampling the
  ~kHz signal.

Nyquist then says a sample's *time* only needs to be known to a small fraction of
the ~1 ms signal period to place two Groups' waveforms on a common axis — so **µs
is already ~1000× margin; the honest requirement is tens of µs.** Cosmic-ray
coincidence and common-mode-noise rejection across arrays are also bounded by the
~kHz sampling, not by clock skew, so they stay µs-class too. **For TES readout,
plain hardware-timestamped PTP is comfortably sufficient; White Rabbit is not
motivated by the physics.** The genuinely tight (~ns) requirement is *intra-Group*
row/sample alignment, which the broadcast serial link already handles — not a
cross-Group PTP requirement.

### Verdict (not final — pending physicist input)

**PTP is probably enough for the cross-Group epoch, but this is not pinned.**
Going to ns-class cross-Group timing insulates against a whole class of
synchronization issues that do not show up in a first-order physics argument, so
it may be *desirable* even though pure TES physics does not demand it — and the
platform may someday read out faster (non-thermal) detectors. A final decision
needs discussion with the physicists. The design therefore:

- treats **plain PTP as the likely target** for cross-Group absolute time, and
- keeps **White-Rabbit-class (ns) precision reachable** through the same seam
  (below), so tightening later does not mean re-architecting — only swapping the
  epoch-source front-end.

## The common seam: one interface, swappable front-end

Both PTP and the LCLS-II-style link converge on the **same internal interface**:
*a disciplined absolute-epoch counter plus a periodic fiducial, fed into the
coordinator's timing generation.* Define the seam there and the whole
Group-internal serial fan-out — the tight, ns-class intra-Group distribution — is
common to every option. The epoch **front-end** is then swappable:

- **PTP front-end:** Ethernet Sync/Delay messages + hardware timestamp + servo →
  disciplines the epoch counter. No timing fiber; ~sub-µs to tens of ns.
- **LCLS-II-link front-end:** a dedicated fiber delivers fiducials + `pulseId`;
  the coordinator locks the same counter to it. Ready reference in
  `lcls-timing-core`.
- **White-Rabbit front-end:** PTP + PHY syntonization into the same counter, if
  ns-class cross-Group is ever required.

This is what makes "support both" plausibly *not* messy: the messy part (tight
intra-Group distribution) is shared; only the epoch source differs, behind one
seam. It also composes cleanly with the frame format — whichever front-end is
active sets the frame's `timeSource`, and the reserved 64-bit `timestamp` slot
holds the resulting epoch regardless. **Not yet designed in detail**; recorded
here as the intended shape so the choice of front-end can stay open.

## The standalone-Group invariant (bench)

A WarmTDM **Group must function fully standalone** — a single Group on a bench,
with no instrument-level timing source attached. This constrains the design the
same way LDMX's local emulator does: the Group's coordinator must be able to
generate its own timing (fiducials, run state, and a valid monotonic timestamp)
with no external dependency. An upstream absolute source, when present,
*supersedes* the self-generated epoch (and updates the frame's `timeSource`);
when absent, the Group self-roots. Self-rooting is the **fallback**, not a
co-equal mode — the eventual normal source of absolute time is the instrument-
level distribution — but it is a permanent requirement because the bench case
never goes away.

This is exactly why the frame timestamp carries a `timeSource` enum: a reader (or
the future multi-Group `Instrument`, issue #80) uses it to know whether two
Groups' timestamps are directly comparable (shared instrument epoch) or need
software alignment (each self-rooted). See `DataChannelization.md` "Timebase".

## Consequences we accept now

- **Timing integration will deprecate current formats.** Adopting a real timing
  distribution will change the frame timestamp semantics (and possibly the timing
  frame itself). We accept that the exact formats being built in the
  channelization work are transitional; the `formatVersion` byte is what makes
  that survivable, and reserving the 64-bit timestamp slot + `timeSource` now is
  what lets the eventual timebase drop in without another flag-day re-layout.
- **This is a separate, larger effort.** No timing-distribution work is scheduled
  here. When it is, this doc is the starting point, and `ldmx-firmware`
  `firmware/common/tdaq/` (the `Fc*` modules, `FcPkg`, `DaqPkg`, and the
  `_DaqHeaders.py` header format) is the concrete reference implementation to
  study.

## References

- `ldmx-firmware` `firmware/common/tdaq/` — LCLS-II timing Rx + Fast Control
  fan-out + DAQ event header (the direction-2 reference implementation).
- `firmware/common/DataChannelization.md` — the self-describing frame header and
  the reserved absolute-time slot / `timeSource` enum this doc motivates.
- `firmware/common/warm_tdm/rtl/TimingPkg.vhd`, `TimingTx.vhd`, `TimingRx.vhd` —
  WarmTDM's current serial timing frame + `runTime` generation (the intra-Group
  broadcast link; 125 MHz timing clock, ~2 µs default row period).
- surf `ethernet/EthMacCore` — WarmTDM's Ethernet MAC; note the pinned surf
  version ships **no** IEEE-1588 hardware-timestamp hooks, so a PTP front-end
  needs that block built or a surf uprev.
- `lcls-timing-core` (LCLS-II submodule in `ldmx-firmware`) — reference for the
  LCLS-II-link epoch front-end.
- IEEE 1588 (PTP); White Rabbit (CERN) — the protocol family for the PTP / ns
  front-ends.
- Issue #80 (multi-Group Instrument) — the layer that would consume a shared
  instrument epoch and correlate self-rooted Groups.

> Open decision (pending physicist input): whether cross-Group timing may stay
> µs-class (plain PTP) or must reach ns-class (White Rabbit). The seam keeps both
> reachable; the frame format is neutral to the outcome.
