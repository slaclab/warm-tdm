#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Exercise the cosim client runner on real Rogue/VirtualClient with MemEmulate.

This checks client plumbing and broadcast controls, not VCS or analog behavior.
Run explicitly in a Rogue/Warm-TDM environment.
"""
import json
from pathlib import Path
import sys
import struct
import tempfile
from types import SimpleNamespace
import unittest

import warm_tdm
import warm_tdm_api as api

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts/hwtest'
sys.path.insert(0, str(SCRIPTS))
import _cosim_common as common
from verify_cosim_controls import check_controls
from verify_cosim_readout import inspect_file
from rogue_operations_smoke import SmokeRoot
import pyrogue as pr


class ClientSmoke(unittest.TestCase):
    def test_file_validator_with_real_stream_io_and_malformed_pid(self):
        with tempfile.TemporaryDirectory(prefix='wtj-cosim-files-') as tmp, SmokeRoot() as root:
            for malformed in [False, True]:
                path = str(Path(tmp) / ('malformed.dat' if malformed else 'valid.dat'))
                root.DataWriter.DataFile.set(path)
                root.DataWriter.Open()
                try:
                    prefix = 'GroupRoot.Group.HardwareGroup.ColumnBoard[0]'
                    config = {prefix + '.WarmTdmCore.Timing.TimingTx.DaqReadoutRate': 123.5,
                              prefix + '.AnalogFrontEnd.Channel[1].SQ1FbAmp.CurrentPerLsb': 0.002}
                    root.sources[255].send(pr.dataToYaml(config).encode())
                    root.sources[9].send(struct.pack('<QQQfBBHQ', 2, 3, 4, -12.5, 3, 1, 0, 0))
                    pid = bytearray(80)
                    struct.pack_into('<BB', pid, 0, 1, 3)
                    root.sources[1].send(pid[:70] if malformed else pid)
                finally:
                    root.DataWriter.Close()
                if malformed:
                    with self.assertRaisesRegex(AssertionError, 'Misaligned PID-debug frame'):
                        inspect_file(path, {(1, 3)}, {(1, 3)}, 123.5, {1: 2000.})
                else:
                    self.assertEqual(inspect_file(path, {(1, 3)}, {(1, 3)}, 123.5, {1: 2000.}),
                                     dict(readout=1, readout_populated=1, pid=1, config=1))
                    with self.assertRaisesRegex(AssertionError, 'Channel mismatch'):
                        inspect_file(path, {(1, 3), (1, 4)}, {(1, 3)}, 123.5, {1: 2000.})

    def test_production_group_virtualclient_broadcasts_and_evidence(self):
        cfg = api.GroupConfig(columnBoards=1, rowBoards=1, maxRows=8)
        with tempfile.TemporaryDirectory(prefix='wtj-cosim-client-') as tmp:
            directory = Path(tmp)
            manifest = directory / 'manifest.json'
            manifest.write_text(json.dumps(dict(firmware_commit=common.git('rev-parse', 'HEAD'),
                server_software_commit=common.git('rev-parse', 'HEAD'),
                surf_commit=common.git('rev-parse', 'HEAD:firmware/submodules/surf'),
                ruckus_commit=common.git('rev-parse', 'HEAD:firmware/submodules/ruckus'),
                fixture='MemEmulate production GroupRoot; CLIENT PLUMBING ONLY, not VCS',
                toolchain='local Rogue; no HDL simulation')))
            with api.GroupRoot(colBoardClass=warm_tdm.ColumnFpgaBoard,
                    colFeClass=warm_tdm.FpgaBoardColumnFeb, rowBoardClass=warm_tdm.RowFpgaBoard,
                    rowFeClass=warm_tdm.FpgaBoardRowFeb, numRowSelects=8, numChipSelects=0,
                    groupConfig=cfg, emulate=True, pollEn=False, initRead=False) as root:
                args = SimpleNamespace(host='127.0.0.1', port=root.zmqServer.port(),
                    output=directory, manifest=manifest, timing_timeout=2., broadcasts_only=True, fir=False)
                self.assertEqual(common.run(args, check_controls), 0)
                report_path = next(directory.glob('cosim-*/result.json'))
                report = json.loads(report_path.read_text())
                self.assertEqual(report['result'], 'PASS')
                self.assertEqual(len(report['checks']), 1)
                self.assertEqual(len(report['boards']), 2)
                self.assertIn('MemEmulate', report['supplied_simulation_manifest']['fixture'])
                self.assertIn('verify_cosim_controls.py', report['script_sha256'])
                # Connection and ordinary failure must still produce evidence and close the client.
                def fail(*unused):
                    raise ValueError('injected check failure')
                self.assertEqual(common.run(args, fail), 1)
                reports = [json.loads(p.read_text()) for p in directory.glob('cosim-*/result.json')]
                self.assertEqual(sorted(r['result'] for r in reports), ['FAIL', 'PASS'])
                self.assertTrue(any('injected check failure' in r.get('error', '') for r in reports))


if __name__ == '__main__':
    unittest.main(verbosity=2)
