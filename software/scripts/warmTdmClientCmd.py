#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Interactive client: exposes client, group, sess and ops without changing hardware."""
import argparse
import code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=9099)
    parser.add_argument('--run-dir', help='Existing measurement run for data/config output')
    args = parser.parse_args(argv)
    import _setupLibPaths  # noqa: F401
    import pyrogue.interfaces
    import warm_tdm_api.operations as ops
    # Validate output before connecting, just as notebook ops.connect does.
    output = ops.OutputDir.existing_run(args.run_dir) if args.run_dir else None
    client = pyrogue.interfaces.VirtualClient(addr=args.host, port=args.port)
    try:
        group = client.root.Group
        sess = ops.set_default_session(ops.Session(group, output=output))
        code.interact(banner='Warm TDM: client, group, sess, ops. No hardware setup has been performed.',
                      local=dict(client=client, group=group, sess=sess, ops=ops))
    finally:
        client.stop()


if __name__ == '__main__':
    main()
