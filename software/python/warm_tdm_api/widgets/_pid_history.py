##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Bounded, hardware-timestamped GUI history; independent of Qt."""
from collections import deque

import numpy as np

from warm_tdm import (
    TIME, COLUMN, ROW, DAC, DROPS, FORMAT, PERIOD, FLAGS, SAMPLE_SIZE,
)


class PidHistory:
    def __init__(self, seconds=60, max_points=6000):
        self.seconds = seconds
        self.samples = deque(maxlen=max_points)
        self.last = None

    def clear(self):
        self.samples.clear()
        self.last = None

    def append(self, value):
        sample = np.asarray(value, dtype=float)
        identity = [TIME, COLUMN, ROW, DROPS, FORMAT, FLAGS]
        if sample.shape != (SAMPLE_SIZE,) or not np.isfinite(sample[identity]).all():
            return False
        previous = self.last
        if previous is not None:
            if (not np.array_equal(sample[[COLUMN, ROW, FORMAT, PERIOD]],
                                   previous[[COLUMN, ROW, FORMAT, PERIOD]], equal_nan=True)
                    or sample[TIME] < previous[TIME] or sample[DROPS] < previous[DROPS]):
                self.clear()
                previous = None
            elif sample[TIME] == previous[TIME]:
                return False  # Cached sample on reconnect or a duplicate update.
        if previous is not None and (sample[TIME] - previous[TIME] > 0.5
                                     or sample[DROPS] != previous[DROPS]
                                     or sample[FLAGS] != previous[FLAGS]):
            gap = sample.copy()
            gap[DAC:DROPS] = np.nan
            self.samples.append(gap)
        self.samples.append(sample.copy())
        self.last = sample.copy()
        self.trim()
        return True

    def trim(self):
        if self.last is not None:
            cutoff = self.last[TIME] - self.seconds
            while self.samples and self.samples[0][TIME] < cutoff:
                self.samples.popleft()

    def arrays(self):
        if not self.samples:
            return np.empty((0, SAMPLE_SIZE))
        data = np.array(self.samples)
        data[:, TIME] -= data[-1, TIME]
        return data
