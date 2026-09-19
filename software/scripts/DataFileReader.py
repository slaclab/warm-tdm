import sys

import _setupLibPaths  # noqa: F401  (registers in-repo library paths)

import warm_tdm_api  # noqa: F401  (makes the operations subpackage importable)
from warm_tdm_api.operations.streamreader import StreamReader


# Read a DataWriter .dat readout stream into data[global_col][row] = [values...].
#
# Thin CLI wrapper around warm_tdm_api.operations.StreamReader, the single reader
# for warm-tdm .dat files: it owns the file-channel demux (warm_tdm._Channels),
# the board -> global-column folding, and the frame decoders
# (warm_tdm._DataFormats). Do NOT re-implement channel checks or frame parsing
# here -- extend StreamReader instead so every reader stays in sync.
def main(args):
    sr = StreamReader()
    sr.readStream(args[1])
    return sr


if __name__ == '__main__':
    sr = main(sys.argv)
    ncols = len(sr.data)
    print(f'Read readout data for {ncols} column(s) from {sys.argv[1]}')
