"""Diagnostic SQ1-feedback and TES-bias ramps.

Sweep one operating-point axis (SQ1 feedback or TES bias) for a row/column while
measuring the SA offset required to null the output at each point, via the
shared :func:`saOffset` primitive.
"""

import numpy as np

from ._common import saOffset


def sq1Ramp(group, row, column, low_offset=-77.0, high_offset=77.0, step=1.0):
    """Run a diagnostic SQ1-feedback ramp for one row/column operating point.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing the SQ1-feedback RAM and force-current controls.
    row : int
        Logical row used to read the ramp center. The caller must activate the
        desired row when required; this function does not change row selection.
    column : int
        Logical column whose SQ1 feedback is swept.
    low_offset, high_offset : float
        Inclusive feedback offsets relative to the loaded ``(column, row)``
        operating point, in microamps.
    step : float
        Feedback-current increment in microamps.

    Returns
    -------
    list[numpy.ndarray]
        SA-offset servo result for every requested feedback point.

    Notes
    -----
    Only ``column`` is written through the SQ1-feedback force path. The final
    feedback and SA-offset controls remain applied after the ramp.
    """
    # Center the diagnostic span on the configured per-row readout value rather
    # than on whatever temporary force-current value happens to be active.
    center = group.Sq1FbCurrent.get(index=(column, row))
    low = center + low_offset
    high = center + high_offset
    numSteps = int((high - low) / step) + 1
    group._log.info(f'sq1Ramp row={row}, col={column}: center={center:.2f}, {numSteps} steps')

    # Each stimulus point requires a fresh SA-offset convergence measurement.
    outputs = []
    for fb in np.arange(low, high + step, step):
        group.Sq1FbForceCurrent.set(value=fb, index=column)
        offset = saOffset(group=group)
        outputs.append(offset)
    return outputs


def sq1RampRow(group, column, **kwargs):
    """Run :func:`sq1Ramp` for every hardware row on one column.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group whose rows are activated in turn.
    column : int
        Logical column to ramp.
    **kwargs
        Forwarded to :func:`sq1Ramp`.

    Returns
    -------
    list[list[numpy.ndarray]]
        Ramp results indexed by hardware row and then feedback point.

    Notes
    -----
    This diagnostic iterates ``MaxRows``, not ``RowIndexOrderList``.
    """
    numRows = group.MaxRows.get()
    group._log.info(f'sq1RampRow col={column}: {numRows} rows')
    results = []
    for row in range(numRows):
        group.ActivateRowIndex(row)
        results.append(sq1Ramp(group, row, column, **kwargs))
        group.DeactivateRowIndex(row)
    return results


def tesRamp(group, row, column, low_offset=0.0, high_offset=100.0, step=1.0):
    """Run a diagnostic TES-bias ramp while measuring required SA offset.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing TES-bias and SA-offset controls.
    row : int
        Logical row associated with the diagnostic. The caller is responsible
        for row activation; TES bias itself is column-wide.
    column : int
        Logical TES-bias column to sweep.
    low_offset, high_offset : float
        Half-open bias span relative to the current TES-bias value, in microamps.
    step : float
        TES-bias increment in microamps.

    Returns
    -------
    list[numpy.ndarray]
        SA-offset servo result for every requested TES-bias point.

    Notes
    -----
    The final TES-bias and SA-offset controls remain applied after the ramp.
    """
    # Use the currently loaded bias as the origin for the requested relative span.
    center = group.TesBias.get(index=column)
    low = center + low_offset
    high = center + high_offset
    numSteps = int((high - low) / step)
    group._log.info(f'tesRamp row={row}, col={column}: center={center:.2f}, {numSteps} steps')

    outputs = []
    for bias in np.arange(low, high, step):
        group.TesBias.set(index=column, value=bias)
        offset = saOffset(group=group)
        outputs.append(offset)
    return outputs


def tesRampRow(group, column, **kwargs):
    """Run :func:`tesRamp` for every hardware row on one column.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group whose rows are activated in turn.
    column : int
        Logical TES-bias column to ramp.
    **kwargs
        Forwarded to :func:`tesRamp`.

    Returns
    -------
    list[list[numpy.ndarray]]
        Ramp results indexed by hardware row and then TES-bias point.

    Notes
    -----
    This diagnostic iterates ``MaxRows``, not ``RowIndexOrderList``.
    """
    numRows = group.MaxRows.get()
    group._log.info(f'tesRampRow col={column}: {numRows} rows')
    results = []
    for row in range(numRows):
        group.ActivateRowIndex(row)
        results.append(tesRamp(group, row, column, **kwargs))
        group.DeactivateRowIndex(row)
    return results
