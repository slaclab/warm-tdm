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
                ret = np.zeros(len(self.dependencies), np.float64)

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
                ret = np.zeros((len(self._config.columnMap)), np.float64)
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

        super().__init__(groups='DocApi',
                         description = "Interface to a WarmTDM 'Flange Group' consisting of multiple Row and Column boards."
                                       "This class contains the top level configuration variables as well as a number of tuning and run control processes.",
                         **kwargs)

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

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

        ############################################
        # Local Variables describing configuration
        ############################################

        self.add(pr.LocalVariable(
            name='NumRowBoards',
            description='Number of row boards in the Group.',
            value=self._config.rowBoards,
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumRows',
            description='Total number of rows in the Group. Max is NumRowBoards * 32.',
            value=len(self._config.rowMap),
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumColumnBoards',
            description='Number of colmumn boards in the Group.',
            value=self._config.columnBoards,
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumColumns',
            description='Total number of columns in the Group. Max is NumColumnBoards * 8.',
            value=len(self._config.columnMap),
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='RowOrder',
            description='Order row readout.'
                        'Each position is a point in time containing the row index to readout.'
                        'Values can be accessed as a full array or as single values using an index key.'
                        'Max number of values is TBD.',
            localGet=lambda: self._config.rowOrder,
            mode='RO',
            typeStr='int[]',
            hidden=True))

        self.add(pr.LocalVariable(
            name='RowMap',
            description='Contains the conversion between row index and (board,channel).'
                        'Values can be accessed as a full array or as single values using an index key.'
                        'Each value is a PhysicalMap object containg board and channel attributes.'
                        'Max Length = RowBoards * 32.',
            localGet=lambda: self._config.rowMap,
            mode='RO',
            typeStr='PhysicalMap[]',
            hidden=True))

        self.add(pr.LocalVariable(
            name='ColumnMap',
            description='Contains the conversion between column index and (board,channel).'
                        'Values can be accessed as a full array or as single values using an index key.'
                        'Each value is a PhysicalMap object containg board and channel attributes.'
                        'Max length = ColumnBoards * 8.',
            localGet=lambda: self._config.columnMap,
            mode='RO',
            typeStr='PhysicalMap[]',
            hidden=True))

        ##################################
        # Tuning enables
        ##################################

        # Tuning row enables
        # Determines if a given row is activated
        # during the tuning process
        rtsize = len(self._config.rowMap) if self._config.rowBoards > 0 else 1
        self.add(pr.LocalVariable(
            name='RowTuneEnable',
            description='Array of booleans which enable the tuning of each row.'
                        'Total length = NumRows.'
                        'Values can be accessed as a full array or as single values using an index key.'
                        'Not yet implemented in the tuning routines.',
            value=np.ones(rtsize, bool),
            groups='TopApi',
            mode='RW'))

        # Tuning column enables
        # Determines if a column is activated
        # during the tuning process
        self.add(pr.LocalVariable(
            name='ColTuneEnable',
            description='Array of booleans which enable the tuning of each column.'
                        'Total length = NumColumns.'
                        'Values can be accessed as a full array or as single values using the an index key.'
                        'Not yet implemented in the tuning routines.',
            value=np.ones(len(self._config.columnMap), bool),
            groups='TopApi',
            mode='RW'))

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
            description='Enables the manual section (RowTuneIndex) of a row for tuning purposes. Used by the tuning scripts.',
            typeStr='bool',
            groups='NoDoc',
            value=False,
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].Mode
                          for m in self._config.rowMap]))


        # Row Tune Channel
        # Sets the selected channel to its ON value
        # Sets all other channels to OFF
        self.add(RowTuneIndexVariable(
            name='RowTuneIndex',
            description='Manual selection of row for tuning. When RowTunEn is true the FasFluxOn value for this row is output. All other rows are set to FasFluxOff.',
            typeStr='int',
            groups='NoDoc',
            value=0,
            config=self._config,
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].Active
                          for m in self._config.rowMap]))


        # FAS Flux off values, accessed with row index
        self.add(GroupLinkVariable(
            name='FasFluxOff',
            description='FasFluxOff value for each row. Total length = RowBoards * 32.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].OffValue
                          for m in self._config.rowMap]))

        # FAS Flux on values, accessed with row index
        self.add(GroupLinkVariable(
            name='FasFluxOn',
            description='FasFluxOn value for each row. Total length = RowBoards * 32.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].OnValue
                          for m in self._config.rowMap]))


        #####################################
        # Column board acces variables
        #####################################

        self.add(SaOutVariable(
            name='SaOutAdc',
            description='Current ADC value in Volts for each column. Total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using an index key.',
            units='V',
            groups='NoDoc',
            config=self._config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].DataPath.WaveformCapture.AdcAverage
                            for m in self._config.columnMap]))

        self.add(ArrayVariableDevice(
            name='SaOutAdcDev',
            groups='NoDoc',
            size=len(self._config.columnMap),
            variable = self.SaOutAdc))

        # Remove amplifier gain
        self.add(pr.LinkVariable(
            name='SaOut',
            description='Current ADC value in mV for each column. Total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.SaOutAdc],
            groups='NoDoc',
            units = 'mV',
            disp = '{:0.06f}',
            linkedGet = lambda index, read: 1e3 * self.SaOutAdc.get(index=index, read=read)/200))

        self.add(GroupLinkVariable(
            name='SaBias',
            description='SaBias value for each column. 1D array with total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.Bias[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name='SaOffset',
            description='SaOffset value for each column. 1D array with total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.Offset[m.channel]
                            for m in self._config.columnMap]))

        self.add(FastDacVariable(
            name='SaFb',
            description='SaFb value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * (RowBoards * 32).'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self._config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SAFb.ColumnVoltages[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name='SaFbForce',
            groups='NoDoc',
            description='SaFb value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SAFb.Override[m.channel]
                            for m in self._config.columnMap]))

        self.add(FastDacVariable(
            name='Sq1Bias',
            description='Sq1Bias value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * (RowBoards * 32).'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self._config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.ColumnVoltages[m.channel]
                            for m in self._config.columnMap]))


        self.add(GroupLinkVariable(
            name='Sq1BiasForce',
            groups='NoDoc',
            description='Sq1Bias value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.Override[m.channel]
                            for m in self._config.columnMap]))

        self.add(FastDacVariable(
            name='Sq1Fb',
            description='Sq1Fb value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * (RowBoards * 32).'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self._config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.ColumnVoltages[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name='Sq1FbForce',
            groups='NoDoc',
            description='Sq1Fb value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.Override[m.channel]
                            for m in self._config.columnMap]))

        self.add(GroupLinkVariable(
            name = 'TesBias',
            description='TesValue value for each column.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
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
            description="FLL Enable Control."))

        self.add(warm_tdm_api.ConfigSelect(self,groups=['NoDoc']))

        #############################################
        # Tuning and diagnostic Processes
        #############################################
        self.add(warm_tdm_api.SaOffsetProcess())
        self.add(warm_tdm_api.SaOffsetSweepProcess(groups=['NoDoc'],config=self._config))
        self.add(warm_tdm_api.SaTuneProcess(config=self._config))
        self.add(warm_tdm_api.Sq1TuneProcess())
        self.add(warm_tdm_api.FasTuneProcess())
        self.add(warm_tdm_api.Sq1DiagProcess())
        self.add(warm_tdm_api.TesRampProcess())
        self.add(warm_tdm_api.SaStripChartProcess(groups=['NoDoc']))

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

