
class GroupConfig:
    """Group Configuration

    Attributes
    ----------
    columnBoards : int
        Number of column boards
    rowBoards : int
        Number of row boards
    maxRows : int
        Maximum row index address space (maps to ROW_ADDR_BITS_G in firmware)
    numColumns : int
        Total number of columns (columnBoards * 8)
    host : str
        Host IP address
    """

    def __init__(self, *, columnBoards, rowBoards, maxRows=128, host='192.168.3.11'):
        self.columnBoards = columnBoards
        self.rowBoards = rowBoards
        self.maxRows = maxRows
        self.numColumns = columnBoards * 8
        self.host = host
