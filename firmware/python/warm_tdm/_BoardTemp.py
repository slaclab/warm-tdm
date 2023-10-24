import pyrogue as pr

import warm_tdm

class BoardTemp(pr.Device):
    def __init__(self, xadc, therm_channels, sa56004x, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LinkVariable(
            name = 'FpgaTempXadc',
            variable = xadc.Temperature,))

        self.add(pr.LinkVariable(
            name = 'FpgaTempSa56004',
            variable = sa56004x.RemoteTemperature))

        self.add(pr.LinkVariable(
            name = 'BoardTempSa56004',
            variable = sa56004x.LocalTemperature))

        def getThermistor(read, var):
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
                variable = xadc.Aux[ch],
                linkedGet = getThermistor))
            
        
