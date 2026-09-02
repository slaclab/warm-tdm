## Timestamped output directory for a data-taking session.
##
## Split out of the former monolithic session.py: OutputDir is fully standalone
## (no Session/client coupling), so it lives in its own module and Session simply
## holds one.

import os
import time
import logging
import datetime

log = logging.getLogger(__name__)


class OutputDir:
    """Timestamped output directory for a data-taking session.

    Owns ``<base>/<YYYYMMDD>/<ctime0>/`` and is constructed independently of any
    client binding (unlike the old ``Client.set_client`` which created this as a
    side effect). Falls back to a local ``data`` dir then the home directory if
    the requested base is not writable.
    """

    DEFAULT_BASE = '/data/warm_tdm/'

    def __init__(self, base=DEFAULT_BASE):
        base = self._resolve_base(base)
        self.date = datetime.datetime.now().strftime('%Y%m%d')
        self.datedir = os.path.join(base, self.date)
        self.ctime0 = str(int(time.time()))
        self.sessiondir = os.path.join(self.datedir, self.ctime0)
        os.makedirs(self.sessiondir, exist_ok=True)
        log.info("Session output directory: %s", self.sessiondir)

    @staticmethod
    def _resolve_base(base):
        """Return the first writable base among: requested, ../data, home."""
        if os.path.isdir(base) and os.access(base, os.W_OK):
            return base
        log.warning("Output path '%s' does not exist or is not writable; "
                    "falling back.", base)

        fallback = os.path.join(os.path.dirname(os.getcwd()), 'data')
        if os.path.isdir(fallback) and os.access(fallback, os.W_OK):
            return fallback
        log.warning("Fallback path '%s' also unusable; defaulting to home.",
                    fallback)
        return os.path.expanduser('~')

    def __fspath__(self):
        return self.sessiondir

    def __repr__(self):
        return f"<OutputDir sessiondir='{self.sessiondir}'>"
