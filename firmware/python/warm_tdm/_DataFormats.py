import numpy as np

from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List

def signed_int(arr):
    return int.from_bytes(arr, 'little', signed=True)

def unsigned_int(arr):
    return int.from_bytes(arr, 'little', signed=False)


# --- Shared self-describing frame header -------------------------------------
#
# The 16-byte prefix on every Warm TDM bulk-data frame (readout, PID-debug
# fixed/float, waveform). This is the host-side companion to
# firmware/common/warm_tdm/rtl/FrameHeaderPkg.vhd -- the byte layout is the
# contract shared by RTL and host, so the two MUST stay in lockstep. See
# firmware/common/DataChannelization.md ("DECISION" / "Timebase").
#
# Layout (little-endian):
#   byte 0     formatType     (FormatType enum below)
#   byte 1     formatVersion  (== EXPECTED_FORMAT_VERSION; bump on any change)
#   byte 2     groupId        (reserved, 0 until the multi-Group model, #80)
#   byte 3     boardId         (source column board; cross-check channel>>4)
#   bytes 4-7  reserved       (0)
#   bytes 8-15 timestampNs    (64-bit absolute nanoseconds)

FRAME_HEADER_BYTES = 16
EXPECTED_FORMAT_VERSION = 1


class FormatType(IntEnum):
    """Frame formatType (header byte 0). Mirrors FrameHeaderPkg constants."""
    READOUT   = 0x00
    PID_FIXED = 0x01
    PID_FLOAT = 0x02
    WAVEFORM  = 0x03


FRAME_HEADER_TYPE = np.dtype([
    ('formatType', np.uint8),
    ('formatVersion', np.uint8),
    ('groupId', np.uint8),
    ('boardId', np.uint8),
    ('reserved', np.uint32),
    ('timestampNs', np.uint64),
])


@dataclass
class FrameHeader:
    """One decoded 16-byte frame-identity header. See FRAME_HEADER_TYPE."""

    formatType: int
    formatVersion: int
    groupId: int
    boardId: int
    timestampNs: int

    @classmethod
    def from_numpy(cls, arr):
        """Parse the header from the first 16 bytes of a frame's uint8 array."""
        rec = arr[:FRAME_HEADER_BYTES].view(FRAME_HEADER_TYPE)[0]
        return cls(
            formatType = int(rec['formatType']),
            formatVersion = int(rec['formatVersion']),
            groupId = int(rec['groupId']),
            boardId = int(rec['boardId']),
            timestampNs = int(rec['timestampNs']))


@dataclass
class DataSample:

    row: int
    col: int
    value: int

    @classmethod
    def from_numpy(cls, arr):
        return cls(
            row = arr[4],
            col = arr[5],
            value = arr[0:4].view(np.float32)[0])

@dataclass
class DataReadout:

    readoutCount: int
    rowSeqCount: int
    runTime: int
    samples: List[DataSample] = field(default_factory=list)

    @classmethod
    def from_numpy(cls, arr):
        #print(arr)
        words = arr[:-8].reshape(-1, 8)
        #print(words)
        return cls(
            readoutCount = unsigned_int(words[0]),
            rowSeqCount = unsigned_int(words[1]),
            runTime = unsigned_int(words[2]),
            samples = [DataSample.from_numpy(w) for w in words[3:]])


# PID-debug frame: one 80-byte record per (col, row) servo visit, streamed on
# DataWriter channels 0-7 (one channel per column) when AdcDsp[col].PidDebugEnable
# is set. This is the canonical binary layout -- it mirrors the AdcDsp PID debug
# word packing (see firmware AdcDsp.vhd and _PidDebugger.py). Decode a frame's raw
# uint8 array with ``arr.view(PID_DEBUG_TYPE)``; fields:
#   accumError     P-term (proportional accumulated error)
#   sumAccumError  I-term (integral)
#   diffAccumError D-term (derivative)
#   pidResult      combined PID output (int64)
#   sq1FbStart/End SQ1FB DAC code before/after this visit's PID update
#   numFluxJumps   flux-jump count applied this visit
#   baseline       tracked baseline
#   dropCount      dropped-frame counter
#   numSamples     samples averaged this readout
#   readoutCount   monotonic readout index (time axis)
PID_DEBUG_FRAME_BYTES = 80

PID_DEBUG_TYPE = np.dtype([
    # Word 0
    ('col', np.uint8),
    ('row', np.uint8),
    ('runTimeLow', np.uint16),
    ('runTimeHigh', np.uint32),
    # Word 1
    ('baseline', np.uint32),
    ('dummy1', np.uint32),
    # Word 2
    ('accumError', np.int32),       # P-term
    ('dummy2', np.uint32),
    # Word 3
    ('sq1FbStart', np.uint16),
    ('dummy3_0', np.uint16),
    ('dummy3_1', np.uint32),
    # Word 4
    ('sumAccumError', np.int32),    # I-term
    ('dummy4', np.uint32),
    # Word 5
    ('diffAccumError', np.int32),   # D-term
    ('dummy5', np.uint32),
    # Word 6
    ('pidResult', np.int64),
    # Word 7
    ('numFluxJumps', np.int8),
    ('dummy7_0', np.uint8),
    ('dummy7_1', np.uint16),
    ('dummy7_2', np.uint32),
    # Word 8
    ('sq1FbEnd', np.uint16),
    ('dummy8_0', np.uint16),
    ('dropCount', np.uint32),
    # Word 9
    ('numSamples', np.uint32),
    ('readoutCount', np.uint32),
])

# The per-(col,row) timeseries fields worth keeping from each PID-debug frame.
# (Excludes the dummy padding and the split runTime words.)
PID_DEBUG_FIELDS = (
    'accumError', 'sumAccumError', 'diffAccumError', 'pidResult',
    'sq1FbStart', 'sq1FbEnd', 'numFluxJumps', 'baseline',
    'dropCount', 'numSamples', 'readoutCount',
)


@dataclass
class PidDebug:
    """One decoded PID-debug frame (80 bytes, channels 0-7). See PID_DEBUG_TYPE."""

    col: int
    row: int
    fields: dict

    @classmethod
    def from_numpy(cls, arr):
        # view() yields a shape-(1,) structured array; take element 0 to get the
        # record scalar whose fields are numpy scalars (.item() -> python int).
        rec = arr.view(PID_DEBUG_TYPE)[0]
        return cls(
            col = int(rec['col']) & 0b111,
            row = int(rec['row']) & 0xFF,
            fields = {k: rec[k].item() for k in PID_DEBUG_FIELDS})


# Floating-point PID-debug frame: one 40-byte record per (col, row) servo visit,
# emitted by the AdcDspFp path (float PID firmware, USE_FLOAT_PID_G) on the same
# PID-debug channels 0-7. This is a DIFFERENT layout from the 80-byte fixed-point
# PID_DEBUG_TYPE above -- shorter, and the PID terms are IEEE-754 float32 rather
# than fixed-point ints. It mirrors the AdcDspFp PID debug word packing (see
# firmware AdcDspFp.vhd and _PidDebuggerFp.py register decode). Decode a frame's
# raw uint8 array with ``arr.view(PID_DEBUG_FP_TYPE)``; fields:
#   accumErrorFp   P-term (float)
#   sq1FbFullFp    full-precision SQ1FB feedback (float)
#   sumAccumFp     I-term / accumulated integral (float)
#   newSumAccum    updated integral after this visit (float)
#   sq1FbNewFp     new SQ1FB feedback this visit (float)
#   numFluxJumps   flux-jump count applied this visit
#   sq1FbInt       SQ1FB DAC code (uint14) actually written
#   accumSamples   samples averaged this readout
#   dropCount      dropped-frame counter
PID_DEBUG_FP_FRAME_BYTES = 40

PID_DEBUG_FP_TYPE = np.dtype([
    # Word 0
    ('col', np.uint8),
    ('row', np.uint8),
    ('runTimeLow', np.uint16),
    ('runTimeHigh', np.uint32),
    # Word 1
    ('accumErrorFp', np.float32),
    ('sq1FbFullFp', np.float32),
    # Word 2
    ('sumAccumFp', np.float32),
    ('newSumAccum', np.float32),
    # Word 3
    ('sq1FbNewFp', np.float32),
    ('numFluxJumps', np.int32),
    # Word 4
    ('sq1FbInt', np.uint16),
    ('accumSamples', np.uint8),
    ('pad4', np.uint8),
    ('dropCount', np.uint32),
])

# Timeseries fields worth keeping from each FP PID-debug frame (excludes padding
# and the split runTime words).
PID_DEBUG_FP_FIELDS = (
    'accumErrorFp', 'sq1FbFullFp', 'sumAccumFp', 'newSumAccum', 'sq1FbNewFp',
    'numFluxJumps', 'sq1FbInt', 'accumSamples', 'dropCount',
)


@dataclass
class PidDebugFp:
    """One decoded floating-point PID-debug frame (40 bytes, channels 0-7).

    See PID_DEBUG_FP_TYPE. Distinct from the 80-byte fixed-point PidDebug; select
    by frame size (len == PID_DEBUG_FP_FRAME_BYTES).
    """

    col: int
    row: int
    fields: dict

    @classmethod
    def from_numpy(cls, arr):
        rec = arr.view(PID_DEBUG_FP_TYPE)[0]
        return cls(
            col = int(rec['col']) & 0b111,
            row = int(rec['row']) & 0xFF,
            fields = {k: rec[k].item() for k in PID_DEBUG_FP_FIELDS})


# Waveform-capture frame: raw ADC samples for one capture, streamed on the
# waveform stream (file stream type 8). Layout mirrors the live decode in
# _WaveformCapture.WaveformCaptureReceiver.process(): the frame is a uint16 word
# array whose header word 0 (low nibble) is the capture channel (0-7, or >=8 for
# an all-channel interleaved capture) and word 1 is the decimation; ADC samples
# start at word 8 as int16, with the low 2 bits of each sample carrying markers
# (so the ADC value is sample // 4). This is the offline/file decoder companion
# to that live receiver -- decode a frame's raw uint8 array with
# WaveformReadout.from_numpy(arr).
WAVEFORM_HEADER_WORDS = 8

@dataclass
class WaveformReadout:
    """One decoded waveform-capture frame (file stream 8). See the module note."""

    channel: int      # capture channel; >=8 means all-channel interleaved
    decimation: int
    adcs: np.ndarray  # int16 ADC values (markers already stripped)
    markers: np.ndarray  # low-2-bit marker per sample

    @classmethod
    def from_numpy(cls, arr):
        words = arr.view(np.uint16)
        channel = int(words[0] & 0b1111)
        decimation = int(words[1])
        raw = words[WAVEFORM_HEADER_WORDS:].view(np.int16)
        markers = raw & 0x3
        adcs = raw // 4
        # For an all-channel capture the samples are interleaved 8-wide.
        if channel >= 8 and adcs.size % 8 == 0:
            adcs = adcs.reshape(-1, 8)
            markers = markers.reshape(-1, 8)
        return cls(channel=channel, decimation=decimation, adcs=adcs, markers=markers)

