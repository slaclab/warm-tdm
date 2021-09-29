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
                                 maximum=len(group._config.rowOrder),
                                 groups='TopApi',
                                 description="Row Configuration Selection"))

        self.add(pr.LocalVariable(name='RowSelect',
                                 value=0,
                                 mode='RW',
                                 minimum=0,
                                 maximum=len(group._config.columnMap),
                                 groups='TopApi',
                                 description="Row Configuration Selection"))

        self.add(pr.LinkVariable(name='RowTuneEnable',
                                 mode='RW',
                                 disp = {False: 'False', True: 'True'},
                                 dependencies=[self.RowSelect,self.RowSelect,group.RowTuneEnable],
                                 linkedSet=self._rowTuneEnSet,
                                 linkedGet=self._rowTuneEnGet,
                                 description="Tune enable for each row"))

        self.add(pr.LinkVariable(name='ColTuneEnable',
                                 mode='RW',
                                 disp = {False: 'False', True: 'True'},
                                 dependencies=[self.RowSelect,self.ColumnSelect,group.ColTuneEnable],
                                 linkedSet=self._colTuneEnSet,
                                 linkedGet=self._colTuneEnGet,
                                 description="Tune enable for each column"))

        self.add(pr.LinkVariable(name='TesBias',
                                 mode='RW',
                                 disp='{:.3f}',
                                 dependencies=[self.ColumnSelect,group.TesBias],
                                 linkedSet=self._tesBiasSet,
                                 linkedGet=self._tesBiasGet,
                                 description=""))

        self.add(pr.LinkVariable(name='SaBias',
                                 mode='RW',
                                 disp='{:.3f}',
                                 dependencies=[self.ColumnSelect,group.SaBias],
                                 linkedSet=self._saBiasSet,
                                 linkedGet=self._saBiasGet,
                                 description=""))

        self.add(pr.LinkVariable(name='SaOffset',
                                 mode='RW',
                                 disp='{:.3f}',
                                 dependencies=[self.ColumnSelect,group.SaOffset],
                                 linkedSet=self._saOffsetSet,
                                 linkedGet=self._saOffsetGet,
                                 description=""))

        self.add(pr.LinkVariable(name='SaOut',
                                 mode='RO',
                                 disp='{:.3f}',
                                 dependencies=[self.ColumnSelect,group.SaOut],
                                 linkedGet=self._saOutGet,
                                 description=""))

        self.add(pr.LinkVariable(name='SaFb',
                                 mode='RW',
                                 disp='{:.3f}',
                                 dependencies=[self.ColumnSelect,self.RowSelect,group.SaFb],
                                 linkedSet=self._saFbSet,
                                 linkedGet=self._saFbGet,
                                 description=""))

        self.add(pr.LinkVariable(name='Sq1Bias',
                                 mode='RW',
                                 disp='{:.3f}',
                                 dependencies=[self.ColumnSelect,self.RowSelect,group.Sq1Bias],
                                 linkedSet=self._sq1BiasSet,
                                 linkedGet=self._sq1BiasGet,
                                 description=""))

        self.add(pr.LinkVariable(name='Sq1Fb',
                                 mode='RW',
                                 disp='{:.3f}',
                                 dependencies=[self.ColumnSelect,self.RowSelect,group.Sq1Fb],
                                 linkedSet=self._sq1FbSet,
                                 linkedGet=self._sq1FbGet,
                                 description=""))

        self.add(pr.LinkVariable(name='FasFluxOff',
                                 mode='RW',
                                 disp='{:.3f}',
                                 dependencies=[self.RowSelect,group.FasFluxOff],
                                 linkedSet=self._fasFluxOffSet,
                                 linkedGet=self._fasFluxOffGet,
                                 description=""))

        self.add(pr.LinkVariable(name='FasFluxOn',
                                 mode='RW',
                                 disp='{:.3f}',
                                 dependencies=[self.RowSelect,group.FasFluxOn],
                                 linkedSet=self._fasFluxOnSet,
                                 linkedGet=self._fasFluxOnGet,
                                 description=""))

    def _rowTuneEnGet(self, read):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            return self.parent.RowTuneEnable.get(read=read,index=row)

    def _rowTuneEnSet(self, value, write):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            return self.parent.RowTuneEnable.set(value=value,write=write,index=row)

    def _colTuneEnGet(self, read):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.ColTuneEnable.get(read=read,index=col)

    def _colTuneEnSet(self, value, write):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.ColTuneEnable.set(value=value,write=write,index=col)

    def _tesBiasGet(self, read):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.TesBias.get(read=read,index=col)

    def _tesBiasSet(self, value, write):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.TesBias.set(value=value,write=write,index=col)

    def _saBiasGet(self, read):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.SaBias.get(read=read,index=col)

    def _saBiasSet(self, value, write):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.SaBias.set(value=value,write=write,index=col)

    def _saOffsetGet(self, read):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.SaOffset.get(read=read,index=col)

    def _saOffsetSet(self, value, write):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.SaOffset.set(value=value,write=write,index=col)

    def _saOutGet(self, read):
        with self.root.updateGroup():
            col = self.ColumnSelect.value()
            return self.parent.SaOut.get(read=read,index=col)

    def _saFbGet(self, read):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            col = self.ColumnSelect.value()
            return self.parent.SaFb.get(read=read,index=(col,row))

    def _saFbSet(self, value, write):
        with self.root.updateGroup():
            row = self.ColumnSelect.value()
            col = self.ColumnSelect.value()
            return self.parent.SaFb.set(value=value,write=write,index=(col,row))

    def _sq1BiasGet(self, read):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            col = self.ColumnSelect.value()
            return self.parent.Sq1Bias.get(read=read,index=(col,row))

    def _sq1BiasSet(self, value, write):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            col = self.ColumnSelect.value()
            return self.parent.Sq1Bias.set(value=value,write=write,index=(col,row))

    def _sq1FbGet(self, read):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            col = self.ColumnSelect.value()
            return self.parent.Sq1Fb.get(read=read,index=(col,row))

    def _sq1FbSet(self, value, write):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            col = self.ColumnSelect.value()
            return self.parent.Sq1Fb.set(value=value,write=write,index=(col,row))

    def _fasFluxOffGet(self, read):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            return self.parent.FasFluxOff.get(read=read,index=row)

    def _fasFluxOffSet(self, value, write):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            return self.parent.FasFluxOff.set(value=value,write=write,index=row)

    def _fasFluxOnGet(self, read):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            return self.parent.FasFluxOn.get(read=read,index=row)

    def _fasFluxOnSet(self, value, write):
        with self.root.updateGroup():
            row = self.RowSelect.value()
            return self.parent.FasFluxOn.set(value=value,write=write,index=row)
