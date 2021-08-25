import pyrogue as pr

import warm_tdm

class RowModuleDacs(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for i in range(12):
            self.add(warm_tdm.Ad9106(
                name = f'Ad9106[{i}]',
                offset = i * 0x100000))

    def readBlocks(self, *, recurse=True, variable=None, checkEach=False, index=-1, **kwargs):
        """
        Perform background reads
        """
        checkEach = checkEach or self.forceCheckEach

        # Wait for outstanding blocks before starting
#        print(f"Calling root.checkBlocks() in {self.path}")
        self.parent.checkBlocks(recurse=True)

        if variable is not None:
            pr.startTransaction(variable._block, type=rim.Read, checkEach=checkEach, variable=variable, index=index, **kwargs)

        else:
            for block in self._blocks:
                if block.bulkOpEn:
                    pr.startTransaction(block, type=rim.Read, checkEach=checkEach, **kwargs)

            if recurse:
                for key,value in self.devices.items():
                    value.readBlocks(recurse=True, checkEach=checkEach, **kwargs)
 #                   print(f'Called {value.path}.readBlocks(), calling checkBlocks()')
                    value.checkBlocks(recurse=True)
 #                   print(f'Called {value.path}.checkBlocks()')
