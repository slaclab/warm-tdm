#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Summarize readout, integer/FP PID, waveform and configuration in one stream file."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args(argv)
    if not args.file.is_file():
        parser.error('File does not exist: ' + str(args.file))
    import _setupLibPaths  # noqa: F401
    from warm_tdm_api.operations.streamreader import StreamReader
    reader = StreamReader()
    reader.readStream(str(args.file))
    print(json.dumps(dict(
        file=str(args.file), readout_columns=sorted(reader.data),
        readout_samples=sum(len(v) for rows in reader.data.values() for v in rows.values()),
        pid_columns=sorted(reader.pid), waveform_boards=sorted(reader.waveform),
        embedded_config=bool(reader.config), dropped_readouts=reader.dropped_readouts,
        malformed_pid=reader.malformed_pid), indent=2))
    return reader


if __name__ == '__main__':
    main()
