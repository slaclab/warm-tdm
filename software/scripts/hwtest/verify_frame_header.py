#!/usr/bin/env python3
##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
"""Verify the self-describing 16-byte frame header end-to-end (Issue #82, Phase 3).

This is the integrated frame-format check the design calls for (see
firmware/common/DataChannelization.md "Verification of the frame formats"):
drive the REAL data path and decode with the REAL host reader, rather than a
standalone module bench. It takes a short data run through an operations Session,
then walks the resulting .dat file record-by-record and asserts, for every bulk
frame:

  * the 16-byte header parses: formatType in {readout, pid-fixed, pid-float,
    waveform}, formatVersion == EXPECTED_FORMAT_VERSION;
  * the frame length matches the format (readout variable; pid-fixed 96;
    pid-float 56);
  * boardId == (file channel >> 4)   -- the "body is authoritative, channel is a
    checkable hint" invariant;
  * the absolute-ns timestamp is nonzero (the run has advanced);
  * readout per-sample columns are GLOBAL (boardId*8 + local): every sample's
    col lies in [boardId*8, boardId*8+8).

Run it against ANY warmTdmServer that produces real framed data:

  * GroupTb cosim (Vivado 2024.1 + VCS):
        cd firmware/simulations/GroupTb && make        # build + launch the sim
        # in another shell, with the conda env active:
        cd software/scripts && python warmTdmServer.py --sim
        # then:
        cd software/scripts/hwtest && python verify_frame_header.py --acq 5
  * Real hardware: point --host/--port at the live server.

Emulate (MemEmulate) does NOT produce real framed data (the file-write path is
bypassed), so it cannot exercise this check -- use the cosim or real hardware.
"""
import argparse
import sys

import pyrogue.utilities.fileio

from _hwtest_common import add_conn_args, connect, Checklist

import warm_tdm


def _classify(channel, data):
    """Return (name, decoder|None) for a file record by channel + header."""
    if channel == warm_tdm.CONFIG_CHANNEL:
        return 'config', None
    if len(data) < warm_tdm.FRAME_HEADER_BYTES:
        return 'short', None
    hdr = warm_tdm.FrameHeader.from_numpy(data)
    ft = hdr.formatType
    if ft == warm_tdm.FormatType.READOUT:
        return 'readout', warm_tdm.DataReadout
    if ft == warm_tdm.FormatType.PID_FIXED:
        return 'pid-fixed', warm_tdm.PidDebug
    if ft == warm_tdm.FormatType.PID_FLOAT:
        return 'pid-float', warm_tdm.PidDebugFp
    if ft == warm_tdm.FormatType.WAVEFORM:
        return 'waveform', warm_tdm.WaveformReadout
    return f'unknown(formatType={ft:#x})', None


def check_file(path, chk):
    """Walk a .dat file and assert the frame header invariants."""
    counts = {}
    bad_version = []
    bad_board = []
    bad_zero_ts = []
    bad_global_col = []
    bad_pid_len = []
    bad_pid_chan = []
    n_frames = 0

    with pyrogue.utilities.fileio.FileReader(files=[path]) as fd:
        for header, data in fd.records():
            channel = header.channel
            name, decoder = _classify(channel, data)
            counts[name] = counts.get(name, 0) + 1
            if decoder is None:
                continue
            n_frames += 1
            hdr = warm_tdm.FrameHeader.from_numpy(data)

            if hdr.formatVersion != warm_tdm.EXPECTED_FORMAT_VERSION:
                bad_version.append((name, hdr.formatVersion))
            # boardId must match the file-channel high nibble.
            if hdr.boardId != (channel >> 4):
                bad_board.append((name, hdr.boardId, channel >> 4))
            if hdr.timestampNs == 0:
                bad_zero_ts.append(name)

            # PID frames have a fixed total length (header + body).
            if name == 'pid-fixed' and len(data) != warm_tdm.PID_DEBUG_FRAME_BYTES:
                bad_pid_len.append(('pid-fixed', len(data), warm_tdm.PID_DEBUG_FRAME_BYTES))
            if name == 'pid-float' and len(data) != warm_tdm.PID_DEBUG_FP_FRAME_BYTES:
                bad_pid_len.append(('pid-float', len(data), warm_tdm.PID_DEBUG_FP_FRAME_BYTES))

            # PID-debug streams are collapsed onto one board-local stream: every
            # PID frame must land on file channel board*16 + PID_DEBUG_STREAM (the
            # 8 per-column streams no longer exist).
            if name in ('pid-fixed', 'pid-float') and \
                    warm_tdm.stream_of(channel) != warm_tdm.PID_DEBUG_STREAM:
                bad_pid_chan.append((name, warm_tdm.stream_of(channel),
                                     warm_tdm.PID_DEBUG_STREAM))

            # Readout per-sample columns must be GLOBAL (boardId*8 + local).
            if name == 'readout':
                dr = decoder.from_numpy(data)
                lo = hdr.boardId * 8
                for s in dr.samples:
                    if not (lo <= int(s.col) < lo + 8):
                        bad_global_col.append((int(s.col), hdr.boardId))
                        break

    print(f'Decoded {n_frames} bulk frame(s); record types: {counts}')

    chk.item(n_frames > 0, 'at least one bulk frame decoded',
             'no framed data in file -- is real data being produced?')
    chk.item(not bad_version, 'all frames carry the expected formatVersion',
             '' if not bad_version else f'mismatches: {bad_version[:5]}')
    chk.item(not bad_board, 'boardId == file-channel high nibble (body vs channel)',
             '' if not bad_board else f'mismatches (name,body,chan): {bad_board[:5]}')
    chk.item(not bad_zero_ts, 'header timestamp is nonzero',
             '' if not bad_zero_ts else f'zero-timestamp frames: {set(bad_zero_ts)}')
    chk.item(not bad_pid_len, 'PID frame lengths match header+body',
             '' if not bad_pid_len else f'(name,got,want): {bad_pid_len[:5]}')
    chk.item(not bad_pid_chan, 'PID frames arrive on the collapsed PID stream',
             '' if not bad_pid_chan else f'(name,got,want): {bad_pid_chan[:5]}')
    chk.item(not bad_global_col, 'readout sample columns are global (boardId*8+local)',
             '' if not bad_global_col else f'(col,boardId): {bad_global_col[:5]}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    add_conn_args(parser)
    parser.add_argument('--acq', type=float, default=5.0,
                        help='acquisition time in seconds (default: 5)')
    parser.add_argument('--file', type=str, default=None,
                        help='skip acquisition and check an existing .dat file instead')
    args = parser.parse_args(argv)

    chk = Checklist('Frame header (Issue #82 Phase 3)')

    if args.file:
        path = args.file
        print(f'Checking existing file: {path}')
    else:
        sess = connect(args)
        path = sess.take_data(args.acq)
        print(f'Acquired: {path}')

    check_file(path, chk)
    return chk.report()


if __name__ == '__main__':
    sys.exit(main())
