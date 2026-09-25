# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.

"""Stopped-timing RS/CS discovery, refinement, and shared-line verification.

The response convention is the same as one-level FAS tuning: an on state
minimizes nulled SA feedback. Off currents must already provide isolation.
All candidate currents remain temporary until final pair measurements pass.
"""

import copy
import sys
import time

import numpy as np

import warm_tdm_api

import warm_tdm_api.tuning as tuning


class _Stopped(Exception):
    """Internal cooperative Stop; partial results are retained."""


def _grid_seed(responses, rs_values, cs_values, tolerance, minimum_response):
    """Choose a measured point in one connected response-minimum region.

    Subtract each column's offset before taking the median. Restrict centering
    to the component containing the sampled minimum so separate periodic minima
    are never averaged into an unmeasured, potentially closed pair.
    """
    responses = np.asarray(responses, dtype=float)
    if not np.all(np.isfinite(responses)):
        raise RuntimeError('FAS discovery contains non-finite or missing samples')
    score = np.median(
        responses - responses.min(axis=(1, 2), keepdims=True), axis=0)
    start = tuple(int(i) for i in np.unravel_index(np.argmin(score), score.shape))
    limit = score[start] + tolerance
    component = {start}
    pending = [start]
    while pending:
        i, j = pending.pop()
        for adjacent in ((i-1, j), (i+1, j), (i, j-1), (i, j+1)):
            a, b = adjacent
            if (0 <= a < score.shape[0] and 0 <= b < score.shape[1]
                    and adjacent not in component and score[adjacent] <= limit):
                component.add(adjacent)
                pending.append(adjacent)
    points = np.array(sorted(component))
    center = np.median(points, axis=0)
    i, j = (int(x) for x in points[
        np.argmin(np.sum((points - center)**2, axis=1))])
    # A response to just one axis cannot establish a two-level operating pair.
    if (np.any(np.ptp(responses[:, i, :], axis=1) <= minimum_response)
            or np.any(np.ptp(responses[:, :, j], axis=1) <= minimum_response)):
        raise RuntimeError(
            'FAS discovery found no resolved response on both RS and CS; '
            'check the sweep range/resolution, off currents, SQ1 bias, and '
            'enabled columns')
    return float(rs_values[j]), float(cs_values[i])


class _TwoLevelTune:
    def __init__(self, group, process):
        self.group = group
        self.process = process
        self.log = process._log
        self.tx = group.HardwareGroup.ColumnBoard[0].WarmTdmCore.Timing.TimingTx
        self.rows = [int(row) for row in group.RowReadoutOrder.get(read=True)]
        self.mask = np.array(group.colEnableBools, dtype=bool, copy=True)
        self.columns = np.flatnonzero(self.mask)
        self.delay = float(process.FasFluxSampleDelay.get())
        self.tolerance = float(process.FasMinimumTolerance.get())
        self.minimum_response = float(process.FasMinimumResponse.get())
        self.isolation_tolerance = float(process.FasIsolationTolerance.get())
        self.bias = float(process.Sq1BiasCurrent.get())
        for name, value, positive in (
                ('FasFluxSampleDelay', self.delay, True),
                ('FasMinimumTolerance', self.tolerance, False),
                ('FasMinimumResponse', self.minimum_response, True),
                ('FasIsolationTolerance', self.isolation_tolerance, False)):
            if not np.isfinite(value) or (value <= 0 if positive else value < 0):
                raise ValueError(f'{name} must be finite and '
                                 f'{"positive" if positive else "nonnegative"}')
        if not np.isfinite(self.bias):
            raise ValueError('Sq1BiasCurrent must be finite')
        self.axes = {
            'RS': self._axis(process.FasFluxLowOffset.get(),
                             process.FasFluxHighOffset.get(),
                             process.FasFluxNumSteps.get()),
            'CS': self._axis(process.CsFluxLowOffset.get(),
                             process.CsFluxHighOffset.get(),
                             process.CsFluxNumSteps.get()),
        }
        discovery_steps = int(process.DiscoveryNumSteps.get())
        if discovery_steps < 3:
            raise ValueError('DiscoveryNumSteps must be at least 3')
        self.grid_axes = {axis: np.linspace(values[0], values[-1], discovery_steps)
                          for axis, values in self.axes.items()}
        self.curves = []
        self.discovery = []
        self.validation = []
        self.drivers = {}
        self.lines = {}
        self.mapping = []
        for row, mapping in enumerate(copy.deepcopy(group.RowMap.get())):
            pair = {'RS': self._line(mapping, row, 'rs')}
            if 'csBoard' in mapping or 'csAddr' in mapping:
                pair['CS'] = self._line(mapping, row, 'cs')
            self.mapping.append(pair)
        if not self.rows or not self.columns.size:
            raise RuntimeError('FAS tuning requires active rows and columns')
        for row in self.rows:
            if row < 0 or row >= len(self.mapping):
                raise RuntimeError(f'Active logical row {row} is outside RowMap')
            if 'CS' not in self.mapping[row]:
                raise RuntimeError(
                    'Run one-level and two-level logical rows separately')
        self.on = {board: np.array(driver.FasOn.Current.get(), copy=True)
                   for board, driver in self.drivers.items()}
        self.off = {board: np.array(driver.FasOff.Current.get(), copy=True)
                    for board, driver in self.drivers.items()}
        for key in self.lines:
            if not np.isfinite(self._current(self.off, key)):
                raise ValueError(f'Non-finite FasOff current for {key}')
        self.modes = {board: driver.Mode.get(read=True)
                      for board, driver in self.drivers.items()}
        self.force = {name: np.array(getattr(group, name).get(), copy=True)
                      for name in ('SaFbForceCurrent', 'Sq1BiasForceCurrent',
                                   'Sq1FbForceCurrent')}
        self.sa_fb = np.array(group.SaFbCurrent.get(), copy=True)
        self.started_boards = []
        self.forces_started = False
        self.selected = {}
        self.written = []

    @staticmethod
    def _axis(low, high, steps):
        if not np.isfinite(low) or not np.isfinite(high) or high <= low or steps < 3:
            raise ValueError('Two-level FAS axes require finite low < high and >=3 steps')
        return np.linspace(low, high, int(steps))

    def _line(self, mapping, row, prefix):
        try:
            key = (int(mapping[prefix + 'Board']), int(mapping[prefix + 'Addr']))
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f'RowMap[{row}] needs both {prefix}Board and {prefix}Addr') from exc
        board, address = key
        if not 0 <= board <= 3 or not 0 <= address < 32:
            raise RuntimeError(f'Invalid physical {prefix} address {key} in RowMap[{row}]')
        if key in self.lines and self.lines[key] != prefix:
            raise RuntimeError(f'Physical FAS line {key} is used as both RS and CS')
        try:
            driver = self.group.HardwareGroup.RowBoard[board].RowDacDriver
        except (KeyError, IndexError, AttributeError) as exc:
            raise RuntimeError(f'RowMap references unavailable row board {board}') from exc
        if not callable(getattr(driver, 'manual_set', None)):
            raise RuntimeError(f'RowBoard[{board}] does not provide ManualSet')
        self.drivers[board] = driver
        self.lines[key] = prefix
        return key

    @staticmethod
    def _current(tables, key):
        return float(tables[key[0]][key[1]])

    def _publish(self):
        self.process._publishResults(self.curves)
        self.process.FasDiscoveryOutput.set(copy.deepcopy(self.discovery))
        self.process.FasValidationOutput.set(copy.deepcopy(self.validation))

    def _checkpoint(self):
        if not tuning._pause_point(self.process, self._publish):
            raise _Stopped()

    def _drive(self, key, current):
        request = self.drivers[key[0]].manual_set(
            address=key[1], current=current, check_mode=False)
        self.log.debug('FAS ManualSet board=%d address=%d requested=%s result=%s',
                       key[0], key[1], current, request)
        # ManualSet has one pending slot and no completion acknowledgement.
        # Space even cleanup writes before issuing the next physical request or
        # changing mode. The caller controls this hardware-dependent delay.
        deadline = time.monotonic() + self.delay
        while time.monotonic() < deadline:
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            # Stop must not wait out a long analog settling delay. Even on
            # Stop, leave a scheduling interval between physical requests.
            if not self.process._runEn:
                break

    def _all_off(self):
        errors = []
        # Disable chip paths first, including lines belonging to inactive rows.
        for key in sorted(self.lines, key=lambda key: (self.lines[key] != 'cs', key)):
            if key[0] not in self.started_boards:
                continue
            try:
                self._drive(key, self._current(self.off, key))
            except Exception as exc:
                self.log.exception('Failed to return FAS line %s to FasOff', key)
                errors.append(exc)
        if errors:
            raise errors[0]

    def _pair_off(self, pair):
        original_error = sys.exc_info()[1]
        errors = []
        for axis in ('CS', 'RS'):
            key = pair[axis]
            try:
                self._drive(key, self._current(self.off, key))
            except Exception as exc:
                self.log.exception('Failed to turn off %s %s', axis, key)
                errors.append(exc)
        if errors and (original_error is None or isinstance(original_error, _Stopped)):
            raise errors[0]

    def _seed_sa(self, row):
        value = self.force['SaFbForceCurrent'].copy()
        value[self.columns] = self.sa_fb[self.columns, row]
        self.group.SaFbForceCurrent.set(value)

    def _measure(self):
        self._checkpoint()
        if self.tx.Running.get(read=True):
            raise RuntimeError('Timing started during FAS tuning')
        values = np.array(tuning.saFbServo(
            group=self.group, process=self.process, publish=self._publish,
            require_convergence=True), copy=True)
        self._checkpoint()
        if not np.all(np.isfinite(values[self.columns])):
            raise RuntimeError('Non-finite FAS servo response')
        self.process._incrementSteps(1)
        return values

    def _discover(self, row):
        pair = self.mapping[row]
        rs, cs = self.grid_axes['RS'], self.grid_axes['CS']
        record = dict(logicalRow=row, rsBoard=pair['RS'][0], rsAddress=pair['RS'][1],
                      csBoard=pair['CS'][0], csAddress=pair['CS'][1],
                      rsValues=rs.copy(), csValues=cs.copy(), rsOn=None, csOn=None,
                      responses=np.full((len(self.mask), len(cs), len(rs)), np.nan))
        self.discovery.append(record)
        self.process.Message.set(f'FAS discovery row {row}: RS x CS')
        try:
            for i, cs_current in enumerate(cs):
                self._checkpoint()
                self._drive(pair['CS'], cs_current)
                # Reset the servo seed at each grid line to limit path history.
                self._seed_sa(row)
                for j, rs_current in enumerate(rs):
                    self._checkpoint()
                    self._drive(pair['RS'], rs_current)
                    values = self._measure()
                    record['responses'][self.columns, i, j] = values[self.columns]
            rs_on, cs_on = _grid_seed(
                record['responses'][self.columns], rs, cs,
                self.tolerance, self.minimum_response)
            record.update(rsOn=rs_on, csOn=cs_on)
            self.log.debug('FAS row %d bootstrap RS=%s CS=%s uA', row, rs_on, cs_on)
            return {'RS': rs_on, 'CS': cs_on}
        finally:
            self._pair_off(pair)

    def _sweep(self, row, axis, companion_current):
        pair = self.mapping[row]
        other = 'CS' if axis == 'RS' else 'RS'
        key, companion = pair[axis], pair[other]
        data = warm_tdm_api.CurveData(xValues=self.axes[axis])
        for col in range(len(self.mask)):
            data.addCurve(warm_tdm_api.Curve(col))
        data.logicalRow, data.board, data.address = row, *key
        data.select = axis
        data.companionBoard, data.companionAddress = companion
        data.companionCurrent = companion_current
        data.fasOn = None
        data.rowFasOn = None
        self.curves.append(data)
        self.process.Message.set(f'FAS {axis} sweep row {row}')
        self._seed_sa(row)
        try:
            self._drive(companion, companion_current)
            for current in self.axes[axis]:
                self._checkpoint()
                self._drive(key, current)
                values = self._measure()
                for col in self.columns:
                    data.curveList[col].addPoint(values[col])
            minima = []
            for col in self.columns:
                points = data.curveList[col].points
                if np.ptp(points) <= self.minimum_response:
                    raise RuntimeError(f'No resolved {axis} response for row {row}, column {col}')
                minima.append(tuning._fas_minimum_center(
                    data.xValues, points, self.tolerance)[0])
            data.rowFasOn = float(np.median(minima))
            return data.rowFasOn
        finally:
            self._pair_off(pair)

    def _verify(self, row):
        pair = self.mapping[row]
        on = {axis: self.selected[key] for axis, key in pair.items()}
        record = dict(logicalRow=row, rsOn=on['RS'], csOn=on['CS'],
                      rsBoard=pair['RS'][0], rsAddress=pair['RS'][1],
                      csBoard=pair['CS'][0], csAddress=pair['CS'][1],
                      responses={}, passed=False)
        self.validation.append(record)
        self.process.Message.set(f'FAS shared-setting verification row {row}')
        try:
            # Consecutive observations differ in only one switch state.
            for label, rs_active, cs_active in (
                    ('offOff', False, False), ('onOff', True, False),
                    ('onOn', True, True), ('offOn', False, True)):
                self._checkpoint()
                for axis, active in (('RS', rs_active), ('CS', cs_active)):
                    self._drive(pair[axis], on[axis] if active else
                                self._current(self.off, pair[axis]))
                self._seed_sa(row)
                values = self._measure()
                values[~self.mask] = np.nan
                record['responses'][label] = values
            off = np.array([record['responses'][label][self.columns]
                            for label in ('offOff', 'onOff', 'offOn')])
            active = record['responses']['onOn'][self.columns]
            if np.any(np.ptp(off, axis=0) > self.isolation_tolerance):
                raise RuntimeError(f'FAS row {row} failed off-state isolation')
            if np.any(np.min(off, axis=0) - active <= self.minimum_response):
                raise RuntimeError(
                    f'FAS row {row} has insufficient on-state response with shared currents')
            record['passed'] = True
        except Exception as exc:
            record['error'] = str(exc)
            raise
        finally:
            self._pair_off(pair)

    def _restore_forces(self):
        if not self.forces_started:
            return
        errors = []
        for name, value in self.force.items():
            try:
                getattr(self.group, name).set(value)
            except Exception as exc:
                self.log.exception('Failed to restore %s', name)
                errors.append(exc)
        if errors:
            raise errors[0]

    def _cleanup(self):
        original_error = sys.exc_info()[1]
        errors = []
        for action in (self._all_off, self._restore_forces):
            try:
                action()
            except Exception as exc:
                errors.append(exc)
        if errors and (original_error is None or isinstance(original_error, _Stopped)):
            raise errors[0]

    def _timing_mode(self):
        if self.tx.Running.get(read=True):
            raise RuntimeError('Timing started before FAS programming')
        for driver in self.drivers.values():
            driver.Mode.setDisp('TIMING')
            if int(driver.Mode.get(read=True)) != 0:
                raise RuntimeError('Could not suppress FasOn write-through')

    def _restore_modes(self):
        original_error = sys.exc_info()[1]
        errors = []
        for board in self.started_boards:
            try:
                self.drivers[board].Mode.set(self.modes[board])
            except Exception as exc:
                self.log.exception('Failed to restore RowBoard[%d] mode', board)
                errors.append(exc)
        if errors and (original_error is None or isinstance(original_error, _Stopped)):
            raise errors[0]

    def _rollback(self):
        errors = []
        try:
            self._timing_mode()
            for key in self.written:
                try:
                    self.drivers[key[0]].FasOn.Current.set(
                        self._current(self.on, key), index=key[1])
                except Exception as exc:
                    self.log.exception('Failed to roll back FasOn %s', key)
                    errors.append(exc)
            if errors:
                raise errors[0]
        finally:
            self._restore_modes()

    def _acquire(self):
        self._checkpoint()
        if self.tx.Running.get(read=True):
            raise RuntimeError('FAS tuning requires timing to be stopped')
        for board, driver in self.drivers.items():
            self.started_boards.append(board)
            driver.Mode.setDisp('MANUAL')
            if int(driver.Mode.get(read=True)) != 1:
                raise RuntimeError(f'Could not set RowBoard[{board}] to MANUAL')
        self._all_off()
        self._checkpoint()
        self.forces_started = True
        for name, value in (('Sq1BiasForceCurrent', self.bias),
                            ('Sq1FbForceCurrent', 0.0)):
            currents = self.force[name].copy()
            currents[self.columns] = value
            getattr(self.group, name).set(currents)
        candidates = {}
        for row in self.rows:
            self._checkpoint()
            pair = self.mapping[row]
            seed = self._discover(row)
            for axis in ('RS', 'CS'):
                other = 'CS' if axis == 'RS' else 'RS'
                seed[axis] = self._sweep(row, axis, seed[other])
                candidates.setdefault(pair[axis], []).append(seed[axis])
        self.selected = {key: float(np.median(values))
                         for key, values in candidates.items()}
        self.log.debug('FAS shared physical candidates: %s', self.selected)
        for row in self.rows:
            self._verify(row)
        for curve in self.curves:
            curve.fasOn = self.selected[(curve.board, curve.address)]
        self._checkpoint()

    def run(self, do_set):
        count = (len(self.grid_axes['RS']) * len(self.grid_axes['CS'])
                 + sum(len(values) for values in self.axes.values()) + 4)
        self.process.TotalSteps.set(len(self.rows) * count)
        self.log.info('Two-level FAS tune: rows=%s columns=%s measurements=%d',
                      self.rows, self.columns.tolist(), len(self.rows) * count)
        self._publish()
        try:
            try:
                try:
                    self._acquire()
                finally:
                    # Restore measured outputs/forces before persistent writes.
                    self._cleanup()
                if do_set:
                    # Suppress FasOn write-through so programming multiple
                    # lines cannot turn them all on together.
                    self._timing_mode()
                    for key, current in self.selected.items():
                        self._checkpoint()
                        self.written.append(key)  # Include a partially failing write.
                        self.drivers[key[0]].FasOn.Current.set(current, index=key[1])
            finally:
                self._restore_modes()
            # Include Stop arriving during the final mode restoration in the
            # programming transaction. Rollback also suppresses write-through.
            self._checkpoint()
            self.process.Message.set('FAS tune complete' if do_set else
                                     'FAS candidates verified; FasOn unchanged')
        except _Stopped:
            if self.written:
                self._rollback()
            self.process.Message.set('Stopped by user; FasOn unchanged')
        except BaseException:
            if self.written:
                try:
                    self._rollback()
                except Exception:
                    self.log.exception('FAS programming rollback incomplete')
            raise
        finally:
            self._publish()
        return self.curves


def fasTuneTwoLevel(*, group, process, doSet):
    """Discover and refine two-level maps without changing logical addressing."""
    return _TwoLevelTune(group, process).run(doSet)
