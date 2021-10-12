import pyrogue as pr
import warm_tdm
import warm_tdm_api
import numpy as np


class Group(pr.Device):
    def __init__(self, groupConfig, groupId, dataWriter, simulation=False, emulate=False, **kwargs):
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

        self.add(warm_tdm.HardwareGroup(groupId=groupId,
                                        dataWriter=dataWriter,
                                        simulation=simulation,
                                        emulate=emulate,
                                        host=groupConfig.host,
                                        colBoards=groupConfig.columnBoards,
                                        rowBoards=groupConfig.rowBoards,
                                        rows=len(groupConfig.rowMap),
                                        groups=['Hardware'],
                                        expand=True))

        # Row Map
        self.add(pr.LocalVariable(name='RowMap',
                                  localGet=lambda: self._config.rowMap,
                                  mode='RO',
                                  typeStr='PhysicalMap[]',
                                  hidden=True,
                                  description="Row Map"))

        # Col Map
        self.add(pr.LocalVariable(name='ColumnMap',
                                  localGet=lambda: self._config.columnMap,
                                  mode='RO',
                                  typeStr='PhysicalMap[]',
                                  hidden=True,
                                  description="Column Map"))

        # Row Order
        self.add(pr.LocalVariable(name='RowOrder',
                                  localGet=lambda: self._config.rowOrder,
                                  mode='RO',
                                  typeStr='int[]',
                                  hidden=True,
                                  description="Row Order"))

        # Col Enable
        self.add(pr.LocalVariable(name='ColumnEnable',
                                  localGet=lambda: self._config.columnEnable,
                                  mode='RO',
                                  typeStr='bool[]',
                                  hidden=True,
                                  description="Column Enable"))

        # Number of columns supported in this group
        self.add(pr.LocalVariable(name='NumColumns',
                                  value=len(self._config.columnMap),
                                  mode='RO',
                                  groups='TopApi',
                                  description="Number of columns"))

        self.add(pr.LocalVariable(name='NumColumnBoards',
                                  value=self._config.columnBoards,
                                  mode='RO',
                                  groups='TopApi',
                                  description="Number of column boards"))

        # Number of rows supported in this group
        self.add(pr.LocalVariable(name='NumRows',
                                  value=len(self._config.rowMap),
                                  mode='RO',
                                  groups='TopApi',
                                  description="Number of rows"))

        self.add(pr.LocalVariable(name='NumRowBoards',
                                  value=self._config.rowBoards,
                                  mode='RO',
                                  groups='TopApi',
                                  description="Number of row boards"))

        # Enable Row Tune Override
        self.add(pr.LinkVariable(name='RowForceEn',
                                 value=False,
                                 mode='RW',
                                 typeStr='bool',
                                 groups='TopApi',
                                 #dependencies=[self.HardwareGroup.RowBoard[0].RowForceEn],
                                 linkedSet=self._rowForceEnSet,
                                 linkedGet=self._rowForceEnGet,
                                 description="Row Tune Enable"))

        # Row Tune Channel
        self.add(pr.LinkVariable(name='RowForceIndex',
                                 value=0,
                                 groups='TopApi',
                                 #dependencies=[self.HardwareGroup.RowBoard[0].RowForceIndex],
                                 mode='RW',
                                 typeStr='int',
                                 linkedSet=self._rowForceIdxSet,
                                 linkedGet=self._rowForceIdxGet,
                                 description="Row Tune Index"))

        # Tuning row enables
        self.add(pr.LocalVariable(name='RowTuneEnable',
                                  value=np.array([True] * len(self._config.rowMap),np.bool),
                                  groups='TopApi',
                                  mode='RW',
                                  description="Tune enable for each row"))

        # Tuning column enables
        self.add(pr.LocalVariable(name='ColTuneEnable',
                                  value=np.array([True] * len(self._config.columnMap),np.bool),
                                  groups='TopApi',
                                  mode='RW',
                                  description="Tune enable for each column"))

        #deps = [self.HardwareGroup.ColumnBoard[].SaBiasOffset.Bias[chan]
                #for board in range(self._config.columnBoards)
                #for chan in range(8)]

        # FLL Enable value
        self.add(pr.LinkVariable(name='FllEnable',
                                 value=False,
                                 mode='RW',
                                 groups='TopApi',
                                 #dependencies=deps,
                                 linkedSet=self._fllEnableSet,
                                 linkedGet=self._fllEnableGet,
                                 description="FLL Enable Control"))

        deps = [self.HardwareGroup.ColumnBoard[m.board].TesBias.BiasCurrent[m.channel]
                for m in self._config.columnMap]

        # TES Bias values, accessed with column index value
        self.add(pr.LinkVariable(name='TesBias',
                                 mode='RW',
                                 groups='TopApi',
                                 linkedSet=self._tesBiasSet,
                                 linkedGet=self._tesBiasGet,
                                 description=""))

        deps = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.Bias[m.channel]
                for m in self._config.columnMap]

        # SA Bias values, accessed with column index value
        self.add(pr.LinkVariable(name='SaBias',
                                 mode='RW',
                                 groups='TopApi',
                                 dependencies=deps,
                                 linkedSet=self._saBiasSet,
                                 linkedGet=self._saBiasGet,
                                 description=""))

        deps = [self.HardwareGroup.ColumnBoard[m.board].SaBiasOffset.Offset[m.channel]
                for m in self._config.columnMap]

        # SA Offset values, accessed with column index value
        self.add(pr.LinkVariable(name='SaOffset',
                                 mode='RW',
                                 groups='TopApi',
                                 dependencies=deps,
                                 linkedSet=self._saOffsetSet,
                                 linkedGet=self._saOffsetGet,
                                 description=""))

        deps = [self.HardwareGroup.ColumnBoard[board].DataPath.WaveformCapture.AdcAverage
                for board in range(self._config.columnBoards)]

        # SA Out values, accessed with column index value
        self.add(pr.LinkVariable(name='SaOut',
                                 mode='RO',
                                 groups='TopApi',
                                 dependencies=deps,
                                 linkedGet=self._saOutGet,
                                 description=""))


        deps = [self.HardwareGroup.ColumnBoard[m.board].SAFb.ColumnVoltages[m.channel]
                for m in self._config.columnMap]


        # SA FB values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='SaFb',
                                 mode='RW',
                                 groups='TopApi',
                                 disp = '{:0.03f}',
                                 dependencies=deps,
                                 linkedSet=self._fastDacSetFunc('SAFb'),
                                 linkedGet=self._fastDacGetFunc('SAFb'),
                                 description=""))

        deps = [self.HardwareGroup.ColumnBoard[m.board].SAFb.Override[m.channel]
                for m in self._config.columnMap]

        self.add(pr.LinkVariable(name = 'SaFbForce',
                                 mode = 'RW',
                                 groups = 'TopApi',
                                 disp = '{:0.03f}',
                                 dependencies = deps,
                                 linkedSet = self._fastDacForceSetFunc('SAFb'),
                                 linkedGet = self._fastDacForceGetFunc('SAFb')))


        deps = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.ColumnVoltages[m.channel]
                for m in self._config.columnMap]


        # SQ1 Bias values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='Sq1Bias',
                                 mode='RW',
                                 groups='TopApi',
                                 disp = '{:0.03f}',
                                 dependencies=deps,
                                 linkedSet=self._fastDacSetFunc('SQ1Bias'),
                                 linkedGet=self._fastDacGetFunc('SQ1Bias'),
                                 description=""))

        deps = [self.HardwareGroup.ColumnBoard[m.board].SQ1Bias.Override[m.channel]
                for m in self._config.columnMap]

        self.add(pr.LinkVariable(name = 'Sq1BiasForce',
                                 mode = 'RW',
                                 groups = 'TopApi',
                                 disp = '{:0.03f}',
                                 dependencies = deps,
                                 linkedSet = self._fastDacForceSetFunc('SQ1Bias'),
                                 linkedGet = self._fastDacForceGetFunc('SQ1Bias')))
                 

        deps = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.ColumnVoltages[m.channel]
                for m in self._config.columnMap]

        # SQ1 Fb values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='Sq1Fb',
                                 mode='RW',
                                 groups='TopApi',
                                 disp = '{:0.03f}',
#                                dependencies=deps,
                                 linkedSet=self._fastDacSetFunc('SQ1Bias'),
                                 linkedGet=self._fastDacGetFunc('SQ1Bias'),
                                 description=""))

        deps = [self.HardwareGroup.ColumnBoard[m.board].SQ1Fb.Override[m.channel]
                for m in self._config.columnMap]

        self.add(pr.LinkVariable(name = 'Sq1FbForce',
                                 mode = 'RW',
                                 groups = 'TopApi',
                                 disp = '{:0.03f}',
                                 dependencies = deps,
                                 linkedSet = self._fastDacForceSetFunc('SQ1Fb'),
                                 linkedGet = self._fastDacForceGetFunc('SQ1Fb')))


        # FAS Flux off values, accessed with row index
        self.add(pr.LinkVariable(name='FasFluxOff',
                                 mode='RW',
                                 groups='TopApi',
#                                 dependencies=deps,
                                 linkedSet=self._fasFluxOffSet,
                                 linkedGet=self._fasFluxOffGet,
                                 description=""))

        # FAS Flux on values, accessed with row index
        self.add(pr.LinkVariable(name='FasFluxOn',
                                 mode='RW',
                                 groups='TopApi',
                                 linkedSet=self._fasFluxOnSet,
                                 linkedGet=self._fasFluxOnGet,
                                 description=""))

        # Initialize System
        self.add(pr.LocalCommand(name='Init',
                                 function=self._init,
                                 groups='TopApi',
                                 description="Initialize System"))

        self.add(warm_tdm_api.ConfigSelect(self))

        self.add(warm_tdm_api.SaOffsetProcess())
        self.add(warm_tdm_api.SaTuneProcess(config=self._config))
        self.add(warm_tdm_api.Sq1TuneProcess())
        self.add(warm_tdm_api.FasTuneProcess())
        self.add(warm_tdm_api.Sq1DiagProcess())
        self.add(warm_tdm_api.TesRampProcess())


    def __colSetLoopHelper(self, value, index):
        # Construct a generator to loop over
        if index != -1:
            return ((idx, self._config.columnMap[idx].board, self._config.columnMap[idx].channel, val) for idx, val in zip(range(index, index+1), [value]))
        else:
            return ((idx, self._config.columnMap[idx].board, self._config.columnMap[idx].channel, val) for idx, val in enumerate(value))

    def __colGetLoopHelper(self, index):
        # Construct a generator to loop over

        if index != -1:
            ra = range(index, index+1)
        else:
            ra = range(len(self._config.columnMap))

        return ((idx, self._config.columnMap[idx].board, self._config.columnMap[idx].channel) for idx in ra)

    # Set Row Tune Override
    def _rowForceEnSet(self, value, write):
        with self.root.updateGroup():

            for col in self.HardwareGroup.ColumnBoard:
                #col.RowForceEn.set(value,write=write)  # Waiting on force variables
                pass

            for row in self.HardwareGroup.RowBoard:
                pass
                #row.RowForceEn.set(value,write=write)  # Waiting on force variables

#                 for dac in row.RowModuleDacs.Ad9106.values():
#                     dac.node(f'PRESTORE_SEL{i}').setDisp('Constant')
#                     dac.node(f'WAVE_SEL{i}').setDisp('Prestored')
#                     dac.node(f'DAC{i}_CONST').set(0) # Check this, might be offset binary


    # Get Row Tune Override
    def _rowForceEnGet(self, read):
        return False

#         with self.root.updateGroup():
#             for row in self.HardwareGroup.RowBoard:
#                 for dac in row.RowModuleDacs.Ad9106.values():
#                     if (dac.node(f'PRESTORE_SEL{i}').getDisp() != 'Constant' or
#                         dac.node(f'WAVE_SEL{i}').getDisp() != 'Prestored'):
#                         return False

#                 return True


    # Set Row Tune Index
    def _rowForceIdxSet(self, value, write):
        with self.root.updateGroup():

            for col in self.HardwareGroup.ColumnBoard:
                pass
                #col.RowTuneIdx.set(value,write=write) # Waiting on force variables

            for row in self.HardwareGroup.RowBoard:
                pass
                #row.RowTuneIdx.set(value,write=write) # Waiting on force variables

    # Get Row Tune Index
    def _rowForceIdxGet(self, read):
        with self.root.updateGroup():

            #return self.HardwareGroup.RowBoard[0].RowTuneIdx.get(read=read) # Waiting on force variables
            return 0

    # Set TES bias value, index is column
    def _tesBiasSet(self, value, write, index):
        with self.root.updateGroup():
            for idx, board, chan, val in self.__colSetLoopHelper(value, index):

                self.HardwareGroup.ColumnBoard[board].TesBias.BiasCurrent[chan].set(value=val, write=write)

    # Get TES bias value, index is column
    def _tesBiasGet(self, read, index):
        with self.root.updateGroup():
            ret = np.ndarray((len(self._config.columnMap),),np.float)

            for idx, board, chan in self.__colGetLoopHelper(index):
                ret[idx] = self.HardwareGroup.ColumnBoard[board].TesBias.BiasCurrent[chan].get(read=read)

            if index != -1:
                return ret[index]
            else:
                return ret

    # Set SA Bias value, index is column
    def _saBiasSet(self, value, write, index):
        with self.root.updateGroup():
            for idx, board, chan, val in self.__colSetLoopHelper(value, index):
                self.HardwareGroup.ColumnBoard[board].SaBiasOffset.Bias[chan].set(value=val, write=write)

    # Get SA Bias value, index is column
    def _saBiasGet(self, read, index):
        with self.root.updateGroup():
            ret = np.ndarray((len(self._config.columnMap),),np.float)

            for idx, board, chan in self.__colGetLoopHelper(index):
                ret[idx] = self.HardwareGroup.ColumnBoard[board].SaBiasOffset.Bias[chan].get(read=read)

            if index != -1:
                return ret[index]
            else:
                return ret

    # Set SA Offset value, index is column
    def _saOffsetSet(self, value, write, index):
        with self.root.updateGroup():
            for idx, board, chan, val in self.__colSetLoopHelper(value, index):
                self.HardwareGroup.ColumnBoard[board].SaBiasOffset.Offset[chan].set(value=val, write=write)

    # Get SA Offset value, index is column
    def _saOffsetGet(self, read, index):
        with self.root.updateGroup():
            ret = np.ndarray((len(self._config.columnMap),),np.float)

            for idx, board, chan in self.__colGetLoopHelper(index):
                ret[idx] = self.HardwareGroup.ColumnBoard[board].SaBiasOffset.Offset[chan].get(read=read)


            if index != -1:
                return ret[index]
            else:
                return ret

    # Get SA Out value, index is column
    def _saOutGet(self, read, index):
        with self.root.updateGroup():
            ret = np.ndarray((len(self._config.columnMap),),np.float)

            for board in range(self._config.columnBoards):
                self.HardwareGroup.ColumnBoard[board].DataPath.WaveformCapture.AdcAverage.get(read=read, check=False)

            self.checkBlocks(recurse=True)
            for idx, board, chan in self.__colGetLoopHelper(index):
                ret[idx] = -1 * self.HardwareGroup.ColumnBoard[board].DataPath.WaveformCapture.AdcAverage.get(index=chan, read=False)

            if index != -1:
                return ret[index]
            else:
                return ret


    # Force the SA Feedback DACs to value
    def _fastDacForceSetFunc(self, name):
        def _fastDacForceSet(value, *, write, index):
            with self.root.updateGroup():

            # index access
                if index != -1:
                    colIndex = index
                    colBoard = self._config.columnMap[colIndex].board
                    colChan = self._config.columnMap[colIndex].channel

                    self.HardwareGroup.ColumnBoard[colBoard].node(name).Override[colChan].set(value=value,write=write)

                # Full array access
                else:

                    for colIndex in range(len(self._config.columnMap)):
                        colBoard = self._config.columnMap[colIndex].board
                        colChan = self._config.columnMap[colIndex].channel

                        self.HardwareGroup.ColumnBoard[colBoard].node(name).Override[colIndex].set(value=value[colIndex],write=write)
                        
        return _fastDacForceSet

    # Get the last forced SA Feedback DAC value
    def _fastDacForceGetFunc(self, name):
        def _fastDacForceGet(*, read, index):
            with self.root.updateGroup():
                # index access
                if index != -1:
                    colIndex = index
                    colBoard = self._config.columnMap[colIndex].board
                    colChan = self._config.columnMap[colIndex].channel
                    
                    return self.HardwareGroup.ColumnBoard[colBoard].node(name).Override[colChan].get(read=read)
                else:
                    # Full array access                    
                    ret = np.zeros(len(self._config.columnMap), np.float)

                    for colIndex in range(len(self._config.columnMap)):
                        colBoard = self._config.columnMap[colIndex].board
                        colChan = self._config.columnMap[colIndex].channel

                        ret[colIndex] =  self.HardwareGroup.ColumnBoard[colBoard].node(name).Override[colChan].get()

                    return ret
                                   
        return _fastDacForceGet

    # Set fast dac value, index is (column, row) tuple
    def _fastDacSetFunc(self, name):
        def _fastDacSet(value, *, write, index):
            with self.root.updateGroup():

                # index access
                if index != -1:
                    colIndex = index[0]
                    rowIndex = index[1]
                    colBoard = self._config.columnMap[colIndex].board
                    colChan = self._config.columnMap[colIndex].channel

                    self.HardwareGroup.ColumnBoard[colBoard].node(name).ColumnVoltages[colChan].set(value=value, write=write, index=rowIndex)

                # Full array access
                else:
                    for colIndex in range(len(self._config.columnMap)):
                        colBoard = self._config.columnMap[colIndex].board
                        colChan = self._config.columnMap[colIndex].channel

                        self.HardwareGroup.ColumnBoard[colBoard].node(name).ColumnVoltages[colChan].set(value=value[colIndex], write=write, index=-1)
        return _fastDacSet


    # Get fast dac value, index is (column, row) tuple
    def _fastDacGetFunc(self, name):
        def _fastDacGet(*, read, index):
            with self.root.updateGroup():

                # index access
                if index != -1:
                    colIndex = index[0]
                    rowIndex = index[1]
                    colBoard = self._config.columnMap[colIndex].board
                    colChan = self._config.columnMap[colIndex].channel

                    return self.HardwareGroup.ColumnBoard[colBoard].node(name).ColumnVoltages[colChan].get(read=read, index=rowIndex)

                # Full array access
                else:
                    ret = np.ndarray((len(self._config.columnMap),len(self._config.rowMap)),np.float)

                    for colIndex in range(len(self._config.columnMap)):
                        colBoard = self._config.columnMap[colIndex].board
                        colChan = self._config.columnMap[colIndex].channel

                        ret[colIndex] = self.HardwareGroup.ColumnBoard[colBoard].node(name).ColumnVoltages[colChan].get(read=read, index=-1)

                    return ret
                
        return _fastDacGet


    # Set FAS Flux Off value, index is row
    def _fasFluxOffSet(self, value, write, index):
        with self.root.updateGroup():

            # index access
            if index != -1:
                board = self._config.rowMap[index].board
                chan = self._config.rowMap[index].channel

                #self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.set(value=value, write=write)

            # Full array access
            else:

                for idx in range(len(self._config.rowMap)):
                    board = self._config.rowMap[index].board
                    chan = self._config.rowMap[index].channel

                    #self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.set(value=value[idx], write=write)

    # Get FAS Flux value
    def _fasFluxOffGet(self, read, index):
        with self.root.updateGroup():

            # index access
            if index != -1:
                board = self._config.rowMap[index].board
                chan = self._config.rowMap[index].channel

                #return self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.get(index=index, read=read)
                return 0.0

            # Full array access
            else:
                ret = np.ndarray((len(self._config.rowMap),),np.float)

                for idx in range(len(self._config.rowMap)):
                    board = self._config.rowMap[index].board
                    chan = self._config.rowMap[index].channel

                    #ret[idx] = self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.get(index=idx, read = read) #BEN
                    ret[idx] = 0.0

                return ret

    # Set FAS Flux Off value, index is row
    def _fasFluxOnSet(self, value, write, index):
        with self.root.updateGroup():

            # index access
            if index != -1:
                board = self._config.rowMap[index].board
                chan = self._config.rowMap[index].channel

                #return self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].ActiveValue.set(value=value, write=write)

            # Full array access
            else:

                for idx in range(len(self._config.rowMap)):
                    board = self._config.rowMap[index].board
                    chan = self._config.rowMap[index].channel

                    #self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].ActiveValue.set(value=value[idx],write=write)

    # Get FAS Flux value
    def _fasFluxOnGet(self, read, index):
        with self.root.updateGroup():

            # index access
            if index != -1:
                board = self._config.rowMap[index].board
                chan = self._config.rowMap[index].channel

                #return self.HardwareGroup.RowBoard[board].FasFluxOn[chan].get(index= index, read=read)
                return 0.0

            # Full array access
            else:
                ret = np.ndarray((len(self._config.rowMap),),np.float)

                for idx in range(len(self._config.rowMap)):
                    board = self._config.rowMap[index].board
                    chan = self._config.rowMap[index].channel

                    #ret[idx] = self.HardwareGroup.RowBoard[board].FasFluxOn[chan].get(index=index, read=read) #BEN
                    ret[idx] = 0.0

                return ret

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
        self.FllEnable.set(value=False)

        # Drive high TES bias currents?????
        pass
