import pyrogue as pr
import warm_tdm

class FrontEndDevice(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'Type',
            mode = 'RO',
            value = self.__class__.__name__))
    

class ColumnBoardC00StandardChannel(FrontEndDevice):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.ColumnBoardC00SaAmp(
            name = 'SAAmp'))

        self.add(warm_tdm.FastDacAmplifierSE(
            name = 'SAFbAmp',
            defaults = {
                'Invert': True,
                'ShuntR': 7.15e3,
                'FbR': 4.7e3}))

        self.add(warm_tdm.FastDacAmplifierSE(
            name = 'SQ1BiasAmp',
            defaults = {
                'Invert': True,
                'ShuntR': 10.0e3,
                'FbR': 4.7e3}))

        self.add(warm_tdm.FastDacAmplifierSE(
            name = 'SQ1FbAmp',
            defaults = {
                'Invert': True,
                'ShuntR': 11.3e3,
                'FbR': 4.7e3}))

        
class ColumnBoardC00FebBypassChannel(FrontEndDevice):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.FEAmplifier3(
            name = 'SAAmp'))

        self.add(warm_tdm.FastDacAmplifierSE(
            name = 'SAFbAmp',
            defaults = {
                'Invert': True,
                'InputR': 100.0,
                'FbR': 502.0,        
                'ShuntR': 7129.7        
            }
        ))

        self.add(warm_tdm.FastDacAmplifierSE(
            name = 'SQ1BiasAmp',
            defaults = {
                'Invert': True,
                'InputR': 100.0,
                'FbR': 502.0,                
                'ShuntR': 2149.7
            }
        ))

        self.add(warm_tdm.FastDacAmplifierSE(
            name = 'SQ1FbAmp',
            defaults = {
                'Invert': True,
                'InputR': 100.0,
                'FbR': 502.0,
                'ShuntR': 10149.7
            }
        ))

class ColumnBoardC00StandardFrontEnd(FrontEndDevice):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for i in range(8):
            self.add(warm_tdm.ColumnBoardC00StandardChannel(
                name = f'Channel[{i}]'))


class ColumnBoardC00FebBypassCh0(FrontEndDevice):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.ColumnBoardC00FebBypassChannel(
            name = 'Channel[0]'))
    
        for i in range(1, 8):
            self.add(warm_tdm.ColumnBoardC00StandardChannel(
                name = f'Channel[{i}]'))
