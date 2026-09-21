# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""FP period configuration and integer/FP PID controls with fake register I/O."""
import ast
import importlib.util
import logging
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_pure(path):
    spec = importlib.util.spec_from_file_location('fp_config', ROOT/path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


config = load_pure('firmware/python/warm_tdm/_PidFpConfig.py')


def functions(path, names, env):
    tree = ast.parse((ROOT/path).read_text())
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
    for n in nodes:
        n.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), env)
    assert all(name in env for name in names)
    return SimpleNamespace(**{name: env[name] for name in names})


class Register:
    def __init__(self, value=0, name='', events=None):
        self.data = value
        self.get = Mock(side_effect=lambda read=True: self.data)
        self.value = lambda: self.data
        self.name = name
        self.events = events if events is not None else []
        self.set = Mock(side_effect=self.store)

    def store(self, value, write=True):
        self.data = value
        self.events.append((self.name, value, write))


def driver(slope=-.125):
    events = []
    dev = SimpleNamespace(amp=SimpleNamespace(currentPerLsb=lambda: slope), ClearPidState=Mock())
    for name, value in (
            ('PidEnableRaw', False), ('ControlBusy', False), ('DacWriteBusy', False),
            ('WrapMultiplierRaw', 1), ('FluxQuantumFpRaw', 0),
            ('InvFluxQuantumFpRaw', 0), ('PhysicalFluxQuantumDac', 0)):
        setattr(dev, name, Register(value, name, events))
    fn = functions('firmware/python/warm_tdm/_AdcDspFp.py',
                   ('_configureFluxQuantum', '_setFluxQuantum', '_getFluxQuantum',
                    '_setWrapMultiplier', '_setCoef', '_enablePid'),
                   {'self': dev, 'warm_tdm': config})
    return dev, fn, events


@pytest.mark.parametrize('slope', [.125, -.125])
def test_fractional_period_zero_and_multiplier_are_coherent(slope):
    dev, fn, events = driver(slope)
    fn._setFluxQuantum(125.03125, True)
    assert dev.FluxQuantumFpRaw.data == 1000.25
    assert dev.InvFluxQuantumFpRaw.data == config.float32(1/1000.25)
    assert fn._getFluxQuantum(True) == 125.03125
    fn._setWrapMultiplier(8, True)
    assert dev.FluxQuantumFpRaw.data == 8002
    assert dev.InvFluxQuantumFpRaw.data == config.float32(1/8002)
    assert fn._getFluxQuantum(True) == 125.03125
    fn._setFluxQuantum(0, True)
    assert dev.FluxQuantumFpRaw.data == dev.InvFluxQuantumFpRaw.data == 0
    assert fn._getFluxQuantum(True) == 0
    assert dev.WrapMultiplierRaw.data == 8
    assert events[-4:-2] == [('FluxQuantumFpRaw', 0, True), ('InvFluxQuantumFpRaw', 0, True)]


def test_reciprocal_uses_the_stored_float32_period():
    q, period, reciprocal = config.flux_period_registers(.123456789, .001, 7)
    assert period == config.float32(q*7)
    assert reciprocal == config.float32(1/period)
    assert config.flux_period_registers(2000, .125, 1)[1] == 16000


@pytest.mark.parametrize('value', [-1, math.nan, math.inf, 1e-50, 1e10])
def test_invalid_quantum_does_not_partially_write(value):
    dev, fn, events = driver()
    with pytest.raises(ValueError):
        fn._setFluxQuantum(value, True)
    assert not events


@pytest.mark.parametrize('value', [0, -1, 1.5, True, math.inf, 100])
def test_invalid_multiplier_does_not_change_hardware_or_interpretation(value):
    dev, fn, events = driver()
    fn._setFluxQuantum(125, True)
    events.clear()
    with pytest.raises(ValueError):
        fn._setWrapMultiplier(value, True)
    assert not events
    assert dev.WrapMultiplierRaw.data == 1
    assert fn._getFluxQuantum(True) == 125


@pytest.mark.parametrize('slope', [0, math.nan, math.inf])
def test_invalid_amplifier_calibration_is_rejected(slope):
    dev, fn, events = driver(slope)
    with pytest.raises(ValueError):
        fn._setFluxQuantum(1, True)
    assert not events


@pytest.mark.parametrize('busy', ['PidEnableRaw', 'ControlBusy', 'DacWriteBusy'])
def test_period_writes_require_disabled_drained_controller(busy):
    dev, fn, events = driver()
    getattr(dev, busy).data = True
    with pytest.raises(RuntimeError, match='Disable PID'):
        fn._setFluxQuantum(125, True)
    assert not events
    # Cache-only staging still computes both halves, without hardware status reads.
    for name in ('PidEnableRaw', 'ControlBusy', 'DacWriteBusy'):
        getattr(dev, name).get.reset_mock()
    fn._setFluxQuantum(125, False)
    assert events[:2] == [('FluxQuantumFpRaw', 1000, False), ('InvFluxQuantumFpRaw', config.float32(.001), False)]
    for name in ('PidEnableRaw', 'ControlBusy', 'DacWriteBusy'):
        getattr(dev, name).get.assert_not_called()


def test_gain_and_disable_setters_do_not_full_clear_feedback():
    dev, fn, events = driver()
    coef = Register()
    fn._setCoef(coef, .125, True)
    fn._setCoef(coef, .125, True)
    fn._enablePid(False, True)
    dev.ClearPidState.assert_not_called()
    for value in (math.nan, math.inf, 1e100):
        with pytest.raises(ValueError):
            fn._setCoef(coef, value, True)
    assert coef.set.call_count == 2


def test_integer_i_link_and_enable_leave_state_lifecycle_to_hardware():
    path = 'firmware/python/warm_tdm/_AdcDsp.py'
    dev = SimpleNamespace(I_CoefRaw=Register(), PidEnableRaw=Register(),
                          ClearPidState=Mock())
    env = {'self': dev}
    fn = functions(path, ('_setCoef', '_enablePid'), env)
    # Exercise the actual I_Coef callback wiring, not just its helper: the old
    # link passed clearState=True and unconditionally forced a full reset.
    tree = ast.parse((ROOT/path).read_text())
    call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and
                any(k.arg == 'name' and isinstance(k.value, ast.Constant) and
                    k.value.value == 'I_Coef' for k in n.keywords))
    setter = next(k.value for k in call.keywords if k.arg == 'linkedSet')
    set_i = eval(compile(ast.Expression(setter), path, 'eval'), env)
    for value, write in ((.125, True), (.125, True), (0, True), (-.25, False)):
        set_i(value, write)
        dev.I_CoefRaw.set.assert_called_with(value, write=write)
    for value, write in ((False, True), (True, True), (True, True), (False, False)):
        fn._enablePid(value, write)
        dev.PidEnableRaw.set.assert_called_with(value, write=write)
    dev.ClearPidState.assert_not_called()


def session(fp=True):
    group = SimpleNamespace(PidP_Gain=SimpleNamespace(set=Mock()),
                            PidI_Gain=SimpleNamespace(set=Mock()))
    if not fp:
        group.PidD_Gain = SimpleNamespace(set=Mock())
    boards = {i: SimpleNamespace(DataPath=SimpleNamespace(AdcDsp={
        j: SimpleNamespace(PidDebugEnable=SimpleNamespace(set=Mock())) for j in range(8)}))
        for i in range(2)}
    dev = SimpleNamespace(group=group, cbs=boards,
                          col_enable_bools=lambda: [i in (1, 9) for i in range(16)],
                          col_to_board_chan=lambda col: divmod(col, 8))
    fn = functions('software/python/warm_tdm_api/operations/session/_setup.py',
                   ('set_pid',), {'math': math, 'log': logging.getLogger('test')}).set_pid
    return dev, lambda **kwargs: fn(dev, **kwargs)


@pytest.mark.parametrize('d', [None, 0, -0.0])
def test_fp_pi_and_debug_target_selected_boards(d):
    dev, set_pid = session()
    set_pid(p=.05, i=.001, d=d, debug=True)
    assert [call.kwargs for call in dev.group.PidP_Gain.set.call_args_list] == [
        {'value': .05, 'index': 1}, {'value': .05, 'index': 9}]
    for board in (0, 1):
        dev.cbs[board].DataPath.AdcDsp[1].PidDebugEnable.set.assert_called_once_with(True)
        dev.cbs[board].DataPath.AdcDsp[0].PidDebugEnable.set.assert_not_called()


def test_unsupported_d_and_invalid_requests_fail_before_any_gain_write():
    dev, set_pid = session()
    for kwargs in ({'p': 1, 'd': .1}, {'p': 1, 'i': math.nan},
                   {'p': 1, 'cols': [1, 16]}):
        with pytest.raises(ValueError):
            set_pid(**kwargs)
    dev.group.PidP_Gain.set.assert_not_called()
    dev.group.PidI_Gain.set.assert_not_called()


def test_integer_d_and_debug_only_calls_still_work():
    dev, set_pid = session(fp=False)
    set_pid(d=.2, cols=[9])
    dev.group.PidD_Gain.set.assert_called_once_with(value=.2, index=9)
    dev.group.PidP_Gain.set.assert_not_called()
    dev2, set_fp = session()
    del dev2.group.PidP_Gain
    del dev2.group.PidI_Gain
    set_fp(debug=False, cols=[9])
    dev2.cbs[1].DataPath.AdcDsp[1].PidDebugEnable.set.assert_called_once_with(False)
