# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Operations setup on a production two-board tree backed by MemEmulate.

Run explicitly with Rogue and the repository's software/python, firmware/python
and SURF/python on PYTHONPATH. Only localhost ZMQ is used. Memory emulation
does not execute the fast-DAC FSM; that verification is stubbed in the slow-zero
test, whose assertions cover actual slow-DAC register readbacks.
"""
import unittest
from unittest.mock import patch

import numpy as np
import pyrogue.interfaces as interfaces
import warm_tdm
import warm_tdm_api
import warm_tdm_api.operations as ops


class SetupSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = warm_tdm_api.GroupRoot(
            colBoardClass=warm_tdm.ColumnFpgaBoard,
            colFeClass=warm_tdm.FpgaBoardColumnFeb,
            rowBoardClass=warm_tdm.RowFpgaBoard,
            rowFeClass=warm_tdm.FpgaBoardRowFeb,
            numRowSelects=8, numChipSelects=0,
            groupConfig=warm_tdm_api.GroupConfig(columnBoards=2, rowBoards=1, maxRows=8),
            emulate=True, pollEn=False, initRead=False)
        cls.addClassCleanup(cls.root.stop)
        cls.root.start()
        cls.client = interfaces.VirtualClient(addr='127.0.0.1', port=cls.root.zmqServer.port())
        cls.addClassCleanup(cls.client.stop)

    def sessions(self):
        for group in (self.root.Group, self.client.root.Group):
            yield ops.Session(group)

    def test_direct_and_client_mux_and_dead_masks(self):
        for session in self.sessions():
            with self.subTest(group=type(session.group).__name__):
                group = session.group
                group.ColEnableMask.set((1 << 1) | (1 << 9))
                # Exercise the full-width integer across ZMQ, including an
                # explicitly disabled column on the second board.
                mask = (1 << 255) | 5
                session.apply_dead_masks({1: 3, 9: 5, 10: mask})
                self.assertEqual(session.read_hardware_dead_masks()[10], mask)
                self.assertEqual(group.RowEnableMasks.get(index=10), mask)
                group.RowReadoutOrder.set([3, 1, 2])
                np.testing.assert_array_equal(group.HardwareGroup.RowReadoutOrder.get(), [3, 1, 2])
                session.setup_mux(sample_num=128, enable_pid_debug=True)
                session.set_pid(p=0.5, i=0.25, debug=True)
                for col in range(16):
                    board, channel = divmod(col, 8)
                    dsp = session.cbs[board].DataPath.AdcDsp[channel]
                    enabled = col in (1, 9)
                    self.assertEqual(bool(dsp.PidEnable.get()), enabled)
                    self.assertEqual(bool(dsp.PidDebugEnable.get()), enabled)
                    if enabled:
                        self.assertAlmostEqual(group.PidP_Gain.get(index=col), 0.5)
                self.assertEqual(session.read_hardware_dead_masks()[9], 5)
                # A subsequent setup must disable a column that was enabled.
                group.ColEnableMask.set(0)
                session.setup_mux()
                for cb in session.cbs.values():
                    for dsp in cb.DataPath.AdcDsp.values():
                        self.assertFalse(dsp.PidEnable.get())
                        self.assertFalse(dsp.PidDebugEnable.get())

    def test_direct_and_client_zero_slow_outputs_with_all_columns_disabled(self):
        for session in self.sessions():
            with self.subTest(group=type(session.group).__name__):
                outputs = []
                for cb in session.cbs.values():
                    for channel in range(8):
                        for leaf, initial in (
                                (cb.SaBiasOffset.BiasCurrent[channel], 25.0),
                                (cb.SaBiasOffset.OffsetVoltage[channel], 0.5),
                                (cb.TesBias.BiasCurrent[channel], 30.0)):
                            leaf.set(initial)
                            self.assertGreater(abs(leaf.get(read=True)), 0.1)
                            outputs.append(leaf)
                session.group.ColEnableMask.set(0)
                with patch.object(session, '_apply_force_verified', return_value=(True, {})):
                    self.assertTrue(session.stop_and_zero())
                for leaf in outputs:
                    self.assertAlmostEqual(leaf.get(read=True), 0.0, delta=0.01)


if __name__ == '__main__':
    unittest.main(verbosity=2)
