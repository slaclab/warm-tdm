
class GroupConfig:
    """Group Configuration

    Attributes
    ----------
    columnBoards : int
        Number of column boards
    rowBoards : int
        Number of row boards
    rowAddrBits : int
        Hardware row-address width, i.e. the deployed RTL generic ROW_ADDR_BITS_G
        (range 3..8). The firmware row RAMs are `2**rowAddrBits` deep. This is a
        property of the bitfile, NOT a software choice: default 8 (=> depth 256)
        matches the RTL default that every 325 target inherits; the
        ColumnFpgaBoard160Coord target builds with 5 (=> depth 32). Software has
        no way to read this back, so it must be told which bitfile is deployed.
    maxRows : int
        Number of row indices the software actually maps/uses. A software choice,
        bounded above by the hardware depth: `1 <= maxRows <= 2**rowAddrBits`.
        This is NOT the same as the address depth — it is how many of the
        available row slots we map into Rogue variables (and size the RowMap RAM
        for). Default 256 (the full depth of an 8-bit build).
    rowAddrDepth : int
        Convenience: `2**rowAddrBits`, the hardware row RAM depth.
    numColumns : int
        Total number of columns (columnBoards * 8)
    host : str
        Host IP address
    """

    def __init__(self, *, columnBoards, rowBoards, maxRows=256, rowAddrBits=8, host='192.168.3.11'):
        if not 3 <= rowAddrBits <= 8:
            raise ValueError(
                f'rowAddrBits (RTL ROW_ADDR_BITS_G) must be in 3..8, got {rowAddrBits}.')
        self.rowAddrBits = rowAddrBits
        self.rowAddrDepth = 2 ** rowAddrBits

        # maxRows is a software choice bounded by the hardware address depth --
        # they are different quantities and must not be conflated.
        if not 1 <= maxRows <= self.rowAddrDepth:
            raise ValueError(
                f'maxRows must be between 1 and the hardware row depth '
                f'2**rowAddrBits = {self.rowAddrDepth} (rowAddrBits={rowAddrBits}), '
                f'got {maxRows}.')

        self.columnBoards = columnBoards
        self.rowBoards = rowBoards
        self.maxRows = maxRows
        self.numColumns = columnBoards * 8
        self.host = host
