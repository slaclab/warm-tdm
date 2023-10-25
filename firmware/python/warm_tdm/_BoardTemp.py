import pyrogue as pr
import math
import warm_tdm

class BoardTemp(pr.Device):
    def __init__(self, xadc, therm_channels, sa56004x, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LinkVariable(
            name = 'FpgaTempXadc',
            mode = 'RO',
            variable = xadc.Temperature,))

        self.add(pr.LinkVariable(
            name = 'FpgaTempSa56004',
            mode = 'RO',
            variable = sa56004x.RemoteTemperature))

        self.add(pr.LinkVariable(
            name = 'BoardTempSa56004',
            mode = 'RO',
            variable = sa56004x.LocalTemperature))

        def getThermistor(read, var):
            print(f'getThermistor(read={read}, var={var.path})')
            voltage = var.dependencies[0].get(read=read)
            if voltage == 0.0:
                #math.log call will die if voltage -> resistance = 0
                return -273.15
            current = (1.0 - voltage) / 10000
            resistance = voltage / current
            tempKelvin = 3750 / math.log( resistance / 0.03448533 )
            tempCelcius = tempKelvin - 273.15
            return tempCelcius
        

        for i, ch in enumerate(therm_channels):
            self.add(pr.LinkVariable(
                name = f'Thermistor{i}',
                dependencies = [xadc.Aux[ch]],
                units = 'degC',
                disp = '{:0.3f}',
                linkedGet = getThermistor))

    def readAndCheckBlocks(self, recurse=True, variable=None, checkEach=False):
        xadc.readAndCheckBlocks(recurse, variable, checkEach)
        sa56004x.readAndCheckBlocks(recurse, variable, checkEach)
            
        
