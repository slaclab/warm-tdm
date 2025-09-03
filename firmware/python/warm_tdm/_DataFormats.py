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
            row = arr[5],
            col = arr[6],
            value = arr[0:4].view(np.float32)[0])

@dataclass
class DataReadout:

    readoutCount: int
    rowSeqCount: int
    runTime: int
    samples: List[DataSample] = field(default_factory=list)

    @classmethod
    def from_numpy(cls, arr):
        words = arr[:-8].reshape(-1, 8)
        return cls(
            readoutCount = unsigned_int(words[0]),
            rowSeqCount = unsigned_int(words[1]),
            runTime = unsigned_int(words[2]),
            samples = [DataSample.from_numpy(w) for w in words[3:]])
        


    
