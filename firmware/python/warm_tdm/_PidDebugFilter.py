##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
import rogue.interfaces.stream

import warm_tdm


class PidDebugFilter(rogue.interfaces.stream.Master, rogue.interfaces.stream.Slave):
    """Pass through only the PID-debug frames for one column.

    The 8 per-column PID-debug streams are collapsed onto one board-local stream
    in firmware (DataPath ``U_AxiStreamMux_1`` ROUTED); the source column is
    carried in the frame body. One ``PidDebugFilter`` is instantiated per column
    and connected between the collapsed stream and that column's ``PidDebugger``:
    it accepts every frame but only re-emits (``_sendFrame``) the ones whose body
    column matches, so each downstream receiver still sees only its own column --
    the wire demux the per-column tDests used to provide moves into software.

    ``col`` lives in body byte 0, low 3 bits, i.e. header-relative offset
    ``warm_tdm.FRAME_HEADER_BYTES`` -- the same location ``PidDebugger.process``
    and the offline StreamReader read it from. The frame is forwarded unmodified;
    the downstream ``PidDebugger`` does its own 16-byte header strip.
    """

    def __init__(self, column):
        rogue.interfaces.stream.Master.__init__(self)
        rogue.interfaces.stream.Slave.__init__(self)
        self._column = column

    def _acceptFrame(self, frame):
        with frame.lock():
            if frame.getError() != 0:
                return
            size = frame.getPayload()
            if size < warm_tdm.FRAME_HEADER_BYTES + 1:
                return
            raw = bytearray(1)
            frame.read(raw, warm_tdm.FRAME_HEADER_BYTES)
            if (raw[0] & 0x7) != self._column:
                return
        # Re-emit the unmodified frame to this column's receiver.
        self._sendFrame(frame)
