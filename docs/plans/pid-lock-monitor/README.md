# Live PID lock monitor

## Goal and current status

The Python GUI plots multiple logical row/global column pairs with overlay and
separate-panel layouts, DAC/full-feedback modes, synchronized mean error and net
wrap count, bounded history, pause/resume and per-channel stale indication.
Logical rows work independently of flat or two-level physical RowMap topology.
Selections are local to each GUI window; hardware debug enables remain shared.

Implementation and synthetic integration checks are complete. Hardware
acceptance remains outstanding. The broader metrics proposal remains separate:
[PID analyzer](../pid-debug-analysis/PLAN.md) (#108).

The permanent [software guide](../../../software/SOFTWARE_GUIDE.md#pid-lock-tab)
owns usage, selection syntax, limits and sample interpretation.

## Implementation decisions

- Existing integer/FP receivers publish coherent `RowPids.PID[row].Sample`
  snapshots at up to 10 Hz per row; scalar diagnostics retain their existing
  update rate. No extra raw-frame receiver or decoding path is added.
- The GUI attaches removable listeners directly to selected sample variables.
  Receive callbacks queue owned copies; the Qt timer drains bounded queues and
  redraws once per batch. Listener removal never stops the shared VirtualClient.
  This avoids the installed Rogue PyDM plugin's client-stopping channel teardown.
- The old `HardwareGroup.PidLockMonitor` selector remains for older clients but
  does not own the new GUI selection. `ConfigSelect` remains independent.
- Each channel has its own bounded history. Visible traces share the latest
  visible hardware timestamp as their plotting origin, exposing stalled traces.
- Search/ranges and a selected-channel list support up to 32 detailed channels.
  Colors repeat beyond eight; large selections receive a crowding notice.
  Saved selections, acquisition-mask presets and a heatmap remain future work.

Primary modules: `widgets/_pid_lock_tab.py`, `_pid_channel_picker.py`,
`_pid_selection.py`, `_pid_source.py`, `_pid_history.py`, plus the existing
`_PidDebugger.py`, `_PidDebuggerFp.py` and `_DataFormats.py` receiver path.

## Evidence and remaining acceptance

The original September 18 implementation passed all 213 then-existing software
pytest cases and a real Rogue/ZMQ/PyDM synthetic smoke test. The multi-channel
update passes 53 focused monitor/selection/listener tests. The expanded
`software/tests/rogue_pid_lock_smoke.py` exercises actual integer/FP streams on
two synthetic boards, independent GUI windows sharing one client, layouts,
explicit column enables, pause/resume, channel removal/re-addition and closing
one window while the other continues receiving. The smoke also exercises picker
validation, hide/show and the link-transition callback. Actual network/server
restart recovery and hardware operation still need bench acceptance.

Next: test actual integer and FP boards for responsiveness, polarity, wrap
continuity, debug-stream traffic and masked-row behavior. Compare simultaneous
rows/columns and independent clients; exercise stale channels and reconnects.
No FPGA build or hardware test was performed for these GUI changes.

Samples use cached DSP configuration without a configuration timestamp in each
frame. Refresh after out-of-band writes; transitions can temporarily disagree
with queued frames. Integer v3 assumes the current 19-bit saturated net counter.
FP wrap periods can span several physical flux quanta. Shared plot time assumes
synchronized board timing. This sampled display can miss fast transients and is
not an event counter or spectral measurement.
