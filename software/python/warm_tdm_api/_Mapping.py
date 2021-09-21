
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
    row : int
    column: int
""" Virtual Detector Mapping
    Attributes
    ----------
    row : int
        Physical Row
    column : int
        Physical Column
"""

