# Timing distribution: global time in, experiment-local fan-out

System-level model for where WarmTDM's timing and absolute time will eventually
come from, and how that shapes decisions we are making now (notably the
self-describing frame timestamp — see
[`firmware/common/DataChannelization.md`](../../firmware/common/DataChannelization.md)
"Timebase"). Written to flesh out the likely path so today's format work
accommodates it, not to specify the timing subsystem itself.

> Status (2026-08-19): **design discussion / forward-looking.** No timing-
> distribution firmware is being built as part of the channelization work. The
> concrete near-term deliverable is only that the frame format reserves a
> **64-bit absolute-nanoseconds** timestamp slot so this can drop in later without
> a re-layout; the timing *source*/epoch is recorded once in per-run metadata, not
> per frame (see `DataChannelization.md` "Timebase"). The timing integration
> itself is a large, separate future effort that will deprecate several current
> formats — accepted knowingly.

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
and a 64-bit timestamp. This independently matches the 16-byte shared-header
decision in the channelization work. Note LDMX packs its timestamp as a
*composite fiducial* (coarse pulse id + fine bunch count) because *their* time is
bunch-structured; WarmTDM instead uses **plain 64-bit absolute nanoseconds** (its
125 MHz clock makes ns exact), keeping the header a pure physical-time value and
leaving within-run structure — row/sequence counters — in the format body. See
`DataChannelization.md` "Timebase".

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
- **Absolute time as 64-bit nanoseconds**, seeded from the global source when
  present and self-generated on the bench, carried in the 64-bit frame-header
  timestamp slot the channelization work reserves. (Internally the source may
  distribute a fiducial/counter; what lands in the frame header is plain absolute
  ns — see `DataChannelization.md` "Timebase".)

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

### Clock drift under PTP, and the fiducial-realignment mitigation

There is a subtlety that is the real heart of the PTP-vs-LCLS-II difference.
Under PTP, **each Group's readout is clocked by its own local 125 MHz
oscillator.** PTP disciplines each Group's *notion of absolute time* (the epoch
counter) to sub-µs, but it does **not** make the physical oscillators tick in
lockstep — they free-run and **drift relative to one another**. So even with
perfectly synced timestamps, the **readout-sequence phase between Groups slowly
walks**: Group A begins readout sequence N (a full pass through all rows) at a
slightly different real instant than Group B, and that difference accumulates.

Under the **LCLS-II-style scheme this cannot happen** — the *same physical clock*
is fanned to every Group, so the oscillators are one source and sequence phase
stays locked by construction (syntonization is free). This is a large part of why
the LCLS-II approach is cleaner and easier to reason about.

**Mitigation for PTP — and WarmTDM already has the mechanism.** To keep Groups'
readout sequences phase-aligned under PTP, gate each Group's **readout-sequence
start** on a *shared fiducial* derived from the common PTP time (e.g. begin a
sequence when the epoch crosses a period boundary), holding the coordinator until
the fiducial. This is structurally identical to the existing **`pwrSync`** logic
in `TimingTx.vhd`: when `pwrSyncEn = '1'`, a sequence-start boundary (the wrap
from the last row back to row 0) freezes the timebase in `pwrSyncWait` and only
advances when a `syncPulse` arrives — today used to align the readout sequence to
the voltage-regulator / power-supply frequency. The PTP case reuses exactly this
"hold the sequence start until a fiducial" pattern, with the fiducial sourced from
PTP time instead of the supply sync. That the firmware already does this for the
regulator is good evidence the PTP approach **fits in easily enough**.

Note the mitigation aligns *sequence phase*, not the per-sample oscillator phase;
it bounds inter-Group drift to within one realignment period rather than letting
it accumulate freely. Sub-row/sample phase coherence across Groups (if ever
needed) is the ns-class regime that only a shared clock (LCLS-II / White Rabbit)
provides — see the two-regime framing above.

### Stated preference (2026-08-19)

The **LCLS-II approach is preferred** — distributing the same clock to all Groups
is cleaner and easier to reason about (no inter-Group drift, sequence phase locked
by construction). **Both approaches are kept in consideration for now**, and PTP
appears to fit in easily enough — notably because the drift mitigation reuses the
existing `pwrSync` sequence-start-hold mechanism. Not a final decision.

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
active, the reserved 64-bit `timestamp` slot holds absolute nanoseconds
regardless, and *which* front-end was active is recorded once in the per-run
metadata, not per frame. **Not yet designed in detail**; recorded here as the
intended shape so the choice of front-end can stay open.

## Timing master hardware (what sits at the top of the tree)

Both schemes need dedicated hardware at the root of the multi-Group timing tree.
It is a different animal in each case, and this is where the build-vs-buy tradeoff
really lives. **Neither is needed for a standalone Group** — a single Group's
coordinator self-roots (see the invariant below); the master only appears when
going multi-Group.

**Hard constraint on WarmTDM boards:** the current column/row FPGA boards expose
only **2 SFP ports** to the FPGA — nowhere near enough to fan a timing link to
many Groups. So in *either* scheme the master cannot be an ordinary WarmTDM board
driving all the fibers directly; a dedicated fanout stage is required.

### LCLS-II-style master: an FPGA timing generator + a fanout card

The source is a **timing generator** in `lcls-timing-core` — the **TPG** (Timing
Pattern Generator) family, `TPGMini` / `TPGMiniCore` / `TPGMiniStream`. In LCLS-II
its timebase core is `ClockTime_186MHz`, which *"increments a 64-bit nanosecond
timestamp in 1300/7 MHz steps"* (~185.7 MHz).

**WarmTDM would distribute at its own rate, not LCLS-II's.** The base clock would
be **125 MHz** (a **2.5 Gbps** serial link), not 186 MHz — matching WarmTDM's
existing 125 MHz timing clock rather than the accelerator's 1300/7 MHz. So the
TPG machinery is the *reference architecture* (generator → serialized fiducial
stream → GT), but the timebase and line rate are WarmTDM's; the 64-bit ns
timestamp would increment in 125 MHz (8 ns) steps. Given a `txClk`,
`TPGMiniCore`-style logic emits the serialized timing stream (`txData`/`txDataK`)
onto a GT lane. Two ways to source it:

- **Upstream in:** receive a real LCLS-II timing fiber (`Lcls2TimingRx`) and
  re-fan it — this is what LDMX's `FcHub` does. Only relevant if WarmTDM is ever
  attached to an actual accelerator timing system.
- **Self-generated:** instantiate `TPGMiniCore` to *be* the master, with no
  upstream — the standalone-experiment case. This is the WarmTDM-realistic path.

Either way the generator lives on an FPGA, but because a WarmTDM board has only 2
SFPs, the generated timing signal must go to a **dedicated fanout card** that
splits one timing source into a fiber (or copper) per Group. LDMX's reference for
the whole master is the **`FcHubBittware`** target — the generator + fan-out
implemented on a Bittware PCIe card with many GT lanes. WarmTDM would need an
equivalent: an FPGA configured as the TPG master feeding a fanout card, not a
stock column/row board.

### PTP master: a GPS grandmaster appliance + PTP-aware switches

PTP's master is not custom firmware at all — it is a **PTP grandmaster clock**, a
COTS network appliance that holds a high-stability oscillator (OCXO or Rubidium),
usually **disciplined to GPS/GNSS** (rooftop antenna) so its time is absolute UTC,
and serves `Sync`/`Announce` onto the Ethernet. The other dedicated piece is the
**network**: to hit sub-µs you want **PTP-aware switches** (transparent or
boundary clocks) so per-hop queuing delay does not corrupt the offset estimate.
There is no custom hub board — but the fanout is still "dedicated hardware," just
COTS (grandmaster + switches) rather than an FPGA card you build.

### The contrast

| | LCLS-II-style master | PTP master |
|---|---|---|
| Time source | FPGA **TPG** generator (`TPGMiniCore` + `ClockTime_186MHz`), self-gen or from an LCLS-II fiber | **GPS-disciplined grandmaster** appliance |
| Fan-out | dedicated **fanout card** (FPGA + many GTs; `FcHubBittware`-class) — required since boards have only 2 SFPs | **PTP-aware switches** on the data Ethernet |
| Build vs buy | **build** (custom FPGA + fanout card) | **buy** (grandmaster + switches) |
| Absolute UTC | only if fed from GPS/upstream | native (grandmaster is GPS-disciplined) |
| Per-endpoint FPGA cost | timing Rx (already have the shape) | hardware-timestamp MAC on every board (surf lacks it) |
| Where complexity concentrates | one fanout/generator card you design | spread across switches + every endpoint |

The strategic read: LCLS-II-style concentrates custom work in *one generator +
fanout card you build* and reuses the endpoint timing-Rx you already have; PTP
lets you *buy* the master (and gets GPS/UTC for free) but spreads FPGA work to
every endpoint and makes switch quality your problem. Both still require a
dedicated fanout stage because no WarmTDM board can drive more than 2 links.

## The standalone-Group invariant (bench)

A WarmTDM **Group must function fully standalone** — a single Group on a bench,
with no instrument-level timing source attached. This constrains the design the
same way LDMX's local emulator does: the Group's coordinator must be able to
generate its own timing (fiducials, run state, and a valid monotonic absolute-ns
timestamp) with no external dependency. Framed as one model: a standalone Group is
the *degenerate instrument* (one Group is the whole instrument), whose epoch is
self-rooted; a multi-Group instrument disciplines every Group to a shared clock so
all timestamps sit on one epoch. Self-rooting is the **fallback**, not a co-equal
mode — the eventual normal source of absolute time is the instrument-level
distribution — but it is a permanent requirement because the bench case never
goes away.

Which epoch applied (self-rooted vs. instrument-distributed) is recorded once in
the **per-run metadata** (config channel), not in every frame — a reader or the
future multi-Group `Instrument` (issue #80) consults that to know whether two
Groups' timestamps are directly comparable or need software alignment. The frame
timestamp itself is just absolute nanoseconds. See `DataChannelization.md`
"Timebase".

## Consequences we accept now

- **Timing integration will deprecate current formats.** Adopting a real timing
  distribution will change how the 64-bit ns timestamp is sourced/disciplined
  (and possibly the timing frame itself). We accept that the exact formats being
  built in the channelization work are transitional; the `formatVersion` byte is
  what makes that survivable, and reserving the 64-bit absolute-ns timestamp slot
  now is what lets the eventual timebase drop in without another flag-day
  re-layout. (The timestamp's *meaning* — absolute ns — does not change; only its
  epoch source does, recorded per-run.)
- **This is a separate, larger effort.** No timing-distribution work is scheduled
  here. When it is, this doc is the starting point, and `ldmx-firmware`
  `firmware/common/tdaq/` (the `Fc*` modules, `FcPkg`, `DaqPkg`, and the
  `_DaqHeaders.py` header format) is the concrete reference implementation to
  study.

## References

- `ldmx-firmware` `firmware/common/tdaq/` — LCLS-II timing Rx + Fast Control
  fan-out + DAQ event header (the direction-2 reference implementation).
- `firmware/common/DataChannelization.md` — the self-describing frame header and
  the reserved 64-bit absolute-ns timestamp slot this doc motivates (timing
  source/epoch recorded per-run, not per frame).
- `firmware/common/warm_tdm/rtl/TimingPkg.vhd`, `TimingTx.vhd`, `TimingRx.vhd` —
  WarmTDM's current serial timing frame + `runTime` generation (the intra-Group
  broadcast link; 125 MHz timing clock, ~2 µs default row period). The
  `pwrSync`/`pwrSyncWait` logic in `TimingTx.vhd` is the existing precedent for
  holding a readout-sequence start until a fiducial — the pattern the PTP
  drift-mitigation would reuse.
- surf `ethernet/EthMacCore` — WarmTDM's Ethernet MAC; note the pinned surf
  version ships **no** IEEE-1588 hardware-timestamp hooks, so a PTP front-end
  needs that block built or a surf uprev.
- `lcls-timing-core` (LCLS-II submodule in `ldmx-firmware`) — reference for the
  LCLS-II-link epoch front-end. The **TPG** generator family
  (`LCLS-II/core/rtl/TPGMini{,Core,Stream}.vhd`, `ClockTime_186MHz.vhd`) is the
  timing-master source; WarmTDM would adapt it to a **125 MHz base / 2.5 Gbps
  link** (8 ns timestamp steps) rather than LCLS-II's 1300/7 MHz.
- WarmTDM boards expose only **2 SFP ports** to the FPGA — a dedicated fanout
  card is required for a multi-Group master in either scheme.
- IEEE 1588 (PTP); White Rabbit (CERN) — the protocol family for the PTP / ns
  front-ends.
- Issue #80 (multi-Group Instrument) — the layer that would consume a shared
  instrument epoch and correlate self-rooted Groups.

> Open decision (pending physicist input): whether cross-Group timing may stay
> µs-class (plain PTP) or must reach ns-class (White Rabbit). The seam keeps both
> reachable; the frame format is neutral to the outcome.
