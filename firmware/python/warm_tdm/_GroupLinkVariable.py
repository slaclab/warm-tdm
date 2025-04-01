import pyrogue as pr

class GroupLinkVariable(pr.LinkVariable):
    def __init__(self, **kwargs):
        super().__init__(
            linkedSet=self._set,
            linkedGet=self._get,
            **kwargs)
        deps =  kwargs['dependencies']
        if len(deps) > 0:
            self._units = deps[0].units

    def _set(self, *, value, index, write):
        if len(self.dependencies) == 0:
            return

        #print(f'{self.path}.set({value=}, {index=}, {write=})')
        # Dependencies represent the channel values in channel order
        # So just use those references to do there set accesses
        with self.parent.root.updateGroup():
            if index != -1:
                self.dependencies[index].set(value=value, write=write)
            else:
                for idx, (var, val) in enumerate(zip(self.dependencies, value)):
                    var.set(value=val, write=False)

                pr.writeAndVerifyBlocks(self.depBlocks)

    # Get group values, index is column or row
    def _get(self, *, index, read):
        if len(self.dependencies) == 0:
            return 0
        with self.parent.root.updateGroup():
            if index != -1:
                ret = self.dependencies[index].get(read=read)
            else:
                ret = np.zeros(len(self.dependencies), np.float64)

                if read is True:
                    # Read the variables without blocking
                    for idx, var in enumerate(self.dependencies):
                        var.get(read=True, check=False)

                    # Wait for read transactions
                    for b in self.depBlocks:
                        pr.checkTransaction(b)

                # Assign results to return variable
                for idx, var in enumerate(self.dependencies):
                    ret[idx] = var.get(read=False)

            #if read: print(f'{self.path}.get({index=}, {read=}) - {ret}')
            return ret
        
