#-----------------------------------------------------------------------------
# This file is part of the 'warm-tdm' project. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'warm-tdm' project, including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import sys

import _setupLibPaths  # noqa: F401  (registers in-repo library paths)

import warm_tdm_api  # noqa: F401  (makes the operations subpackage importable)
from warm_tdm_api.operations.streamreader import StreamReader


# Read the floating-point PID-debug streams from a DataWriter .dat file into
# pid[global_col][row][field] = [values...].
#
# Thin CLI wrapper around warm_tdm_api.operations.StreamReader, the single reader
# for warm-tdm .dat files. StreamReader dispatches PID-debug frames by size and
# decodes the 40-byte float format via warm_tdm._DataFormats (PID_DEBUG_FP_TYPE /
# PID_DEBUG_FP_FRAME_BYTES, emitted by the AdcDspFp path). Do NOT redeclare the
# frame dtype or the channel check here -- extend StreamReader / _DataFormats
# instead so every reader stays in sync. (The fixed-point AdcDsp PID-debug format
# is a different 80-byte layout; the same StreamReader handles both.)
def main(args):
    sr = StreamReader()
    sr.readStream(args[1])
    return sr


if __name__ == '__main__':
    sr = main(sys.argv)
    ncols = len(sr.pid)
    print(f'Read FP PID-debug data for {ncols} column(s) from {sys.argv[1]}')
