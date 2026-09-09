"""FAS (Flux-Actuated Switch) tuning.

Sweep each active physical FAS line, use the shared :func:`saFbServo` to record
the SA feedback needed to null each enabled column, select the response minimum
per row, and optionally program the fitted ``FasOn`` currents. One-level row
maps only; ``FasOff`` is never modified.
"""

import numpy as np
import time

import warm_tdm_api

from ._common import _pause_point, saFbServo


def _fas_minimum_center(x_values, points, tolerance):
    """Find the center of a sampled FAS-response minimum.

    Start at the global minimum and expand in both directions while adjacent
    samples remain within ``tolerance`` of it. This avoids the low-current bias
    of ``argmin()`` when the servo response has a flat, quantized bottom.

    Parameters
    ----------
    x_values : array-like
        FAS-current samples in acquisition order.
    points : array-like
        SA-feedback response samples corresponding to ``x_values``.
    tolerance : float
        Maximum response above the global minimum that remains part of the
        selected contiguous region.

    Returns
    -------
    tuple
        ``(center, low_index, high_index, minimum_value)``. ``center`` is the
        midpoint between the first and last FAS-current samples in the region.

    Raises
    ------
    ValueError
        If no finite response samples are available.
    """
    x_values = np.asarray(x_values, dtype=np.float64)
    points = np.asarray(points, dtype=np.float64)
    count = min(x_values.size, points.size)
    if count == 0:
        raise ValueError('Cannot select a FAS minimum from an empty curve')

    x_values = x_values[:count]
    points = points[:count]
    finite = np.isfinite(points)
    if not np.any(finite):
        raise ValueError('Cannot select a FAS minimum from non-finite samples')

    finite_indices = np.flatnonzero(finite)
    minimum_index = int(
        finite_indices[np.argmin(points[finite_indices])])
    minimum_value = points[minimum_index]
    threshold = minimum_value + max(0.0, float(tolerance))

    low = minimum_index
    while low > 0 and finite[low - 1] and points[low - 1] <= threshold:
        low -= 1
    high = minimum_index
    while (high + 1 < count and finite[high + 1]
           and points[high + 1] <= threshold):
        high += 1

    center = 0.5 * (x_values[low] + x_values[high])
    return float(center), low, high, float(minimum_value)


def fasSweep(*, group, row, board, address, driver, enabled_mask,
             off_current, currents, delay, process, publish=None):
    """Measure the nulled SA-feedback response to one physical FAS line.

    The caller has already resolved the logical-row mapping, placed the row
    board in MANUAL mode, and cached its FAS-off current. Each FAS-current point
    is driven with ``manual_set()``, then :func:`saFbServo` determines the SA
    feedback required to null the enabled columns.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group being measured.
    row : int
        Logical row associated with the physical FAS line.
    board : int
        Row-board index containing the line.
    address : int
        Board-local FAS address in the range 0..31.
    driver : warm_tdm.RowDacDriver2
        Row-DAC driver, already configured for MANUAL operation.
    enabled_mask : array-like of bool
        Logical columns whose servo responses should be recorded.
    off_current : float
        Cached current used to return this line to its inactive state.
    currents : array-like
        Ordered FAS-current sweep values.
    delay : float
        Interruptible wall-clock delay after each manual write, in seconds.
    process : FasTuneProcess
        Parent process providing servo parameters, progress, and control state.
    publish : callable, optional
        Receives the in-progress ``CurveData`` at pause points.

    Returns
    -------
    CurveData
        Per-column SA-feedback responses plus ``logicalRow``, ``board``,
        ``address``, and an initially unset ``fasOn`` result.

    Notes
    -----
    The physical line is returned to ``off_current`` in a ``finally`` block,
    including after Stop or an acquisition exception.
    """
    log = process._log
    log.debug(
        'FAS sweep row %s start: board=%d address=%d low=%s high=%s '
        'steps=%d delay=%s currents=%s',
        row, board, address, currents[0], currents[-1], len(currents), delay,
        currents.tolist())
    # Attach physical/logical metadata before acquisition so an incomplete
    # curve can be serialized while paused or stopped.
    data = warm_tdm_api.CurveData(xValues=currents)
    for column in range(group.NumColumns.get()):
        data.addCurve(warm_tdm_api.Curve(column))
    data.logicalRow = row
    data.board = board
    data.address = address
    data.fasOn = None

    publish_data = None if publish is None else lambda: publish(data)

    log.debug(
        'FAS sweep row %s using captured FasOff[%d]=%s uA',
        row, address, off_current)
    try:
        for step, current in enumerate(currents):
            if not _pause_point(process, publish_data):
                log.debug(
                    'FAS sweep row %s stopped before step %d/%d',
                    row, step + 1, len(currents))
                break

            # MANUAL mode was set and verified once by fasTune; rechecking it
            # here would add a register read to every co-simulation point.
            request = driver.manual_set(
                address=address, current=current, check_mode=False)
            # Record a point only after the inner servo completes; partial
            # servo iterations are not valid FAS response samples.
            log.debug(
                'FAS sweep row %s step %d/%d ManualSet: requested=%s uA '
                'result=%s',
                row, step + 1, len(currents), current, request)

            # Stop() waits for the worker thread, so keep a user-configured
            # settling delay interruptible rather than sleeping in one block.
            deadline = time.monotonic() + max(0.0, delay)
            while time.monotonic() < deadline:
                if not _pause_point(process, publish_data):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    break
                time.sleep(min(0.05, remaining))
            if not _pause_point(process, publish_data):
                log.debug(
                    'FAS sweep row %s stopped while settling step %d/%d',
                    row, step + 1, len(currents))
                break

            log.debug(
                'FAS sweep row %s step %d/%d starting SA FB servo',
                row, step + 1, len(currents))
            points = saFbServo(
                group=group, process=process, publish=publish_data)
            if not _pause_point(process, publish_data):
                log.debug(
                    'FAS sweep row %s stopped during SA FB servo at '
                    'step %d/%d', row, step + 1, len(currents))
                break
            log.debug(
                'FAS sweep row %s step %d/%d response=%s',
                row, step + 1, len(currents), np.asarray(points).tolist())
            for column, point in enumerate(points):
                if enabled_mask[column]:
                    data.curveList[column].addPoint(point)
            process._incrementSteps(1)
            log.debug(
                'FAS sweep row %s step %d/%d recorded',
                row, step + 1, len(currents))
            if not _pause_point(process, publish_data):
                break
    finally:
        log.debug(
            'FAS sweep row %s restoring board=%d address=%d to FasOff=%s uA',
            row, board, address, off_current)
        request = driver.manual_set(
            address=address, current=off_current, check_mode=False)
        log.debug('FAS sweep row %s FasOff restore result=%s', row, request)

    log.debug(
        'FAS sweep row %s complete: collectedPoints=%s',
        row, [len(curve.points) for curve in data.curveList])
    return data


def fasTune(*, group, process=None, doSet=True):
    """Tune the one-level FAS-on current for every active logical row.

    Active logical rows come from ``RowIndexOrderList`` and are resolved through
    ``RowMap``. Sweep points use ``RowDacDriver2.manual_set()``; persistent
    ``FasOn`` entries are optionally written only after every row sweep
    completes. A provisional SQ1 bias makes the FAS state observable before SQ1
    tuning; the original SQ1 force-current values are restored on exit.
    ``FasOff`` is never modified.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing the row mapping, row-DAC drivers, and SA readout.
    process : FasTuneProcess
        Required process supplying sweep/servo settings and partial-result
        publication.
    doSet : bool, default=True
        Program selected currents into persistent ``FasOn`` RAM after every row
        completes. When false, return and publish candidates without programming.

    Returns
    -------
    list[CurveData]
        One FAS sweep result per completed active row, in active-row order.
        Each successful result includes its selected physical ``fasOn`` value.

    Raises
    ------
    ValueError
        If no ``process`` is supplied.
    RuntimeError
        If timing is running, no rows or columns are enabled, a row mapping is
        invalid/two-level, ManualSet is unavailable, or a row produces no data.

    Notes
    -----
    All force-current overrides and row-board modes are snapshotted and restored
    on exit. Persistent ``FasOn`` programming is deferred until all sweeps
    succeed and is rolled back if Stop or an exception interrupts programming.
    """
    if process is None:
        raise ValueError('fasTune requires its FasTuneProcess')

    log = process._log
    log.debug('FAS tune entry: doSet=%s', doSet)
    # Manual row actuation is only deterministic while sequenced timing is off.
    tx = group.HardwareGroup.ColumnBoard[0].WarmTdmCore.Timing.TimingTx
    timing_running = tx.Running.get(read=True)
    log.debug('FAS tune timing Running=%s', timing_running)
    if timing_running:
        log.error('FAS tune rejected because timing is running')
        raise RuntimeError('FAS tuning requires timing to be stopped')

    row_map = group.RowMap.get()
    active_rows = [int(row) for row in group.RowIndexOrderList.get(read=True)]
    enabled_mask = np.asarray(group.ColTuneEnable.value(), dtype=bool)
    enabled_columns = np.flatnonzero(enabled_mask).tolist()
    log.debug(
        'FAS tune configuration: activeRows=%s enabledColumns=%s '
        'rowMapLength=%d', active_rows, enabled_columns, len(row_map))
    if not active_rows:
        log.error('FAS tune rejected because the active row list is empty')
        raise RuntimeError('FAS tuning requires at least one active row')
    if not enabled_columns:
        log.error('FAS tune rejected because no columns are enabled')
        raise RuntimeError('FAS tuning requires at least one enabled column')

    # Resolve logical rows once. The simple tuner intentionally rejects the
    # two-level chip-select mapping because it can drive only one physical line.
    targets = []
    drivers = {}
    for row in active_rows:
        if row < 0 or row >= len(row_map):
            raise RuntimeError(
                f'Active logical row {row} is outside RowMap length '
                f'{len(row_map)}')
        mapping = row_map[row]
        log.debug('FAS tune resolving logical row %d: %s', row, mapping)
        if 'csAddr' in mapping or 'csBoard' in mapping:
            log.error(
                'FAS tune rejected logical row %d two-level mapping: %s',
                row, mapping)
            raise RuntimeError(
                'The simple FAS tune supports one-level RowMap entries only')
        board = int(mapping['rsBoard'])
        address = int(mapping['rsAddr'])
        if address < 0 or address >= 32:
            raise RuntimeError(
                f'RowMap[{row}] rsAddr={address} is outside 0..31')
        try:
            driver = group.HardwareGroup.RowBoard[board].RowDacDriver
        except (KeyError, IndexError, AttributeError, TypeError) as exc:
            raise RuntimeError(
                f'RowMap[{row}] references unavailable row board {board}') from exc
        if not callable(getattr(driver, 'manual_set', None)):
            raise RuntimeError(
                f'RowBoard[{board}] firmware/software does not provide '
                'ManualSet')
        drivers[board] = driver
        targets.append((row, board, address, driver))
        log.debug(
            'FAS tune logical row %d resolved to board=%d address=%d',
            row, board, address)

    # Several logical rows may alias one physical line; preserve one snapshot
    # and later combine their candidates for each unique board/address pair.
    unique_targets = {}
    for _, board, address, driver in targets:
        unique_targets[(board, address)] = driver

    # Freeze settings for the run so a GUI edit cannot change the sweep midway.
    sweep_currents = np.linspace(
        process.FasFluxLowOffset.get(),
        process.FasFluxHighOffset.get(),
        process.FasFluxNumSteps.get(),
        endpoint=True)
    sweep_delay = process.FasFluxSampleDelay.get()
    minimum_tolerance = process.FasMinimumTolerance.get()

    # Launch all initial hardware reads together, then reconstruct the converted
    # currents from the refreshed shadows. These snapshots also drive cleanup.
    driver_items = list(drivers.items())
    board_count = len(driver_items)
    snapshots = warm_tdm_api.readAndCheck(
        group.SaFbForceCurrent,
        group.Sq1BiasForceCurrent,
        group.Sq1FbForceCurrent,
        group.SaFbCurrent,
        *(driver.Mode for _, driver in driver_items),
        *(driver.FasOn.Current for _, driver in driver_items),
        *(driver.FasOff.Current for _, driver in driver_items))
    (sa_fb_snapshot,
     sq1_bias_snapshot,
     sq1_fb_snapshot,
     sa_fb_table) = snapshots[:4]
    # Split the grouped result back into per-board lookup tables. Complete FAS
    # arrays replace repeated per-address reads inside the row loop.
    row_snapshots = snapshots[4:]
    mode_snapshot = dict(zip(
        drivers, row_snapshots[:board_count]))
    fas_on_tables = dict(zip(
        drivers, row_snapshots[board_count:2 * board_count]))
    fas_off_tables = dict(zip(
        drivers, row_snapshots[2 * board_count:]))
    fas_on_snapshot = {
        key: fas_on_tables[key[0]][key[1]]
        for key in unique_targets
    }
    log.debug(
        'FAS tune snapshots: modes=%s SaFbForceCurrent=%s '
        'Sq1BiasForceCurrent=%s Sq1FbForceCurrent=%s FasOn=%s',
        mode_snapshot, sa_fb_snapshot.tolist(), sq1_bias_snapshot.tolist(),
        sq1_fb_snapshot.tolist(), fas_on_snapshot)

    curves = []
    candidates = {}
    programming_started = False
    process.TotalSteps.set(len(active_rows) * len(sweep_currents))
    log.debug('FAS tune TotalSteps=%s', process.TotalSteps.value())

    try:
        # SQ1 must be biased for the simulated FAS response to be observable.
        # Preserve disabled columns while applying the bootstrap only to the
        # enabled force paths.
        bootstrap_bias = sq1_bias_snapshot.copy()
        bootstrap_fb = sq1_fb_snapshot.copy()
        bootstrap_bias[enabled_columns] = process.Sq1BiasCurrent.get()
        bootstrap_fb[enabled_columns] = 0.0
        log.debug(
            'FAS tune applying bootstrap SQ1 state to enabled columns: '
            'bias=%s feedback=%s',
            bootstrap_bias.tolist(), bootstrap_fb.tolist())
        warm_tdm_api.stageAndCommit(
            (group.Sq1FbForceCurrent, bootstrap_fb),
            (group.Sq1BiasForceCurrent, bootstrap_bias))

        # Every subsequent ManualSet assumes MANUAL mode. Stage all row-board
        # mode changes first and verify them in one grouped commit.
        for board, driver in drivers.items():
            log.debug('FAS tune setting RowBoard[%d] Mode=MANUAL', board)
        warm_tdm_api.stageAndCommit(*[
            (driver.Mode, 1) for driver in drivers.values()])

        for index, (row, board, address, _) in enumerate(targets):
            if not _pause_point(
                    process, lambda: process._publishResults(curves)):
                process.Message.set('Stopped by user; FasOn unchanged')
                return curves

            log.debug(
                'FAS tune starting logical row %d (%d/%d), board=%d '
                'address=%d',
                row, index + 1, len(targets), board, address)
            process.Message.set(
                f'FAS row {row} ({index + 1}/{len(targets)})')

            # Timing is stopped during FAS tuning, so the per-row SAFb RAM is
            # not driving the DAC. Explicitly copy this row's SA-tuned values
            # into the force-current path before starting the software servo.
            # Starting on the fitted SA branch avoids inheriting a stale or
            # railed override value from an earlier operation.
            row_sa_fb = sa_fb_snapshot.copy()
            for column in enabled_columns:
                row_sa_fb[column] = sa_fb_table[column, row]
            log.debug(
                'FAS tune logical row %d applying SA-tuned feedback to '
                'force-current path: %s', row, row_sa_fb.tolist())
            group.SaFbForceCurrent.set(row_sa_fb)

            curve = fasSweep(
                group=group,
                row=row,
                board=board,
                address=address,
                driver=drivers[board],
                enabled_mask=enabled_mask,
                off_current=fas_off_tables[board][address],
                currents=sweep_currents,
                delay=sweep_delay,
                process=process,
                publish=lambda data: process._publishResults(
                    curves + [data]))
            curves.append(curve)
            if not _pause_point(
                    process, lambda: process._publishResults(curves)):
                log.debug(
                    'FAS tune stopped after logical row %d; '
                    'leaving FasOn unchanged', row)
                process.Message.set('Stopped by user; FasOn unchanged')
                return curves

            # Select a minimum for each enabled column, then use the median so
            # one noisy or marginal column cannot dominate the physical line.
            minima = []
            for column in enabled_columns:
                points = curve.curveList[column].points
                if points:
                    minimum, low, high, minimum_value = _fas_minimum_center(
                        curve.xValues, points, minimum_tolerance)
                    minima.append(minimum)
                    log.debug(
                        'FAS tune row %d column %d minimum-region center=%s '
                        'uA indices=%d..%d x=%s..%s uA minimum=%s uA '
                        'tolerance=%s uA from %d point(s)',
                        row, column, minimum, low, high,
                        curve.xValues[low], curve.xValues[high],
                        minimum_value, minimum_tolerance, len(points))
            if not minima:
                log.error(
                    'FAS tune logical row %d produced no enabled-column '
                    'samples', row)
                raise RuntimeError(
                    f'No FAS samples were collected for logical row {row}')
            row_candidate = float(np.median(minima))
            candidates.setdefault((board, address), []).append(row_candidate)
            log.debug(
                'FAS tune row %d candidate=%s uA from minima=%s',
                row, row_candidate, np.asarray(minima).tolist())

        # Collapse aliased logical-row candidates to one programmed current per
        # physical board/address pair.
        selected = {
            key: float(np.median(values))
            for key, values in candidates.items()
        }
        log.debug(
            'FAS tune physical-line candidates=%s selected=%s',
            candidates, selected)

        for curve in curves:
            curve.fasOn = selected[(curve.board, curve.address)]

        if not _pause_point(
                process, lambda: process._publishResults(curves)):
            log.debug('FAS tune stopped before FasOn programming')
            process.Message.set('Stopped by user; FasOn unchanged')
            return curves

        if not doSet:
            log.debug(
                'FAS tune SetAfterFinish is disabled; leaving FasOn unchanged '
                'and publishing candidates=%s', selected)
            return curves

        # Defer all persistent writes until acquisition and fitting succeed,
        # then stage every selected FasOn entry before one grouped commit.
        programming_started = True
        for key, current in selected.items():
            log.debug(
                'FAS tune staging RowBoard[%d] FasOn[%d]=%s uA',
                key[0], key[1], current)
        warm_tdm_api.stageAndCommit(*[
            (unique_targets[key].FasOn.Current, current, key[1])
            for key, current in selected.items()
        ])

        # Catch Stop arriving during the grouped register transaction. A Pause
        # waits here and resumes without rolling back the completed write.
        if not _pause_point(
                process, lambda: process._publishResults(curves)):
            log.debug(
                'FAS tune rolling back FasOn after Stop: snapshot=%s',
                fas_on_snapshot)
            for key, original in fas_on_snapshot.items():
                log.debug(
                    'FAS tune staging rollback RowBoard[%d] FasOn[%d]=%s uA',
                    key[0], key[1], original)
            warm_tdm_api.stageAndCommit(*[
                (unique_targets[key].FasOn.Current, original, key[1])
                for key, original in fas_on_snapshot.items()
            ])
            programming_started = False
            process.Message.set('Stopped by user; FasOn unchanged')
            return curves

        log.debug('FAS tune programming complete: selected=%s', selected)
        process.Message.set('FAS tune complete')
        return curves

    except Exception:
        log.exception('FAS tune failed')
        if programming_started:
            log.debug(
                'FAS tune rolling back FasOn after failure: snapshot=%s',
                fas_on_snapshot)
            for key, current in fas_on_snapshot.items():
                log.debug(
                    'FAS tune staging rollback RowBoard[%d] FasOn[%d]=%s uA',
                    key[0], key[1], current)
            warm_tdm_api.stageAndCommit(*[
                (unique_targets[key].FasOn.Current, current, key[1])
                for key, current in fas_on_snapshot.items()
            ])
        raise
    finally:
        # Manual outputs and force-current overrides are temporary measurement
        # state. Restore them even when fitting or persistent programming fails.
        log.debug('FAS tune cleanup starting')
        for key, driver in unique_targets.items():
            try:
                off_current = fas_off_tables[key[0]][key[1]]
                log.debug(
                    'FAS tune cleanup RowBoard[%d] address=%d '
                    'ManualSet FasOff=%s uA',
                    key[0], key[1], off_current)
                request = driver.manual_set(
                    address=key[1], current=off_current, check_mode=False)
                log.debug(
                    'FAS tune cleanup RowBoard[%d] address=%d result=%s',
                    key[0], key[1], request)
            except Exception as exc:
                log.error(
                    'Failed to return row board %s address %s to FasOff: %s',
                    key[0], key[1], exc)
        log.debug(
            'FAS tune restoring force currents as one transaction group: '
            'SaFb=%s Sq1Bias=%s Sq1Fb=%s',
            sa_fb_snapshot.tolist(), sq1_bias_snapshot.tolist(),
            sq1_fb_snapshot.tolist())
        for board, mode in mode_snapshot.items():
            log.debug(
                'FAS tune staging RowBoard[%d] Mode=%s', board, mode)
        warm_tdm_api.stageAndCommit(
            (group.SaFbForceCurrent, sa_fb_snapshot),
            (group.Sq1BiasForceCurrent, sq1_bias_snapshot),
            (group.Sq1FbForceCurrent, sq1_fb_snapshot),
            *[(drivers[board].Mode, mode)
              for board, mode in mode_snapshot.items()])
        log.debug('FAS tune cleanup complete')
