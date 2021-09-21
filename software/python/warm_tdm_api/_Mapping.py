
from dataclasses import dataclass


@dataclass
class PhysicalMapping:
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
class VirtualMapping:
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
    columnMap: PhysicalMapping
    columnEnable: [bool]
    rowMap: PhysicalMapping
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
        columnBoards: str
            Number of column boards
        rowBoards: str
            Number of row boards
    """

