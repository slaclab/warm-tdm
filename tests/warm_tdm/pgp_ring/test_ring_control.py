#-----------------------------------------------------------------------------
# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of Warm TDM, including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in LICENSE.txt.
#-----------------------------------------------------------------------------
# Test methodology:
# - Sweep: 2/3/8-board rings, every sink, RX depths 8/10, and queued responses.
# - Stimulus/checks: Select one cocotb scenario per pytest case; see
#   ring_control_cocotb.py for packet, admission, recovery and status assertions.
# - Timing: Bound simulator execution and terminate its process group on timeout.
# - Scope: Compile production RTL in isolated libraries; core-interface analysis
#   checks associations only. These tests do not exercise vendor GTX behavior.
"""Isolated tests of the production ring control, routing, and loss recovery."""
from pathlib import Path
import os
import json
import re
import signal
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from test_rx_buffer import FLAGS, ROOT, SURF_SOURCES

HERE = Path(__file__).resolve().parent
RTL = ROOT / "firmware/common/warm_tdm/rtl"


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    if not shutil.which("ghdl"):
        pytest.skip("GHDL is required")
    build = tmp_path_factory.mktemp("ring_control")

    def command(*args):
        result = subprocess.run(["ghdl", *args], cwd=build, text=True,
                                capture_output=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr

    command("-a", *FLAGS, "--work=unisim",
            str(ROOT / "tests/common/vhdl/unisim_vcomponents.vhd"))
    sources = SURF_SOURCES + [
        "axi/axi-stream/rtl/AxiStreamMux.vhd",
        "axi/axi-stream/rtl/AxiStreamFlush.vhd",
        "base/general/rtl/ArbiterPkg.vhd",
        "protocols/pgp/shared/PgpTxVcFifo.vhd",
        "axi/axi-stream/rtl/AxiStreamDeMux.vhd",
        "base/crc/rtl/CRC32Rtl.vhd",
    ]
    sources += [f"protocols/pgp/pgp2b/core/rtl/{name}.vhd" for name in [
        "Pgp2bLane", "Pgp2bTx", "Pgp2bTxCell", "Pgp2bTxSched", "Pgp2bTxPhy",
        "Pgp2bRx", "Pgp2bRxCell", "Pgp2bRxPhy"]]
    source_paths = [ROOT / "firmware/submodules/surf" / f for f in sources]
    if os.environ.get("WARM_TDM_RING_FULL_RECORDS") != "1":
        # The DUT uses 2- and 8-byte streams only. Avoid simulating the unused
        # 128-byte record capacity on every ring node. This changes no FIFO
        # width, configured stream width, pipeline, or protocol behavior. Keep
        # 16-byte capacity for SURF's unused default generic values.
        original = ROOT / "firmware/submodules/surf/axi/axi4/rtl/AxiPkg.vhd"
        compact = build / "AxiPkg.vhd"
        text = original.read_text()
        old = "AXI_MAX_DATA_WIDTH_C  : positive := 1024;"
        assert text.count(old) == 1
        compact.write_text(text.replace(old, "AXI_MAX_DATA_WIDTH_C  : positive := 128;"))
        source_paths[source_paths.index(original)] = compact
    command("-i", *FLAGS, "--work=surf", *map(str, source_paths))
    command("-i", *FLAGS, "--work=warm_tdm", *[
        str(RTL / f) for f in ["PgpRingPkg.vhd", "PgpRingFlowControl.vhd",
                              "PgpRingRxFifo.vhd", "RingRouter.vhd"]])
    benches = list((HERE / "tb").glob("Ring*ControlTb.vhd"))
    command("-i", *FLAGS, *map(str, benches))
    for bench in benches:
        command("-m", *FLAGS, bench.stem)
    return build


def run(compiled, bench, **generics):
    from cocotb_tools.config import lib_name_path
    import find_libpython

    # Scenario parameters live in Python; only structural dimensions are VHDL
    # generics. Each invocation gets its own result file in the isolated build.
    structural = {"BOARDS_G", "RX_DEPTH_G", "BRIDGE_DEPTH_G", "STATUS_CYCLES_G"}
    args = [f"-g{k}={str(v).lower()}" for k, v in generics.items() if k in structural]
    name = bench + "_" + "_".join(f"{k}={v}" for k, v in generics.items())
    log = compiled / (name + ".log")
    results = compiled / (name + ".xml")
    env = dict(os.environ, LIBPYTHON_LOC=find_libpython.find_libpython(),
               PYGPI_PYTHON_BIN=sys.executable, PYTHONPATH=str(HERE),
               COCOTB_TOPLEVEL=bench.lower(), COCOTB_TEST_MODULES="ring_control_cocotb",
               TOPLEVEL_LANG="vhdl", COCOTB_RESULTS_FILE=str(results),
               RING_CASE=json.dumps(dict(bench=bench, **generics)))
    with log.open("w") as stream:
        process = subprocess.Popen([
            "ghdl", "-r", *FLAGS, bench, *args,
            f"--vpi={lib_name_path('vpi', 'ghdl')}",
            "--assert-level=error", "--ieee-asserts=disable", "--unbuffered",
        ], cwd=compiled, text=True, stdout=stream, stderr=subprocess.STDOUT,
            start_new_session=True, env=env)
        try:
            process.wait(timeout=3600 if os.environ.get("WARM_TDM_RING_FULL_RECORDS") == "1" else 1200)
        except subprocess.TimeoutExpired:
            # LLVM GHDL launches a child executable. Killing only the wrapper
            # leaves that simulation running after pytest has reported failure.
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            pytest.fail(f"Simulation timed out; log: {log}")
    output = log.read_text()
    assert process.returncode == 0, output
    assert results.is_file(), output
    cases = ET.parse(results).findall(".//testcase")
    assert len(cases) == 1, output
    assert cases[0].find("failure") is None and cases[0].find("error") is None, output
    assert cases[0].find("skipped") is None, output
    return output


@pytest.mark.parametrize("boards", [2, 3, 8])
def test_collection_broadcast(compiled, boards):
    run(compiled, "RingFlowControlTb", BOARDS_G=boards)


def test_router_recovery_and_admission(compiled):
    run(compiled, "RingRouterControlTb")


def test_native_pgp_status_latency(compiled):
    run(compiled, "RingPgpStatusControlTb")


def test_core_interface_analysis(compiled):
    """Check actual PgpCore associations without pretending to simulate GTX.

    Import the real entity declarations for vendor-dependent/unexercised blocks,
    then analyze the complete production PgpCore architecture. No stand-in
    behavior is supplied or elaborated.
    """
    surf = ROOT / "firmware/submodules/surf"

    def analyze(path, library):
        result = subprocess.run(["ghdl", "-a", *FLAGS, f"--work={library}",
                                 str(path)], cwd=compiled, text=True,
                                capture_output=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr

    for source in ["base/general/rtl/TextUtilPkg.vhd",
                   "axi/axi-lite/rtl/AxiLitePkg.vhd",
                   "xilinx/7Series/gtx7/rtl/Gtx7CfgPkg.vhd"]:
        analyze(surf / source, "surf")
    for source in [
        "xilinx/7Series/general/rtl/ClockManager7.vhd",
        "protocols/pgp/pgp2b/gtx7/rtl/Pgp2bGtx7VarLat.vhd",
        "protocols/pgp/pgp2b/core/rtl/Pgp2bAxi.vhd",
        "protocols/srp/rtl/SrpV3AxiLite.vhd",
        "axi/axi-lite/rtl/AxiLiteCrossbar.vhd",
        "axi/axi-stream/rtl/AxiStreamDeMux.vhd",
    ]:
        text = (surf / source).read_text()
        entity = text[:re.search(r"^architecture\b", text, re.M | re.I).start()]
        path = compiled / (Path(source).stem + "_interface.vhd")
        path.write_text(entity)
        analyze(path, "surf")
    analyze(RTL / "PgpCore.vhd", "warm_tdm")


@pytest.mark.parametrize("depth,frames,stall", [(8, 1, True), (10, 2, True),
                                               (10, 3, True), (10, 3, False)])
def test_overflow_recovery(compiled, depth, frames, stall):
    run(compiled, "RingRecoveryControlTb", RX_DEPTH_G=depth, FRAMES_G=frames,
        STALL_G=stall)


@pytest.mark.parametrize("boards,sink", [(n, sink) for n in (2, 3, 8) for sink in range(n)])
def test_ring_congestion(compiled, boards, sink):
    run(compiled, "RingTrafficControlTb", BOARDS_G=boards, SINK_G=sink)


def test_large_queued_responses(compiled):
    # Sixteen KiB offered to an eight-KiB blocked receiver. Source ready, not
    # a bound on outstanding SRP reads, must retain the excess upstream.
    run(compiled, "RingTrafficControlTb", BOARDS_G=2, SINK_G=0, WORDS_G=1024)
