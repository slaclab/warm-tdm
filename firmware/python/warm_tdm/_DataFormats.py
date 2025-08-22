import numpy as np

from collections import defaultdict
from dataclasses import dataclass, field
from typing import List

def signed_int(arr):
    return int.from_bytes(arr, 'little', signed=True)

def unsigned_int(arr):
    return int.from_bytes(arr, 'little', signed=False)    


@dataclass
class DataSample:

    row: int
    col: int
    value: int

    @classmethod
    def from_numpy(cls, arr):
        return cls(
            row = arr[3],
            col = arr[4],
            value = signed_int(arr[0:3]))

@dataclass
class DataReadout:

    readoutCount: int
    rowSeqCount: int
    runTime: int
    samples: List[DataSample] = field(default_factory=list)

    @classmethod
    def from_numpy(cls, arr):
        words = arr[:-5].reshape(-1, 5)
        return cls(
            readoutCount = unsigned_int(words[0:2, 0:4]),
            rowSeqCount = unsigned_int(words[2:4, 0:4]),
            runTime = unsigned_int(words[4:6, 0:4]),
            samples = [DataSample.from_numpy(w) for w in words[6:]])
        


    
