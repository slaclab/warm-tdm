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

        super().__init__(**kwargs)

        # Add the data writer
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter'))
        self >> self.DataWriter.getChannel(100)

        self.add(warm_tdm_api.Group(groupConfig=groupConfig,
                                    groupId=0,
                                    expand=True,
                                    dataWriter=self.DataWriter,
                                    simulation=simulation,
                                    emulate=emulate,
                                    plots=plots))

