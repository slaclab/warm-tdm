# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Integer reciprocal calculation, full-range bound and host write ordering."""
from types import SimpleNamespace
from unittest.mock import Mock
import time
import numbers

import numpy as np
import pytest

from software.tests.test_fp_pid_controls import functions, Register

config = functions('firmware/python/warm_tdm/_AdcDsp.py',
                   ('flux_reciprocal_registers',), {'numbers': numbers})


def test_all_quanta_normalize_to_the_existing_multiplier():
    assert config.flux_reciprocal_registers(0) == (0, 0)
    for q in range(1, 8192):
        registers = config.flux_reciprocal_registers(q)
        r, shift = registers
        assert 65536 <= r <= 131071 and 16 <= shift <= 29
        assert r*q <= 1 << shift < (r+1)*q
        assert config.flux_reciprocal_registers(np.int64(q)) == registers


def test_one_correction_suffices_across_the_full_candidate_range():
    # For a fixed exact quotient the underestimate is largest at its lower
    # endpoint. Check every quotient interval for every supported quantum, including
    # the candidate bound; this is millions of probes without a float oracle.
    maximum_error = maximum_residual = 0
    for q in range(1, 8192):
        registers = config.flux_reciprocal_registers(q)
        r, shift = registers
        exact_edges = np.arange(0, 270666, q, dtype=np.int64)
        # Also probe just before each estimated-quotient transition: those
        # and the final endpoint bound the uncorrected residual sawtooth.
        h = np.arange(1, ((270665*r) >> shift)+1, dtype=np.int64)
        estimate_edges = ((h*(1 << shift)+r-1)//r)-1
        m = np.concatenate((exact_edges, estimate_edges, [270665]))
        n = ((m*r) >> shift) + 1
        exact = m//q + 1
        error = exact-n
        assert error.min() == 0 or error.min() == 1
        maximum_error = max(maximum_error, int(error.max()))
        assert error.max() <= 1
        # An integer candidate maximizes local feedback in each fractional interval.
        local = 7862 + m + 1 - n*q
        corrected = local - np.where(local > 7862, q, 0)
        assert (np.abs(corrected) <= 7862).all()
        assert (n + (local > 7862) == exact).all()
        maximum_residual = max(maximum_residual, int(local.max()))
    assert maximum_error == 1
    assert maximum_residual <= 7867


@pytest.mark.parametrize('q', [-1, 8192, 1.5, True, float('inf'), float('nan')])
def test_invalid_quantum_cannot_produce_a_register_word(q):
    with pytest.raises(ValueError):
        config.flux_reciprocal_registers(q)


def driver():
    events = []
    dev = SimpleNamespace()
    for name in ('PidEnableRaw', 'ControlBusy', 'FluxReciprocalRaw', 'FluxReciprocalShift', 'FluxQuantumRaw'):
        setattr(dev, name, Register(0, name, events))
    fn = functions('firmware/python/warm_tdm/_AdcDsp.py', ('_setFluxQuantumRegisters',),
                   {'self': dev, 'time': time,
                    'flux_reciprocal_registers': config.flux_reciprocal_registers})
    return dev, fn._setFluxQuantumRegisters, events


def test_software_programs_all_wrap_registers():
    dev, setter, events = driver()
    for q in (1239, 1, 8191, 0):
        setter(q, True)
        inverse, shift = config.flux_reciprocal_registers(q)
        assert events[-3:] == [('FluxReciprocalRaw', inverse, True),
                              ('FluxReciprocalShift', shift, True),
                              ('FluxQuantumRaw', q, True)]


@pytest.mark.parametrize('busy', ['PidEnableRaw', 'ControlBusy'])
def test_busy_controller_cannot_be_partially_configured(busy):
    dev, setter, events = driver()
    getattr(dev, busy).data = True
    with pytest.raises(RuntimeError, match='Disable PID'):
        setter(1239, True)
    assert not events
    dev.PidEnableRaw.get.reset_mock()
    dev.ControlBusy.get.reset_mock()
    setter(1239, False)
    inverse, shift = config.flux_reciprocal_registers(1239)
    assert events == [('FluxReciprocalRaw', inverse, False),
                      ('FluxReciprocalShift', shift, False),
                      ('FluxQuantumRaw', 1239, False)]
    dev.PidEnableRaw.get.assert_not_called()
    dev.ControlBusy.get.assert_not_called()


def test_state_clear_is_waited_for_but_cannot_hang_the_driver():
    dev, setter, events = driver()
    dev.ControlBusy.get.side_effect = [False, True, True, False]
    setter(1239, True)
    assert len(events) == 3
    fake_time = SimpleNamespace(monotonic=Mock(side_effect=[0, 2]), sleep=Mock())
    fn = functions('firmware/python/warm_tdm/_AdcDsp.py', ('_setFluxQuantumRegisters',),
                   {'self': dev, 'time': fake_time,
                    'flux_reciprocal_registers': config.flux_reciprocal_registers})
    dev.ControlBusy.get.side_effect = [False, True]
    with pytest.raises(TimeoutError):
        fn._setFluxQuantumRegisters(1239, True)
