-------------------------------------------------------------------------------
-- Title      : Chip-Select Flux-Activated Switch Behavioral Model
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library warm_tdm;
use warm_tdm.WaferSimPkg.all;

entity ChipFasModel is
   generic (
      PARAMS_G : ChipFasParamsType := CHIP_FAS_SYNTHETIC_C);
   port (
      biasCurrentAmp      : in  real;
      selectCurrentAmp    : in  real;
      phaseCycles         : out real;
      staticResistanceOhm : out real;
      voltageVolt         : out real);
end entity ChipFasModel;

architecture sim of ChipFasModel is
begin

   assert validSquidParams(PARAMS_G.squid)
      report "ChipFasModel: invalid chip-FAS SQUID parameters"
      severity failure;
   assert PARAMS_G.selectPolarity /= 0
      report "ChipFasModel: select polarity must be +1 or -1"
      severity failure;
   assert PARAMS_G.seriesResistanceOhm >= 0.0
      report "ChipFasModel: series resistance must be nonnegative"
      severity failure;

   comb : process (all) is
      variable voltage : real;
   begin
      phaseCycles <= chipFasPhaseCycles(PARAMS_G, selectCurrentAmp);
      voltage := chipFasBranchVoltage(
         PARAMS_G, biasCurrentAmp, selectCurrentAmp);
      voltageVolt <= voltage;
      if abs(biasCurrentAmp) > 1.0E-30 then
         staticResistanceOhm <= abs(voltage / biasCurrentAmp);
      else
         staticResistanceOhm <= PARAMS_G.seriesResistanceOhm;
      end if;
   end process comb;

end architecture sim;
