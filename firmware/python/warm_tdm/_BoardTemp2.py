import pyrogue as pr
import math
import warm_tdm

class BoardTemp2(pr.Device):
    def __init__(self, xadc, local_therm_channels, fe_therm_channels, sa56004x, **kwargs):
        super().__init__(**kwargs)

        self.xadc = xadc
        self.sa56004x = sa56004x

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

        def getLocalThermistor(read, var):
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

        def getLocalThermistor(read, var):
            print(f'getLocalThermistor(read={read}, var={var.path})')
            voltage = var.dependencies[0].get(read=read)
            if voltage == 0.0:
                #math.log call will die if voltage -> resistance = 0
                return -273.15
            current = (1.0 - voltage) / 10000
            resistance = voltage / current
            tempKelvin = 3750 / math.log( resistance / 0.03448533 )
            tempCelcius = tempKelvin - 273.15
            return tempCelcius

        def getFeThermistor(read, var):
            print(f'getFeThermistor(read={read}, var={var.path})')
            voltage = var.dependencies[0].get(read=read)
            if voltage == 0.0:
                #math.log call will die if voltage -> resistance = 0
                return -273.15
            current = (5.0 - voltage) / 56000
            resistance = voltage / current
            tempKelvin = 3750 / math.log( resistance / 0.03448533 )
            tempCelcius = tempKelvin - 273.15
            return tempCelcius
        
        

        for i, ch in enumerate(local_therm_channels):
            self.add(pr.LinkVariable(
                name = f'LocalThermistor{i}',
                dependencies = [xadc.Aux[ch]],
                units = 'degC',
                disp = '{:0.3f}',
                linkedGet = getLocalThermistor))

        for i, ch in enumerate(fe_therm_channels):
            self.add(pr.LinkVariable(
                name = f'FeThermistor{i}',
                dependencies = [xadc.Aux[ch]],
                units = 'degC',
                disp = '{:0.3f}',
                linkedGet = getFeThermistor))
            

    def readAndCheckBlocks(self, recurse=True, variable=None, checkEach=False):
        self.xadc.readAndCheckBlocks(recurse, variable, checkEach)
        self.sa56004x.readAndCheckBlocks(recurse, variable, checkEach)
            
        
