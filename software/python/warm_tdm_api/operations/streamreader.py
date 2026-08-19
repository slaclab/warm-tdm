##
## Stream data reader
##
## A DataWriter .dat file interleaves several stream channels. The channel byte
## is namespaced by board via warm_tdm.file_channel() (= board*16 + stream_type),
## mirroring the on-wire TDEST (see warm_tdm._HardwareGroup wiring and
## firmware/common/DataChannelization.md):
##   - stream 0-7 : per-column PID-debug frames (data model #3), present only when
##                  AdcDsp[col].PidDebugEnable was set during the run.
##   - stream 8   : waveform capture -> `waveform` (folded into the file when the
##                  run tees app 8 to the file; also still drives the live GUI).
##   - stream 9   : the readout stream (per-(col,row) SQ1FB values) -> `data`.
##   - channel 255: the tree config/status YAML dump -> `config` (file-scope, not
##                  board-namespaced).
## This is the FILE-channel namespace (the DataWriter's 1-byte channel field),
## which is distinct from the on-wire RSSI/PGP TDEST -- see warm_tdm._Channels
## for the distinction. Offline, all we have is the file channel; the board index
## is recovered from it (warm_tdm.board_of) and folded into a GLOBAL column
## (board*8 + local_col) so multiple column boards do not collide. Board 0
## reproduces the historical single-board layout exactly, so old single-board
## files decode unchanged. StreamReader reads all channels in a single pass;
## StreamData exposes the readout + config, PidDebugData exposes the PID-debug
## timeseries.

import re
from collections import defaultdict

import pyrogue
import rogue.utilities
import rogue.utilities.fileio

# NOTE: as a subpackage of warm_tdm_api, this module is only importable once
# warm_tdm_api itself has been imported, so warm_tdm_api / warm_tdm / surf are
# already on the library path. The previous import-time pyrogue.addLibraryPath()
# block (relative to __file__) is therefore both redundant and, after the move
# into warm_tdm_api/operations/, wrong. Path setup belongs to the entry-point
# script (e.g. warmTdmServer.py) or WARM_TDM_PATH, not to a library module.
import warm_tdm_api
import warm_tdm

# The file-channel encoding (stream types, board namespacing, the config
# channel) is defined once in warm_tdm._Channels and shared with the write side
# (warm_tdm._HardwareGroup); this module reads it via the warm_tdm namespace
# (warm_tdm.CONFIG_CHANNEL, warm_tdm.board_of, warm_tdm.is_readout,
# warm_tdm.is_waveform, ...) rather than re-declaring the numbers here.

# Column channels per column board. The frame body carries a board-local column
# (0-7); global_col = board*CHANS_PER_BOARD + local_col.
CHANS_PER_BOARD = 8

# Defensive config parse: some framework variables serialize a display-formatted
# float into the config YAML as a quoted `!!float` scalar with comma thousands
# separators (e.g. a Bandwidth monitor with disp='{:,.3f}' -> "!!float
# '326,838,882.903'"). PyYAML cannot parse the commas back, and a single bad leaf
# aborts the whole document decode -- so FileReader(configChan=255) raises on
# real files. This is a rogue bug (slaclab/rogue#1282), present in every released
# rogue. We strip the commas out of quoted !!float scalars before parsing.
_QUOTED_FLOAT_RE = re.compile(r"!!float '([-+0-9.,eE]+)'")


def _desep_commas(text):
    """Remove comma thousands-separators from quoted !!float scalars."""
    return _QUOTED_FLOAT_RE.sub(
        lambda m: "!!float '" + m.group(1).replace(',', '') + "'", text)


nesteddict = lambda:defaultdict(nesteddict)

def signed_int(arr):
    return int.from_bytes(arr, 'little', signed=True)

def unsigned_int(arr):
    return int.from_bytes(arr, 'little', signed=False)

class StreamReader():
    def __init__(self):
        self.data = nesteddict()
        # PID-debug timeseries: pid[col][row][field] -> list, built from the
        # per-column channels 0-7. Empty if the run had PidDebugEnable off.
        self.pid = nesteddict()
        # Waveform captures: waveform[board] -> list of WaveformReadout, built
        # from the per-board waveform stream (stream type 8). Empty unless the
        # run folded waveform captures into the file.
        self.waveform = nesteddict()
        # Parsed tree configuration captured in the file (channel 255), or {} if
        # the file predates config capture / has no config frame.
        self.config = {}

    def readStream(self, filename):
        # clear the dictionaries
        self.data = nesteddict()
        self.pid = nesteddict()
        self.waveform = nesteddict()
        self.config = {}
        configBlobs = []
        with pyrogue.utilities.fileio.FileReader(files=[filename]) as fd:
            for header, data in fd.records():
                channel = header.channel
                # Config/status frame (tree YAML dump). Collect the raw payload
                # and parse it ourselves rather than via FileReader(configChan=),
                # whose strict decode trips over the comma-float bug above.
                if channel == warm_tdm.CONFIG_CHANNEL:
                    configBlobs.append(bytes(data).decode('utf-8', errors='ignore'))
                # readout (any board); board recovered from the channel byte
                elif warm_tdm.is_readout(channel):
                    self._accept_readout(data, warm_tdm.board_of(channel))
                # PID-debug (any board); col/row come from the frame body
                elif warm_tdm.is_pid_debug(channel):
                    self._accept_pid(data, warm_tdm.board_of(channel))
                # waveform capture (any board); folded into the file when enabled
                elif warm_tdm.is_waveform(channel):
                    self._accept_waveform(data, warm_tdm.board_of(channel))

        if configBlobs:
            self.config = self._parseConfig(''.join(configBlobs))

    def _accept_readout(self, data, board):
        """Decode one readout frame into data[global_col][row] timeseries.

        The frame body carries a board-local column (0-7); fold in the board
        index recovered from the file channel to form the global column.
        """
        dr = warm_tdm.DataReadout.from_numpy(data)
        for s in dr.samples:
            global_col = board * CHANS_PER_BOARD + s.col
            if not self.data[global_col][s.row]:
                self.data[global_col][s.row] = []
            self.data[global_col][s.row].append(s.value)

    def _accept_pid(self, data, board):
        """Decode one PID-debug frame into pid[global_col][row][field] timeseries.

        The PID-debug channels carry two frame layouts, distinguished by size:
        the 80-byte fixed-point format (AdcDsp) and the 40-byte float format
        (AdcDspFp). Both decode via warm_tdm._DataFormats to a col/row + fields
        dict; a frame of neither size is skipped defensively.
        """
        if len(data) == warm_tdm.PID_DEBUG_FRAME_BYTES:
            msg = warm_tdm.PidDebug.from_numpy(data)
        elif len(data) == warm_tdm.PID_DEBUG_FP_FRAME_BYTES:
            msg = warm_tdm.PidDebugFp.from_numpy(data)
        else:
            return  # not a PID-debug frame (or truncated); skip defensively
        global_col = board * CHANS_PER_BOARD + msg.col
        slot = self.pid[global_col][msg.row]
        for field, value in msg.fields.items():
            if not slot[field]:
                slot[field] = []
            slot[field].append(value)

    def _accept_waveform(self, data, board):
        """Decode one waveform-capture frame into waveform[board] list.

        Keyed by board (not column) because a capture frame's own header carries
        the capture channel (and an all-channel capture spans all 8). Decodes via
        warm_tdm._DataFormats.WaveformReadout.
        """
        wf = warm_tdm.WaveformReadout.from_numpy(data)
        if not self.waveform[board]:
            self.waveform[board] = []
        self.waveform[board].append(wf)

    @staticmethod
    def _parseConfig(text):
        """Parse the channel-255 config YAML defensively.

        Returns the parsed config dict, or {} if it cannot be parsed. Sanitizes
        the comma-float serialization bug (slaclab/rogue#1282) first, then uses
        PyRogue's own YAML loader.
        """
        try:
            return pyrogue.yamlToData(stream=_desep_commas(text)) or {}
        except Exception:
            # Never let a config-decode problem break data readout; callers fall
            # back to documented default constants when config is unavailable.
            return {}
