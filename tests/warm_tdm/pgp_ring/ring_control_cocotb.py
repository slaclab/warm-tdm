#-----------------------------------------------------------------------------
# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of Warm TDM, including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in LICENSE.txt.
#-----------------------------------------------------------------------------
# Test methodology:
# - DUT: Thin VHDL fixtures instantiate production ring/PGP logic and flatten
#   records; delayed sidebands and an unthrottled PHY model exclude vendor GTX.
# - Sweep: 2/3/8 boards, every blocked sink, RX depths 8/10 and queued bursts.
# - Stimulus: Independent packet encodings, stalled sinks, missing tails, link
#   loss, incompatible peers, runtime reset and changes to native PGP status.
# - Checks: Payload order, SSI sidebands, pause clearing, admission, loss recovery
#   and bounded status latency. Overflow is required only in forced-loss cases.
# - Timing: Drive on falling edges; sample transfers before rising-edge TPD
#   updates. Finite sources are awaited; the entrypoint owns lifetime monitors.
"""Cocotb stimulus and independent checks for the ring integration fixtures."""
import json
import os

import cocotb
from cocotb.handle import Immediate
from cocotb.triggers import FallingEdge, RisingEdge, Timer

FIELDS = {"Data": 64, "Keep": 8, "User": 16, "Dest": 8,
          "Last": 1, "Valid": 1, "Ready": 1}
ABORT = 0x52494E47000000F0
ABORT_MASK = 0xFFFFFFFFFFF8FEFF
PAYLOAD = 0x123456789ABCDEF0
DRIVEN = {}


def value(handle):
    return int(handle.value)


class Stream:
    """One lane of a flattened stream; SSI has two user bits per byte."""

    def __init__(self, dut, prefix, lane=0):
        self.handles = {key: getattr(dut, (prefix + key).lower()) for key in FIELDS}
        self.lane = lane

    def get(self, field):
        width = FIELDS[field]
        return (value(self.handles[field]) >> (width * self.lane)) & ((1 << width) - 1)

    def set(self, field, data):
        width = FIELDS[field]
        handle = self.handles[field]
        shift = width * self.lane
        # Share intended input values across lane drivers; GHDL deposits need
        # a delta before readback, so reading the signal would lose lane writes.
        current = DRIVEN.get(handle._path, 0)
        DRIVEN[handle._path] = ((current & ~(((1 << width) - 1) << shift)) |
                               (data << shift))
        handle.value = Immediate(DRIVEN[handle._path])

    def drive(self, data=0, keep=255, user=0, dest=0, last=0, valid=1):
        for field, item in zip(("Data", "Keep", "User", "Dest", "Last", "Valid"),
                               (data, keep, user, dest, last, valid)):
            self.set(field, item)

    def snapshot(self):
        return tuple(self.get(field) for field in FIELDS if field != "Ready")

    @property
    def eofe(self):
        last_byte = self.get("Keep").bit_length() - 1
        return (self.get("User") >> (2 * max(last_byte, 0))) & 1

    async def send(self, clk, **word):
        # Observe the ready that accepts this beat, before the next registered
        # state changes it. Keep all fields stable until that sampling edge.
        await FallingEdge(clk)
        self.drive(**word)
        for _ in range(65536):
            await RisingEdge(clk)
            if self.get("Ready"):
                return
        raise AssertionError(f"Stream lane {self.lane} stalled for 65536 clocks: {self.snapshot()}")

    async def idle(self, clk):
        await FallingEdge(clk)
        self.set("Valid", 0)


def initialize(dut, inputs, outputs, lanes=1):
    for prefix in inputs:
        for field in FIELDS:
            if field != "Ready":
                getattr(dut, (prefix + field).lower()).value = Immediate(0)
        for lane in range(lanes):
            Stream(dut, prefix, lane).drive(valid=0)
    for prefix in outputs:
        for lane in range(lanes):
            Stream(dut, prefix, lane).set("Ready", 1)


async def flow(dut, case, tasks):
    boards = case["BOARDS_G"]
    dut.good.value = (1 << boards) - 1
    dut.legacy.value = 0
    dut.localpauseflat.value = 0

    def expect(pause):
        assert value(dut.pauseflat) == sum(pause << (2 * i) for i in range(boards))

    # The fixture resets its nodes; injection must stay paused until a healthy
    # return is qualified and the coordinator's release traverses the ring.
    await Timer(80, unit="ns")
    expect(3)
    await Timer(8, unit="us")
    expect(0)
    assert value(dut.addressflat) == sum(i << (3 * i) for i in range(boards))
    # Assert and clear each VC at each board, then overlap independent pressure.
    for board in range(boards):
        for vc in range(2):
            dut.localpauseflat.value = 1 << (board * 2 + vc)
            await Timer(4, unit="us")
            expect(1 << vc)
            dut.localpauseflat.value = 0
            await Timer(4, unit="us")
            expect(0)
    dut.localpauseflat.value = 1 | (2 << (2 * (boards - 1)))
    await Timer(4, unit="us")
    expect(3)
    dut.localpauseflat.value = 0
    await Timer(4, unit="us")
    expect(0)
    # Broken links and legacy peers must inhibit injection, then recover after
    # their health/protocol advertisement is restored.
    dut.good.value = (1 << (boards - 1)) - 1
    await Timer(4, unit="us")
    expect(3)
    dut.good.value = (1 << boards) - 1
    await Timer(8, unit="us")
    expect(0)
    dut.legacy.value = 1
    await Timer(4, unit="us")
    expect(3)
    dut.legacy.value = 0
    await Timer(8, unit="us")
    expect(0)


async def router(dut, case, tasks):
    initialize(dut, ["rx", "appTx"], ["tx", "appRx"])
    dut.rst.value = 1
    dut.pause.value = 0
    dut.rxgood.value = 1
    rx, tx, app_rx, app_tx = [Stream(dut, p) for p in ("rx", "tx", "appRx", "appTx")]
    counts = dict(errors=0, good=0, forwarded=0, markers=0)

    async def monitor():
        """Lifetime agent: check router outputs until entrypoint cleanup."""
        held = None
        while True:
            await RisingEdge(dut.clk)
            if value(dut.rst):
                held = None
                continue
            if held is not None:
                assert tx.snapshot() == held, "TX changed while stalled"
            held = tx.snapshot() if tx.get("Valid") and not tx.get("Ready") else None
            if app_rx.get("Valid") and app_rx.get("Ready") and app_rx.get("Last"):
                if app_rx.eofe:
                    counts["errors"] += 1
                else:
                    counts["good"] += 1
                    assert app_rx.get("Data") == PAYLOAD
                    assert app_rx.get("User") & 2, "Fresh frame lost SOF"
            if tx.get("Valid") and tx.get("Ready") and tx.get("Last"):
                if tx.get("Data") & ABORT_MASK == ABORT:
                    counts["markers"] += 1
                    assert not tx.get("Data") & 0x100
                else:
                    counts["forwarded"] += 1

    tasks.append(cocotb.start_soon(monitor()))

    async def send(**word):
        await rx.send(dut.clk, **word)
        await rx.idle(dut.clk)

    async def head(dest):
        # Packetizer v2: version[3:0], destination[23:16], SOF[63].
        await send(data=2 | (dest << 16) | (1 << 63), user=2)

    async def tail(eof=1):
        # Tail: valid payload-byte count[19:16], application EOF[8].
        await send(data=(8 << 16) | (eof << 8), last=1)

    async def marker(first):
        await send(data=ABORT | (first << 8), user=2, last=1)

    await Timer(80, unit="ns")
    dut.rst.value = 0
    await Timer(5, unit="us")
    # A new SOF must close a missing-tail frame before delivering the next one.
    await head(0x10)
    await send(data=PAYLOAD)
    await head(0x10)
    await send(data=PAYLOAD)
    await tail()
    await Timer(200, unit="ns")
    assert counts["errors"] == 1 and counts["good"] == 1, counts
    # Leave two application contexts open, then abort while the link recovers.
    for dest in (0x10, 0x20):
        await head(dest)
        await send(data=PAYLOAD)
        await tail(eof=0)
    dut.rxgood.value = 0

    async def restore_link():
        await Timer(10, unit="us")
        dut.rxgood.value = 1

    restore = cocotb.start_soon(restore_link())
    tasks.append(restore)
    await marker(1)
    await restore
    await Timer(200, unit="ns")
    assert counts["errors"] == 3 and counts["markers"] == 1, counts
    await marker(0)
    await Timer(200, unit="ns")
    assert counts["errors"] == 3 and counts["markers"] == 1, counts
    await head(0x10)
    await send(data=PAYLOAD)
    await tail()
    await Timer(200, unit="ns")
    assert counts["good"] == 2, counts
    # An incomplete local packet cannot block transit. Pause blocks admission
    # once the local packet completes, but cannot interrupt an admitted packet.
    await app_tx.send(dut.clk, dest=1, user=2)
    await app_tx.idle(dut.clk)
    dut.pause.value = 1
    await head(0x12)
    await send(data=PAYLOAD)
    await tail()
    await Timer(200, unit="ns")
    assert counts["forwarded"] == 1 and not tx.get("Valid"), counts
    await app_tx.send(dut.clk, dest=1, last=1)
    await app_tx.idle(dut.clk)
    await Timer(300, unit="ns")
    assert counts["forwarded"] == 1 and not tx.get("Valid"), counts
    dut.pause.value = 0
    # Stall before the first beat is consumed, then assert pause mid-packet.
    tx.set("Ready", 0)
    for _ in range(1024):
        if tx.get("Valid"):
            break
        await FallingEdge(dut.clk)
    assert tx.get("Valid"), "Local packet was not admitted after pause cleared"
    dut.pause.value = 1
    await Timer(80, unit="ns")
    tx.set("Ready", 1)
    await Timer(300, unit="ns")
    assert counts["forwarded"] == 2, counts

    # Reset with an admitted but stalled packet. Both ends share reset, which
    # cancels pending valid; the next RX frame must have a clean context.
    dut.pause.value = 0
    tx.set("Ready", 0)
    await app_tx.send(dut.clk, dest=1, user=2, last=1)
    await app_tx.idle(dut.clk)
    for _ in range(1024):
        if tx.get("Valid"):
            break
        await FallingEdge(dut.clk)
    assert tx.get("Valid"), "No admitted packet available for the reset check"
    dut.rst.value = 1
    await Timer(80, unit="ns")
    assert not tx.get("Valid") and not app_rx.get("Valid")
    dut.rst.value = 0
    tx.set("Ready", 1)
    await Timer(5, unit="us")
    await head(0x10)
    await send(data=PAYLOAD)
    await tail()
    await Timer(200, unit="ns")
    assert counts["good"] == 3, counts


async def traffic(dut, case, tasks):
    boards, sink, words = case["BOARDS_G"], case["SINK_G"], case.get("WORDS_G", 128)
    initialize(dut, ["src"], ["sink"], boards)
    Stream(dut, "sink", sink).set("Ready", 0)
    counts = [0] * boards
    paused = [False] * boards
    active = False

    async def source(board):
        stream = Stream(dut, "src", board)
        for index in range(words):
            await stream.send(dut.axisclk, data=(board << 32) | index, dest=sink,
                              user=2 if index == 0 else 0, last=int(index == words - 1))
        await stream.idle(dut.axisclk)

    async def monitor():
        """Lifetime agent: check every sink until entrypoint cleanup."""
        streams = [Stream(dut, "sink", i) for i in range(boards)]
        held = [None] * boards
        while True:
            await RisingEdge(dut.axisclk)
            for board, stream in enumerate(streams):
                if held[board] is not None:
                    assert stream.snapshot() == held[board], "RX changed while stalled"
                held[board] = stream.snapshot() if stream.get("Valid") and not stream.get("Ready") else None
                if stream.get("Valid") and stream.get("Ready"):
                    assert board == sink, "Packet routed to wrong board"
                    source_id = stream.get("Data") >> 32
                    assert source_id < boards, "Corrupt source"
                    assert stream.get("Dest") & 7 == source_id
                    assert stream.get("Keep") == 255
                    assert stream.get("Data") & 0xFFFFFFFF == counts[source_id]
                    assert bool(stream.get("User") & 2) == (counts[source_id] == 0)
                    assert bool(stream.get("Last")) == (counts[source_id] == words - 1)
                    assert not stream.eofe
                    counts[source_id] += 1

    async def pressure_monitor():
        """Lifetime agent: record pause and forbid loss until entrypoint cleanup."""
        while True:
            await RisingEdge(dut.clk)
            if active:
                assert value(dut.overflow) == 0, "Ring RX overflow"
                for board in range(boards):
                    paused[board] |= bool(value(dut.pauseflat) & (1 << (board * 2)))

    tasks.extend([cocotb.start_soon(monitor()), cocotb.start_soon(pressure_monitor())])
    # Train the status chain, then offer one frame from every node to a blocked
    # sink. All sources must eventually observe pressure without receive loss.
    await Timer(30, unit="us")
    assert value(dut.pauseflat) == 0
    active = True
    sources = [cocotb.start_soon(source(i)) for i in range(boards)]
    tasks.extend(sources)
    await Timer(30, unit="us")
    assert all(paused), paused
    # Release the sink and require every source's exact ordered payload. Pause
    # must clear after draining even if no additional packets are sent.
    Stream(dut, "sink", sink).set("Ready", 1)
    for _ in range(350):
        await Timer(1, unit="us")
        if counts == [words] * boards:
            break
    assert counts == [words] * boards, counts
    for task in sources:
        await task
    await Timer(25, unit="us")
    assert value(dut.pauseflat) == 0, "Pause stuck after draining"


async def recovery(dut, case, tasks):
    initialize(dut, ["src"], ["sink"])
    src, sink = Stream(dut, "src"), Stream(dut, "sink")
    sink.set("Ready", int(not case["STALL_G"]))
    counts = dict(bytes=0, frames=0, overflow=0, eofe=0, probes=0, probe_words=0)
    recovering = False

    async def pressure_monitor():
        """Lifetime agent: count receive loss until entrypoint cleanup."""
        while True:
            await RisingEdge(dut.clk)
            if value(dut.rst) == 0:
                counts["overflow"] += value(dut.overflow)

    async def monitor():
        """Lifetime agent: check termination and fresh probes until cleanup."""
        pending = 0
        valid_probe = False
        while True:
            await RisingEdge(dut.ethclk)
            if sink.get("Valid") and sink.get("Ready"):
                size = sink.get("Keep").bit_count()
                counts["bytes"] += size
                if pending == 0:
                    valid_probe = recovering and bool(sink.get("User") & 2)
                valid_probe &= (sink.get("Data") == (0x12345678 << 32) | (pending // 8)
                                and size == 8)
                pending += size
                if recovering and sink.get("Data") >> 32 == 0x12345678:
                    counts["probe_words"] += 1
                if sink.get("Last"):
                    counts["frames"] += 1
                    counts["eofe"] += sink.eofe
                    if recovering and pending == 32 and valid_probe and not sink.eofe:
                        counts["probes"] += 1
                    pending = 0

    tasks.extend([cocotb.start_soon(monitor()), cocotb.start_soon(pressure_monitor())])
    # Send read-sized replies through the unthrottled PHY. The chosen depth,
    # frame count and sink stall select either forced overflow or a lossless run.
    await Timer(10, unit="us")
    frames = case["FRAMES_G"]
    for _ in range(frames):
        for index in range(4120 // 8):
            await src.send(dut.clk, data=index, dest=0x18, user=2 if index == 0 else 0,
                           last=int(index == 4120 // 8 - 1))
        await src.idle(dut.clk)
    await Timer(2, unit="us")
    # Release away from the sink sampling edge, including its fractional clock.
    await FallingEdge(dut.ethclk)
    sink.set("Ready", 1)
    await Timer(20, unit="us")
    # Overflow cases must actually force loss; otherwise recovery went untested.
    expect_loss = case["STALL_G"] and (case["RX_DEPTH_G"] == 8 or frames >= 3)
    assert bool(counts["overflow"]) == expect_loss, counts
    if counts["overflow"]:
        assert counts["eofe"] > 0, "Damaged frame was not terminated before fresh traffic"
    # Fresh traffic follows the recovery check; it cannot supply a missing tail
    # or trigger the abort that the preceding assertion requires on its own.
    recovering = True
    for _ in range(3):
        for index in range(4):
            await src.send(dut.clk, data=(0x12345678 << 32) | index, dest=0x18,
                           user=2 if index == 0 else 0, last=int(index == 3))
        await src.idle(dut.clk)
        await Timer(3, unit="us")
    if not counts["overflow"]:
        assert counts["bytes"] == 4120 * frames + 96 and counts["frames"] == frames + 3, counts
    assert counts["probe_words"] == 12 and counts["probes"] == 3, counts


async def pgp_status(dut, case, tasks):
    initialize(dut, ["src"], ["sink"], 2)
    dut.locdata.value = 0
    dut.pressure.value = 0
    enabled = True
    words = [0, 0]

    async def source(vc):
        stream = Stream(dut, "src", vc)
        while enabled:
            for index in range(64):
                await stream.send(dut.clk, data=index + vc * 256, keep=3,
                                  user=2 if index == 0 else 0, last=int(index == 63))
        await stream.idle(dut.clk)

    async def monitor():
        """Lifetime agent: check native PGP errors/progress until cleanup."""
        streams = [Stream(dut, "sink", vc) for vc in range(2)]
        while True:
            await RisingEdge(dut.clk)
            if value(dut.rst) == 0:
                assert not value(dut.cellerror) and not value(dut.frameerror)
                for vc, stream in enumerate(streams):
                    words[vc] += stream.get("Valid")

    tasks.append(cocotb.start_soon(monitor()))
    # Allow digital PGP link training before timing its native status path.
    for _ in range(200):
        await Timer(1, unit="us")
        if value(dut.txgood) and value(dut.rxgood):
            break
    assert value(dut.txgood) and value(dut.rxgood), "PGP did not train"
    sources = [cocotb.start_soon(source(vc)) for vc in range(2)]
    tasks.extend(sources)
    max_cycles = 0
    # Measure changing status at varied phases, first with both VCs busy and
    # then idle. The same 64-clock bound must hold in both modes.
    for mode in range(2):
        if mode:
            enabled = False
            for task in sources:
                await task
            await Timer(10, unit="us")
        before = words.copy()
        for phase in range(64):
            for _ in range(phase % 17 + 1):
                await RisingEdge(dut.clk)
            await FallingEdge(dut.clk)
            data, pressure = phase + mode * 64, 3 if phase % 2 == 0 else 0
            dut.locdata.value = data
            dut.pressure.value = pressure
            for elapsed in range(64):
                await RisingEdge(dut.clk)
                if value(dut.rxdata) == data and value(dut.rxpause) == pressure:
                    break
            else:
                raise AssertionError("PGP status exceeded 64-clock hop budget before GTX")
            max_cycles = max(max_cycles, elapsed)
        if not mode:
            assert all(words[vc] > before[vc] for vc in range(2))
    dut._log.info("Maximum digital status latency = %d clocks", max_cycles)


@cocotb.test(timeout_time=1200, timeout_unit="us")
async def ring_control(dut):
    DRIVEN.clear()
    case = json.loads(os.environ["RING_CASE"])
    tests = {"RingFlowControlTb": flow, "RingRouterControlTb": router,
             "RingTrafficControlTb": traffic, "RingRecoveryControlTb": recovery,
             "RingPgpStatusControlTb": pgp_status}
    tasks = []
    try:
        await tests[case["bench"]](dut, case, tasks)
        # Surface failures from any finite task before terminating its owner.
        for task in tasks:
            if task.done():
                task.result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
