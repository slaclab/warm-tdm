##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Channel-selection parsing, independent of Qt and Rogue."""
import re

# Limit detailed time traces, not the size of the hardware channel catalog.
MAX_PLOT_CHANNELS = 32


def parse_indices(text, available):
    """Parse explicit indices/ranges against actual topology, without expansion bombs."""
    available = set(available)
    result = set()
    for token in text.split(','):
        match = re.fullmatch(r'\s*(\d+)\s*(?:-\s*(\d+)\s*)?', token)
        if match is None:
            raise ValueError('Use comma-separated indices or inclusive ranges, e.g. 0, 3, 8-11.')
        low = int(match[1])
        high = int(match[2]) if match[2] else low
        if high < low:
            raise ValueError('Ranges must be ascending.')
        selected = {i for i in available if low <= i <= high}
        if len(selected) != high - low + 1:
            raise ValueError(f'{token.strip()} includes indices unavailable on this server.')
        result.update(selected)
    return sorted(result)


def channel_pairs(columns, rows, topology):
    cols = parse_indices(columns, topology)
    selected_rows = parse_indices(rows, set().union(*(topology[c] for c in cols)))
    if len(cols) * len(selected_rows) > MAX_PLOT_CHANNELS:
        raise ValueError(f'Select at most {MAX_PLOT_CHANNELS} channels for detailed plots.')
    pairs = [(c, r) for c in cols for r in selected_rows]
    if any(r not in topology[c] for c, r in pairs):
        raise ValueError('Some rows are unavailable on one or more selected columns.')
    return pairs


def channel_label(column, row):
    return f'B{column // 8} · C{column % 8} · R{row} (global {column})'
