# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Live P-gain exploration on one already-tuned column; no automatic gain application."""
import math
import time
import numpy as np


def sweep_pid_p(session, column, gains, seconds=12, tolerance=20.0, results=None):
    """Measure actual selected logical rows; restore the original P gain on exit.

    Timing/PID must already be running. I/D remain unchanged. This samples AXI
    registers once per second, so flux excursions between polls can be missed.
    `results` can retain completed candidates if a later candidate is interrupted.
    """
    gains = [float(value) for value in gains]
    if not gains or not all(math.isfinite(g) for g in gains):
        raise ValueError('Provide finite P gains')
    if not math.isfinite(seconds) or seconds < 3 or int(seconds) != seconds:
        raise ValueError('seconds must be an integer >= 3')
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('tolerance must be finite and nonnegative')
    enabled = session.col_enable_bools()
    if not 0 <= column < len(enabled) or not enabled[column]:
        raise ValueError('Choose an enabled column')
    rows = np.asarray(session.group.RowReadoutOrder.get(), dtype=int)
    if not rows.size or np.any(rows < 0) or len(set(rows.tolist())) != rows.size:
        raise ValueError('Expected unique, nonnegative logical rows')
    board, chan = session.col_to_board_chan(column)
    dsp = session.cbs[board].DataPath.AdcDsp[chan]
    tx = session.coordinator_cb.WarmTdmCore.Timing.TimingTx
    if not tx.Running.get() or not dsp.PidEnable.get():
        raise ValueError('Start timing and enable PID before sweeping')
    mask = int(dsp.RowEnableMask.get())
    if any(not (mask & (1 << int(row))) for row in rows):
        raise ValueError('Selected rows include PID-masked rows')

    def samples(variable):
        values = np.asarray(variable.get())
        selected = values[rows]
        if not np.all(np.isfinite(selected)):
            raise ValueError('Non-finite row measurements')
        return selected

    # Check indexing before changing gains.
    samples(dsp.AccumError)
    samples(dsp.FluxJumps)
    gain = session.group.PidP_Gain
    previous = float(gain.get(index=column))
    results = [] if results is None else results
    try:
        for p in gains:
            session.set_pid(p=p, cols=[column])
            initial = samples(dsp.FluxJumps).copy()
            trajectory, flux_excursions = [], []
            for _ in range(int(seconds)):
                time.sleep(1.0)
                trajectory.append(float(np.mean(np.abs(samples(dsp.AccumError)))))
                flux_excursions.append((samples(dsp.FluxJumps) - initial).tolist())
            floor = float(np.mean(trajectory[-3:]))
            settled = next((i + 1 for i in range(len(trajectory) - 2)
                            if all(abs(v - floor) <= tolerance for v in trajectory[i:])), None)
            # Opposite signs on different rows must not cancel.
            excursion = int(np.max(np.abs(np.asarray(flux_excursions))))
            results.append(dict(p=p, column=column, rows=rows.tolist(), trajectory=trajectory,
                                floor=floor, settle_s=settled, max_flux_excursion=excursion,
                                flux_excursions=flux_excursions))
    finally:
        gain.set(value=previous, index=column)
    return results
