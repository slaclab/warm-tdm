#-----------------------------------------------------------------------------
# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of Warm TDM, including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in LICENSE.txt.
#-----------------------------------------------------------------------------
# Test methodology:
# - Compile the actual Ethernet bandwidth helper and checked-out SURF pacer.
# - Run bounded GHDL/cocotb cases at both Ethernet rates; stimulus and throughput
#   assertions live in bandwidth_cocotb.py. No vendor-IP or socket behavior.
# - Exercise the real GroupTb Tcl selector with only Vivado commands stubbed.
"""Isolated Ethernet simulation-bandwidth and build-selection regression."""
from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SURF = ROOT / "firmware/submodules/surf"
FLAGS = ["--std=08", "-fsynopsys", "-frelaxed-rules", "-O2"]
SOURCES = [
    "base/general/rtl/StdRtlPkg.vhd",
    "base/general/rtl/TextUtilPkg.vhd",
    "base/general/rtl/ArbiterPkg.vhd",
    "axi/axi4/rtl/AxiPkg.vhd",
    "axi/axi-stream/rtl/AxiStreamPkg.vhd",
    "axi/axi-stream/rtl/AxiStreamPipeline.vhd",
    "axi/axi-stream/rtl/AxiStreamMux.vhd",
    "protocols/ssi/rtl/SsiPkg.vhd",
    "simlink/sim/RogueTcpStreamPacer.vhd",
]


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    if not shutil.which("ghdl"):
        pytest.skip("GHDL is required")
    build = tmp_path_factory.mktemp("eth_bandwidth")

    def command(*args):
        result = subprocess.run(["ghdl", *args], cwd=build, text=True,
                                capture_output=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr

    command("-i", *FLAGS, "--work=surf", *[str(SURF / f) for f in SOURCES])
    command("-i", *FLAGS, "--work=warm_tdm",
            str(ROOT / "firmware/common/warm_tdm/sim/EthSimBandwidth.vhd"))
    command("-i", *FLAGS, str(HERE / "EthSimBandwidthTb.vhd"))
    command("-m", *FLAGS, "EthSimBandwidthTb")
    return build


@pytest.mark.parametrize("eth10g", [False, True], ids=["1G", "10G"])
def test_bandwidth(compiled, eth10g):
    from cocotb_tools.config import lib_name_path
    import find_libpython

    name = "10g" if eth10g else "1g"
    log = compiled / f"{name}.log"
    results = compiled / f"{name}.xml"
    env = dict(os.environ, LIBPYTHON_LOC=find_libpython.find_libpython(),
               PYGPI_PYTHON_BIN=sys.executable, PYTHONPATH=str(HERE),
               COCOTB_TOPLEVEL="ethsimbandwidthtb", COCOTB_TEST_MODULES="bandwidth_cocotb",
               TOPLEVEL_LANG="vhdl", COCOTB_RESULTS_FILE=str(results),
               ETH_10G=str(int(eth10g)))
    with log.open("w") as stream:
        process = subprocess.Popen([
            "ghdl", "-r", *FLAGS, "EthSimBandwidthTb",
            f"-gETH_10G_G={str(eth10g).lower()}",
            f"--vpi={lib_name_path('vpi', 'ghdl')}",
            "--assert-level=error", "--ieee-asserts=disable", "--stop-time=500us",
        ], cwd=compiled, stdout=stream, stderr=subprocess.STDOUT,
            start_new_session=True, env=env)
        try:
            process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            pytest.fail(f"Simulation timed out; log: {log}")
    output = log.read_text()
    assert process.returncode == 0, output
    assert results.is_file(), output
    cases = ET.parse(results).findall(".//testcase")
    assert len(cases) == 1, output
    assert not any(cases[0].find(tag) is not None
                   for tag in ("failure", "error", "skipped")), output


def test_ethcore_interfaces(compiled):
    """Analyze EthCore against real interfaces without elaborating vendor IP."""
    def analyze(path, library):
        result = subprocess.run(["ghdl", "-a", *FLAGS, f"--work={library}", str(path)],
                                cwd=compiled, text=True, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr

    analyze(ROOT / "tests/common/vhdl/unisim_vcomponents.vhd", "unisim")
    for source in ["base/general/rtl/TextUtilPkg.vhd",
                   "axi/axi-lite/rtl/AxiLitePkg.vhd",
                   "ethernet/EthMacCore/rtl/EthMacPkg.vhd",
                   "ethernet/GigEthCore/core/rtl/GigEthPkg.vhd",
                   "ethernet/TenGigEthCore/core/rtl/TenGigEthPkg.vhd",
                   "protocols/rssi/v1/rtl/RssiPkg.vhd"]:
        analyze(SURF / source, "surf")
    rtl = ROOT / "firmware/common/warm_tdm/rtl"
    analyze(rtl / "WarmTdmPkg.vhd", "warm_tdm")
    core = rtl / "EthCore.vhd"
    # Strip only architectures, leaving checked-out generic/port declarations.
    # No stand-in behavior is supplied or used to claim a system simulation.
    sources = {p.stem: p for p in SURF.rglob("*.vhd") if "rtl" in p.parts}
    sources["RogueTcpStreamWrap"] = SURF / "simlink/sim/RogueTcpStreamWrap.vhd"
    for entity in sorted(set(re.findall(r"entity surf\.(\w+)", core.read_text()))):
        text = sources[entity].read_text()
        path = compiled / f"{entity}_interface.vhd"
        path.write_text(text[:re.search(r"^architecture\b", text, re.M | re.I).start()])
        analyze(path, "surf")
    analyze(core, "warm_tdm")


@pytest.mark.parametrize("setting,expected", [
    (None, "true"), ("0", "false"), ("false", "false"), ("NO", "false"),
    ("1", "true"), ("TRUE", "true"), ("yes", "true"), ("10G", None), ("", None),
])
def test_group_selector(tmp_path, setting, expected):
    if not shutil.which("tclsh"):
        pytest.skip("Tcl is required")
    # Preserve and check unrelated simulation generics as Vivado would.
    (tmp_path / "vivado_proc.tcl").write_text("""
proc loadRuckusTcl {args} {}
proc loadSource {args} {}
proc get_filesets {name} { return $name }
set generics {EXISTING_G=1}
proc get_property {args} { return $::generics }
proc set_property {name value fileset} {
    if {$name eq "generic"} { set ::generics $value }
}
""")
    script = tmp_path / "selector.tcl"
    script.write_text(f"""
rename source tcl_source
proc source {{args}} {{ uplevel 1 [list tcl_source [lindex $args end]] }}
source {{{ROOT / 'firmware/simulations/GroupTb/ruckus.tcl'}}}
puts "GENERICS=$generics"
""")
    env = dict(os.environ, RUCKUS_DIR=str(tmp_path), TOP_DIR=str(ROOT / "firmware"),
               PROJ_DIR=str(ROOT / "firmware/simulations/GroupTb"), USE_FLOAT_PID="0",
               VARIATION_SEED="123", TES_CURRENT_SCALE="1000.0")
    env.pop("ETH_10G", None)
    if setting is not None:
        env["ETH_10G"] = setting
    result = subprocess.run(["tclsh", str(script)], text=True, capture_output=True,
                            env=env, timeout=10)
    if expected is None:
        assert result.returncode != 0
        assert "ETH_10G must be" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert f"ETH_10G_G={expected}" in result.stdout
        for generic in ("EXISTING_G=1", "USE_FLOAT_PID_G=false",
                        "VARIATION_SEED_G=123", "TES_CURRENT_SCALE_G=1000.0"):
            assert generic in result.stdout
