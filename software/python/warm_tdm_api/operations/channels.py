##
## Pure channel helpers for the operations layer: addressing, identifiers, and
## dead-channel masks.
##
## Three related channel concerns, all pure (NO hardware coupling -- no Session,
## no rogue tree, no live client), so they can be imported and unit-tested
## without a connection:
##   - addressing:   col_to_board_chan (global column -> board, channel)
##   - identifiers:  get_row_col (parse a 'c<col>r<row>'/'r<row>c<col>' string)
##   - dead masks:   make/write/read_dead_masks (per-column dead-row bitmask +
##                   its on-disk .cfg format). The mask shape matches the
##                   AdcDsp[col].RowEnableMask hardware register; these pure
##                   helpers stay client-side. The Session-side hardware bridge
##                   Session.apply_dead_masks (issue #83, G9) writes the masks to
##                   RowEnableMask. Graduating the mask onto a Group variable is
##                   deliberately deferred: RowEnableMask is a 256-bit int, and
##                   the existing GroupArrayLinkVariable carries only np.float64
##                   arrays -- a mask-capable Group node (or a Group command) can
##                   follow if server-side execution is ever needed.

import re


def col_to_board_chan(col, chans_per_board=8):
    """Map a global column index to ``(board_index, channel)``.

    Pure arithmetic: ``board = col // chans_per_board``, ``channel = col %
    chans_per_board``. The single source of this mapping for the operations layer
    -- both the live ``Session`` (which passes the count derived from its bound
    ``Group``) and offline ``unit_conversions`` call this so the ``//8`` split is not
    duplicated. The default (8) matches every column board shipped to date; live
    callers should pass the tree-derived value rather than rely on it.

    Args:
        col (int): global column index.
        chans_per_board (int): columns (channels) per column board.

    Returns:
        tuple: (board_index, channel).
    """
    return col // chans_per_board, col % chans_per_board


def get_row_col(value):
    """
    Extract column and row indices from a channel string.

    Accepts 'c<col>r<row>' or 'r<row>c<col>' format.

    Args:
        value (str): Channel identifier, e.g. 'c0r5' or 'r5c0'.

    Returns:
        tuple: (col, row) as integers.

    Raises:
        ValueError: If value does not match either accepted format.
    """
    match = re.fullmatch(r"(?:c(?P<col>\d+)r(?P<row>\d+)|r(?P<row_alt>\d+)c(?P<col_alt>\d+))", value)
    if not match:
        raise ValueError(
            f"Invalid channel format: {value!r}. Expected 'c<col>r<row>' or 'r<row>c<col>'."
        )

    col = match.group("col")
    row = match.group("row")
    # Handle r<row>c<col> format
    if col is None or row is None:
        col = match.group("col_alt")
        row = match.group("row_alt")

    return (int(col), int(row))


def make_dead_masks(channels, ncol=8, nrow=256):
    """
    Build a per-column bitmask marking specified channels as dead (disabled).

    Each mask is an nrow-bit integer where 1 = active, 0 = dead. Row order is
    physical (chip select / row select), not readout order.

    Args:
        channels (list): Channel strings to mark dead, e.g. ['c0r5', 'r3c1'].
        ncol (int): Number of columns. Default is 8.
        nrow (int): Number of rows (bits) per mask. Default is 256.

    Returns:
        dict: {col: mask} where mask is an nrow-bit integer.
    """
    # Start with all channels active (all bits set)
    dead_masks = {col: (1 << nrow) - 1 for col in range(ncol)}

    # Clear the bit for each dead channel
    for channel in channels:
        col, row = get_row_col(channel)
        dead_masks[col] &= ~(1 << row)

    return dead_masks


def write_dead_masks(dead_masks, mask_filename="dead_masks.cfg", nrow=256):
    """
    Write dead channel masks to a human-readable configuration file.

    Each line corresponds to one column (ascending order). Bits are written
    LSB-first, left to right, in groups of 10 for readability.

    Args:
        dead_masks (dict): {col: mask} as returned by make_dead_masks().
        mask_filename (str): Output file path. Default is 'dead_masks.cfg'.
        nrow (int): Number of rows (bits) per mask. Default is 256.
    """
    with open(mask_filename, "w") as f:
        for col, mask in dead_masks.items():
            # Convert to fixed-width binary string, LSB first
            binary_mask = f"{mask:0{nrow}b}"[::-1]
            # Split into groups of 10 bits for readability
            mask_groups = [binary_mask[i:i+10] for i in range(0, nrow, 10)]
            f.write(f"{'   '.join(mask_groups)}\n")

    print(f"Current dead mask written to {mask_filename}")


def read_dead_masks(mask_filename="dead_masks.cfg", nrow=256):
    """
    Read dead channel masks from a file written by write_dead_masks().

    Args:
        mask_filename (str): Path to the mask file. Default is 'dead_masks.cfg'.
        nrow (int): Expected number of bits per mask. Must match the value used
            when writing. Default is 256.

    Returns:
        dict: {col: mask} integers, or empty dict if file not found.

    Raises:
        ValueError: If any line has the wrong number of bits.
    """
    dead_masks = {}
    try:
        with open(mask_filename, "r") as f:
            for col, line in enumerate(f):
                # Strip all whitespace (spaces between groups and newline)
                binary_mask = re.sub(r"\s+", "", line)
                if len(binary_mask) != nrow:
                    raise ValueError(
                        f"Row {col} in '{mask_filename}' has {len(binary_mask)} bits, expected {nrow}."
                    )
                # File stores LSB first; reverse before converting to int
                dead_masks[col] = int(binary_mask[::-1], 2)
    except FileNotFoundError:
        print(f"Error: {mask_filename} not found.")
        return {}
    return dead_masks
