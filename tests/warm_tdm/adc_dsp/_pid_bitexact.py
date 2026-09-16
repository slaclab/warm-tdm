# Shared stimulus + capture harness for the AdcDsp bit-exact re-qualification
# (whole-path captured-golden approach; see docs/plans/pid-cosim-verification/).
#
# The accumulator split moved the ADC accumulation out of AdcDsp into
# AdcAccumulator. To prove the move is behavior-preserving we drive the SAME
# scripted raw-ADC + timing stimulus into two DUTs that expose an identical
# cocotb port set:
#   * the pre-split AdcDsp (capture bench) -> records a golden of its mAxil
#     SQ1-FB-DAC write transactions, and
#   * the current AdcAccumulator + AdcDsp (compare bench) -> must reproduce that
#     exact write sequence.
#
# The mAxil writes are observed through the wrapper's AxiDualPortRam sink
# sideband (DAC_WR_VALID / DAC_WR_ADDR / DAC_WR_DATA): one write per enabled row,
# addr = rowIndex, data(13:0) = offset-binary sq1Fb. Keeping the stimulus and the
# monitor here (one source) guarantees both benches drive bit-identical inputs.
# The later retained-feedback implementation intentionally changes subsequent
# visits that force an external DAC value without clearing controller state.
# Its compare test declares those new expectations explicitly; the frozen
# pre-split RTL and golden remain historical evidence for the accumulator split.

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge
from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from firmware.submodules.surf.tests.axi.utils import axil_read_u32, axil_write_u32


# AdcDsp local AXI-Lite register map (identical old vs current; see AdcDsp.vhd
# comb process, LOCAL crossbar master at offset 0x000).
REG_CONTROL       = 0x0000  # bit0 = fllEnable, bit8 = outputMode, bit16 = accumShift
REG_P_COEF        = 0x0004
REG_I_COEF        = 0x0008
REG_D_COEF        = 0x000C
REG_FLUX_QUANTUM  = 0x0040
REG_ROW_ENABLE    = 0x0060

# Read-only PID-state registers (same offsets old vs current). These reflect the
# last-processed row's registered state; read after a visit's drain they expose
# that visit's accumError / integrator / result / feedback for diagnosis.
REG_ACCUM_ERROR      = 0x0010
REG_LAST_ACCUM_ERROR = 0x0014
REG_SUM_ACCUM        = 0x0018
REG_PID_RESULT       = 0x0020
REG_SQ1FB            = 0x0028

FLL_ENABLE_MASK = 0x00000001

# LocalTimingType flattened layout. The pre-split and current TimingPkg records
# have identical bit layout (259 bits, same field order/widths); only field
# names differ (rowIndex->logicalRow, runTime->runTimeNs, rowIndexNext->
# nextLogicalRow). So one packer serves both benches.
TIMING_FIELD_LAYOUT = {
    "startRun": (0, 1),
    "endRun": (1, 1),
    "running": (2, 1),
    "runTime": (3, 64),
    "rowStrobe": (67, 1),
    "rowSeqStart": (68, 1),
    "daqReadoutStart": (69, 1),
    "sample": (70, 1),
    "firstSample": (71, 1),
    "lastSample": (72, 1),
    "stageNextRow": (73, 1),
    "rowSeq": (74, 8),
    "rowIndex": (82, 8),
    "rowIndexNext": (90, 8),
    "rowTime": (98, 32),
    "rowSeqCount": (130, 64),
    "daqReadoutCount": (194, 64),
    "waveformCapture": (258, 1),
}


def _mask(width: int) -> int:
    return (1 << width) - 1


def _pack_timing(**fields: int) -> int:
    word = 0
    for name, (offset, width) in TIMING_FIELD_LAYOUT.items():
        value = fields.get(name, 0)
        word |= (value & _mask(width)) << offset
    return word


def adc_code_to_tdata(code: int) -> int:
    """Left-justify a 14-bit two's-complement ADC code into tData(15:2)."""
    return (code & _mask(14)) << 2


# ----------------------------------------------------------------------------
# Deterministic stimulus definition (the single source of truth for both benches)
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class RowVisit:
    row: int
    adc_code: int          # constant 14-bit two's-complement ADC code for the row
    num_samples: int = 16  # ADC beats accumulated in the row window
    seq_start: bool = False
    sq1fb_dac: int = 0x2000  # per-visit feedback (offset binary), driven one clock
                             # AFTER this visit's rowStrobe -- see visit(). Distinct
                             # per-visit values expose a feedback-capture that reads
                             # the previous row's DAC (AdcAccumulator finding 1).


@dataclass(frozen=True)
class Stimulus:
    p_coef: int
    i_coef: int
    d_coef: int
    row_enable_mask: int
    sq1fb_dac: int                 # initial/reset feedback (offset binary) present
                                   # at the first visit's rowStrobe; per-visit values
                                   # thereafter come from RowVisit.sq1fb_dac.
    visits: list[RowVisit] = field(default_factory=list)


# Coefficients live in sfixed(0 downto -23); +1.0 is unrepresentable, so the
# largest positive coefficient is (2**23)-1.
UNIT_COEF = (1 << 23) - 1

# One fixed scenario, exercised by both benches. Three enabled rows visited over
# several sequences with distinct per-row ADC levels, so the P term responds each
# visit and the I term integrates across visits -> a varied, non-trivial sq1Fb
# trajectory and a distinct mAxil write per enabled row visit.
#
# Two coverage groups the original constant-DAC / small-error stimulus missed:
#   * per-visit DISTINCT feedback DACs -- each row's writeback base must be its OWN
#     row's feedback, not the previous visit's (AdcAccumulator finding 1);
#   * OVERFLOW visits whose accumulated (adc*beats) exceeds the signed 18-bit range
#     -- the accumError must SATURATE like the pre-split DSP, not wrap to the
#     opposite sign (AdcDsp finding 2). num_samples=250 accumulates 249 beats (the
#     firstSample cycle only transitions into ACCUMULATE), so adc_code*249 is the
#     mathematical sum; 249000 and -249000 straddle the +/-131071 rails.
STIMULUS = Stimulus(
    p_coef=UNIT_COEF // 4,
    i_coef=UNIT_COEF // 64,
    d_coef=0,
    row_enable_mask=0b111,
    sq1fb_dac=0x2000,  # offset-binary mid-scale, present at the first rowStrobe
    visits=[
        # Group A -- feedback coupling: small errors, distinct per-visit DACs.
        RowVisit(row=0, adc_code=120, seq_start=True, sq1fb_dac=0x2123),
        RowVisit(row=1, adc_code=-80, sq1fb_dac=0x2345),
        RowVisit(row=2, adc_code=40, sq1fb_dac=0x2567),
        RowVisit(row=0, adc_code=120, seq_start=True, sq1fb_dac=0x1F00),
        RowVisit(row=1, adc_code=-80, sq1fb_dac=0x2200),
        RowVisit(row=2, adc_code=40, sq1fb_dac=0x2400),
        RowVisit(row=0, adc_code=120, seq_start=True, sq1fb_dac=0x2050),
        RowVisit(row=1, adc_code=-80, sq1fb_dac=0x22A0),
        RowVisit(row=2, adc_code=40, sq1fb_dac=0x24F0),
        # Group B -- 18-bit overflow: +249000 (positive rail) then -249000.
        RowVisit(row=0, adc_code=1000, num_samples=250, seq_start=True, sq1fb_dac=0x2000),
        RowVisit(row=1, adc_code=-1000, num_samples=250, sq1fb_dac=0x2000),
    ],
)


class BitExactDriver:
    """Drives the shared cocotb port set common to both wrappers and records the
    mAxil SQ1-FB-DAC write transactions."""

    CLK_PERIOD_NS = 8

    def __init__(self, dut):
        self.dut = dut
        self.axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "S_AXIL"), dut.clk, dut.rst)
        self._timing = {"running": 1}
        self.writes: list[tuple[int, int]] = []
        self._monitor_task = None

    def _apply_timing(self, **transient: int) -> None:
        fields = dict(self._timing)
        fields.update(transient)
        self.dut.TIMING_RX_DATA.value = _pack_timing(**fields)

    async def _tick(self) -> None:
        await RisingEdge(self.dut.clk)

    async def _monitor(self) -> None:
        """Lifetime agent: record every mAxil DAC write. Runs in the read-only
        phase so it never contends with driver signal writes (which happen in the
        normal phase right after a clock edge)."""
        while True:
            await RisingEdge(self.dut.clk)
            await ReadOnly()
            if self.dut.DAC_WR_VALID.value == 1:
                addr = int(self.dut.DAC_WR_ADDR.value)
                data = int(self.dut.DAC_WR_DATA.value) & _mask(14)
                self.writes.append((addr, data))

    async def reset(self) -> None:
        cocotb.start_soon(Clock(self.dut.clk, self.CLK_PERIOD_NS, unit="ns").start())
        self.dut.rst.value = 1
        self.dut.ADC_TVALID.value = 0
        self.dut.ADC_TDATA.value = 0
        self.dut.SQ1FB_DAC.value = 0
        self._apply_timing()
        for _ in range(5):
            await self._tick()
        self.dut.rst.value = 0
        for _ in range(5):
            await self._tick()
        self._monitor_task = cocotb.start_soon(self._monitor())

    async def configure(self, stim: Stimulus) -> None:
        self.dut.SQ1FB_DAC.value = stim.sq1fb_dac
        await axil_write_u32(self.axil, REG_P_COEF, stim.p_coef)
        await axil_write_u32(self.axil, REG_I_COEF, stim.i_coef)
        await axil_write_u32(self.axil, REG_D_COEF, stim.d_coef)
        await axil_write_u32(self.axil, REG_ROW_ENABLE, stim.row_enable_mask)
        await axil_write_u32(self.axil, REG_CONTROL, FLL_ENABLE_MASK)
        # Let any coefficient-write PID-state clear finish before the first row.
        # The clear walks every pidState RAM address (2**ROW_ADDR_BITS = 128), so
        # settle well past that or the first visit's write is swallowed mid-clear.
        self._apply_timing()
        for _ in range(300):
            await self._tick()

    async def visit(self, visit: RowVisit) -> None:
        tdata = adc_code_to_tdata(visit.adc_code)
        # Hold the ADC sample stable and valid across the whole row window so the
        # accumulation window is delimited purely by firstSample/lastSample.
        self.dut.ADC_TDATA.value = tdata
        self.dut.ADC_TVALID.value = 1

        # logicalRow / rowIndex is the "row currently in effect" and must be held
        # stable for the whole visit: the pre-split AdcDsp latches it at rowStrobe,
        # but the current AdcAccumulator latches it at OUTPUT (and AdcDsp indexes
        # its per-row PID-state RAMs by it). Carry it as a persistent field.
        self._timing["rowIndex"] = visit.row

        # Row strobe: register rowIndex, reset the accumulator, latch seqStart.
        # SQ1FB_DAC still holds the PREVIOUS visit's value on this edge -- the
        # FastDacDriver only registers the new row's DAC one clock after rowStrobe.
        self._apply_timing(rowStrobe=1,
                           rowSeqStart=1 if visit.seq_start else 0)
        await self._tick()
        self._apply_timing()

        # New row's feedback becomes visible one clock after rowStrobe (as the
        # FastDacDriver drives dacOut), i.e. AFTER the edge the accumulator uses to
        # (incorrectly) latch it, and stays stable through the sample window.
        self.dut.SQ1FB_DAC.value = visit.sq1fb_dac

        # Gap before firstSample (>3 cycles for the baseline-RAM read latency).
        for _ in range(6):
            await self._tick()

        # firstSample releases WAIT_FIRST_SAMPLE_S -> ACCUMULATE_S.
        self._apply_timing(firstSample=1, sample=1)
        await self._tick()
        self._apply_timing(sample=1)

        # Accumulate num_samples-1 more beats, marking the last with lastSample.
        for n in range(visit.num_samples - 1):
            last = (n == visit.num_samples - 2)
            self._apply_timing(sample=1, lastSample=1 if last else 0)
            await self._tick()
        self._apply_timing()

        # Drain the PID pipeline + FIFO + mAxil AxiLiteMaster write.
        self.dut.ADC_TVALID.value = 0
        for _ in range(40):
            await self._tick()

    async def read_state(self) -> dict[str, int]:
        """Read the last-processed row's PID-state registers (diagnostic hook).

        Dormant by default. To localize a future bit-exact compare failure, run
        both benches with ``run(stim, collect_diag=True)`` and diff each visit's
        ``driver.diag`` entries: accumError isolates the accumulation front-end,
        sumAccum/lastAccumError the per-row integrator/derivative state, etc.
        """
        return {
            "accumError": await axil_read_u32(self.axil, REG_ACCUM_ERROR),
            "lastAccumError": await axil_read_u32(self.axil, REG_LAST_ACCUM_ERROR),
            "sumAccum": await axil_read_u32(self.axil, REG_SUM_ACCUM),
            "pidResult": await axil_read_u32(self.axil, REG_PID_RESULT),
            "sq1Fb": await axil_read_u32(self.axil, REG_SQ1FB),
        }

    async def run(self, stim: Stimulus, collect_diag: bool = False) -> list[tuple[int, int]]:
        await self.reset()
        await self.configure(stim)
        self.diag: list[dict[str, int]] = []
        for v in stim.visits:
            await self.visit(v)
            if collect_diag:
                self.diag.append(await self.read_state())
        return self.writes


# ----------------------------------------------------------------------------
# Golden file I/O
# ----------------------------------------------------------------------------

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_refs" / "presplit_dac_writes.json"


def write_golden(writes: list[tuple[int, int]]) -> None:
    payload = {
        "description": "Pre-split AdcDsp mAxil SQ1-FB-DAC write transactions "
                       "(addr, data14) captured under the shared bit-exact stimulus.",
        "writes": [[a, d] for a, d in writes],
    }
    GOLDEN_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def read_golden() -> list[tuple[int, int]]:
    payload = json.loads(GOLDEN_PATH.read_text())
    return [(a, d) for a, d in payload["writes"]]
