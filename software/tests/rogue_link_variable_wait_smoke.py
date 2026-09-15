# This file is part of the WarmTDM software package. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the WarmTDM software package may be copied, modified, propagated,
# or distributed except according to the terms contained in LICENSE.txt.

"""Link get/set tests with real PyRogue and manually completed memory reads.

Run with a Rogue version supporting ``readAndWaitBlocks``:
    python software/tests/rogue_link_variable_wait_smoke.py

No hardware, GUI, or network connection is needed.
"""

from concurrent.futures import ThreadPoolExecutor
import ast
import importlib.util
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pyrogue as pr
import rogue.interfaces.memory as rim


REPO = Path(__file__).resolve().parents[2]


def load(relative):
    path = REPO / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    # These driver modules do not use the package import; avoid loading the GUI
    # and the rest of the board support just to instantiate the tested devices.
    with patch.dict(sys.modules, {'warm_tdm': SimpleNamespace()}):
        spec.loader.exec_module(module)
    return module


group_vars = load('software/python/warm_tdm_api/_GroupVariables.py')
board_vars = load('firmware/python/warm_tdm/_GroupLinkVariable.py')
fast_dac = load('firmware/python/warm_tdm/_FastDacDriver.py')
ad5679 = load('firmware/python/warm_tdm/_Ad5679R.py')
sa_bias = load('firmware/python/warm_tdm/_SaBiasOffset2.py')
tes_bias = load('firmware/python/warm_tdm/_TesBiasAd5542.py')
timing_tx = load('firmware/python/warm_tdm/_TimingTx.py')
awa_bias = load('firmware/python/warm_tdm/_SaBiasOffsetAwaXe.py')


def closure(relative, name, **env):
    """Exercise a real board callback without constructing unrelated devices."""
    tree = ast.parse((REPO / relative).read_text())
    node = next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), relative, 'exec'), env)
    return env[name]


class HeldMemory(rim.Slave):
    """Keep reads pending until the test explicitly supplies their data."""

    def __init__(self, value=16):
        super().__init__(4, 0x10000)
        self.value = value
        self.pending = []
        self.changed = threading.Condition()
        self.automatic = False
        self.error = None
        self.data = {}
        self.writes = []
        self.reads = []

    def _doTransaction(self, transaction):
        with self.changed:
            if transaction.type() in (rim.Write, rim.Post):
                with transaction.lock():
                    data = bytearray(transaction.size())
                    transaction.getData(data, 0)
                    for i, byte in enumerate(data):
                        self.data[transaction.address() + i] = byte
                    self.writes.append(bytes(data))
                    transaction.done()
                return
            self.pending.append(transaction)
            self.reads.append(transaction.address())
            self.changed.notify_all()
            if self.automatic:
                self.complete()

    def complete(self):
        with self.changed:
            for transaction in self.pending:
                with transaction.lock():
                    if self.error:
                        transaction.error(self.error)
                    else:
                        word = self.value.to_bytes(4, 'little')
                        data = bytearray(self.data.get(transaction.address() + i, word[i % 4])
                                         for i in range(transaction.size()))
                        transaction.setData(data, 0)
                        transaction.done()
            self.pending.clear()

    def finish(self):
        with self.changed:
            self.automatic = True
            self.complete()

    def await_read(self, count=1):
        with self.changed:
            if not self.changed.wait_for(lambda: len(self.pending) >= count, timeout=2):
                raise AssertionError(f'Expected {count} pending hardware reads')


class GetterTests(unittest.TestCase):
    def setUp(self):
        self.root = pr.Root(name='Test', pollEn=False, timeout=2)
        self.memories = []
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.worker_thread = self.pool.submit(threading.get_ident).result()
        self.addCleanup(self.pool.shutdown)
        self.addCleanup(self.root.stop)
        self.addCleanup(self.finish_reads)

    def finish_reads(self):
        for memory in self.memories:
            memory.finish()

    def memory(self, value=16):
        memory = HeldMemory(value)
        self.memories.append(memory)
        return memory

    def remote(self, name, *, size=0, value=16):
        memory = self.memory(value)
        device = pr.Device(name=name, memBase=memory)
        args = dict(numValues=size, valueBits=16, valueStride=32) if size else dict(bitSize=16)
        device.add(pr.RemoteVariable(name='Raw', offset=0, base=pr.UInt, **args))
        self.root.add(device)
        return device.Raw, memory

    def pending_get(self, variable, reads, *, index=-1):
        result = self.pool.submit(variable.get, index=index)
        for memory, count in reads.items():
            memory.await_read(count)
        self.assertFalse(result.done())
        return result

    def test_sa_output_reads_all_enabled_board_blocks_before_conversion(self):
        boards = []
        adc_memories = []
        dac_memories = []
        conversions = []
        waveform_path = 'firmware/python/warm_tdm/_WaveformCapture.py'
        conv = closure(waveform_path, 'conv')
        for index in range(3):
            board = pr.Device(name=f'Board{index}')
            self.root.add(board)
            ma = self.memory(1 << 28)  # AdcAverage converts this to 0.125 V.
            md = self.memory(16384)   # Each offset DAC converts to 0.625 V.
            adc_memories.append(ma)
            dac_memories.append(md)
            wave = pr.Device(name='Waveform', memBase=ma)
            wave.add(pr.RemoteVariable(
                name='AdcAverageRaw', offset=0x10, base=pr.Int,
                numValues=8, valueBits=32, valueStride=32))
            wave.add(pr.LinkVariable(
                name='AdcAverage', dependencies=[wave.AdcAverageRaw],
                linkedGet=closure(waveform_path, '_get', self=wave, conv=conv, np=np)))
            board.add(wave)
            board.add(pr.LinkVariable(name='SaOutAdc', variable=wave.AdcAverage))
            dac = ad5679.Ad5679R(name='Dac', memBase=md)
            board.add(dac)
            calls = []
            conversions.append(calls)

            def ampVin(adc, *offsets, calls=calls):
                # Root listeners can independently evaluate cached values.
                # Check the conversion order in the requested getter itself.
                if threading.get_ident() == self.worker_thread:
                    calls.append((adc, offsets))
                return adc + sum(offsets)

            amp = SimpleNamespace(ampVin=ampVin, saBiasCurrent=lambda vp, vn: vp - vn)
            board.AnalogFrontEnd = SimpleNamespace(Channel=[SimpleNamespace(SAAmp=amp)]*8)
            bias = sa_bias.SaBiasOffset2(
                name='SaBiasOffset', saBiasDac=dac, saOffsetDac=dac,
                frontEnd=board.AnalogFrontEnd)
            board.add(bias)
            board.add(pr.LinkVariable(
                name='SaOut', dependencies=[board.SaOutAdc, *bias.OffsetVoltage.values()],
                linkedGet=closure('firmware/python/warm_tdm/_ColumnFpgaBoard.py',
                                  '_saOutGet', self=board, np=np)))
            boards.append(board)

        # A single enabled channel refreshes its board; the last board is idle.
        self.root.add(pr.LocalVariable(name='Enabled', value=[True] + [False]*7
                                      + [True] + [False]*15))
        for name in ('SaOutAdc', 'SaOut'):
            self.root.add(group_vars.GroupArrayLinkVariable(
                name=name, dependencies=[getattr(board, name) for board in boards],
                readBlocks=True,
                tuneEnVar=self.root.Enabled, config=SimpleNamespace(numColumns=24)))
        self.root.start()

        for variable, expected_value in ((self.root.SaOutAdc, 0.125),
                                         (self.root.SaOut, 1375.0)):
            with self.subTest(variable=variable.name):
                for calls in conversions:
                    calls.clear()
                reads = {memory: 1 for memory in adc_memories[:2]}
                if variable is self.root.SaOut:
                    reads.update({memory: 16 for memory in dac_memories[:2]})
                result = self.pending_get(variable, reads)
                for calls in conversions:
                    self.assertEqual(calls, [])
                self.assertEqual(adc_memories[2].reads, [])
                self.assertEqual(dac_memories[2].reads, [])
                for memory in adc_memories[:2]:
                    memory.complete()
                if variable is self.root.SaOut:
                    self.assertFalse(result.done())
                    for calls in conversions:
                        self.assertEqual(calls, [])
                    for memory in dac_memories[:2]:
                        memory.complete()
                expected = [expected_value]*16 + [0]*8
                np.testing.assert_array_equal(result.result(timeout=1), expected)
                counts = [len(memory.reads) for memory in self.memories]
                np.testing.assert_array_equal(variable.get(read=False), expected)
                self.assertEqual([len(memory.reads) for memory in self.memories], counts)

    def test_shared_block_is_read_once_before_nested_conversions(self):
        raw, memory = self.remote('Raw', value=7)
        calls = []

        def convert(read):
            if threading.get_ident() == self.worker_thread:
                calls.append(read)
            return raw.get(read=read) * 2

        self.root.add(pr.LinkVariable(name='Converted', dependencies=[raw], linkedGet=convert))
        self.root.add(pr.LinkVariable(name='Converted2', dependencies=[raw], linkedGet=convert))
        self.root.add(board_vars.GroupLinkVariable(
            name='Board', dependencies=[self.root.Converted, self.root.Converted2]))
        self.root.add(group_vars.GroupArrayLinkVariable(
            name='Values', dependencies=[self.root.Board], readBlocks=True,
            config=SimpleNamespace(numColumns=2)))
        self.root.start()
        calls.clear()
        count = len(memory.reads)
        result = self.pending_get(self.root.Values, {memory: 1})
        self.assertEqual(calls, [])
        memory.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [14, 14])
        self.assertEqual(len(memory.reads), count + 1)
        self.assertEqual(calls, [False, False])

    def test_scalar_source_selection_does_not_read_inactive_dependencies(self):
        raw0, m0 = self.remote('Awa0', value=12)
        raw1, m1 = self.remote('Awa1', value=24)
        md = self.memory(16384)
        dac = ad5679.Ad5679R(name='Dac', memBase=md)
        self.root.add(dac)
        amp = SimpleNamespace(saBiasCurrent=lambda vp, vn: vp - vn)
        bias = awa_bias.SaBiasOffsetAwaXe(
            name='Bias', awaXe=SimpleNamespace(Ch0Dac300A=raw0, Ch1Dac300A=raw1),
            saBiasDac=dac, saOffsetDac=dac,
            frontEnd=SimpleNamespace(Channel=[SimpleNamespace(SAAmp=amp)]*8))
        self.root.add(bias)
        self.root.add(group_vars.GroupLinkVariable(
            name='Values', dependencies=[bias.BiasCurrent[0]]))
        self.root.start()
        result = self.pending_get(self.root.Values, {m0: 1})
        self.assertEqual(md.reads, [])
        self.assertEqual(m1.reads, [])
        m0.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [12])

        bias.SaBiasSrc[0].set('FEB')
        result = self.pending_get(self.root.Values, {md: 1})
        self.assertEqual(len(m0.reads), 1)
        md.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [625000])

    def test_group_scalar_default_wait_and_disabled_columns(self):
        a, ma = self.remote('A', value=11)
        b, mb = self.remote('B', value=22)
        self.root.add(pr.LocalVariable(name='Enabled', value=[True, False]))
        self.root.add(group_vars.GroupLinkVariable(
            name='Values', dependencies=[a, b], tuneEnVar=self.root.Enabled))
        self.root.start()
        result = self.pending_get(self.root.Values, {ma: 1})
        self.assertEqual(len(ma.pending), 1)
        self.assertEqual(mb.pending, [])
        ma.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [11, 0])

        ma.value = 33
        result = self.pool.submit(self.root.Values.get)
        ma.await_read()
        self.assertFalse(result.done())
        ma.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [33, 0])
        self.assertEqual(mb.pending, [])

    def test_group_array_enabled_board_and_index(self):
        a, ma = self.remote('A', size=8, value=12)
        b, mb = self.remote('B', size=8, value=24)
        self.root.add(pr.LocalVariable(name='Enabled', value=[False]*8 + [True]*8))
        self.root.add(group_vars.GroupArrayLinkVariable(
            name='Values', dependencies=[a, b], tuneEnVar=self.root.Enabled,
            config=SimpleNamespace(numColumns=16)))
        self.root.start()
        result = self.pending_get(self.root.Values, {mb: 1})
        self.assertEqual(ma.pending, [])
        self.assertEqual(len(mb.pending), 1)
        mb.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [0]*8 + [24]*8)
        result = self.pending_get(self.root.Values, {mb: 1}, index=10)
        mb.complete()
        self.assertEqual(result.result(timeout=1), 24)

    def test_fast_dac_conversion_and_table_index(self):
        amp = SimpleNamespace(dacToOutCurrent=lambda raw: raw * 2.0,
                              dacToOutVoltage=lambda raw: raw * 3.0,
                              dacToLoadVoltage=lambda raw: raw * 4.0)
        memory = self.memory(15)
        device = fast_dac.FastDacMem(name='Dac', memBase=memory, size=4, amp=amp)
        self.root.add(device)
        self.root.add(group_vars.FastDacVariable(
            name='Table', dependencies=[device.Current],
            config=SimpleNamespace(numColumns=1)))
        self.root.start()
        result = self.pending_get(self.root.Table, {memory: 1})
        self.assertEqual(len(memory.pending), 1)
        memory.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [[30]*4])
        result = self.pending_get(self.root.Table, {memory: 1}, index=(0, 2))
        memory.complete()
        self.assertEqual(result.result(timeout=1), 30)
        for variable, index in ((device.Current, 2), (device.Voltage, 2)):
            with self.subTest(variable=variable.name):
                result = self.pending_get(variable, {memory: 1}, index=index)
                self.assertEqual(len(memory.pending), 1)
                memory.complete()
                self.assertEqual(result.result(timeout=1), 30 if variable is device.Current else 45)

    def test_fast_dac_override_preserves_cached_reads_through_both_groups(self):
        amp = SimpleNamespace(dacToOutCurrent=lambda raw: raw * 2.0,
                              dacToOutVoltage=lambda raw: raw * 3.0,
                              dacToLoadVoltage=lambda raw: raw * 4.0)
        front_end = SimpleNamespace(Channel=[SimpleNamespace(find=lambda **kw: [amp])]*8)
        memory = self.memory(17)
        driver = fast_dac.FastDacDriver(name='Dac', memBase=memory, frontEnd=front_end, rows=4)
        self.root.add(driver)
        self.root.add(board_vars.GroupLinkVariable(
            name='BoardValues', dependencies=[driver.OverrideCurrent[0]]))
        self.root.add(group_vars.GroupArrayLinkVariable(
            name='Values', dependencies=[self.root.BoardValues],
            config=SimpleNamespace(numColumns=1)))
        self.root.start()
        memory.finish()
        memory.value = 7
        driver.OverrideRaw[0].get(read=True)
        memory.value = 17  # Hardware changes without refreshing the clean cache.
        count = len(memory.reads)
        for variable in (self.root.BoardValues, self.root.Values):
            with self.subTest(variable=variable.name):
                self.assertEqual(variable.get(index=0, read=True), 14)
                np.testing.assert_array_equal(variable.get(read=True), [14])
                self.assertEqual(len(memory.reads), count)

    def test_sa_offset_getters_reach_dac(self):
        memory = self.memory(16384)
        dac = ad5679.Ad5679R(name='Dac', memBase=memory)
        self.root.add(dac)
        amp = SimpleNamespace(saBiasCurrent=lambda vp, vn: vp - vn)
        front_end = SimpleNamespace(Channel=[SimpleNamespace(SAAmp=amp)]*8)
        bias = sa_bias.SaBiasOffset2(name='Bias', saBiasDac=dac, saOffsetDac=dac, frontEnd=front_end)
        self.root.add(bias)
        self.root.add(group_vars.GroupLinkVariable(name='Offset', dependencies=[bias.OffsetVoltage[0]]))
        self.root.start()
        result = self.pending_get(self.root.Offset, {memory: 1})
        memory.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [1.25])
        for variable, index, expected in ((bias.OffsetVoltage[0], -1, 1.25),
                                          (bias.OffsetVoltagePArray, 0, 0.625),
                                          (bias.OffsetVoltageNArray, 0, 0.625),
                                          (bias.BiasCurrent[0], -1, 625000)):
            with self.subTest(variable=variable.name):
                result = self.pending_get(variable, {memory: 1}, index=index)
                self.assertEqual(len(memory.pending), 1)
                memory.complete()
                np.testing.assert_allclose(result.result(timeout=1), expected)

    def test_pid_get_refreshes_zero_cached_sample_count_before_conversion(self):
        samples, ms = self.remote('Samples', value=4)
        coefficient, mc = self.remote('Coefficient', value=3)
        self.root.add(group_vars.PidGainVariable(
            name='Gain', coefficient_dependencies=[coefficient], sample_count=samples))
        self.root.start()
        result = self.pending_get(self.root.Gain, {ms: 1})
        self.assertEqual(len(ms.pending), 1)
        self.assertEqual(mc.pending, [])
        ms.complete()
        mc.await_read()
        self.assertEqual(len(mc.pending), 1)
        mc.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [12])

    def test_pid_get_refreshes_both_sample_window_registers(self):
        memory = self.memory()
        timing = timing_tx.TimingTx(name='Timing', memBase=memory)
        self.root.add(timing)
        coefficient, mc = self.remote('Coefficient', value=3)
        self.root.add(pr.LinkVariable(
            name='CoefficientLink', dependencies=[coefficient], linkedGet=coefficient.get))
        self.root.add(group_vars.PidGainVariable(
            name='Gain', coefficient_dependencies=[self.root.CoefficientLink],
            sample_count=timing.SampleCount))
        self.root.start()
        for register, value in ((timing.SampleStartTime, 10), (timing.SampleEndTime, 14)):
            for i, byte in enumerate(value.to_bytes(4, 'little')):
                memory.data[register.offset + i] = byte
        result = self.pending_get(self.root.Gain, {memory: 1})
        memory.complete()
        memory.await_read()
        memory.complete()
        mc.await_read()
        mc.complete()
        np.testing.assert_array_equal(result.result(timeout=1), [12])

    def test_tes_bias_preserves_cached_getter(self):
        memory = self.memory(16384)
        amp = SimpleNamespace(dacToOutCurrent=lambda vp, vn, delatch: vp - vn + delatch)
        front_end = SimpleNamespace(Channel=[SimpleNamespace(TesBiasAmp=amp)]*8)
        device = tes_bias.TesBiasAd5542(name='Bias', frontEnd=front_end, memBase=memory)
        self.root.add(device)
        self.root.add(group_vars.GroupLinkVariable(
            name='Values', dependencies=[device.BiasCurrent[0]]))
        self.root.start()
        memory.finish()
        device.Dac[0].get(read=True)
        device.Delatch[0].get(read=True)
        memory.value = 32768
        count = len(memory.reads)
        self.assertEqual(device.BiasCurrent[0].get(read=True), -0.625)
        np.testing.assert_array_equal(self.root.Values.get(read=True), [-0.625])
        self.assertEqual(len(memory.reads), count)

    def test_deferred_read_error_is_raised_by_final_wait(self):
        raw, memory = self.remote('A')
        self.root.add(board_vars.GroupLinkVariable(name='Board', dependencies=[raw]))
        self.root.add(group_vars.GroupArrayLinkVariable(
            name='Values', dependencies=[self.root.Board], readBlocks=True,
            config=SimpleNamespace(numColumns=1)))
        self.root.start()
        result = self.pending_get(self.root.Values, {memory: 1})
        memory.error = 'injected read failure'
        memory.complete()
        with self.assertRaisesRegex(Exception, 'injected read failure'):
            result.result(timeout=1)

    def pending_set(self, variable, value, memories, *, index=-1):
        result = self.pool.submit(variable.set, value, index=index)
        for memory in memories:
            memory.await_read()  # Write verification is a read transaction.
        self.assertFalse(result.done())
        return result

    def test_group_setters_wait_for_verification_and_respect_disabled_columns(self):
        a, ma = self.remote('A')
        b, mb = self.remote('B')
        c, mc = self.remote('C', size=8)
        d, md = self.remote('D', size=8)
        self.root.add(pr.LocalVariable(name='Enabled', value=[True, False]))
        self.root.add(pr.LocalVariable(name='ArrayEnabled', value=[True]*8 + [False]*8))
        self.root.add(group_vars.GroupLinkVariable(
            name='Scalars', dependencies=[a, b], tuneEnVar=self.root.Enabled))
        self.root.add(group_vars.GroupArrayLinkVariable(
            name='Arrays', dependencies=[c, d], tuneEnVar=self.root.ArrayEnabled,
            config=SimpleNamespace(numColumns=16)))
        self.root.add(group_vars.FastDacVariable(
            name='Table', dependencies=[c, d], tuneEnVar=self.root.Enabled,
            config=SimpleNamespace(numColumns=2)))
        self.root.start()
        cases = [(self.root.Scalars, [11, 22], [ma], a, 11),
                 (self.root.Arrays, list(range(16)), [mc], c, list(range(8))),
                 (self.root.Table, [[30]*8, [40]*8], [mc], c, [30]*8)]
        for variable, value, active, raw, expected in cases:
            with self.subTest(variable=variable.name):
                result = self.pending_set(variable, value, active)
                for memory in self.memories:
                    self.assertEqual(len(memory.pending), int(memory in active))
                    memory.complete()
                result.result(timeout=1)
                np.testing.assert_array_equal(raw.get(read=False), expected)
        self.assertEqual(md.writes, [])

    def test_nested_board_setter_cache_only_and_default_wait(self):
        raw, memory = self.remote('Raw')
        self.root.add(board_vars.GroupLinkVariable(name='Board', dependencies=[raw]))
        self.root.add(group_vars.GroupArrayLinkVariable(
            name='Values', dependencies=[self.root.Board],
            config=SimpleNamespace(numColumns=1)))
        self.root.start()
        self.root.Values.set([8], write=False)
        self.assertEqual(memory.writes, [])
        self.assertEqual(memory.pending, [])
        result = self.pending_set(self.root.Values, 9, [memory], index=0)
        self.assertEqual(len(memory.pending), 1)
        memory.complete()
        result.result(timeout=1)

        result = self.pool.submit(self.root.Values.set, [10])
        memory.await_read()  # Write verification is a read transaction.
        self.assertFalse(result.done())
        memory.complete()
        result.result(timeout=1)
        self.assertEqual(raw.get(read=False), 10)

    def test_fast_dac_set_conversion_and_index_wait_for_verification(self):
        memory = self.memory()
        amp = SimpleNamespace(dacToOutCurrent=lambda raw: raw * 2.0,
                              dacToOutVoltage=lambda raw: raw * 3.0,
                              dacToLoadVoltage=lambda raw: raw * 4.0,
                              outCurrentToDac=lambda value: int(value / 2),
                              outVoltageToDac=lambda value: int(value / 3))
        device = fast_dac.FastDacMem(name='Dac', size=4, amp=amp, memBase=memory)
        self.root.add(device)
        self.root.start()
        for variable, value, index, raw in ((device.Current, 24, 2, 12),
                                            (device.Voltage, 45, 2, 15)):
            result = self.pending_set(variable, value, [memory], index=index)
            self.assertEqual(len(memory.pending), 1)
            memory.complete()
            result.result(timeout=1)
            self.assertEqual(device.Raw.get(read=False, index=2), raw)

    def test_sa_setter_chain_and_deferred_verification_failure(self):
        memory = self.memory()
        dac = ad5679.Ad5679R(name='Dac', memBase=memory)
        self.root.add(dac)
        front_end = SimpleNamespace(Channel=[SimpleNamespace(SAAmp=SimpleNamespace(
            saBiasCurrent=lambda vp, vn: vp - vn))]*8)
        bias = sa_bias.SaBiasOffset2(name='Bias', saBiasDac=dac, saOffsetDac=dac, frontEnd=front_end)
        self.root.add(bias)
        self.root.start()
        result = self.pending_set(bias.OffsetVoltage[0], 1.25, [memory])
        self.assertEqual(len(memory.pending), 1)
        memory.error = 'injected verification failure'
        memory.complete()
        with self.assertRaisesRegex(Exception, 'injected verification failure'):
            result.result(timeout=1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
