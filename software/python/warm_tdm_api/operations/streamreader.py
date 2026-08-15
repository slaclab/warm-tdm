##
## Stream data reader
##
## A DataWriter .dat file interleaves several stream channels (see
## warm_tdm._HardwareGroup wiring):
##   - channels 0-7  : per-column PID-debug frames (data model #3), present only
##                     when AdcDsp[col].PidDebugEnable was set during the run.
##   - channel  9    : the readout stream (per-(col,row) SQ1FB values) -> `data`.
##   - channel  255  : the tree config/status YAML dump -> `config`.
## StreamReader reads all of them in a single pass; StreamData exposes the
## readout + config, PidDebugData exposes the PID-debug timeseries.

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

# Rogue writes the tree configuration/status to a reserved stream channel when a
# DataWriter file is opened/closed. warm-tdm uses channel 255 (see
# warm_tdm_api._GroupRoot: StreamWriter(configStream={255: ...})).
CONFIG_CHANNEL = 255

# The per-(col,row) readout stream (SQ1FB values) is written on this channel.
READOUT_CHANNEL = 9

# PID-debug frames are written one channel per column (0..7). The frame's own
# header carries col/row, so we treat any of these channels as PID-debug.
PID_DEBUG_CHANNELS = range(8)

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
        # Parsed tree configuration captured in the file (channel 255), or {} if
        # the file predates config capture / has no config frame.
        self.config = {}

    def readStream(self, filename):
        # clear the dictionaries
        self.data = nesteddict()
        self.pid = nesteddict()
        self.config = {}
        configBlobs = []
        with pyrogue.utilities.fileio.FileReader(files=[filename]) as fd:
            for header, data in fd.records():
                # Config/status frame (tree YAML dump). Collect the raw payload
                # and parse it ourselves rather than via FileReader(configChan=),
                # whose strict decode trips over the comma-float bug above.
                if header.channel == CONFIG_CHANNEL:
                    configBlobs.append(bytes(data).decode('utf-8', errors='ignore'))
                # readout
                elif header.channel == READOUT_CHANNEL:
                    dr = warm_tdm.DataReadout.from_numpy(data)
                    for s in dr.samples:
                        if not self.data[s.col][s.row]:
                            self.data[s.col][s.row] = []

                        self.data[s.col][s.row].append(s.value)
                # PID-debug (one channel per column; col/row come from the frame)
                elif header.channel in PID_DEBUG_CHANNELS:
                    self._accept_pid(data)

        if configBlobs:
            self.config = self._parseConfig(''.join(configBlobs))

    def _accept_pid(self, data):
        """Decode one PID-debug frame into pid[col][row][field] timeseries."""
        if len(data) != warm_tdm.PID_DEBUG_FRAME_BYTES:
            return  # not a PID-debug frame (or truncated); skip defensively
        msg = warm_tdm.PidDebug.from_numpy(data)
        slot = self.pid[msg.col][msg.row]
        for field, value in msg.fields.items():
            if not slot[field]:
                slot[field] = []
            slot[field].append(value)

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
