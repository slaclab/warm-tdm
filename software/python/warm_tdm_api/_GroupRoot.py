import pyrogue
import pyrogue.utilities.fileio
import warm_tdm_api


class GroupRoot(pyrogue.Root):
    def __init__(self, groupConfig, simulation=False, emulate=False, **kwargs):
        """
        Root class container for Warm-TDM Groups.
        Parameters
        ----------
        groupConfig : warm_tdm_api.GroupConfig
            Group configuration
        emulate: bool
           Flag to determine if emulation mode should be used
        """

        super().__init__(**kwargs)

        self.add(warm_tdm_api.Group(groupConfig=groupConfig,
                                    simulation=simulation,
                                    emulate=emulate))

        # Add the data writer
        self.add(pyrogue.utilities.fileio.StreamWriter(name='DataWriter'))
        self >> self.DataWriter.getChannel(100)
