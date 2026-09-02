##
## Unit-conversion factor derivation from a captured file's tree config.
##
## Analysis works in physical units, but the streamed data carries raw values:
## SQ1FB DAC codes (not pA) and sample indices (not seconds). This module derives
## the factors that map raw -> physical -- the sample rate (Hz) and the
## SQ1FB-DAC-code-to-current conversion (pA/LSB). It is NOT instrument calibration
## (SA/SQ1 tuning etc. -- that lives in the tuning pr.Processes); it just supplies
## the units the analysis functions scale into.
##
## The Rogue config channel embedded in each data file (see streamreader.py)
## carries the full device-tree state at capture time, so these factors are
## derived from the capture itself instead of hardcoded, always matching the
## front-end / timing that actually produced the data.
##
## These are pure functions of the parsed config dict (flat, keyed by full dotted
## tree path). They do NOT touch live hardware, so analysis stays offline. When
## the needed keys are absent (e.g. a file captured before config embedding), the
## helpers return None and callers fall back to documented default factors.

from .channels import col_to_board_chan

# Documented fallback constants (the historical notebook values). Used only when
# a file has no config channel to derive from. NOTE: sq1fb_to_pA is front-end
# dependent -- this literal matches a specific SQ1FbAmp configuration and is NOT
# correct for arbitrary front ends; deriving from the file is always preferred.
DEFAULT_FS = 396.332
DEFAULT_SQ1FB_TO_PA = 1224.23093499038


def _col_to_board_chan(col):
    """Map a global column index to (board, channel).

    Offline path: a parsed config dict carries no live NumColumns, so the
    columns-per-board count cannot be read back here -- we use the shared
    ``channels.col_to_board_chan`` default (8), the width of every column board
    shipped to date. Live code derives the count from the bound Group instead.
    """
    return col_to_board_chan(col)


def _lookup(config, path):
    """Return the config value at a full dotted tree path, or None if absent."""
    if not config:
        return None
    return config.get(path)


def derive_fs(config, col=0):
    """Sample rate (Hz) for the given column, from the capture's tree config.

    Reads TimingTx.DaqReadoutRate -- the firmware's own computed per-channel
    readout rate (it already folds in the row period, active row count, and
    row-sequences-per-readout). Returns None if the config lacks the key.
    """
    board, _ = _col_to_board_chan(col)
    path = (f'GroupRoot.Group.HardwareGroup.ColumnBoard[{board}]'
            f'.WarmTdmCore.Timing.TimingTx.DaqReadoutRate')
    val = _lookup(config, path)
    return None if val is None else float(val)


def derive_sq1fb_to_pA(config, col, row=None):
    """SQ1FB-DAC-code -> pA conversion for a column, from the capture's config.

    The streamed SQ1FB value is a DAC code (verified through the AdcDsp/Biquad
    path), so the conversion is the SQ1FbAmp's per-LSB output-current slope. The
    firmware exposes that slope as CurrentPerLsb in microamps/LSB; we convert to
    pA/LSB here (x 1e6). `row` is accepted for call-site symmetry but the
    conversion is per-column (front-end), not per-row. Returns None if absent.
    """
    board, chan = _col_to_board_chan(col)
    path = (f'GroupRoot.Group.HardwareGroup.ColumnBoard[{board}]'
            f'.AnalogFrontEnd.Channel[{chan}].SQ1FbAmp.CurrentPerLsb')
    uA_per_lsb = _lookup(config, path)
    if uA_per_lsb is None:
        return None
    return float(uA_per_lsb) * 1.0e6  # uA/LSB -> pA/LSB


def resolve_fs(config, col=0, default=DEFAULT_FS):
    """derive_fs() with fallback to `default` (and a note) when not derivable."""
    val = derive_fs(config, col=col)
    if val is None:
        return default, False
    return val, True


def resolve_sq1fb_to_pA(config, col, row=None, default=DEFAULT_SQ1FB_TO_PA):
    """derive_sq1fb_to_pA() with fallback to `default` when not derivable."""
    val = derive_sq1fb_to_pA(config, col, row=row)
    if val is None:
        return default, False
    return val, True
