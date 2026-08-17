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

## Two candidate directions (both plausible; not yet chosen)

The project has discussed two ways to get an instrument-wide absolute timebase.
Both are hardware that will not exist for some time; the format must accommodate
either.

1. **PTP / White Rabbit.** A standards-based disciplined-clock distribution
   (White Rabbit originated at CERN and is common in accelerator/detector
   timing). Sub-ns alignment across crates; heavier infrastructure.
2. **LCLS-II-style timing link + experiment-local fan-out.** A serial timing
   protocol very similar to LCLS-II, received at a root and re-distributed on an
   experiment-local "fast control" link to every board. This is the direction
   most aligned with existing SLAC firmware WarmTDM already resembles.

The rest of this doc explores direction (2) in more depth, because there is a
strong worked reference for it in the SLAC ecosystem and because WarmTDM's
current timing link is already a serial-protocol fan-out of the same shape.

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
  WarmTDM's current serial timing frame + `runTime` generation.
- Issue #80 (multi-Group Instrument) — the layer that would consume a shared
  instrument epoch and correlate self-rooted Groups.
