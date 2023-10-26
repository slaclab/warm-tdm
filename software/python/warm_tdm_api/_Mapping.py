
from dataclasses import dataclass


@dataclass
class PhysicalMap:
    board: int
    channel: int
    """ Row & Column Physical Mapping
        Attributes
        ----------
        board : int
            Board Index
        channel : int
            Channel index of the board
    """

class GroupConfig(object):
    """ Group Configuration
        Attributes
        ----------
        columnMap : PhysicalMapping
            Column map
        rowMap : PhysicalMapping
            Row map
        rowOrder : int
            Row order list for sequence
        host: str
            Host IP address
        columnBoards: int
            Number of column boards
        rowBoards: int
            Number of row boards
    """


    def __init__(self, *, rowBoards, columnBoards, host, rowOrder=None):

        self.rowBoards = rowBoards
        self.columnBoards = columnBoards
        self.host = host

        # Init row and column map
        self.columnMap = [PhysicalMap(board,chan) for board in range(columnBoards) for chan in range(8)]
        self.rowMap = [PhysicalMap(board,chan) for board in range(rowBoards) for chan in range(32)]

        self.numColumns = len(self.columnMap)
        self.numRows = len(self.rowMap)
        if self.numRows == 0:
            self.numRows = 1

        self.rowOrder = rowOrder
        if self.rowOrder is None:
            self.rowOrder = [i for i in range(len(self.rowMap))],

    def colSetIter(self, value, index):
        # Construct a generator to loop over
        if index != -1:
            return ((idx, self.columnMap[idx].board, self.columnMap[idx].channel, val) for idx, val in zip(range(index, index+1), [value]))
        else:
            return ((idx, self.columnMap[idx].board, self.columnMap[idx].channel, val) for idx, val in enumerate(value))

    def colGetIter(self, index):
        # Construct a generator to loop over
        if index != -1:
            ra = range(index, index+1)
        else:
            ra = range(len(self.columnMap))

        return ((idx, self.columnMap[idx].board, self.columnMap[idx].channel) for idx in ra)



