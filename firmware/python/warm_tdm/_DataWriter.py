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
## Warm-TDM DataWriter: a pyrogue StreamWriter that knows the warm-tdm
## file-channel layout. It exposes named accessors -- readoutChannel(board),
## pidDebugChannel(board), waveformChannel(board) -- so call sites ask for a
## stream by meaning rather than open-coding channel arithmetic. Each accessor
## delegates to warm_tdm.file_channel(), keeping the encoding defined in exactly
## one place (warm_tdm._Channels).
##
## File channels are NOT the same namespace as on-wire TDESTs -- see
## warm_tdm._Channels for the distinction. This class owns the *file* side.

import pyrogue.utilities.fileio

import warm_tdm


class DataWriter(pyrogue.utilities.fileio.StreamWriter):
    """StreamWriter that knows the warm-tdm file-channel layout.

    A drop-in replacement for ``pyrogue.utilities.fileio.StreamWriter`` (same
    constructor) that adds accessors resolving a ``(board, stream)`` pair to the
    board-namespaced file channel via :func:`warm_tdm.file_channel` and returning
    the corresponding writer channel object. Use these in place of
    ``getChannel(<raw int>)`` so the channel-namespacing scheme lives in one
    place rather than being open-coded at each call site.
    """

    #: Reserved file channel for the tree config/status YAML dump. Pass this as
    #: the key of the ``configStream`` dict at construction (mirrors the value
    #: used in warm_tdm_api._GroupRoot).
    CONFIG_CHANNEL = warm_tdm.CONFIG_CHANNEL

    def readoutChannel(self, board):
        """Return the writer channel for a board's operational readout stream.

        Args:
            board (int): source column board index (0-15).

        Returns:
            rogue.interfaces.stream.Slave: the writer channel for that board's
            readout stream.
        """
        return self.getChannel(warm_tdm.file_channel(board, warm_tdm.READOUT_STREAM))

    def pidDebugChannel(self, board):
        """Return the writer channel for a board's PID-debug stream.

        All columns share one PID-debug stream (the source column is carried in
        the frame body), so this is per-board, not per-column.

        Args:
            board (int): source column board index (0-15).

        Returns:
            rogue.interfaces.stream.Slave: the writer channel for that board's
            PID-debug stream.
        """
        return self.getChannel(warm_tdm.file_channel(board, warm_tdm.PID_DEBUG_STREAM))

    def waveformChannel(self, board):
        """Return the writer channel for a board's waveform-capture stream.

        Args:
            board (int): source column board index (0-15).

        Returns:
            rogue.interfaces.stream.Slave: the writer channel for that board's
            waveform stream.
        """
        return self.getChannel(warm_tdm.file_channel(board, warm_tdm.WAVEFORM_STREAM))
