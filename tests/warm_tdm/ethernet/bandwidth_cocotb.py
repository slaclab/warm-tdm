#-----------------------------------------------------------------------------
# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of Warm TDM, including this file, may be copied, modified, propagated,
# or distributed except according to the terms contained in LICENSE.txt.
#-----------------------------------------------------------------------------
# Test methodology:
# - DUT: Real EthSimBandwidth, SURF mux and SimLink pacer; no socket backend.
# - Sweep: 1G/10G, single/both sockets and both full-duplex directions together.
# - Checks: Independent byte/time throughput bounds, shared budget, partial
#   final beats, payload/sideband ordering, stalls, idle credit and reset flush.
# - Timing: Drive on falling edges, sample accepting rising edges before TPD.
"""Ethernet payload bandwidth checks in simulated time, independent of wall time."""
from collections import deque
import os
import random

import cocotb
from cocotb.triggers import FallingEdge, RisingEdge

FIELDS = dict(data=64, keep=8, user=16, dest=8, last=1, valid=1)


def lanes(dut, prefix, field, width):
    packed = int(getattr(dut, prefix + field).value)
    return [(packed >> (width*i)) & ((1 << width)-1) for i in range(4)]


def drive(dut, words):
    for field, width in FIELDS.items():
        getattr(dut, "s" + field).value = sum(
            word.get(field, 0) << (width*i) for i, word in enumerate(words))


def beats(lane, lengths, seed):
    rng = random.Random(seed + lane)
    words = []
    for frame, length in enumerate(lengths):
        # Include all local/remote routes supported by the two socket wrappers.
        dest = (0, 1, 2, 0x10)[frame % 4]
        for offset in range(0, length, 8):
            count = min(8, length-offset)
            words.append(dict(data=rng.getrandbits(64), keep=(1 << count)-1,
                              user=rng.getrandbits(16), dest=dest,
                              last=int(offset+count == length), valid=1))
    return words


async def reset(dut):
    await FallingEdge(dut.clk)
    drive(dut, [{}]*4)
    dut.mready.value = 0
    dut.rst.value = 1
    for _ in range(5):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst.value = 0


async def transfer(dut, streams, *, stalled=False):
    sent = [0]*4
    received = [0]*4
    expected = [deque() for _ in range(4)]
    previous_stall = [None]*4
    first = [None]*2
    last = [None]*2
    total = [0]*2
    # Public contract: no more than one beat of idle credit, charged by valid
    # payload bytes; at 125 MHz 1G earns one byte/cycle, at 156.25 MHz 10G earns 8.
    increment = 8 if os.environ["ETH_10G"] == "1" else 1
    allowance = [8]*2
    rng = random.Random(479)
    completed = None
    for cycle in range(50000):
        await FallingEdge(dut.clk)
        drive(dut, [words[sent[i]] if sent[i] < len(words) else {}
                    for i, words in enumerate(streams)])
        ready = [True]*4
        if stalled:
            # Hold one direction blocked while the opposite direction runs,
            # then mix long pauses and independently stalled sockets.
            ready = [(i >= 2 or cycle >= 160) and rng.random() > 0.3
                     and not (400 <= cycle % 800 < 480) for i in range(4)]
        dut.mready.value = sum(int(value) << i for i, value in enumerate(ready))
        await RisingEdge(dut.clk)
        sready = lanes(dut, "s", "ready", 1)
        for i in range(4):
            if sent[i] < len(streams[i]) and sready[i]:
                expected[i].append(streams[i][sent[i]])
                sent[i] += 1
        outputs = {field: lanes(dut, "m", field, width)
                   for field, width in FIELDS.items()}
        count = [0, 0]
        for i in range(4):
            word = {field: values[i] for field, values in outputs.items()}
            if previous_stall[i] is not None:
                assert word == previous_stall[i], "AXI beat changed while stalled"
            previous_stall[i] = word if word["valid"] and not ready[i] else None
            if word["valid"] and ready[i]:
                assert expected[i], f"Unexpected beat on lane {i}: {word}"
                assert word == expected[i].popleft(), f"Corrupt/reordered lane {i}"
                received[i] += 1
                count[i//2] += word["keep"].bit_count()
                first[i//2] = cycle if first[i//2] is None else first[i//2]
                last[i//2] = cycle
        for d in range(2):
            allowance[d] = min(8, allowance[d] + increment)
            assert count[d] <= allowance[d], "Shared Ethernet payload budget exceeded"
            allowance[d] -= count[d]
            total[d] += count[d]
        if stalled and cycle == 159:
            assert total[0] == 0 and total[1] > 0, "Directions must be independent"
        if received == [len(words) for words in streams]:
            assert sent == received and not any(expected)
            if completed is None:
                completed = cycle
            if cycle - completed >= 12:
                return first, last, total
    raise AssertionError(f"Transfer timed out: sent={sent}, received={received}")


@cocotb.test()
async def bandwidth(dut):
    drive(dut, [{}]*4)
    dut.mready.value = 0
    dut.rst.value = 1
    increment = 8 if os.environ["ETH_10G"] == "1" else 1
    for shared in (False, True):
        await reset(dut)
        streams = [beats(i, [4096]*2, 12) if shared or i % 2 == 0 else []
                   for i in range(4)]
        first, last, total = await transfer(dut, streams)
        for d in range(2):
            duration = last[d] - first[d]
            measured = (total[d]-8)/duration
            assert increment*0.98 <= measured <= increment*1.001, (shared, d, measured)
        dut._log.info("shared=%s bytes=%s cycles=%s bytes/cycle=%s", shared,
                      total, [last[d]-first[d] for d in range(2)], increment)

    # Saturate idle credit, then check partial final words and stable stalls.
    await reset(dut)
    for _ in range(200):
        await RisingEdge(dut.clk)
    await transfer(dut, [beats(i, [1, 7, 8, 9, 63, 64, 65, 511]*3, 81)
                         for i in range(4)], stalled=True)

    # Reset with a pending stalled beat; none of the pre-reset data may escape.
    await reset(dut)
    await FallingEdge(dut.clk)
    drive(dut, [beats(i, [8], 91)[0] for i in range(4)])
    for _ in range(20):
        await RisingEdge(dut.clk)
    assert int(dut.mvalid.value) != 0
    await reset(dut)
    await transfer(dut, [beats(i, [9, 16, 17], 92) for i in range(4)])
