import pyrogue as pr
import warm_tdm
import warm_tdm_api
import numpy as np
import dataclasses



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
    def __init__(self, tuneEnVar=None, groups='TopApi', disp='{:0.4f}', **kwargs):
        super().__init__(
            linkedSet=self._set,
            linkedGet=self._get,
            groups=groups,
            disp=disp,
            **kwargs)
        self.tuneEnVar = tuneEnVar
        deps =  kwargs['dependencies']
        if len(deps) > 0:
            self._units = deps[0].units

    # Set group values, index is column or row
    def _set(self, *, value, index, write):
        if len(self.dependencies) == 0:
            return

        #print(f'{self.path}.set({value=}, {index=}, {write=})')
        # Dependencies represent the channel values in channel order
        # So just use those references to do thtre set accesses
        with self.parent.root.updateGroup():
            if index != -1:
                if self.tuneEnVar.get(index=index):
                    self.dependencies[index].set(value=value, write=write)
            else:
                for idx, (var, val) in enumerate(zip(self.dependencies, value)):
                    if self.tuneEnVar is not None and self.tuneEnVar.get(index=idx):
                        #print(f'Setting {self.path}[{idx}] = {val}')
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
                    # Read only enabled blocks
                    for idx, var in enumerate(self.dependencies):
                        if self.tuneEnVar.get(index=idx):
                            var.get(read=True, check=False)

                    # Wait for read transactions
                    for b in self.depBlocks:
                        pr.checkTransaction(b)

                # Assign results to return variable
                for idx, var in enumerate(self.dependencies):
                    ret[idx] = var.get(read=False)

            #if read: print(f'{self.path}.get({index=}, {read=}) - {ret}')
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
    def __init__(self, config, disp='{:0.04f}', **kwargs):

        self._config = config

        super().__init__(
            mode='RO',
            disp = disp,
            **kwargs)

    # Get SA Out value, index is column
    # Each dep is an array variable of 8 channels for each board
    def _get(self, read=True, index=-1):
        with self.parent.root.updateGroup():
            if index != -1:
                col = self._config.columnMap[index]
                board, chan = col.board, col.channel
                ret = self.dependencies[board].get(index=chan, read=read)
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

            #if read: print(f'{self.path}.get({index=}, {read=}) \n{ret}'),         
            return ret

class FastDacVariable(GroupLinkVariable):
    def __init__(self, config, **kwargs):

        self._config = config
        if 'hidden' not in kwargs:
            kwargs['hidden'] = True

        super().__init__(disp = '{:0.04f}', **kwargs)

    def _set(self, value, index, write):
        with self.parent.root.updateGroup():

            # index access
            if index != -1:
                colIndex = index[0]
                rowIndex = index[1]
                self.dependencies[colIndex].set(value=value, index=rowIndex, write=write)

            # Full array access
            else:
                for colIndex in range(self._config.numColumns):
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
                rows = 256 #len(self._config.rowMap)
                cols = len(self._config.columnMap)

                ret = np.zeros((cols, rows), np.float64)
                for colIndex in range(cols):
                    ret[colIndex] = self.dependencies[colIndex].get(index=-1, read=read)

                return ret



class Group(pr.Device):
    
    def makeGuiGroup(self, arrVar):
        for i in range(self.config.numColumns):
            self.add(pr.LinkVariable(
                name = f'_{arrVar.name}[{i}]',
                mode = arrVar.mode,
                disp = arrVar.disp,
                units = arrVar.units,
                guiGroup = arrVar.name,
                dependencies = [arrVar],
                linkedGet = lambda read, x=i: arrVar.get(read=read, index=x),
                linkedSet = None if arrVar.mode == 'RO' else lambda value, write, x=i: arrVar.set(value, write=write, index=x)))
            
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
        self.config = groupConfig

        # Add the Hardware Device tree
        self.add(warm_tdm.HardwareGroup(
            groupId=groupId,
            dataWriter=dataWriter,
            simulation=simulation,
            emulate=emulate,
            host=groupConfig.host,
            colBoards=groupConfig.columnBoards,
            rowBoards=groupConfig.rowBoards,
#            rows=len(groupConfig.rowMap),
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
            value=self.config.rowBoards,
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumRows',
            description='Total number of rows in the Group. NumRowBoards * 32.',
            value=len(self.config.rowMap),
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumColumnBoards',
            description='Number of colmumn boards in the Group.',
            value=self.config.columnBoards,
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumColumns',
            description='Total number of columns in the Group. NumColumnBoards * 8.',
            value=len(self.config.columnMap),
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='RowOrder',
            description='Order row readout.'
                        'Each position is a point in time containing the row index to readout.'
                        'Values can be accessed as a full array or as single values using an index key.'
                        'Max number of values is TBD.',
            localGet=lambda: self.config.rowOrder,
            mode='RO',
            typeStr='int[]',
            hidden=True))

        self.add(pr.LocalVariable(
            name='RowMap',
            description='Contains the conversion between row index and (board,channel).'
                        'Values can be accessed as a full array or as single values using an index key.'
                        'Each value is a PhysicalMap object containg board and channel attributes.'
                        'Total length = RowBoards * 32.',
            localGet=lambda: [dataclasses.asdict(m) for m in self.config.rowMap],
            mode='RO',
            typeStr='PhysicalMap[]',
            hidden=True))

        self.add(pr.LocalVariable(
            name='ColumnMap',
            description='Contains the conversion between column index and (board,channel).'
                        'Values can be accessed as a full array or as single values using an index key.'
                        'Each value is a PhysicalMap object containg board and channel attributes.'
                        'Total length = ColumnBoards * 8.',
            localGet=lambda: [dataclasses.asdict(d) for d in self.config.columnMap],
            mode='RO',
            typeStr='PhysicalMap[]',
            hidden=True))

        

        ##################################
        # Tuning enables
        ##################################

        # Tuning row enables
        # Determines if a given row is activated
        # during the tuning process
        rtsize = len(self.config.rowMap) if self.config.rowBoards > 0 else 1
        self.add(pr.LocalVariable(
            name='RowTuneEnable',
            description='Array of booleans which enable the tuning of each row.'
                        'Total length = RowBoards * 32.'
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
                        'Total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using the an index key.'
                        'Not yet implemented in the tuning routines.',
            value=np.ones(len(self.config.columnMap), bool),
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
            name='RowTuneMode',
            description='Enables the manual section (RowTuneIndex) of a row for tuning purposes. Used by the tuning scripts.',
            typeStr='bool',
            groups='NoDoc',
            value=False,
            tuneEnVar = self.RowTuneEnable,
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].Mode
                          for m in self.config.rowMap]))


        # Row Tune Channel
        # Sets the selected channel to its ON value
        # Sets all other channels to OFF
        self.add(RowTuneIndexVariable(
            name='RowTuneIndex',
            description='Manual selection of row for tuning. When RowTunEn is true the FasFluxOn value for this row is output. All other rows are set to FasFluxOff.',
            typeStr='int',
            value=0,
            config=self.config,
            tuneEnVar = self.RowTuneEnable,
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].Active
                          for m in self.config.rowMap]))


        # FAS Flux off values, accessed with row index
        self.add(GroupLinkVariable(
            name='FasFluxOff',
            description='FasFluxOff value for each row. Total length = RowBoards * 32.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].OffValue
                          for m in self.config.rowMap],
            tuneEnVar = self.RowTuneEnable))

        # FAS Flux on values, accessed with row index
        self.add(GroupLinkVariable(
            name='FasFluxOn',
            description='FasFluxOn value for each row. Total length = RowBoards * 32.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies=[self.HardwareGroup.RowBoard[m.board].RowSelectArray.RowSelect[m.channel].OnValue
                          for m in self.config.rowMap],
            tuneEnVar = self.RowTuneEnable))

        self.rowSelectedVars = [
            self.RowTuneEnable,
#            self.RowTuneMode,
#            self.RowTuneIndex,
            self.FasFluxOff,
            self.FasFluxOn]


        #####################################
        # Column board acces variables
        #####################################

#         self.add(pr.LocalVariable(
#             name = 'SA_FB_SHUNT_R',
#             hidden = True,
#             mode = 'RO',
#             value = {k:v['SA_FB_SHUNT_R'] for k,v in self.HardwareGroup.ColumnBoard[0].loading.Column[items()}))

#         self.add(pr.LocalVariable(
#             name = 'SQ1_FB_SHUNT_R',
#             hidden = True,
#             mode = 'RO',
#             value = {k:v['SQ1_FB_SHUNT_R'] for k,v in self.HardwareGroup.ColumnBoard[0].loading.items()}))
        

        self.add(GroupLinkVariable(
            name='SaBiasVoltage',
            description='SaBias value for each column. 1D array with total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.BiasVoltage[m.channel]
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))



        self.add(GroupLinkVariable(
            name='SaBiasCurrent',
            description='SaBias value for each column. 1D array with total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.BiasCurrent[m.channel]
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))
        

        self.add(GroupLinkVariable(
            name='SaOffset',
            description='SaOffset value for each column. 1D array with total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.OffsetVoltage[m.channel]
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))

        self.add(SaOutVariable(
            name='SaOutAdc',
            description='Current ADC value in Volts for each column. Total length = ColumnBoards * 8.'
                        'Values can be accessed as a full array or as single values using an index key.',
#            units='V',
            config=self.config,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].DataPath.WaveformCapture.AdcAverage
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))


#         self.add(ArrayVariableDevice(
#             name='SaOutAdcDev',
#             groups='NoDoc',
#             size=len(self.config.columnMap),
#             variable = self.SaOutAdc))


        # Remove amplifier gain and bias
        self.add(SaOutVariable(
            name='SaOut',
            description='Current SA_OUT value in mV for each column before amplifier gain, adjusted for current offset value'
            'Total length = ColumnBoards * 8. '
            'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaOut
                            for m in self.config.columnMap],
            config = self.config,
            disp = '{:0.03f}',))
#            units = 'mV'))


        self.add(SaOutVariable(
            name='SaOutNorm',
            description='Current SA_OUT value in mV for each column before amplifier gain, not adjusted for current offset value'
            'Total length = ColumnBoards * 8. '
            'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SaOutNorm
                            for m in self.config.columnMap],
#            units = 'mV',            
            config = self.config,
            disp = '{:0.03f}'))

        

        self.add(FastDacVariable(
            name='SaFbCurrent',
            description='SaFb value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * 256.'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self.config,
            hidden = True,
#            units = 'mA',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SAFb.ColumnCurrents[m.channel]
                            for m in self.config.columnMap]))

        self.add(GroupLinkVariable(
            name='SaFbForceCurrent',
            description='SaFb value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SAFb.OverrideCurrent[m.channel]
                            for m in self.config.columnMap],
#            units = 'mA',
            tuneEnVar = self.ColTuneEnable))


        self.add(FastDacVariable(
            name='SaFbVoltage',
            description='SaFb value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * (RowBoards * 32).'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self.config,
            hidden = True,
#            units = 'V',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SAFb.ColumnVoltages[m.channel]
                            for m in self.config.columnMap]))

        self.add(GroupLinkVariable(
            name='SaFbForceVoltage',
            description='SaFb value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SAFb.OverrideVoltage[m.channel]
                            for m in self.config.columnMap],
#            units = 'V',
            tuneEnVar = self.ColTuneEnable))


        self.add(FastDacVariable(
            name='Sq1BiasCurrent',
            description='Sq1Bias value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * (RowBoards * 32).'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self.config,
            hidden = True,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.ColumnCurrents[m.channel]
                            for m in self.config.columnMap]))

        self.add(GroupLinkVariable(
            name='Sq1BiasForceCurrent',
            description='Sq1Bias value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.OverrideCurrent[m.channel]
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))
        

        self.add(FastDacVariable(
            name='Sq1BiasVoltage',
            description='Sq1Bias value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * (RowBoards * 32).'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self.config,
            hidden = True,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.ColumnVoltages[m.channel]
                            for m in self.config.columnMap]))


        self.add(GroupLinkVariable(
            name='Sq1BiasForceVoltage',
            description='Sq1Bias value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.OverrideVoltage[m.channel]
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))



        self.add(FastDacVariable(
            name='Sq1FbCurrent',
            description='Sq1Fb value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * (RowBoards * 32).'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self.config,
            hidden = True,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.ColumnCurrents[m.channel]
                            for m in self.config.columnMap]))

        self.add(GroupLinkVariable(
            name='Sq1FbForceCurrent',
            description='Sq1Fb value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.OverrideCurrent[m.channel]
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))
        

        self.add(FastDacVariable(
            name='Sq1FbVoltage',
            description='Sq1Fb value for each column/row used during readout.'
                         '2D array with total length = (ColumnBoards * 8) * (RowBoards * 32).'
                         'Values can be accessed as a full 2D array or pass a (col, row) tuple for the index key to access each value.',
            config = self.config,
            hidden = True,
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.ColumnVoltages[m.channel]
                            for m in self.config.columnMap]))


        self.add(GroupLinkVariable(
            name='Sq1FbForceVoltage',
            description='Sq1Fb value for each column used during tuning.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.OverrideVoltage[m.channel]
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))


        
        self.add(GroupLinkVariable(
            name = 'TesBias',
            description='TesValue value for each column.'
                         '1D array with total length ColumnBoards * 8.'
                         'Values can be accessed as a full array or as single values using an index key.',
            dependencies = [self.HardwareGroup.ColumnBoard[m.board].TesBias.BiasCurrent[m.channel]
                            for m in self.config.columnMap],
            tuneEnVar = self.ColTuneEnable))

        @self.command()
        def ZeroSaBias():
            self.SaBiasCurrent.set(0)
            self.SaOffset.set(0)

        @self.command()
        def ZeroSaFb():
            self.SaFbForceCurrent.set(0)

        @self.command()
        def ZeroSq1Bias():
            self.Sq1BiasForceCurrent.set(0)

        @self.command()
        def ZeroSq1Fb():
            self.Sq1FbForceCurrent.set(0)
        
        @self.command()
        def ZeroDacs():
            self.Sq1FbForceCurrent.set(0)
            self.Sq1BiasForceCurrent.set(0)
            self.SaFbForceCurrent.set(0)
            self.SaBiasCurrent.set(0)
            self.SaOffset.set(0)

        self.columnSelectedVars = [
            self.ColTuneEnable,
            self.SaBiasVoltage,
            self.SaBiasCurrent,
            self.SaOffset,
            self.SaOutAdc,
            self.SaOut,
            self.SaOutNorm,
            self.SaFbForceCurrent,
            self.SaFbForceVoltage,
            self.Sq1BiasForceCurrent,
            self.Sq1BiasForceVoltage,        
            self.Sq1FbForceCurrent,
            self.Sq1FbForceVoltage,
            self.TesBias
        ]

        for var in self.columnSelectedVars:
            self.makeGuiGroup(var)

        self.rowColumnSelectedVars = [
            self.SaFbCurrent,
            self.Sq1BiasCurrent,
            self.Sq1FbCurrent]

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
        self.add(warm_tdm_api.SaOffsetProcess(config=self.config))
        self.add(warm_tdm_api.SaOffsetSweepProcess(config=self.config, group=self))
        self.add(warm_tdm_api.SaTuneProcess(config=self.config))
        self.add(warm_tdm_api.Sq1TuneProcess(config=self.config, groups=['NoDoc']))
        self.add(warm_tdm_api.FasTuneProcess(groups=['NoDoc']))
        self.add(warm_tdm_api.Sq1DiagProcess(groups=['NoDoc']))
        self.add(warm_tdm_api.TesRampProcess(groups=['NoDoc']))
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
