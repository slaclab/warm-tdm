import sys

import _setupLibPaths  # noqa: F401  (registers in-repo library paths)

import warm_tdm_api  # noqa: F401  (makes the operations subpackage importable)
from warm_tdm_api.operations.streamreader import StreamReader


# Read the fixed-point PID-debug streams from a DataWriter .dat file into
# pid[global_col][row][field] = [values...].
#
# Thin CLI wrapper around warm_tdm_api.operations.StreamReader, the single reader
# for warm-tdm .dat files. StreamReader owns the file-channel demux
# (warm_tdm._Channels), the board -> global-column folding, and the 80-byte
# fixed-point PID-debug decode (warm_tdm._DataFormats: PID_DEBUG_TYPE /
# PID_DEBUG_FRAME_BYTES). Do NOT redeclare the frame dtype or the channel check
# here -- extend StreamReader / _DataFormats instead so every reader stays in
# sync. (The floating-point PID-debug format is a different 40-byte layout; see
# PidDebugFileReaderFp.py.)
def main(args):
    sr = StreamReader()
    sr.readStream(args[1])
    return sr


if __name__ == '__main__':
    sr = main(sys.argv)
    ncols = len(sr.pid)
    print(f'Read PID-debug data for {ncols} column(s) from {sys.argv[1]}')
