
class GroupConfig:
    """Group Configuration

    Attributes
    ----------
    columnBoards : int
        Number of column boards
    rowBoards : int
        Number of row boards
    maxRows : int
        Maximum row index address space. Equals 2**ROW_ADDR_BITS_G in firmware.
        Default 256 matches the RTL default ROW_ADDR_BITS_G=8 that every 325
        target inherits; the ColumnFpgaBoard160Coord target overrides this to 5
        (=> maxRows=32). NOTE: this is currently software-side only (RowMap RAM
        sizing) — it is NOT threaded into the firmware HardwareGroup on this
        branch, pending the floating-point / coherent-row-sizing firmware work.
    numColumns : int
        Total number of columns (columnBoards * 8)
    host : str
        Host IP address
    """

    def __init__(self, *, columnBoards, rowBoards, maxRows=256, host='192.168.3.11'):
        self.columnBoards = columnBoards
        self.rowBoards = rowBoards
        self.maxRows = maxRows
        self.numColumns = columnBoards * 8
        self.host = host
