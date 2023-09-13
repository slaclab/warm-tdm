import pyrogue as pr
import warm_tdm
import warm_tdm_api
import numpy as np


class ConfigSelect(pr.Device):
    def __init__(self, group, **kwargs):
        super().__init__(**kwargs)



        self.add(pr.LocalVariable(name='ColumnSelect',
                                 value=0,
                                 mode='RW',
                                 minimum=0,
                                 maximum=group.config.nowRows,
                                 groups='TopApi',
                                 description="Row Configuration Selection"))



        self.add(pr.LocalVariable(name='RowSelect',
                                 value=0,
                                 mode='RW',
                                 minimum=0,
                                 maximum=group.config.numColumns,
                                 groups='TopApi',
                                 description="Row Configuration Selection"))

        def _get(var, read):
            with self.root.updateGroup():
                index = var.dependencies[1].value()
                if len(var.dependencies) == 3:
                    index = (index, var.dependencies[2].value())
                return var.dependencies[0].get(read=read, index=index)

        def _set(var, value, write):
            with self.root.updateGroup():
                index = var.dependencies[1].value()
                if len(var.dependencies) == 3:
                    index = (index, var.dependencies[2].value())
                return var.dependencies[0].set(value=value, write=write, index=index)

        for var in group.columnSelectedVars:
            lv = pr.LinkVariable(
                name = var.name,
                disp = var.disp if var.name != 'ColTuneEnable' else  {False: 'False', True: 'True'},
                units = var.units,
                mode = var.mode,
                dependencies = [var, self.ColumnSelect],
                linkedSet = None if var.mode == 'RO' else _set,
                linkedGet = _get)
            self.add(lv)


        for var in group.rowSelectedVars:
            lv = pr.LinkVariable(
                name = var.name,
                disp = var.disp if var.name != 'RowTuneEnable' else  {False: 'False', True: 'True'},
                units = var.units,
                mode = var.mode,
                dependencies = [var, self.RowSelect],
                linkedSet = None if var.mode == 'RO' else _set,
                linkedGet = _get)
            self.add(lv)

        for var in group.rowColumnSelectedVars:
            self.add(pr.LinkVariable(
                name = var.name,
                disp = var.disp,
                units = var.units,
                mode = var.mode,
                dependencies = [var, self.ColumnSelect, self.RowSelect],
                linkedSet = None if var.mode == 'RO' else _set,
                linkedGet = _get))
