import pyrogue as pr
import numpy as np


class GroupLinkVariable(pr.LinkVariable):
    def __init__(self, tuneEnVar=None, groups='TopApi', disp='{:0.4f}', **kwargs):
        super().__init__(
            linkedSet=self._set,
            linkedGet=self._get,
            disp=disp,
            groups=groups,
            **kwargs)
        self.tuneEnVar = tuneEnVar
        deps = kwargs['dependencies']
        if len(deps) > 0:
            self._units = deps[0].units

    def _set(self, *, value, index, write):
        if len(self.dependencies) == 0:
            return

        with self.parent.root.updateGroup():
            if index != -1:
                if self.tuneEnVar.get(index=index):
                    self.dependencies[index].set(value=value, write=write)
            else:
                for idx, (var, val) in enumerate(zip(self.dependencies, value)):
                    if self.tuneEnVar is not None and self.tuneEnVar.get(index=idx):
                        var.set(value=val, write=False)

                pr.writeAndVerifyBlocks(self.depBlocks)

    def _get(self, *, index, read):
        if len(self.dependencies) == 0:
            return 0
        with self.parent.root.updateGroup():
            if index != -1:
                ret = self.dependencies[index].get(read=read)
            else:
                ret = np.zeros(len(self.dependencies), np.float64)

                if read is True:
                    for idx, var in enumerate(self.dependencies):
                        if self.tuneEnVar.get(index=idx):
                            var.get(read=True, check=False)

                    for b in self.depBlocks:
                        pr.checkTransaction(b)

                for idx, var in enumerate(self.dependencies):
                    ret[idx] = var.get(read=False)

            return ret


class GroupArrayLinkVariable(GroupLinkVariable):
    def __init__(self, config, **kwargs):
        self._config = config
        super().__init__(**kwargs)

    def _get(self, *, index=-1, read=True):
        with self.parent.root.updateGroup():
            if index != -1:
                board = index // 8
                chan = index % 8
                ret = self.dependencies[board].get(index=chan, read=read)
            else:
                for dep in self.dependencies:
                    dep.get(read=read, check=False)

                for dep in self.dependencies:
                    dep.parent.checkBlocks()

                ret = np.zeros(self._config.numColumns, np.float64)
                for i in range(self._config.numColumns):
                    board = i // 8
                    chan = i % 8
                    ret[i] = self.dependencies[board].get(index=chan, read=False)

            return ret

    def _set(self, *, value, index, write):
        with self.parent.root.updateGroup():
            if index != -1:
                if self.tuneEnVar is not None and self.tuneEnVar.get(index=index):
                    board = index // 8
                    chan = index % 8
                    self.dependencies[board].set(value=value, index=chan, write=False)
            else:
                for idx in range(self._config.numColumns):
                    if self.tuneEnVar is not None and self.tuneEnVar.get(index=idx):
                        board = idx // 8
                        chan = idx % 8
                        self.dependencies[board].set(value=value[idx], index=chan, write=False)

            pr.writeAndVerifyBlocks(self.depBlocks)


class FastDacVariable(GroupLinkVariable):
    def __init__(self, config, **kwargs):
        self._config = config

        if 'hidden' not in kwargs:
            kwargs['hidden'] = True

        super().__init__(disp='{:0.04f}', **kwargs)

    def _set(self, value, index, write):
        with self.parent.root.updateGroup():
            if index != -1:
                colIndex = index[0]
                rowIndex = index[1]
                self.dependencies[colIndex].set(value=value, index=rowIndex, write=write)
            else:
                for colIndex in range(self._config.numColumns):
                    self.dependencies[colIndex].set(value=value[colIndex], index=-1, write=write)

    def _get(self, index, read):
        with self.parent.root.updateGroup():
            if index != -1:
                colIndex = index[0]
                rowIndex = index[1]
                return self.dependencies[colIndex].get(index=rowIndex, read=read)
            else:
                cols = self._config.numColumns
                ret = [self.dependencies[colIndex].get(index=-1, read=read) for colIndex in range(cols)]
                return np.array(ret, dtype=np.float64)
