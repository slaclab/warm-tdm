# This file is part of 'warm-tdm'. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Characterize RX overflow and framing after queued replies outlive pause.

These are expected-loss tests, not full-ring stability acceptance. No vendor
simulator, network connection, Rogue installation, or imported HDL is needed.
"""
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SURF_SOURCES = """
axi/axi-stream/rtl/AxiStreamFifoV2.vhd
axi/axi-stream/rtl/AxiStreamGearbox.vhd
axi/axi-stream/rtl/AxiStreamPipeline.vhd
axi/axi-stream/rtl/AxiStreamPkg.vhd
axi/axi-stream/rtl/AxiStreamResize.vhd
axi/axi4/rtl/AxiPkg.vhd
base/crc/rtl/Crc32.vhd
base/crc/rtl/Crc32Parallel.vhd
base/crc/rtl/CrcPkg.vhd
base/fifo/rtl/Fifo.vhd
base/fifo/rtl/FifoCascade.vhd
base/fifo/rtl/FifoOutputPipeline.vhd
base/fifo/rtl/dummy/FifoAlteraMfDummy.vhd
base/fifo/rtl/dummy/FifoXpmDummy.vhd
base/fifo/rtl/inferred/FifoAsync.vhd
base/fifo/rtl/inferred/FifoRdFsm.vhd
base/fifo/rtl/inferred/FifoSync.vhd
base/fifo/rtl/inferred/FifoWrFsm.vhd
base/general/rtl/RstPipeline.vhd
base/general/rtl/StdRtlPkg.vhd
base/general/rtl/TextUtilPkg.vhd
base/ram/inferred/DualPortRam.vhd
base/ram/inferred/LutRam.vhd
base/ram/inferred/SimpleDualPortRamInferred.vhd
base/ram/inferred/TrueDualPortRamInferred.vhd
base/ram/rtl/SimpleDualPortRam.vhd
base/sync/rtl/RstSync.vhd
base/sync/rtl/Synchronizer.vhd
base/sync/rtl/SynchronizerVector.vhd
protocols/packetizer/rtl/AxiStreamDepacketizer2.vhd
protocols/packetizer/rtl/AxiStreamPacketizer2.vhd
protocols/packetizer/rtl/AxiStreamPacketizer2Pkg.vhd
protocols/pgp/pgp2b/core/rtl/Pgp2bPkg.vhd
protocols/pgp/shared/PgpRxVcFifo.vhd
protocols/ssi/rtl/SsiPkg.vhd
""".split()
FLAGS = ["--std=08", "-fsynopsys", "-frelaxed-rules", "-O2"]


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    if not shutil.which("ghdl"):
        pytest.skip("GHDL is required")
    build = tmp_path_factory.mktemp("ring_rx_buffer")
    def command(*args):
        result = subprocess.run(["ghdl", *args], cwd=build, text=True,
                                capture_output=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
    command("-a", *FLAGS, "--work=unisim",
            str(ROOT / "tests/common/vhdl/unisim_vcomponents.vhd"))
    command("-i", *FLAGS, "--work=surf", *[
        str(ROOT / "firmware/submodules/surf" / f) for f in SURF_SOURCES])
    command("-i", *FLAGS, str(HERE / "RingRxBufferTb.vhd"))
    command("-m", *FLAGS, "RingRxBufferTb")
    return build


def metrics(output, label):
    line = next(line for line in output.splitlines() if label in line)
    return {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", line)}


@pytest.mark.parametrize("depth,frames,ready,stall,loss", [
    (8, 1, False, True, True),
    (10, 1, False, True, False),
    (10, 2, False, True, True),
    (10, 3, False, True, True),
    (10, 3, True, True, True),  # Former GTX cosim setting masks overflow.
    (10, 3, False, False, False),
])
def test_queued_replies(compiled, depth, frames, ready, stall, loss):
    result = subprocess.run([
        "ghdl", "-r", *FLAGS, "RingRxBufferTb",
        f"-gRX_DEPTH_G={depth}", f"-gFRAMES_G={frames}",
        f"-gREADY_G={str(ready).lower()}", f"-gSTALL_G={str(stall).lower()}",
        "--assert-level=error", "--ieee-asserts=disable",
    ], cwd=compiled, text=True, capture_output=True, timeout=300)
    output = result.stdout + result.stderr
    name = f"depth{depth}_frames{frames}_ready{ready}_stall{stall}.log"
    (compiled / name).write_text(output)
    assert result.returncode == 0, output
    burst = metrics(output, "BURST_RESULT")
    recovery = metrics(output, "RECOVERY_RESULT")
    if loss:
        assert burst["received"] < 4120 * frames, output
        assert burst["frames"] < frames, output
        assert (burst["overflow_cycles"] > 0) == (not ready), output
        # A dropped tail can merge the first fresh probe into the old frame.
        assert recovery["probes_good"] == 2, output
    else:
        assert burst["received"] == 4120 * frames, output
        assert burst["frames"] == frames, output
        assert burst["overflow_cycles"] == 0, output
        assert recovery["probes_good"] == 3, output
    assert recovery["probe_words"] == 12, output
