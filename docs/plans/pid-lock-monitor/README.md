# Live PID lock monitor

## Goal and current status

Implemented a PyDM `PID Lock` tab selecting a logical row and global column,
with DAC, full-feedback and combined views, synchronized mean error and net
wrap count, bounded history, pause/resume, gaps and stale indication. Logical
rows work independently of flat or two-level physical RowMap topology.

Implementation and synthetic integration checks are complete. Hardware
acceptance remains outstanding. No files have been staged or committed by the
agent. Related broader metrics proposal: [PID analyzer](../pid-debug-analysis/PLAN.md)
(#108); no issue was updated by this task.

## Receiver reuse and sample contract

The existing integer `PidDebugger` and `PidDebuggerFp` receivers now publish
`RowPids.PID[row].Sample` from the decoded frame at the per-row update boundary.
The separate monitor receiver and raw-frame decode helper are removed. The common row base lives
in `_PidDebugger.py`; sample conversion and constants live beside the existing
wire decoders in `_DataFormats.py`. Existing MemEmulate-backed scalar diagnostics
continue updating on every received visit. Samples are limited to 10 Hz per
row, without a new worker thread; calibration or enable changes bypass that
limit. Existing constructors still work without a DSP reference, with feedback
withheld because its configuration/commit state is unknown.

One fresh float64 array carries:
`time_seconds, global_column, logical_row, signed_dac, full_feedback, net_wraps,
mean_error, debug_drops, format_type, wrap_period, flags`.
The timestamp comes from the shared frame header; the old body `RunTime` is
vestigial. All plotted telemetry belongs to the same decoded visit, even if
Rogue coalesces queued notifications. `root.updateGroup()` alone cannot provide
that guarantee for separate scalar channels: variable values are collected
later and PyDM channels notify independently.

FP uses the accepted post-visit `sq1FbNewFp`; `sq1FbFullFp` is the pre-visit value.
Integer full feedback adds the signed absolute net count times the configured
quantum to fractional post-wrap feedback. Both plots use signed controller
DAC-code units before polarity/offset-binary conversion. V1 preserves available
diagnostics without feedback; v2 provides DAC but withholds full feedback because
its counter is truncated. Current v3 full feedback is withheld at count limits.

`HardwareGroup.PidLockMonitor` is a small `pr.Device` adapter forwarding the
selected row's complete array and its column's debug-enable control through
stable PyDM channels. It neither receives nor decodes frames. Selection is
shared between clients and clears the selected sample until another matching
update arrives. The GUI owns history and plotting. The installed Rogue plugin
stops its shared VirtualClient when removing a channel listener, so dynamically
rebinding channels disrupts other subscriptions. `ConfigSelect` also retargets
writable bias/feedback controls and is intentionally independent of monitoring.

`HardwareGroup` chooses integer or FP receivers from `useFloatPid` and registers
all boards' receivers as `PidDebug[global_column]`, preserving board-0 paths.
Both GUI entry points use `WarmTdmDisplay`; the obsolete Designer file and its
`pydmUi` alias were removed. Consumers import package exports, not underscore
implementation modules. Focused tests execute initializer exports in their
actual order to check that contract.

## Files and validation

Primary modules: `_HardwareGroup.py`, `_PidDebugger.py`, `_PidDebuggerFp.py`,
`_DataFormats.py`, `_PidLockMonitor.py`, `widgets/_pid_history.py`,
`widgets/_pid_lock_tab.py`, `_warm_tdm_display.py`, and `warmTdmClientGui.py`.
Usage instructions: [software guide](../../../software/SOFTWARE_GUIDE.md#pid-lock-tab).

Validation on September 18, 2026:

- All **213** software pytest cases passed, including **42** monitor tests for
  fixed/FP frames, wrap continuity, signed count range/limits, legacy formats,
  masked visits, independent row throttling, coherent forwarding, selection,
  malformed frames, history bounds, timestamp/drop gaps and missing calibration.
- `software/tests/rogue_pid_lock_smoke.py` passed with real Rogue, localhost ZMQ,
  PyDM and PySide6 offscreen using synthetic hardware. Both integer and FP
  frames traverse the existing column filters, existing receivers, per-row
  samples, selector and GUI. Verified legacy row diagnostics, checkbox writes,
  both feedback curves, pause/resume, and switching to global column 8 on board 1.
- Inspected the rendered 1150 × 820 capture for wrap continuity and matching time
  ranges. Temporary capture: `/private/tmp/warm-tdm-pid-lock.png`; regenerate with
  `PID_MONITOR_SCREENSHOT` when running the smoke test.
- No FPGA build or hardware test was performed.
- `git diff --check` and syntax parsing of changed Python files passed.

The offline suite uses `anaconda3/envs/rogue-build` with the existing temporary
`simple_pid` path. The GUI smoke uses `miniforge3/envs/bk9130c_dev`,
`QT_API=pyside6`, `QT_QPA_PLATFORM=offscreen`, and localhost socket access outside
the filesystem sandbox. No installed packages were modified.

## Remaining acceptance and limits

Check actual integer and FP boards for display responsiveness, polarity, wrap
continuity, debug-stream traffic and masked-row behavior. Sample reconstruction
and commit gating use cached DSP configuration, which is not timestamped in the
frame. Out-of-band writes require a cache refresh; configuration transitions
and queued old frames can temporarily disagree with that cache.

The current integer-v3 interpretation assumes the 19-bit saturated net-count
firmware; older v3 bitfiles with a narrower counter need their own compatibility
decision. FP wrap periods can span several physical flux quanta. This 10 Hz
sampled view can miss fast transients and is not an event counter or spectral
measurement. Debug enable remains an explicit user action and selection leaves
other columns' enables unchanged.
