
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


@dataclass
class VirtualMap:
    row: int
    column: int
    """ Virtual Detector Mapping
        Attributes
        ----------
        row : int
            Physical Row
        column : int
            Physical Column
    """


@dataclass
class GroupConfig:
    columnMap: PhysicalMap
    columnEnable: [bool]
    rowMap: PhysicalMap
    rowOrder: [bool]
    host: str
    columnBoards: int
    rowBoards: int
    """ Group Configuration
        Attributes
        ----------
        columnMap : PhysicalMapping
            Column map
        columnEnable : [bool]
            Enable flag for each column
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

