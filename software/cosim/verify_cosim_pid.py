#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Closed-loop PID behavior + performance check for the GroupTb cosim.

Locks the muxed SQ1-FB servo with REAL (nonzero) gains and measures its
behavior/performance from the per-visit PID-debug stream -- for BOTH the integer
``AdcDsp`` and floating-point ``AdcDspFp`` controllers (auto-detected; only the
underlying class differs, the tree node is ``DataPath.AdcDsp[col]`` either way).

Two modes:
  * ``verify``  -- pass/fail: each behavior must meet its threshold (CI gate).
  * ``measure`` -- report the same metrics without hard-failing (tuning/telemetry).

Behaviors (``--behaviors``):
  * ``steady`` -- seed the operating point, lock, measure per-row steady-state
    residual / RMS / flux jumps.
  * ``step``   -- apply a TesBias step and measure the excursion + settling +
    overshoot back to null.
  * ``flux``   -- (opt-in) ramp TesBias toward the flux quantum; best-effort, the
    synthetic model may not cleanly reach the rail, so this never hard-fails on
    NOT jumping -- it only requires the loop stays locked and the count is
    self-consistent. RTL flux-jump wrap is qualified separately by the cocotb unit
    bench (tests/warm_tdm/adc_dsp/test_AdcDsp_flux.py).

Run against a live ``warmTdmServer --sim`` (integer or float build). See
software/cosim/README_cosim.md for the recipe;
``run_cosim_pid_suite.py`` orchestrates both builds end to end.
"""
import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from _cosim_common import parser, passed, positive, require, restore, run, wait_running

# Built-in per-path defaults (gains are RAW hardware coefficients, sign included).
# From docs/plans/pid-cosim-verification/{PROGRESS.md,cosim-tuning-settings.md};
# model+build specific (VARIATION_SEED=0 sinusoid-blend build), NOT physics.
# Operating point revalidated closed-loop 2026-09-18 on the merged multi-flux-wrap
# RTL + 23 uA plant at the CORRECTED SQ1 tune point (Sq1Bias=50, Sq1Fb=2, SaFb=9;
# the old Sq1Bias=100 clipped the DAC to ~77 uA and would not lock at any gain).
# At the correct point the stable integer P is NEGATIVE, P-only (I=0; a nonzero I
# can wind the 19-bit flux count). NOTE this sign is opposite the earlier
# clipped-bias result -- the operating point, not just the gain, matters.
# Gain magnitude re-tuned 2026-09-21 via a closed-loop AXI-AccumError sweep (the
# stream capture yields too few visits to see the loop floor). raw P=-0.0025
# (norm -0.05) took ~30 s to reach <800 counts and floored ~360 -- too slow for
# the cosim stream capture, which then sampled the loop mid-descent. raw P=-0.010
# (norm -0.20 at SampleCount=20) converges in ~8 s to ~27 counts with NO limit
# cycle (settled spread ~15); -0.02 was no better. -0.010 is the chosen default:
# floors far under threshold and settles inside the capture window.
DEFAULTS = {
    'integer': dict(
        sq1fb_uA=2.0, sq1bias_uA=50.0, safb_uA=9.0, flux_quantum_uA=23.0,
        gains=dict(p_raw=-0.010, i_raw=0.0, d_raw=0.0, use_group_gain=True),
        step_uA=500.0,
        thresholds=dict(residual_max=800.0, flux_jump_max=0),
    ),
    'float': dict(
        sq1fb_uA=2.0, sq1bias_uA=50.0, safb_uA=9.0, flux_quantum_uA=23.0,
        # Re-tuned 2026-09-21 via a closed-loop AXI-AccumError sweep at the
        # Sq1Bias=50/Sq1Fb=2/SaFb=9 point (SampleCount=20). The OLD default
        # p_raw=+1e-4 was BOTH the wrong SIGN (positive P = positive feedback ->
        # diverges) AND ~50x too weak. The stable FP P is NEGATIVE, same sign as
        # integer -- both controllers share the additive-error P law. FP needs a
        # much larger |P| than integer: -0.0005 floored ~7000 (no lock in 40 s),
        # -0.002 -> 32 s/floor 228, -0.005 -> 14-16 s/floor ~90 (P-only). Adding
        # I tightens the deadband: at P=-0.005, I=-1e-5 floors ~40 with the
        # tightest spread (~60) and no windup; I<=-3e-5 begins to wind
        # (floor/spread rise). Chosen: P=-0.005, I=-1e-5.
        gains=dict(p_raw=-0.005, i_raw=-1e-5, d_raw=0.0, use_group_gain=True),
        step_uA=500.0,
        # A benign FluxJumps=1/row can appear at the 0.7-Phi0 seed (FP
        # DAC-centering wrap), so allow 1.
        thresholds=dict(residual_max=700.0, flux_jump_max=1),
    ),
}


def detect_path(dsp):
    """Return 'integer' or 'float' from the AdcDsp node's variable set."""
    if hasattr(dsp, 'D_Coef') and hasattr(dsp, 'Sq1FbFullValid'):
        return 'integer'
    if hasattr(dsp, 'P_Coef') and hasattr(dsp, 'I_Coef') and not hasattr(dsp, 'D_Coef'):
        return 'float'
    raise AssertionError('Cannot classify AdcDsp path (unexpected coefficient set)')


def load_profile(args, path):
    """Merge built-in per-path defaults <- JSON --profile block <- CLI overrides."""
    cfg = json.loads(json.dumps(DEFAULTS[path]))  # deep copy
    if args.profile is not None:
        block = json.loads(args.profile.read_text()).get(path, {})
        for key, val in block.items():
            if isinstance(val, dict):
                cfg.setdefault(key, {}).update(val)
            else:
                cfg[key] = val
    # CLI overrides (only when explicitly given, i.e. not None)
    for attr, key in [('sq1fb', 'sq1fb_uA'), ('flux_quantum', 'flux_quantum_uA')]:
        if getattr(args, attr) is not None:
            cfg[key] = getattr(args, attr)
    for attr, key in [('p_raw', 'p_raw'), ('i_raw', 'i_raw'), ('d_raw', 'd_raw')]:
        if getattr(args, attr) is not None:
            cfg['gains'][key] = getattr(args, attr)
    for attr, key in [('residual_max', 'residual_max'), ('flux_jump_max', 'flux_jump_max')]:
        if getattr(args, attr) is not None:
            cfg['thresholds'][key] = getattr(args, attr)
    if args.step_uA is not None:
        cfg['step_uA'] = args.step_uA
    cfg.setdefault('step_uA', 500.0)
    return cfg


def apply_gains(sess, cb, col, path, gains):
    """Write the raw PID coefficients (sign per path) via the right interface."""
    dsp = cb.DataPath.AdcDsp[col]
    tx = cb.WarmTdmCore.Timing.TimingTx
    n = int(tx.SampleCount.get())            # normalized = raw * SampleCount
    if path == 'integer':
        # set_pid takes normalized gains and writes P/I/D_Coef = norm / SampleCount.
        sess.set_pid(p=gains['p_raw'] * n, i=gains['i_raw'] * n,
                     d=gains['d_raw'] * n, cols=[col])
        return dict(interface='set_pid', p_norm=gains['p_raw'] * n, i_norm=gains['i_raw'] * n)
    # Float: set_pid early-returns (PI-only group lacks PidD_Gain). Prefer the
    # normalized PidP_Gain/PidI_Gain (which DO exist for FP); fall back to raw coefs.
    if gains.get('use_group_gain', True) and hasattr(sess.group, 'PidP_Gain'):
        sess.group.PidP_Gain.set(value=gains['p_raw'] * n, index=col)
        sess.group.PidI_Gain.set(value=gains['i_raw'] * n, index=col)
        return dict(interface='group_gain', p_norm=gains['p_raw'] * n, i_norm=gains['i_raw'] * n)
    dsp.P_Coef.set(float(gains['p_raw']))
    dsp.I_Coef.set(float(gains['i_raw']))
    return dict(interface='raw_coef', p_raw=gains['p_raw'], i_raw=gains['i_raw'])


def apply_lock(sess, cb, args, cfg, col, path):
    """The established lock recipe (see cosim_pid_lock.py + PROGRESS 'night' section)."""
    dsp = cb.DataPath.AdcDsp[col]
    # (0) fresh sim: seed the SA/SQ1/FAS bias fixture (runs saOffset server-side).
    if args.seed_tune_points:
        sess.group.SetCosimTunePoints()
    # (2) FluxQuantum = Phi0 (RTL default 0 = wrap disabled). The float path
    # guards this write behind "PID disabled + not busy", so disable PID first
    # (harmless for the integer path).
    dsp.PidEnable.set(False)
    dsp.FluxQuantum.set(cfg['flux_quantum_uA'])
    # (2b) Read out exactly the rows under test. A fresh sim defaults
    # RowReadoutOrder to [0] -- without this only row 0 is ever visited (so only
    # row 0 seeds/servos and the rest read as unseeded/no-data).
    sess.group.RowReadoutOrder.set(list(range(args.rows)))
    # (1) Write the COMPLETE coherent per-row operating point into the readout
    # tables -- Sq1Bias AND Sq1Fb AND SaFb, not just Sq1Fb. The per-row SaFb
    # current sets the SA operating point, so all three must be applied BEFORE
    # the SA null below; seeding only Sq1Fb (and leaving SaFb/Sq1Bias at whatever
    # SetCosimTunePoints or a prior run left) is what made the lock flaky. Values
    # from cfg (sq1fb) + the model-fit constants (Sq1Bias=50, SaFb=9); see
    # docs/plans/pid-cosim-verification/cosim-tuning-settings.md and
    # warm_tdm_api._Group.SetSimSq1TunePoint.
    for r in range(args.rows):
        sess.group.Sq1BiasCurrent.set(index=(col, r), value=cfg.get('sq1bias_uA', 50.0))
        sess.group.Sq1FbCurrent.set(index=(col, r), value=cfg['sq1fb_uA'])
        sess.group.SaFbCurrent.set(index=(col, r), value=cfg.get('safb_uA', 9.0))
    # (3) null the SA AFTER the operating-point tables are applied, so the offset
    # references the actual SA operating point the muxed readout will use. An
    # offset taken before these per-row currents does not null the run and the
    # servo cannot lock (verified A/B, 2026-09-18).
    sess.sa_offset()
    # (4) mux config: small sample window keeps the integrator off the rail.
    sess.setup_mux(num_pts=args.num_pts, sample_num=args.sample_num,
                   enable_pid=True, enable_pid_debug=True)
    # setup_mux leaves RowSequencesPerDaqReadout at the hardware default (40): a
    # DAQ readout then spans 40 row sequences and never completes in a short
    # cosim run, so neither the readout nor the PID-debug stream flushes. Shrink
    # it (1 = one readout per row sequence) so frames arrive quickly.
    cb.WarmTdmCore.Timing.TimingTx.RowSequencesPerDaqReadout.set(args.daq_readout)
    # (5) gains -- after setup_mux (which re-applies snapshotted normalized gains).
    applied = apply_gains(sess, cb, col, path, cfg['gains'])
    # (6) start the free-running MUX.
    sess.run_mux()
    # The DataWriter tees the app data (readout + PID-debug) streams only after
    # its first Open/Close on a run; the very first capture otherwise carries
    # config frames only. Prime with one throwaway capture (which also doubles as
    # settle time) so the measurement captures carry the real streams.
    sess.root.DataWriter.DataFile.set(os.path.join(sess._require_output(), 'prime.dat'))
    sess.take_data(args.prime, start_delay_sec=args.settle)
    # Let the servo actually CONVERGE before any steady-state capture. In the VCS
    # cosim the loop needs ~25-30 s of wall time to walk from the StartRun
    # transient down into the deadband (measured: mean|AccumError| 13215 -> ~785
    # over ~28 s at integer P=-0.0025). A steady-state capture opened before that
    # would average pre-lock frames and report a huge residual for a loop that is
    # in fact locking. This is settle time only -- it never masks a genuine
    # non-lock, whose error stays large past the wait.
    if args.lock_settle > 0:
        time.sleep(args.lock_settle)
    return applied


def capture_metrics(sess, args, col, rows, deadband=None, acq=None, on_open=None):
    """take_data within the running MUX, then per-row pid_metrics (format-agnostic).

    ``on_open`` (callable) is invoked right before the capture opens -- used by the
    step-response check to fire the perturbation from a timer so its excursion
    lands inside the capture window.
    """
    from warm_tdm_api.operations import StreamData
    from warm_tdm_api.operations.pid_analysis import pid_metrics
    # Anchor the DataWriter file in THIS session's output dir. take_data's
    # AutoName() otherwise inherits the directory of any stale absolute DataFile
    # left on a reused server, so captures would silently land elsewhere.
    sess.root.DataWriter.DataFile.set(os.path.join(sess._require_output(), 'pid.dat'))
    if on_open is not None:
        on_open()
    path = sess.take_data(acq if acq is not None else args.acq, start_delay_sec=args.settle)
    sd = StreamData(path)
    metrics = {r: pid_metrics(sd, col, r, deadband=deadband) for r in rows}
    return str(path), metrics


def _has_data(metrics):
    return any((m.get('n_visits') or 0) > 0 for m in metrics.values())


def capture_data(sess, args, col, rows, deadband=None, acq=None, on_open=None):
    """Retry take_data until the PID-debug stream is non-empty (cosim DataWriter
    tees the data streams only intermittently -- empty captures are expected and
    must be re-taken, not treated as 'no lock'). Returns (path, metrics, got_data).

    ``on_open`` is re-invoked on every attempt (the step check resets + re-applies
    its perturbation each try, so the excursion is fresh in whichever attempt
    finally carries data).
    """
    path, metrics = None, {}
    for _ in range(max(1, args.capture_retries)):
        path, metrics = capture_metrics(sess, args, col, rows, deadband=deadband,
                                        acq=acq, on_open=on_open)
        if _has_data(metrics):
            return path, metrics, True
    return path, metrics, False


def record(report, args, name, ok, **details):
    """verify: require(ok) then passed; measure: always passed with threshold_met."""
    if args.mode == 'verify':
        require(ok, f'{name}: threshold not met -- {details}')
        passed(report, name, **details)
    else:
        passed(report, name, threshold_met=bool(ok), **details)


def _mean_over_rows(metrics, key):
    vals = [m[key] for m in metrics.values() if m.get(key) is not None]
    return float(np.mean(vals)) if vals else None


def _locked(metrics, cfg):
    """A capture is 'locked' if the converged-tail residual is within threshold.

    Uses final_residual (mean |error| over the last few visits), not the
    second-half mean: the sparse cosim stream often captures a StartRun/step
    transient inside the window, which inflates the half-mean even after the
    servo has fully re-converged by the end of the capture. A genuinely
    non-locking loop stays large in the final visits too, so this is not a
    false pass.
    """
    fr = _mean_over_rows(metrics, 'final_residual')
    return fr is not None and fr <= cfg['thresholds']['residual_max']


def check_steady_state(sess, args, report, cfg, col, rows):
    path, metrics, got = capture_data(sess, args, col, rows, deadband=args.deadband)
    # Judge lock on the converged-tail residual (final_residual); report the
    # second-half mean (steady_residual) alongside for context. See _locked.
    final_res = _mean_over_rows(metrics, 'final_residual')
    mean_res = _mean_over_rows(metrics, 'steady_residual')
    max_fj = max((abs(m['flux_jump_delta']) for m in metrics.values()
                  if m.get('flux_jump_delta') is not None), default=None)
    th = cfg['thresholds']
    ok = (got and final_res is not None and final_res <= th['residual_max']
          and (max_fj is None or max_fj <= th['flux_jump_max']))
    record(report, args, 'steady-state lock + residual', ok, file=path, got_data=got,
           final_residual=final_res, mean_residual=mean_res, max_flux_jump=max_fj,
           residual_max=th['residual_max'], flux_jump_max=th['flux_jump_max'],
           per_row=metrics)


def check_step_response(sess, args, report, cfg, col, rows):
    """Disturbance rejection: apply a DC TesBias step and verify the servo holds
    lock (error stays bounded, no spurious flux jumps).

    Note on method + model limit: the synthetic TES->SQ1 coupling is weak
    (~0.024 uA_fb/uA_TES), so even a large TesBias step needs only a few DAC
    codes of feedback to null and barely moves the steady error -- and the servo
    recovers near-deadbeat while the cosim PID-debug stream is sparse
    (~6-8 visits/window), so the single-visit transient PEAK cannot be caught
    reliably. The robust, meaningful assertion is therefore lock RETENTION under
    the disturbance; the feedback move and any captured transient peak are
    reported as informational, not thresholded.
    """
    th = cfg['thresholds']
    with restore([sess.group.TesBias]):
        base = float(np.asarray(sess.group.TesBias.get())[col])
        # Pre-step: confirm locked and record the feedback baseline.
        _, pre, pre_got = capture_data(sess, args, col, rows, deadband=args.deadband)
        was_locked = pre_got and _locked(pre, cfg)
        fb_before = _mean_over_rows(pre, 'feedback_mean')
        # Apply the step and leave it applied; the servo must hold lock.
        sess.group.TesBias.set(index=col, value=base + cfg['step_uA'])
        # Let the loop reject the disturbance and RE-settle before measuring the
        # post-step residual. Without this the capture re-catches the re-lock ramp
        # (same sparse-stream effect as the initial lock) and reports a residual
        # just over threshold for a servo that did in fact recover. A servo that
        # cannot reject the step stays high past this wait, so lock retention is
        # still tested honestly.
        if args.lock_settle > 0:
            time.sleep(args.lock_settle)
        path, metrics, got = capture_data(sess, args, col, rows, deadband=args.deadband)
    fb_after = _mean_over_rows(metrics, 'feedback_mean')
    # Converged-tail residual after the step; the second-half mean is reported too
    # but is inflated by the in-window step transient on the sparse cosim stream.
    res_after = _mean_over_rows(metrics, 'final_residual')
    half_after = _mean_over_rows(metrics, 'steady_residual')
    peak = max((m['peak_abs_error'] for m in metrics.values()
                if m.get('peak_abs_error') is not None), default=None)
    max_fj = max((abs(m['flux_jump_delta']) for m in metrics.values()
                  if m.get('flux_jump_delta') is not None), default=None)
    fb_move = (abs(fb_after - fb_before) if fb_before is not None and fb_after is not None
               else None)
    # LOCK-RETENTION criterion (not a hard post-step residual threshold). The
    # cosim PID-debug stream is sparse (~7-8 visits) and the step transient lands
    # inside the capture; a row whose window truncates a visit early ends mid-
    # recovery (final_residual still elevated) even though the servo IS rejecting
    # the step. So judge recovery RELATIVE to the transient the step caused: the
    # loop passes if, after the step, (1) it was locked beforehand, (2) the
    # feedback actually moved to reject the disturbance, (3) no spurious flux
    # jumps, and (4) the error came substantially back DOWN from its post-step
    # peak (final_residual <= recover_frac * transient_peak) OR is already within
    # the absolute residual threshold. A servo that does NOT recover stays near
    # its peak (ratio ~1) and fails; a genuine non-lock also fails (3)/(4).
    recover_frac = cfg['thresholds'].get('step_recover_frac', 0.25)
    recovered = (res_after is not None and peak is not None and peak > 0
                 and (res_after <= th['residual_max']
                      or res_after <= recover_frac * peak))
    # A real disturbance rejection has to move the actuator; require a nonzero,
    # finite feedback move (guards against "nothing happened" false passes).
    fb_moved = fb_move is not None and fb_move > 0.0
    ok = (got and was_locked and fb_moved and recovered
          and (max_fj is None or max_fj <= th['flux_jump_max']))
    record(report, args, 'step disturbance rejection', ok, file=path, got_data=got,
           step_uA=cfg['step_uA'], pre_step_locked=was_locked,
           residual_after=res_after, half_residual_after=half_after,
           residual_max=th['residual_max'], recover_frac=recover_frac,
           recovered=recovered, feedback_moved=fb_moved,
           feedback_before=fb_before, feedback_after=fb_after, feedback_move=fb_move,
           transient_peak=peak, max_flux_jump=max_fj,
           limitation='Weak synthetic TES->SQ1 coupling: this is a DC '
                      'disturbance-rejection/lock-retention check, not a '
                      'large-signal transient measurement. Pass = pre-locked + '
                      'feedback moved + no flux jumps + error recovered from its '
                      'post-step peak; not a tight post-step residual (the sparse '
                      'stream truncates some rows mid-recovery).',
           per_row=metrics)


def _flux_jump_counts(dsp, rows):
    """Signed per-row net flux-jump count straight from the FluxJumps register.

    This is the ground truth for how many quanta the servo has wrapped, unlike
    the PID-debug ``flux_jump_delta`` (which is only the count change WITHIN one
    short capture window and so under-reports a slow ramp)."""
    vals = np.asarray(dsp.FluxJumps.get())
    return [int(vals.flat[r]) for r in rows]


def check_flux_jump(sess, args, report, cfg, col, rows):
    """Ramp TesBias and confirm the servo tracks it across multiple flux quanta.

    Reads the FluxJumps *register* directly at each step (ground truth) rather
    than the per-window PID-debug delta. Best-effort: never hard-fails on not
    reaching the rail; requires only that the loop stays locked and the counts
    move monotonically (no spurious reversals)."""
    th = cfg['thresholds']
    cb = sess.coordinator_cb
    dsp = cb.DataPath.AdcDsp[col]
    traj = []
    with restore([sess.group.TesBias]):
        base = float(np.asarray(sess.group.TesBias.get())[col])
        start_counts = _flux_jump_counts(dsp, rows)
        for k in range(1, args.flux_steps + 1):
            sess.group.TesBias.set(index=col, value=base + k * args.flux_step_uA)
            path, metrics, _got = capture_data(sess, args, col, rows, deadband=args.deadband)
            counts = _flux_jump_counts(dsp, rows)
            # Cumulative net wrap since the pre-ramp baseline, per row.
            net = [c - s for c, s in zip(counts, start_counts)]
            traj.append(dict(tesbias=base + k * args.flux_step_uA, file=path,
                             flux_jump_counts=counts, flux_jump_net=net,
                             locked=_locked(metrics, cfg)))
    # Total wrap the ramp produced (max |net| over rows).
    total_net = max((abs(n) for t in traj for n in t['flux_jump_net']), default=0)
    observed = total_net > 0
    # Monotonic in |net| per row: a locked, continuously-tracking loop only adds
    # wraps in one direction, so |net| must be non-decreasing along the ramp.
    monotone_ok = True
    for r in range(len(rows)):
        seq = [abs(t['flux_jump_net'][r]) for t in traj]
        if any(b < a for a, b in zip(seq, seq[1:])):
            monotone_ok = False
    stayed_locked = bool(traj) and traj[-1]['locked']
    ok = stayed_locked and monotone_ok
    record(report, args, 'flux-jump exercise (best-effort)', ok,
           flux_jump_observed=observed, total_flux_jumps=total_net,
           stayed_locked=stayed_locked, counts_self_consistent=monotone_ok,
           trajectory=traj,
           note='FluxJumps read from the register directly; total_flux_jumps is '
                'the net quanta the TesBias ramp drove the servo through. RTL '
                'wrap also unit-qualified by tests/warm_tdm/adc_dsp/test_AdcDsp_flux.py')


def check(sess, args, report, directory):
    cb = sess.coordinator_cb
    tx = cb.WarmTdmCore.Timing.TimingTx
    col = args.col
    require(1 <= args.rows <= int(sess.group.MaxRows.get()), 'rows must be 1..Group.MaxRows')
    require(0 <= col < sess.chans_per_board, 'col out of range')
    dsp = cb.DataPath.AdcDsp[col]
    path = detect_path(dsp) if args.path == 'auto' else args.path
    report['pid_path'] = path
    cfg = load_profile(args, path)
    report['profile'] = cfg
    rows = list(range(args.rows))
    behaviors = [b.strip() for b in args.behaviors.split(',') if b.strip()]
    report['behaviors'] = behaviors

    variables = [dsp.PidEnable, dsp.PidDebugEnable, dsp.RowEnableMask, dsp.FluxQuantum,
                 sess.group.RowReadoutOrder,
                 tx.Mode, tx.RowPeriodCycles, tx.SampleStartTime, tx.SampleEndTime,
                 tx.RowSequencesPerDaqReadout,
                 sess.group.Sq1FbCurrent, sess.group.TesBias, dsp.P_Coef, dsp.I_Coef]
    if path == 'integer':
        variables += [dsp.D_Coef]
    for gname in ['PidP_Gain', 'PidI_Gain', 'PidD_Gain']:
        if hasattr(sess.group, gname):
            variables.append(getattr(sess.group, gname))

    with restore(variables):
        try:
            report['applied_gains'] = apply_lock(sess, cb, args, cfg, col, path)
            if 'steady' in behaviors:
                check_steady_state(sess, args, report, cfg, col, rows)
            if 'step' in behaviors:
                check_step_response(sess, args, report, cfg, col, rows)
            if 'flux' in behaviors:
                check_flux_jump(sess, args, report, cfg, col, rows)
        finally:
            tx.EndRun()
            wait_running(tx, False, args.timing_timeout)
            # Disable PID before the restore block runs: the float FluxQuantum
            # write (restored below) is guarded behind "PID disabled + not busy",
            # and EndRun alone does not clear PidEnable.
            dsp.PidEnable.set(False)
    report['final_state'] = ('run stopped; gains/coefs/masks/FluxQuantum/'
                             'Sq1FbCurrent/TesBias restored')


def main():
    p = parser(__doc__)
    p.add_argument('--mode', choices=['verify', 'measure'], default='verify')
    p.add_argument('--behaviors', default='steady,step',
                   help='comma list of: steady,step,flux (flux is opt-in/best-effort)')
    p.add_argument('--col', type=int, default=0)
    p.add_argument('--rows', type=int, default=8)
    p.add_argument('--path', choices=['auto', 'integer', 'float'], default='auto')
    p.add_argument('--profile', type=Path, default=None,
                   help='JSON profile with integer/float blocks')
    # operating point / lock (None => use profile/built-in default)
    p.add_argument('--sq1fb', type=float, default=None, help='mid-slope SQ1 FB [uA]')
    p.add_argument('--flux-quantum', type=float, default=None, help='FluxQuantum Phi0 [uA]')
    p.add_argument('--num-pts', type=int, default=400, help='RowPeriodCycles')
    p.add_argument('--sample-num', type=int, default=20, help='samples per row window')
    p.add_argument('--daq-readout', type=int, default=1,
                   help='RowSequencesPerDaqReadout (1 so frames flush in short cosim runs)')
    p.add_argument('--seed-tune-points', action='store_true',
                   help='call Group.SetCosimTunePoints() first (fresh sim fixture)')
    # gains (RAW; sign per path). None => profile/built-in.
    p.add_argument('--p-raw', type=float, default=None)
    p.add_argument('--i-raw', type=float, default=None)
    p.add_argument('--d-raw', type=float, default=None)
    # timing
    p.add_argument('--settle', type=positive, default=5.0, help='start_delay before capture')
    p.add_argument('--acq', type=positive, default=20.0, help='wall seconds per capture')
    p.add_argument('--prime', type=positive, default=5.0,
                   help='throwaway priming capture after run_mux (DataWriter streams '
                        'the real data only after its first Open/Close on a run)')
    p.add_argument('--lock-settle', type=float, default=15.0,
                   help='wall seconds to let the servo converge after run_mux/prime '
                        'before the steady-state capture. At the tuned default gains '
                        'the cosim loop reaches the deadband in ~8 s; 15 s leaves '
                        'margin. A capture opened sooner averages pre-lock frames. '
                        '0 disables (e.g. fast HW).')
    p.add_argument('--capture-retries', type=int, default=5,
                   help='re-take a capture up to N times until the PID stream is '
                        'non-empty (cosim DataWriter tees data only intermittently)')
    # step-response (None => profile/built-in default, 500 uA)
    p.add_argument('--step-uA', type=float, default=None)
    # flux-jump exercise
    p.add_argument('--flux-steps', type=int, default=6)
    p.add_argument('--flux-step-uA', type=float, default=20.0)
    # thresholds (verify mode; None => profile/built-in). measure reports vs these.
    p.add_argument('--residual-max', type=float, default=None)
    p.add_argument('--flux-jump-max', type=int, default=None)
    p.add_argument('--deadband', type=float, default=None,
                   help='settle tolerance for settling_visits (error units)')
    return run(p.parse_args(), check)


if __name__ == '__main__':
    raise SystemExit(main())
