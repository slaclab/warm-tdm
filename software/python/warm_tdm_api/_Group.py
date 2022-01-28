import pyrogue as pr
import warm_tdm
import warm_tdm_api
import numpy as np

class ArrayVariableDevice(pr.Device):
    def __init__(self, *, variable, size, **kwargs):
        super().__init__(**kwargs)

        for i in range(size):
            self.add(pr.LinkVariable(
                name=f'idx[{i}]',
                linkedGet = lambda read, ch=i: variable.get(index=ch, read=read),
                linkedSet = lambda value, write, ch=i: variable.set(value=value, index=ch, write=write)))

# Generic LinkVariable class for accessing a set of
# Variables across multiple boards as a single array.
# Dependencies must be passed in Column order for generic
# get and set functions to work.
class GroupLinkVariable(pr.LinkVariable):
    def __init__(self, groups='TopApi', disp='{:0.4f}', **kwargs):
        super().__init__(
            linkedSet=self._set,
            linkedGet=self._get,
            groups=groups,
            disp=disp,
            **kwargs)

    # Set group values, index is column or row
    def _set(self, *, value, index, write):
        if len(self.dependencies) == 0:
            return
        # Dependencies represent the channel values in channel order
        # So just use those references to do the set accesses
        with self.parent.root.updateGroup():
            if index != -1:
                self.dependencies[index].set(value=value, write=write)
            else:
                for var, val in zip(self.dependencies, value):
                    var.set(value=val, write=write)

    # Get group values, index is column or row
    def _get(self, *, index, read):
        #print(f'{self.path}._get(index={index}, read={read}) - deps={self.dependencies}')
        if len(self.dependencies) == 0:
            return 0
        with self.parent.root.updateGroup():
            if index != -1:
                return self.dependencies[index].get(read=read)
            else:
                ret = np.zeros(len(self.dependencies), np.float)

                for idx, var in enumerate(self.dependencies):
                    ret[idx] = var.get(read=read)

                return ret

class RowTuneEnVariable(GroupLinkVariable):
    def __init__(self, **kwargs):

        self._value = False
        super().__init__(**kwargs)

    def _set(self, *, value, write):
        with self.parent.root.updateGroup():
            mode = 'Tune' if value is True else 'Run'
            for var in self.dependencies:
                var.set(value=mode, write=write)
            self._value = value

    def _get(self, read):
        with self.parent.root.updateGroup():
            return self._value

class RowTuneIndexVariable(GroupLinkVariable):
    def __init__(self, config, **kwargs):

        self._value = 0
        self._config = config
        self._rows = len(config.rowMap)
        
        super().__init__(**kwargs)

    def _set(self, *, value, write):

        # Corner case of no row boards in group
        if self._rows == 0:
            self._value = value
            return
        
        with self.parent.root.updateGroup():
            # First turn off any channel that is on
            for var in self.dependencies:
                if var.get() is True:
                    var.set(value=False, write=write)
            #Then turn on the selected channel
            self.dependencies[value].set(value=True, write=write)
            self._value = value

    def _get(self, read):
        with self.parent.root.updateGroup():
            return self._value



class SaOutVariable(GroupLinkVariable):
    def __init__(self, config, **kwargs):

        self._config = config

        super().__init__(
            mode='RO',
            disp = '{:0.06f}',
            **kwargs)

    # Get SA Out value, index is column
    def _get(self, read, index):
        with self.parent.root.updateGroup():
            if index != -1:
                col = self._config.columnMap[index]
                board, chan = col.board, col.channel
                return self.dependencies[board].get(index=chan, read=read)
            else:

                # Issue a read to all boards and wait for response
                for dep in self.dependencies:
                    dep.get(read=read, check=False)

                for dep in self.dependencies:
                    dep.parent.checkBlocks()

                # Iterate through all the channel values now held in shadow memory and assign to array
                ret = np.zeros((len(self._config.columnMap)), np.float)
                for idx, board, chan in self._config.colGetIter(index):
                    ret[idx] = self.dependencies[board].get(index=chan, read=False)

                return ret

class FastDacVariable(GroupLinkVariable):
    def __init__(self, config, **kwargs):

        self._config = config
        super().__init__(**kwargs)

    def _set(self, value, index, write):
        with self.parent.root.updateGroup():

            # index access
            if index != -1:
                colIndex = index[0]
                rowIndex = index[1]
                self.dependencies[colIndex].set(value=value, index=rowIndex, write=write)

            # Full array access
            else:
                for colIndex in range(len(self._config.columnMap)):
                    colBoard = self._config.columnMap[colIndex].board
                    colChan = self._config.columnMap[colIndex].channel
                    self.dependencies[colIndex].set(value=value[colIndex], index=-1, write=write)


    def _get(self, index, read):
        with self.parent.root.updateGroup():

            # index access
            if index != -1:
                colIndex = index[0]
                rowIndex = index[1]
                return self.dependencies[colIndex].get(index=rowIndex, read=read)

            # Full array access
            else:
                rows = len(self._config.rowMap)
                cols = len(self._config.columnMap)

                # Handle corner case of now row boards in group
                # Just pretend there are 64 channels
                if rows == 0:
                    rows = 64

                ret = np.zeros((cols, rows), np.float64)
                for colIndex in range(cols):
                    ret[colIndex] = self.dependencies[colIndex].get(index=-1, read=read)

                return ret



class Group(pr.Device):
    def __init__(self, groupConfig, groupId, dataWriter, simulation=False, emulate=False, plots=False, **kwargs):
        """
        Warm TDM Device
        Parameters
        ----------
        groupConfig : warm_tdm_api.GroupConfig
            Group configuration
        simulation: bool
           Flag to determine if simulation mode is enabled
        emulate: bool
           Flag to determine if emulation mode should be used
        """

        super().__init__(**kwargs)

        # Configuration
        self._config = groupConfig

        # Add the Hardware Device tree
        self.add(warm_tdm.HardwareGroup(
            groupId=groupId,
            dataWriter=dataWriter,
            simulation=simulation,
            emulate=emulate,
            host=groupConfig.host,
            colBoards=groupConfig.columnBoards,
            rowBoards=groupConfig.rowBoards,
            rows=len(groupConfig.rowMap),
            plots=plots,
            groups=['Hardware'],
            expand=True))

        ############################################
        # Local Variables describing configuration
        ############################################

        # Row Map
        self.add(pr.LocalVariable(
            name='RowMap',
            localGet=lambda: self._config.rowMap,
            mode='RO',
            typeStr='PhysicalMap[]',
            hidden=True))

        # Col Map
        self.add(pr.LocalVariable(
            name='ColumnMap',
            localGet=lambda: self._config.columnMap,
            mode='RO',
            typeStr='PhysicalMap[]',
            hidden=True))

        # Row Order
        self.add(pr.LocalVariable(
            name='RowOrder',
            localGet=lambda: self._config.rowOrder,
            mode='RO',
            typeStr='int[]',
            hidden=True))

        # Col Enable
        self.add(pr.LocalVariable(
            name='ColumnEnable',
            localGet=lambda: self._config.columnEnable,
            mode='RO',
            typeStr='bool[]',
            hidden=True))

        # Number of columns supported in this group
        self.add(pr.LocalVariable(
            name='NumColumns',
            value=len(self._config.columnMap),
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumColumnBoards',
            value=self._config.columnBoards,
            mode='RO',
            groups='TopApi'))

        # Number of rows supported in this group
        self.add(pr.LocalVariable(
            name='NumRows',
            value=len(self._config.rowMap),
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumRowBoards',
            value=self._config.rowBoards,
            mode='RO',
            groups='TopApi'))


        ##################################
        # Tuning enables
        ##################################

        # Tuning row enables
        # Determines if a given row is activated
        # during the tuning process
        rtsize = len(self._config.rowMap) if self._config.rowBoards > 0 else 1
        self.add(pr.LocalVariable(
            name='RowTuneEnable',
            value=np.ones(rtsize, np.bool),
            groups='TopApi',
            mode='RW',
            description="Tune enable for each row"))

        # Tuning column enables
        # Determines if a column is activated
        # during the tuning process
        self.add(pr.LocalVariable(
            name='ColTuneEnable',
            value=np.ones(len(self._config.columnMap), np.bool),
            groups='TopApi',
            mode='RW',
            description="Tune enable for each column"))



        ##################################
        # Row board access variables
        ##################################

        # Enable Row Tune Override
        # Puts all hardware row selects into tuning mode
#         self.add(pr.LocalVariable(
#             name='RowTuneEn',
#             value=False,
#             groups='TopApi',
#             mode='RW'))

        self.add(RowTuneEnVariable(
            name='RowTuneEn',
            typeStr='bool',
            value=False,
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].Mode
                          for m in self._config.rowMap]))


        # Row Tune Channel
        # Sets the selected channel to its ON value
        # Sets all other channels to OFF
        self.add(RowTuneIndexVariable(
            name='RowTuneIndex',
            typeStr='int',
            value=0,
            config=self._config,
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].Active
                          for m in self._config.rowMap]))


        # FAS Flux off values, accessed with row index
        self.add(GroupLinkVariable(
            name='FasFluxOff',
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].OffValue
                          for m in self._config.rowMap]))

        # FAS Flux on values, accessed with row index
        self.add(GroupLinkVariable(
            name='FasFluxOn',
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].OnValue
                          for m in self._config.rowMap]))


        #####################################
        # Column board acces variables
        #####################################

        self.add(SaOutVariable(
            name='SaOutAdc',
            units='V',
            config=self._config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].DataPath.WaveformCapture.AdcAverage
                            for m in self._config.columnMap]))

        self.add(ArrayVariableDevice(
            name='SaOutAdcDev',
            size=len(self._config.columnMap),
            variable = self.SaOutAdc))

        # Remove amplifier gain
        self.add(pr.LinkVariable(
            name='SaOut',
            dependencies = [self.SaOutAdc],
            units = 'mV',
            disp = '{:0.06f}',
            linkedGet = lambda index, read: 1e3 * self.SaOutAdc.get(index=index, read=read)/200))

        self.add(GroupLinkVariable(
            name='SaBias',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.Bias[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name='SaOffset',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.Offset[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name='SaFbForce',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SAFb.Override[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name='Sq1BiasForce',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.Override[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name='Sq1FbForce',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.Override[m.channel]
                            for m in self._config.columnMap]))

        self.add(FastDacVariable(
            name='SaFb',
            config = self._config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SAFb.ColumnVoltages[m.channel]
                            for m in self._config.columnMap]))

        self.add(FastDacVariable(
            name='Sq1Bias',
            config = self._config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.ColumnVoltages[m.channel]
                            for m in self._config.columnMap]))

        self.add(FastDacVariable(
            name='Sq1Fb',
            config = self._config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.ColumnVoltages[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name = 'TesBias',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].TesBias.BiasCurrent[m.channel]
                            for m in self._config.columnMap]))

        # FLL Enable value
        # Not yet implemented
        self.add(pr.LocalVariable(
            name='FllEnable',
            value=False,
            mode='RW',
            groups='TopApi',
            #dependencies=deps,
#            linkedSet=self._fllEnableSet,
#            linkedGet=self._fllEnableGet,
            description="FLL Enable Control"))





        # Initialize System
        self.add(pr.LocalCommand(name='Init',
                                 function=self._init,
                                 groups='TopApi',
                                 description="Initialize System"))

        self.add(warm_tdm_api.ConfigSelect(self))

        #############################################
        # Tuning and diagnostic Processes
        #############################################
        self.add(warm_tdm_api.SaOffsetProcess())
        self.add(warm_tdm_api.SaOffsetSweepProcess(config=self._config))
        self.add(warm_tdm_api.SaTuneProcess(config=self._config))
        self.add(warm_tdm_api.Sq1TuneProcess())
        self.add(warm_tdm_api.FasTuneProcess())
        self.add(warm_tdm_api.Sq1DiagProcess())
        self.add(warm_tdm_api.TesRampProcess())
        self.add(warm_tdm_api.SaStripChartProcess())



    # Set FLL Enable value
    def _fllEnableSet(self, value, write):
        with self.root.updateGroup():

            for col in self.HardwareGroup.ColumnBoard:
                pass
                #col.FllEnable.set(value,write=write) # Does not exist yet

    # Get FLL Enable value
    def _fllEnableGet(self, read):
        with self.root.updateGroup():

            #return self.HardwareGroup.ColumnBoard[0].FllEnable.get(read=read) # Does not exist yet
            return False

    # Init system
    def _init(self):

        # Local defaults
        #self.LoadConfig("defaults.yml")
        pass

        # Disable FLL
        #self.FllEnable.set(value=False)

        # Drive high TES bias currents?????
        #pass
