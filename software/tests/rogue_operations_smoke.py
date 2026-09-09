# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Actual Rogue threads, localhost client and file I/O; synthetic instrument.

Activate Rogue and set software/python, firmware/python and SURF/python on
PYTHONPATH, then run this file explicitly. No board connection is created.
"""
import _thread
from pathlib import Path
import struct
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

import numpy as np
import pyrogue as pr
import pyrogue.interfaces as interfaces
import pyrogue.utilities.fileio
import rogue
import warm_tdm_api.operations as ops
from warm_tdm._FastDacDriver import FastDacDriver


class Source(rogue.interfaces.stream.Master):
    def send(self, payload):
        frame = self._reqFrame(len(payload), True)
        with frame.lock():
            frame.write(bytearray(payload), 0)
        self._sendFrame(frame)


class SmokeRoot(pr.Root):
    def __init__(self):
        super().__init__(name='GroupRoot', pollEn=False)
        group = pr.Device(name='Group')
        group.add(pr.LocalVariable(name='NumColumns', value=8))
        group.add(pr.LocalVariable(name='NumColumnBoards', value=1))
        hwg = pr.Device(name='HardwareGroup')
        cb = pr.Device(name='ColumnBoard[0]')
        core = pr.Device(name='WarmTdmCore')
        timing = pr.Device(name='Timing')
        tx = pr.Device(name='TimingTx')
        tx.add(pr.LocalVariable(name='Running', value=False))
        tx.add(pr.LocalVariable(name='StopCalls', value=0))
        tx.add(pr.LocalVariable(name='Mode', value=0))
        def start():
            tx.Running.set(True)
        def stop():
            tx.Running.set(False)
            tx.StopCalls.set(tx.StopCalls.get() + 1)
        tx.add(pr.LocalCommand(name='StartRun', function=start))
        tx.add(pr.LocalCommand(name='EndRun', function=stop))
        timing.add(tx)
        core.add(timing)
        cb.add(core)
        for setter, name in [('Sq1FbForceCurrent', 'SQ1Fb'),
                             ('SaFbForceCurrent', 'SAFb'), ('Sq1BiasForceCurrent', 'SQ1Bias')]:
            driver = pr.Device(name=name)
            driver.add(pr.LocalVariable(name='FailRead', value=False))
            values = np.zeros(8)
            def raw(driver_node=driver, values=values, ch=0):
                if driver_node.FailRead.get():
                    raise OSError('injected raw read failure')
                return float(values[ch])
            for ch in range(8):
                driver.add(pr.LocalVariable(name=f'DacRawNow[{ch}]', value=0.0,
                    localGet=lambda raw=raw, ch=ch: raw(ch=ch)))
                dependency = driver.DacRawNow[ch]
                driver.add(pr.LinkVariable(name=f'DacCurrentNow[{ch}]',
                    dependencies=[dependency],
                    linkedGet=lambda read, dependency=dependency: dependency.get(read=read)))
            def apply(value, values=values):
                values[:] = value
            group.add(pr.LinkVariable(name=setter, linkedGet=lambda values=values: values.copy(),
                                      linkedSet=apply))
            cb.add(driver)
        hwg.add(cb)
        group.add(hwg)
        def work(dev):
            try:
                if dev.Fail.get():
                    raise RuntimeError('injected process failure')
                while dev._runEn:
                    time.sleep(0.005)
            finally:
                dev.CleanupCount.set(dev.CleanupCount.get() + 1)
        proc = pr.Process(name='SaTuneProcess', function=work)
        proc.add(pr.LocalVariable(name='Fail', value=False))
        proc.add(pr.LocalVariable(name='CleanupCount', value=0))
        proc.add(pr.LocalVariable(name='SaTuneOutput', value='result'))
        group.add(proc)
        self.add(group)
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter'))
        self.sources = {ch: Source() for ch in [9, 1, 255]}
        for ch, source in self.sources.items():
            source >> self.DataWriter.getChannel(ch)
        self.server = interfaces.ZmqServer(root=self, addr='127.0.0.1', port=0)
        self.addInterface(self.server)


class FastDacReadbackTests(unittest.TestCase):
    def test_current_get_refreshes_raw_memory_and_value_uses_cache(self):
        memory = rogue.interfaces.memory.Emulate(4, 0x1000)
        amp = SimpleNamespace(dacToOutCurrent=lambda raw: raw * 0.25,
                              dacToOutVoltage=lambda raw: raw * 0.01,
                              dacToLoadVoltage=lambda raw: raw * 0.01)
        front_end = SimpleNamespace(Channel={
            ch: SimpleNamespace(find=lambda **kwargs: [amp]) for ch in range(8)})
        root = pr.Root(name='ReadbackRoot', pollEn=False, initRead=False)
        self.addCleanup(root.stop)
        root.addInterface(memory)
        driver = FastDacDriver(name='SQ1Fb', frontEnd=front_end, rows=2, memBase=memory)
        root.add(driver)
        writer = pr.Device(name='MemoryWriter', memBase=memory)
        for ch in range(8):
            writer.add(pr.RemoteVariable(name=f'Raw[{ch}]', offset=0x9000 + 4*ch,
                                         bitSize=14, base=pr.UInt))
        writer_root = pr.Root(name='WriterRoot', pollEn=False, initRead=False)
        self.addCleanup(writer_root.stop)
        writer_root.add(writer)
        root.start()
        writer_root.start()
        for ch in range(8):
            with self.subTest(channel=ch):
                writer.Raw[ch].set(100 + ch)
                self.assertEqual(driver.DacCurrentNow[ch].get(), (100 + ch) * 0.25)
                writer.Raw[ch].set(200 + ch)
                self.assertEqual(driver.DacCurrentNow[ch].value(), (100 + ch) * 0.25)
                self.assertEqual(driver.DacCurrentNow[ch].get(read=False), (100 + ch) * 0.25)
                self.assertEqual(driver.DacCurrentNow[ch].get(), (200 + ch) * 0.25)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='wtj-ops-smoke-')
        self.addCleanup(self.directory.cleanup)
        self.root = SmokeRoot()
        self.addCleanup(self.root.stop)
        self.root.start()
        self.client = interfaces.VirtualClient(addr='127.0.0.1', port=self.root.server.port())
        self.addCleanup(self.client.stop)
        self.tx = self.root.Group.HardwareGroup.ColumnBoard[0].WarmTdmCore.Timing.TimingTx
        self.proc = self.root.Group.SaTuneProcess

    def sessions(self):
        for group in [self.root.Group, self.client.root.Group]:
            yield ops.Session(group, output=SimpleNamespace(sessiondir=self.directory.name))

    def test_direct_and_client_topology_and_timed_process_stop(self):
        for sess in self.sessions():
            self.assertEqual(list(sess.cbs), [0])
            self.assertEqual(sess.chans_per_board, 8)
            self.assertEqual(sess.rbs, {})
            previous = self.proc.CleanupCount.get()
            with self.assertRaises(TimeoutError):
                sess.run_process('SaTuneProcess', poll_sec=0.01, timeout_sec=0.05)
            self.assertFalse(self.proc.Running.get())
            self.assertEqual(self.proc.CleanupCount.get(), previous + 1)

    def test_direct_and_client_process_error(self):
        for sess in self.sessions():
            with self.assertRaisesRegex(RuntimeError, 'Stopped after error'):
                sess.run_process('SaTuneProcess', poll_sec=0.01, timeout_sec=1, Fail=True)
            self.assertFalse(self.proc.Running.get())

    def test_direct_and_client_writer_and_run_ownership(self):
        for sess in self.sessions():
            for running in [False, True]:
                self.tx.Running.set(running)
                stops = self.tx.StopCalls.get()
                sess.take_data(0, start_delay_sec=0)
                self.assertFalse(self.root.DataWriter.IsOpen.get())
                self.assertEqual(self.tx.Running.get(), running)
                self.assertEqual(self.tx.StopCalls.get(), stops + int(not running))

    def test_startup_interrupt_and_file_setup_error_cleanup(self):
        for sess in self.sessions():
            timer = threading.Timer(0.03, _thread.interrupt_main)
            timer.start()
            try:
                with self.assertRaises(KeyboardInterrupt):
                    sess.take_data(0, start_delay_sec=0.15)
            finally:
                timer.cancel()
                timer.join()
            self.assertFalse(self.tx.Running.get())
            self.assertFalse(self.root.DataWriter.IsOpen.get())
            sess.output = None
            with self.assertRaisesRegex(RuntimeError, 'No output directory'):
                sess.take_data(0, start_delay_sec=0)
            self.assertFalse(self.tx.Running.get())

    def test_tuning_interrupt_stops_real_worker(self):
        sess = next(self.sessions())
        timer = threading.Timer(0.04, _thread.interrupt_main)
        timer.start()
        try:
            with self.assertRaises(KeyboardInterrupt):
                sess.run_process('SaTuneProcess', poll_sec=0.01)
        finally:
            timer.cancel()
            timer.join()
        self.assertFalse(self.proc.Running.get())
        self.assertEqual(self.proc.CleanupCount.get(), 1)

    def test_real_direct_and_client_force_verification_rejects_read_failure(self):
        for sess in self.sessions():
            driver = self.root.Group.HardwareGroup.ColumnBoard[0].SQ1Fb
            driver.FailRead.set(False)
            self.assertEqual(sess.set_force('Sq1Fb', 12.5, tries=1, settle_sec=0), (True, {}))
            driver.FailRead.set(True)
            ok, residual = sess.set_force('Sq1Fb', 0.0, tries=1, settle_sec=0)
            self.assertFalse(ok)
            self.assertEqual(len(residual), 8)
            self.assertTrue(all(np.isnan(value) for value in residual.values()))
            driver.FailRead.set(False)

    def test_real_stream_file_readout_pid_and_config_units(self):
        path = str(Path(self.directory.name) / 'stream.dat')
        writer = self.root.DataWriter
        writer.DataFile.set(path)
        writer.Open()
        try:
            prefix = 'GroupRoot.Group.HardwareGroup.ColumnBoard[0]'
            config = {prefix + '.WarmTdmCore.Timing.TimingTx.DaqReadoutRate': 123.5,
                prefix + '.AnalogFrontEnd.Channel[1].SQ1FbAmp.CurrentPerLsb': 0.002}
            self.root.sources[255].send(pr.dataToYaml(config).encode())
            payload = struct.pack('<QQQfBBHQ', 2, 3, 4, -12.5, 3, 1, 0, 0)
            self.root.sources[9].send(payload)
            pid = bytearray(80)
            struct.pack_into('<BB', pid, 0, 1, 3)
            struct.pack_into('<i', pid, 16, -7)
            struct.pack_into('<q', pid, 48, -12345)
            struct.pack_into('<II', pid, 72, 10, 22)
            self.root.sources[1].send(pid)
        finally:
            writer.Close()
        reader = ops.StreamReader()
        reader.readStream(path)
        self.assertEqual(reader.data[1][3], [-12.5])
        self.assertEqual(reader.pid[1][3]['accumError'], [-7])
        self.assertEqual(reader.pid[1][3]['pidResult'], [-12345])
        self.assertEqual(reader.pid[1][3]['readoutCount'], [22])
        self.assertEqual(ops.derive_fs(reader.config, col=1), 123.5)
        self.assertEqual(ops.derive_sq1fb_to_pA(reader.config, col=1), 2000.0)
        repaired = reader._parseConfig("x: !!float '1,234.5'\n")
        self.assertEqual(repaired['x'], 1234.5)


if __name__ == '__main__':
    print('Runtime:', rogue.Version.current(), 'NumPy:', np.__version__, flush=True)
    unittest.main(verbosity=2)
