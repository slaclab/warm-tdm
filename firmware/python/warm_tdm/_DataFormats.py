import numpy as np

from dataclasses import dataclass, field
from enum import IntEnum

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


# One 8-byte readout sample word (EventBuilder DO_DATA_S packing):
#   bytes 0-3  value  (float32 SQ1FB DAC code)
#   byte  4    row    (tID)
#   byte  5    col    (GLOBAL column = boardId*8 + board-local; packed by RTL)
#   bytes 6-7  high   (high sample bits; unused by the host today)
# The whole sample block decodes as ONE structured-array view -- no per-sample
# Python object or numpy op. See DataReadout.from_numpy.
DATA_SAMPLE_TYPE = np.dtype([
    ('value', np.float32),
    ('row', np.uint8),
    ('col', np.uint8),
    ('high', np.uint16),
])

# Readout body offset: 16-byte header + daqReadoutCount(8) + rowSeqCount(8).
_READOUT_SAMPLE_OFFSET = FRAME_HEADER_BYTES + 16


@dataclass
class DataSample:

    row: int
    col: int   # global column (board*8 + board-local); the RTL packs this directly
    value: float

    @classmethod
    def from_numpy(cls, arr):
        rec = arr[:8].view(DATA_SAMPLE_TYPE)[0]
        return cls(
            row = int(rec['row']),
            col = int(rec['col']),
            value = float(rec['value']))

@dataclass
class DataReadout:
    """One decoded readout frame: 16-byte shared header + 2 structural counter
    words (daqReadoutCount, rowSeqCount) + per-sample words + a trailing 8-byte
    burnCount word. The absolute-ns timestamp lives in the header (it superseded
    the old per-frame runTime word).

    The per-sample columns/rows/values are exposed as parallel numpy arrays
    (``cols``, ``rows``, ``values``) decoded in a single structured-array view --
    iterate those for speed. ``samples`` is a lazily-built list of ``DataSample``
    for callers that prefer per-object access; it is materialized only on first
    access.

    ``burnCount`` is the RTL's run-cumulative count of readout frames dropped
    because the downstream FIFO was paused (EventBuilder.vhd). It resets on
    startRun and is snapshotted into every frame's trailer, so the value on the
    final frame of a run is the run total. A nonzero value means readout data was
    lost to backpressure -- consumers should surface it (see StreamReader).
    """

    header: 'FrameHeader'
    readoutCount: int   # daqReadoutCount
    rowSeqCount: int
    burnCount: int      # run-cumulative dropped-frame count (trailer word)
    cols: np.ndarray = field(default_factory=lambda: np.empty(0, np.uint8))
    rows: np.ndarray = field(default_factory=lambda: np.empty(0, np.uint8))
    values: np.ndarray = field(default_factory=lambda: np.empty(0, np.float32))

    @classmethod
    def from_numpy(cls, arr):
        header = FrameHeader.from_numpy(arr)
        # Header counter words follow the 16-byte identity header; the last
        # 8-byte word is the burnCount trailer (low 32 bits) the RTL appends
        # when tLast is set. The sample block in between decodes as one view.
        rec = arr[_READOUT_SAMPLE_OFFSET:-8].view(DATA_SAMPLE_TYPE)
        return cls(
            header = header,
            readoutCount = unsigned_int(arr[FRAME_HEADER_BYTES:FRAME_HEADER_BYTES+8]),
            rowSeqCount = unsigned_int(arr[FRAME_HEADER_BYTES+8:FRAME_HEADER_BYTES+16]),
            burnCount = unsigned_int(arr[-8:-4]),
            cols = rec['col'],
            rows = rec['row'],
            values = rec['value'])

    @property
    def samples(self):
        """Lazily materialize the per-sample list (compat shim over the arrays)."""
        return [DataSample(row=int(r), col=int(c), value=float(v))
                for c, r, v in zip(self.cols, self.rows, self.values)]

    @property
    def timestampNs(self):
        return self.header.timestampNs


# PID-debug frame: the 16-byte shared header + an 80-byte fixed-point body (one
# record per (col, row) servo visit), streamed on the PID-debug channels when
# AdcDsp[col].PidDebugEnable is set. PID_DEBUG_TYPE is the BODY layout (view
# ``arr[FRAME_HEADER_BYTES:].view(PID_DEBUG_TYPE)``); it mirrors the AdcDsp PID
# debug word packing (see firmware AdcDsp.vhd and _PidDebugger.py). The body's
# word-0 runTime bits are now vestigial padding -- the header timestamp is
# authoritative. Fields:
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
PID_DEBUG_BODY_BYTES = 80
PID_DEBUG_FRAME_BYTES = FRAME_HEADER_BYTES + PID_DEBUG_BODY_BYTES  # 96 (header + body)

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
    """One decoded fixed-point PID-debug frame (16-byte header + 80-byte body).

    col is board-local (0-7); the header carries boardId/groupId/timestamp. See
    PID_DEBUG_TYPE for the body layout.
    """

    header: 'FrameHeader'
    col: int
    row: int
    fields: dict

    @classmethod
    def from_numpy(cls, arr):
        header = FrameHeader.from_numpy(arr)
        # view() yields a shape-(1,) structured array; take element 0 to get the
        # record scalar whose fields are numpy scalars (.item() -> python int).
        rec = arr[FRAME_HEADER_BYTES:].view(PID_DEBUG_TYPE)[0]
        return cls(
            header = header,
            col = int(rec['col']) & 0b111,
            row = int(rec['row']) & 0xFF,
            fields = {k: rec[k].item() for k in PID_DEBUG_FIELDS})


# Floating-point PID-debug frame: the 16-byte shared header + a 40-byte float body
# (one record per (col, row) servo visit), emitted by the AdcDspFp path (float PID
# firmware, USE_FLOAT_PID_G) on the PID-debug channels. PID_DEBUG_FP_TYPE is the
# BODY layout (view ``arr[FRAME_HEADER_BYTES:].view(PID_DEBUG_FP_TYPE)``) -- a
# DIFFERENT body from the 80-byte fixed-point PID_DEBUG_TYPE (float32 PID terms).
# Mirrors the AdcDspFp PID debug word packing (see AdcDspFp.vhd /
# _PidDebuggerFp.py). Body word-0 runTime bits are vestigial (header timestamp is
# authoritative). Fields:
#   accumErrorFp   P-term (float)
#   sq1FbFullFp    full-precision SQ1FB feedback (float)
#   sumAccumFp     I-term / accumulated integral (float)
#   newSumAccum    updated integral after this visit (float)
#   sq1FbNewFp     new SQ1FB feedback this visit (float)
#   numFluxJumps   flux-jump count applied this visit
#   sq1FbInt       SQ1FB DAC code (uint14) actually written
#   accumSamples   samples averaged this readout
#   dropCount      dropped-frame counter
PID_DEBUG_FP_BODY_BYTES = 40
PID_DEBUG_FP_FRAME_BYTES = FRAME_HEADER_BYTES + PID_DEBUG_FP_BODY_BYTES  # 56 (header + body)

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
    """One decoded floating-point PID-debug frame (16-byte header + 40-byte body).

    col is board-local (0-7); the header carries boardId/groupId/timestamp. See
    PID_DEBUG_FP_TYPE for the body layout. Distinct from the fixed-point PidDebug;
    dispatch by header.formatType (PID_FLOAT vs PID_FIXED).
    """

    header: 'FrameHeader'
    col: int
    row: int
    fields: dict

    @classmethod
    def from_numpy(cls, arr):
        header = FrameHeader.from_numpy(arr)
        rec = arr[FRAME_HEADER_BYTES:].view(PID_DEBUG_FP_TYPE)[0]
        return cls(
            header = header,
            col = int(rec['col']) & 0b111,
            row = int(rec['row']) & 0xFF,
            fields = {k: rec[k].item() for k in PID_DEBUG_FP_FIELDS})


# Waveform-capture frame: the 16-byte shared header + a 16-byte config beat +
# raw ADC samples, streamed on the waveform stream (file stream type 8). The RTL
# emits, in INT_AXIS_CONFIG_C (16-byte) beats: beat 0 = shared identity header;
# beat 1 = the config word (low nibble = capture channel 0-7, or >=8 for an
# all-channel interleaved capture; bits[31:16] = decimation); then ADC samples as
# int16 with the low 2 bits carrying markers (ADC value = sample // 4). Offline/
# file companion to _WaveformCapture.WaveformCaptureReceiver.process().
WAVEFORM_CONFIG_WORD_OFFSET = FRAME_HEADER_BYTES // 2   # uint16 index of config beat
WAVEFORM_SAMPLE_WORD_OFFSET = (FRAME_HEADER_BYTES + 16) // 2  # uint16 index of first sample

@dataclass
class WaveformReadout:
    """One decoded waveform-capture frame (file stream 8). See the module note."""

    header: 'FrameHeader'
    channel: int      # capture channel; >=8 means all-channel interleaved
    decimation: int
    adcs: np.ndarray  # int16 ADC values (markers already stripped)
    markers: np.ndarray  # low-2-bit marker per sample

    @classmethod
    def from_numpy(cls, arr):
        header = FrameHeader.from_numpy(arr)
        words = arr.view(np.uint16)
        channel = int(words[WAVEFORM_CONFIG_WORD_OFFSET] & 0b1111)
        decimation = int(words[WAVEFORM_CONFIG_WORD_OFFSET + 1])
        raw = words[WAVEFORM_SAMPLE_WORD_OFFSET:].view(np.int16)
        markers = raw & 0x3
        adcs = raw // 4
        # For an all-channel capture the samples are interleaved 8-wide.
        if channel >= 8 and adcs.size % 8 == 0:
            adcs = adcs.reshape(-1, 8)
            markers = markers.reshape(-1, 8)
        return cls(header=header, channel=channel, decimation=decimation,
                   adcs=adcs, markers=markers)

