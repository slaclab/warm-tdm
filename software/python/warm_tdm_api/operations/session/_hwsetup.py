## Transitional hardware-setup convenience shims.
##
## Every method here is a thin client-side delegate to a Group broadcast variable
## whose *real* home is an owning tree node (issue #83: G3 CableResistance, G4
## PowerSupplySynchronized, G6 LedEnable). They are grouped in this one small
## mixin precisely because they are slated for deletion: as each capability
## graduates onto the tree, drop the method here (and its shim/`__all__` entry)
## -- a clean file-scoped operation, not surgery on a shared module. Do NOT grow
## a path-resolution layer around them; push each to its node instead. See
## docs/plans/wtj-refactor/PLAN.md.
##
## Relies on TopologyCore state (self.group). Mounted on Session.


class HwSetupMixin:
    """Transitional Group-broadcast convenience shims (pending graduation)."""

    def disable_leds(self):
        """Disable status-blinking LEDs on all boards.

        Delegates to the Group ``LedEnable`` variable, which owns the broadcast
        (issue #83, G6). Kept as a thin ``operations`` convenience so existing
        call sites (``ops.disable_leds()``) don't change.
        """
        self.group.LedEnable.set(False)
        print("Disabled LEDs on all boards.")

    def set_cryo_resistance(self, Rcryo_Ohm):
        """Set cryostat roundtrip cable resistance on all boards' AFE amps.

        Broadcasts ``Rcryo_Ohm`` to every AFE ``CableR`` model node (column
        ``Channel[*].{SAAmp,SAFbAmp,SQ1BiasAmp,SQ1FbAmp,TesBiasAmp}``; row
        ``Amp[*]``).

        This now delegates to the Group ``CableResistance`` variable, which owns
        the broadcast (issue #83, G3). Kept as a thin ``operations`` convenience
        so notebook/script call sites (``ops.set_cryo_resistance(R)``) don't
        change.
        """
        self.group.CableResistance.set(Rcryo_Ohm)
        print(f"Set cryostat resistance to {Rcryo_Ohm} Ohm.")

    def set_ps_synch(self, sync_mode):
        """Set power-supply synchronization mode on all boards.

        ``sync_mode`` truthy => synchronized (PwrSyncA/B/C=OSC, PwrSyncEn on);
        falsy => unsynchronized (all LOW, PwrSyncEn off).

        Delegates to the Group ``PowerSupplySynchronized`` variable, which owns
        the broadcast (issue #83, G4). Kept as a thin ``operations`` convenience
        so existing call sites (``ops.set_ps_synch(1)``) don't change.
        """
        self.group.PowerSupplySynchronized.set(bool(sync_mode))
        print("Synchronized power supplies."
              if sync_mode else "Unsynchronized power supplies.")

    def check_ps_synch(self):
        """Print (and return) the power-supply synchronization state.

        Reads the Group ``PowerSupplySynchronized`` variable (issue #83, G4).
        """
        synched = bool(self.group.PowerSupplySynchronized.get())
        print(f"Power supplies are {'Synchronized' if synched else 'Unsynchronized'}.")
        return synched
