import pyrogue as pr

import warm_tdm

class WarmTdmConfig(pr.Device):
    def __init__(self, axil_clk_freq=125.0e6, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name = 'AnaPwrEn',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'AnaPwrStatus',
            mode = 'RO',
            offset = 0x00,
            bitOffset = 1,
            bitSize = 1,
            enum = {
                0: 'Disabled',
                1: 'Enabled'}))

        self.add(pr.RemoteVariable(
            name = 'PwrSyncA',
            offset = 0x04,
            bitOffset = 0,
            bitSize = 2,
            enum = {
                0: 'LOW',
                1: 'HIGH',
                2: 'OSC'}))

        self.add(pr.RemoteVariable(
            name = 'PwrSyncB',
            offset = 0x08,
            bitOffset = 0,
            bitSize = 2,
            enum = {
                0: 'LOW',
                1: 'HIGH',
                2: 'OSC'}))

        self.add(pr.RemoteVariable(
            name = 'PwrSyncC',
            offset = 0x0C,
            bitOffset = 0,
            bitSize = 2,
            enum = {
                0: 'LOW',
                1: 'HIGH',
                2: 'OSC'}))

        self.add(pr.RemoteVariable(
            name = 'SyncPeriodDiv2',
            offset = 0x10,
            bitOffset = 0,
            bitSize = 32,
            value = int(axil_clk_freq/(2*2e6))))

        self.add(pr.LinkVariable(
            name = 'SyncFrequency',
            dependencies = [self.SyncPeriodDiv2],
            mode ='RO',
            disp = '{:0.3f}',
            units = 'MHz',
            linkedGet = lambda read: 1.0e-6 * axil_clk_freq / (2*self.SyncPeriodDiv2.get(read=read))))
            
        
