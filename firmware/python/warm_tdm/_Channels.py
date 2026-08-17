##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
##
## Canonical DataWriter file-channel encoding — the single source of truth for
## which stream a given file channel carries, shared by the write side
## (warm_tdm._HardwareGroup, which wires board streams onto DataWriter channels)
## and the read side (warm_tdm_api.operations.streamreader, which demuxes them).
##
## This module lives in the lower-level ``warm_tdm`` package on purpose: the
## write side is in ``warm_tdm`` and must not import the higher-level
## ``warm_tdm_api``, while the read side already imports ``warm_tdm``. Defining
## the encoding here lets both sides share ONE definition rather than duplicating
## the channel numbers (see firmware/common/DataChannelization.md, "Keep the
## channel scheme in one place").
##
## ----------------------------------------------------------------------------
## Two DISTINCT namespaces -- do not conflate them:
##
##   1. On-wire TDEST (RSSI/PGP stream). An 8-bit field the FIRMWARE and the
##      transport demux use, set in RTL (RingRouter tags tDest[6:4] = board ring
##      address; DataPath sets tDest[3:0] = stream type). The host splits it in
##      two stages: UdpRssiPack.application(dest=board) peels the high nibble,
##      then packetizer.application(stream) peels the low nibble. By the time we
##      reach the code below, the TDEST has already been consumed -- board
##      identity is known from WHICH per-board demux the frame came out of, and
##      stream identity from WHICH packetizer app.
##
##   2. File channel (DataWriter). A 1-byte field the SOFTWARE writes into the
##      .dat file so a single interleaved file can be demuxed back offline. This
##      is what file_channel()/board_of()/stream_of() below encode, and what
##      DataWriter.getChannel(...) takes.
##
## These are separate fields on separate layers. We DELIBERATELY give the file
## channel the same board<<4 | stream_type layout as the wire TDEST so the two
## are trivially cross-checkable (a reader can assert body.boardId == channel>>4)
## and so there is one mental model to hold -- but that equality is a design
## choice made here, NOT an inherent property. Nothing forces the file channel to
## match the wire TDEST; this module is the single place that decides it does.
## ----------------------------------------------------------------------------
##
## The file-channel byte layout:
##
##     file_channel[7:4] = source column board (matches PGP ring address)
##     file_channel[3:0] = stream type within that board
##
## i.e. ``file_channel = board * 16 + stream_type``. An 8-bit channel therefore
## addresses 16 boards x 16 stream types. Board 0 is byte-identical to the
## historical single-board layout (PID-debug 0-7, waveform 8, readout 9), so
## files written by a single-board system decode unchanged; the board index only
## matters once a second column board is present.
##
## NOTE (relic, do not renumber): the operational readout sits at stream type 9,
## ABOVE the eight debug channels 0-7. This is a development-order artifact that
## is now a wire/format contract. The board-namespacing scheme is built around
## keeping stream type 9 = readout.

# Stream types within a board (the low nibble of the file channel / TDEST).
PID_DEBUG_STREAMS = range(0, 8)   # one per column channel (0-7)
WAVEFORM_STREAM   = 8             # raw ADC waveform capture
READOUT_STREAM    = 9             # operational per-(col,row) readout

# Bits allocated to the stream-type nibble. board = channel >> STREAM_BITS.
STREAM_BITS = 4
STREAM_MASK = (1 << STREAM_BITS) - 1   # 0x0F

# Reserved whole-byte channel for the tree config/status YAML dump that the
# DataWriter writes on file open/close (see warm_tdm_api._GroupRoot). It is not
# board-namespaced: it is a single file-scope channel. 255 = board 15, stream 15
# under the encoding, which no real (board, stream) pair reaches, so it stays
# clear of the namespaced range.
CONFIG_CHANNEL = 255


def file_channel(board, stream_type):
    """Return the DataWriter file channel for a board's stream.

    ``file_channel = board * 16 + stream_type`` — the wire-mirroring encoding.

    Args:
        board (int): source column board index (0-15).
        stream_type (int): stream type within the board (0-15); use the
            ``PID_DEBUG_STREAMS`` / ``WAVEFORM_STREAM`` / ``READOUT_STREAM``
            constants.

    Returns:
        int: the file channel (0-255).
    """
    if not 0 <= board <= 0x0F:
        raise ValueError(f'board {board} out of range 0..15')
    if not 0 <= stream_type <= STREAM_MASK:
        raise ValueError(f'stream_type {stream_type} out of range 0..15')
    return (board << STREAM_BITS) | stream_type


def board_of(channel):
    """Return the source board index encoded in a file channel."""
    return channel >> STREAM_BITS


def stream_of(channel):
    """Return the stream type encoded in a file channel."""
    return channel & STREAM_MASK


def is_pid_debug(channel):
    """True if the channel carries a PID-debug stream (any board)."""
    return channel != CONFIG_CHANNEL and stream_of(channel) in PID_DEBUG_STREAMS


def is_waveform(channel):
    """True if the channel carries a waveform stream (any board)."""
    return channel != CONFIG_CHANNEL and stream_of(channel) == WAVEFORM_STREAM


def is_readout(channel):
    """True if the channel carries the operational readout stream (any board)."""
    return channel != CONFIG_CHANNEL and stream_of(channel) == READOUT_STREAM
