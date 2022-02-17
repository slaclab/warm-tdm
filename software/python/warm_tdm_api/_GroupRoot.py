import pyrogue
import pyrogue.utilities.fileio
import warm_tdm_api


class GroupRoot(pyrogue.Root):
    def __init__(self, groupConfig, simulation=False, emulate=False, plots=False, **kwargs):
        """
        Root class container for Warm-TDM Groups.
        Parameters
        ----------
        groupConfig : warm_tdm_api.GroupConfig
            Group configuration
        emulate: bool
           Flag to determine if emulation mode should be used
        """

        if simulation:
            kwargs['pollEn'] = False
            kwargs['timeout'] = 1000

        super().__init__(description = "Top level Rogue Root for the WarmTDM System."
                                       "Each Root will support one or more WarmTDM 'Groups'."
                                       "This interface supports configuration load and save as well as the top level reset control.",
                         **kwargs)

        self.LoadConfig.addToGroup('DocApi')
        self.SaveConfig.addToGroup('DocApi')
        self.GetYamlConfig.addToGroup('DocApi')
        self.SetYamlConfig.addToGroup('DocApi')
        self.HardReset.addToGroup('DocApi')
        self.CountReset.addToGroup('DocApi')
        self.Initialize.addToGroup('DocApi')

        # Add the data writer
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter',groups='DocApi'))
        self >> self.DataWriter.getChannel(100)
        self.DataWriter.ReadDevice.addToGroup('NoDoc')
        self.DataWriter.WriteDevice.addToGroup('NoDoc')
        self.DataWriter.BufferSize.addToGroup('NoDoc')
        self.DataWriter.MaxFileSize.addToGroup('NoDoc')
        self.DataWriter.CurrentSize.addToGroup('NoDoc')

        self.add(warm_tdm_api.Group(groupConfig=groupConfig,
                                    groupId=0,
                                    expand=True,
                                    dataWriter=self.DataWriter,
                                    simulation=simulation,
                                    emulate=emulate,
                                    plots=plots))

